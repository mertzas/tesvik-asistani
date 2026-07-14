import json
import os
from datetime import datetime, timezone
from typing import List
from uuid import UUID

import stripe
from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.models import init_db, get_db, Organization, User, Query, Tesvik, FinancialProfile, PlanType, settings
from app.auth import (
    get_current_user,
    get_current_org,
    hash_password,
    create_access_token,
    verify_password,
    check_rate_limit,
)
from app.schemas import (
    UserSignup,
    UserLogin,
    TokenResponse,
    AskQuestion,
    AskResponse,
    SearchResult,
    UserResponse,
    OrganizationResponse,
    PlanUpgrade,
    QueryResponse,
    UsageStats,
    AnalyticsResponse,
    FinancialProfileCreate,
    FinancialProfileResponse,
    TesvikEslesmeResponse,
    TesvikEslesmeItem,
    ButceOnerisiResponse,
    EticaretGiderGirdisi,
    EticaretDestekResponse,
)
from app.rag import answer
from app.billing import create_checkout_session, confirm_checkout_session, cancel_subscription, handle_webhook, get_plan_limits
from app.admin import router as admin_router
from app.matching import esles, toplam_tahmini_destek, tutari_tahmini_hesapla
from app.budget import hesapla as butce_hesapla
from app.cilek_panel import router as cilek_router
from app.ikas_panel import router as ikas_router
from app.urun_sektor_anahtarlari import anahtar_kelimeden_sektor_bul
from app.eticaret_destek_hesaplayici import eticaret_destek_hesapla
from app.scheduler import setup_scheduler

# Global scheduler instance
_scheduler = None

app = FastAPI(
    title="Teşvik Asistanı SaaS",
    description="Devlet teşviklerini bulmanın en kolay yolu",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include admin routes
app.include_router(admin_router)
app.include_router(cilek_router)
app.include_router(ikas_router)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@app.on_event("startup")
def on_startup():
    global _scheduler
    init_db()
    _scheduler = setup_scheduler()
    _scheduler.start()


@app.on_event("shutdown")
def on_shutdown():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()


# ============ AUTH ENDPOINTS ============

@app.post("/api/auth/signup", response_model=TokenResponse)
def signup(request: UserSignup, db: Session = Depends(get_db)):
    """Yeni hesap oluştur."""
    # Email benzersiz mi kontrol et
    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu email zaten kullanımda"
        )

    # Organization oluştur
    org = Organization(
        name=request.company_name,
        email=request.email,
    )
    db.add(org)
    db.flush()

    # User oluştur
    user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        org_id=org.id,
    )
    db.add(user)
    db.commit()

    # Token oluştur
    token = create_access_token({
        "sub": str(user.id),
        "org_id": str(org.id),
    })

    return TokenResponse(
        access_token=token,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
        }
    )


@app.post("/api/auth/login", response_model=TokenResponse)
def login(request: UserLogin, db: Session = Depends(get_db)):
    """Giriş yap."""
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya şifre yanlış"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap deaktif"
        )

    token = create_access_token({
        "sub": str(user.id),
        "org_id": str(user.org_id),
    })

    return TokenResponse(
        access_token=token,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
        }
    )


# ============ MAIN API ENDPOINTS ============

@app.post("/api/sor", response_model=AskResponse)
def sor(
    request: AskQuestion,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Teşvik sorusu sor."""
    # Rate limiting kontrolü
    if not check_rate_limit(current_org, db):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Aylık sorgulama limitini aştınız. Upgrading düşünün."
        )

    try:
        # Kullanıcının doldurduğu finansal profil varsa, Claude'a bağlam
        # olarak veriyoruz - "Durum Analizi" başlığı bunsuz jenerik kalır.
        profil_row = db.query(FinancialProfile).filter(FinancialProfile.org_id == current_org.id).first()
        profil = None
        if profil_row is not None:
            profil = {
                "sektör": profil_row.sektor,
                "bölge": profil_row.bolge,
                "çalışan sayısı": profil_row.calisan_sayisi,
                "yıllık ciro": profil_row.yillik_ciro,
                "hedefler": profil_row.hedefler,
                "ilk yıl mı": profil_row.ilk_yil_mi,
                "tarım kategorisi": profil_row.tarim_kategori,
                "ürün türü": profil_row.urun_turu,
                "arazi büyüklüğü (dekar)": profil_row.arazi_buyuklugu_dekar,
            }

        # Mevcut RAG sistemini çalıştır
        answer_text = answer(request.question, profil)

        # Veritabanından alakalı teşvikleri bul
        # Basit keyword matching (ileri sürümlerde embedding kullanacağız)
        keywords = request.question.lower().split()
        tesvikler = db.query(Tesvik).filter(
            Tesvik.detay.ilike(f"%{' '.join(keywords)}%")
        ).limit(10).all()

        # Literal metin eslesmesi bos/az sonuc verdiyse, sorguda "cilek",
        # "sut" gibi bilinen bir urun/faaliyet adi gecip gecmedigine bak;
        # geciyorsa o sektore (orn. tarim) etiketli tesvikleri de ekle.
        # 210 kayittaki program adlari nadiren belirli urun isimlerini
        # gecirdigi icin (bkz. app/urun_sektor_anahtarlari.py) bu olmadan
        # "çilek" gibi bir arama hep 0 sonuc donuyordu.
        if len(tesvikler) < 5:
            hedef_sektor = anahtar_kelimeden_sektor_bul(request.question)
            if hedef_sektor:
                mevcut_idler = {t.id for t in tesvikler}
                sektor_tesvikleri = [
                    t for t in db.query(Tesvik).all()
                    if hedef_sektor in {s.lower() for s in (t.uygunluk_kriterleri or {}).get("sektorler", [])}
                    and t.id not in mevcut_idler
                ]
                tesvikler = tesvikler + sektor_tesvikleri[: 10 - len(tesvikler)]

        results = [
            SearchResult(
                id=t.id,
                kurum=t.kurum,
                baslik=t.baslik,
                ozet=t.ozet,
                hedef_kitle=t.hedef_kitle,
                baslama_tarihi=t.baslama_tarihi,
                bitis_tarihi=t.bitis_tarihi,
            )
            for t in tesvikler
        ]

        # Query'yi veritabanına kaydet
        query = Query(
            org_id=current_org.id,
            question=request.question,
            results=[r.dict() for r in results],
            tokens_used=len(request.question.split()),  # Basit tahmin
        )
        db.add(query)
        db.commit()

        return AskResponse(
            query_id=query.id,
            question=request.question,
            results=results,
            tokens_used=query.tokens_used,
            message=answer_text,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hata: {str(e)}"
        )


# ============ FINANCIAL PROFILE / MATCHING / BUDGET (PRO+) ============

def _require_pro(current_org: Organization):
    if current_org.plan == PlanType.FREE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu özellik PRO ve üzeri planlarda kullanılabilir. Planınızı yükseltin.",
        )


@app.put("/api/profil", response_model=FinancialProfileResponse)
def upsert_financial_profile(
    request: FinancialProfileCreate,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """İşletme/çiftçi finansal profilini oluştur veya güncelle."""
    profil = db.query(FinancialProfile).filter(FinancialProfile.org_id == current_org.id).first()
    if profil is None:
        profil = FinancialProfile(org_id=current_org.id)
        db.add(profil)

    profil.sektor = request.sektor.lower()
    profil.bolge = request.bolge
    profil.calisan_sayisi = request.calisan_sayisi
    profil.yillik_ciro = request.yillik_ciro
    profil.hedefler = request.hedefler
    profil.giderler = request.giderler
    profil.arazi_buyuklugu_dekar = request.arazi_buyuklugu_dekar
    profil.urun_turu = request.urun_turu
    profil.tarim_kategori = request.tarim_kategori
    profil.ilk_yil_mi = request.ilk_yil_mi

    db.commit()
    db.refresh(profil)
    return profil


@app.get("/api/profil", response_model=FinancialProfileResponse)
def get_financial_profile(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    profil = db.query(FinancialProfile).filter(FinancialProfile.org_id == current_org.id).first()
    if profil is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Önce finansal profil oluşturun (PUT /api/profil)")
    return profil


@app.get("/api/eslesme", response_model=TesvikEslesmeResponse)
def tesvik_eslesme(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Finansal profile göre uygun teşvikleri skorlayıp sıralar."""
    _require_pro(current_org)

    profil = db.query(FinancialProfile).filter(FinancialProfile.org_id == current_org.id).first()
    if profil is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Önce finansal profil oluşturun (PUT /api/profil)")

    sonuclar = esles(profil, db)
    tahmini_min, tahmini_max = toplam_tahmini_destek(sonuclar, profil)

    return TesvikEslesmeResponse(
        eslesen_tesvikler=[
            TesvikEslesmeItem(
                id=s.tesvik.id,
                kurum=s.tesvik.kurum,
                baslik=s.tesvik.baslik,
                ozet=s.tesvik.ozet,
                tesvil_tutari=s.tesvik.tesvil_tutari,
                kaynak_url=s.tesvik.kaynak_url,
                skor=s.skor,
                gerekce=s.gerekce,
                eksik_kriterler=s.eksik_kriterler,
                tutari_min=s.tesvik.tutari_min,
                tutari_max=s.tesvik.tutari_max,
                tutari_hesaplama_formulu=s.tesvik.tutari_hesaplama_formulu,
                tutari_tahmini_profil=tutari_tahmini_hesapla(s.tesvik, profil),
                basvuru_sartlari=s.tesvik.basvuru_sartlari,
                gerekli_belgeler=s.tesvik.gerekli_belgeler,
                basvuru_yeri=s.tesvik.basvuru_yeri,
                basvuru_suresi=s.tesvik.basvuru_suresi,
                destek_verilme_suresi=s.tesvik.destek_verilme_suresi,
                kategori=s.tesvik.kategori,
                alt_kategori=(s.tesvik.uygunluk_kriterleri or {}).get("alt_kategori"),
            )
            for s in sonuclar
        ],
        tahmini_toplam_destek_min=tahmini_min,
        tahmini_toplam_destek_max=tahmini_max,
    )


@app.get("/api/butce-onerisi", response_model=ButceOnerisiResponse)
def butce_onerisi(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """TÜİK/sektör benchmark'larına göre stok maliyeti ve reklam bütçesi önerisi."""
    _require_pro(current_org)

    profil = db.query(FinancialProfile).filter(FinancialProfile.org_id == current_org.id).first()
    if profil is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Önce finansal profil oluşturun (PUT /api/profil)")

    try:
        oneri = butce_hesapla(profil, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ButceOnerisiResponse(**oneri.__dict__)


@app.post("/api/eticaret/destek-hesapla", response_model=EticaretDestekResponse)
def eticaret_destek_hesapla_endpoint(
    request: EticaretGiderGirdisi,
    current_org: Organization = Depends(get_current_org),
):
    """Ticaret Bakanlığı E-İhracat Destekleri (5986 sayılı Karar) kapsamında,
    girilen yıllık gider kalemleri için tahmini geri ödeme tutarını hesaplar."""
    giderler = {
        k: v for k, v in request.model_dump().items()
        if k not in ("hedef_ulke_mi", "ihracatci_birligi_uyesi_mi") and v is not None
    }
    sonuc = eticaret_destek_hesapla(
        giderler,
        hedef_ulke_mi=request.hedef_ulke_mi,
        ihracatci_birligi_uyesi_mi=request.ihracatci_birligi_uyesi_mi,
    )
    return EticaretDestekResponse(
        hedef_ulke_mi=sonuc.hedef_ulke_mi,
        uygulanan_oran=sonuc.uygulanan_oran,
        kalemler=[k.__dict__ for k in sonuc.kalemler],
        toplam_yillik_gider_tl=sonuc.toplam_yillik_gider_tl,
        toplam_tahmini_geri_odeme_tl=sonuc.toplam_tahmini_geri_odeme_tl,
        notlar=sonuc.notlar,
    )


# ============ ORGANIZATION ENDPOINTS ============

@app.get("/api/organizations/me", response_model=OrganizationResponse)
def get_current_organization(current_org: Organization = Depends(get_current_org)):
    """Mevcut organizasyonu getir."""
    return current_org


@app.post("/api/organizations/upgrade", response_model=dict)
def upgrade_plan(
    request: PlanUpgrade,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Plan yükseltmek için Stripe Checkout oturumu oluşturur; dönen checkout_url'e yönlendirilmelidir."""
    try:
        result = create_checkout_session(str(current_org.id), request.plan, db)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.post("/api/organizations/confirm-checkout", response_model=dict)
def confirm_checkout(
    session_id: str,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Checkout success_url'ine dönüşte, webhook beklemeden ödemeyi doğrulayıp planı günceller."""
    try:
        return confirm_checkout_session(str(current_org.id), session_id, db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.post("/api/organizations/downgrade")
def downgrade_plan(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Free plana geri dön."""
    success = cancel_subscription(str(current_org.id), db)
    if success:
        return {"message": "Abonelik iptal edildi"}
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Abonelik iptal edilemedi"
    )


# ============ ANALYTICS ENDPOINTS ============

@app.get("/api/analytics/usage", response_model=AnalyticsResponse)
def get_usage_stats(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Kullanım istatistikleri."""
    from datetime import timedelta

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    queries = db.query(Query).filter(
        Query.org_id == current_org.id,
        Query.created_at >= thirty_days_ago
    ).all()

    plan_limits = get_plan_limits(current_org.plan)

    return AnalyticsResponse(
        org_id=current_org.id,
        usage_stats=UsageStats(
            queries_this_month=len(queries),
            queries_limit=plan_limits["queries_per_month"],
            api_calls_this_month=0,  # TODO: Track API calls separately
            users_active=db.query(User).filter(User.org_id == current_org.id, User.is_active).count(),
            storage_used_mb=0.0,  # TODO: Calculate storage
        ),
        created_at=datetime.now(timezone.utc),
    )


@app.get("/api/queries/history", response_model=List[QueryResponse])
def get_query_history(
    limit: int = 50,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Sorgulama geçmişini getir."""
    queries = db.query(Query).filter(
        Query.org_id == current_org.id
    ).order_by(Query.created_at.desc()).limit(limit).all()

    return queries


# ============ BILLING WEBHOOK ============

@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhooks. STRIPE_WEBHOOK_SECRET ayarlıysa imza doğrulanır."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if settings.STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz webhook imzası")
    else:
        event = json.loads(payload)

    handle_webhook(event, db)
    return {"status": "ok"}


# ============ LEGACY ENDPOINTS (Backward Compatibility) ============

@app.post("/sor")
def sor_legacy(request: AskQuestion, db: Session = Depends(get_db)):
    """Legacy endpoint - kimlik doğrulama olmadan."""
    try:
        answer_text = answer(request.question)
        tesvikler = db.query(Tesvik).limit(5).all()
        return {
            "cevap": answer_text,
            "tesvikler": [
                {
                    "kurum": t.kurum,
                    "baslik": t.baslik,
                    "ozet": t.ozet,
                }
                for t in tesvikler
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ STATIC FILES ============

@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/dashboard")
def dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "dashboard.html"))


@app.get("/cilek-paneli")
def cilek_paneli_sayfasi():
    return FileResponse(os.path.join(STATIC_DIR, "cilek_dashboard.html"))


if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ============ HEALTH CHECK ============

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}
