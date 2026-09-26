import json
import logging
import os
from datetime import datetime, timezone
from typing import List
from uuid import UUID

import stripe
from fastapi import FastAPI, HTTPException, Depends, Request, status
# DIKKAT: bu modulde `Query` adi SQLAlchemy modeli (app.models.Query) icin
# kullaniliyor. FastAPI'nin sorgu parametresi bu yuzden takma adla alindi;
# dogrudan `Query(...)` yazmak sorgu parametresi yerine veritabani modelini
# cagirir ve endpoint sessizce yanlis davranir.
from fastapi import Query as SorguParam
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
from app.rag import answer, retrieve
from app.billing import create_checkout_session, confirm_checkout_session, cancel_subscription, handle_webhook, get_plan_limits
from app.admin import router as admin_router
from app.matching import esles, toplam_tahmini_destek, tutari_tahmini_hesapla
from app.budget import hesapla as butce_hesapla
from app.cilek_panel import router as cilek_router
from app.ikas_panel import router as ikas_router
from app.eticaret_destek_hesaplayici import eticaret_destek_hesapla
from app.rate_limit import org_hiz_siniri, ip_hiz_siniri
from app.logging_setup import kur as gunluklemeyi_kur
from app.veri_tazeligi import tazelik_raporu, genel_durum
from app.nace_9903 import (
    bolum_sarti, ek3_kaydi, ek3_kayitlari, ek3_yuklendi_mi, il_bolgesi,
    kaynak_bilgisi,
    olcek_uygunlugu,
)
from app.urun_sektor_anahtarlari import govde, kucult

gunluklemeyi_kur()
logger = logging.getLogger(__name__)
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

        # Gosterilecek kayitlar, AI danismanin gordugu kayitlarin AYNISI olmali.
        #
        # Onceki hali burada kendi arama mantigini kuruyordu: ham sorguyu
        # bosluklardan bolup TEK bir ILIKE '%tum kelimeler%' deniyor, sonuc
        # azsa sektor genislemesi yapiyordu. answer() ise kendi retrieve()'ini
        # calistirdigi icin iki yol farkli kayit kumeleri goruyordu. Somut
        # sonuc (dogrulandi 2026-09-26): "ÇİLEK SERASI İÇİN HİBE VAR MI"
        # sorgusunda listede 10 dogru kayit gorunurken ayni yanitin mesaj
        # alani "eslesen bir tesvik/destek programi bulamadim" diyordu -
        # ayni ekranda birbiriyle celisen iki cevap.
        #
        # Arama mantigi artik tek yerde: app/rag.retrieve() (Turkce govde
        # ayiklama ve sektor genislemesi dahil).
        tesvikler = retrieve(request.question, limit=10)

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
            # model_dump(mode="json") -> datetime alanlari ISO string'e
            # cevrilir. Onceki .dict() ham datetime nesnesi donduruyordu ve
            # JSON sutununa yazilirken "Object of type datetime is not JSON
            # serializable" ile TUM /api/sor istegi cokuyordu. Sadece
            # baslama_tarihi dolu olan 7 kayit (Tarim Bakanligi) eslesince
            # tetiklendigi icin fark edilmemisti - tarim sorularinin cogunda
            # AI danisman tamamen kirikti.
            results=[r.model_dump(mode="json") for r in results],
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


@app.get("/api/eslesme", response_model=TesvikEslesmeResponse,
         dependencies=[Depends(org_hiz_siniri(20))])
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
                aktif_mi=s.tesvik.aktif_mi,
                durum_notu=s.tesvik.durum_notu,
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


@app.get("/api/butce-onerisi", response_model=ButceOnerisiResponse,
         dependencies=[Depends(org_hiz_siniri(20))])
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


@app.post("/api/eticaret/destek-hesapla", response_model=EticaretDestekResponse,
          dependencies=[Depends(org_hiz_siniri(30))])
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
        logger.exception("Beklenmeyen hata: %s", e)
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


# ============ NACE / 9903 UYGUNLUK ============

@app.get("/api/nace/ara", dependencies=[Depends(ip_hiz_siniri(30))])
def nace_ara(q: str = SorguParam(..., min_length=1, max_length=80,
                            description="NACE kodu veya tanım metni")):
    """9903 sayılı Karar'ın EK-3 listesinde arama.

    Kimlik doğrulaması istemiyor: bu, Resmî Gazete'de yayımlanmış kamuya açık
    bir mevzuat ekidir, kullanıcıya ait hiçbir veri içermez.
    """
    if not ek3_yuklendi_mi():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="9903 EK-3 listesi şu an okunamıyor.",
        )
    aranan = kucult(q).strip()
    sonuclar = []
    for k in ek3_kayitlari():
        # Sart metni de aranıyor: aranan kelime NACE tanımında değil şartlarda
        # geçebiliyor. Örnek: "sera" kelimesi 01.19.99'un tanımında yok
        # ("Başka yerde sınıflandırılmamış tek yıllık diğer bitkisel ürünlerin
        # yetiştirilmesi") ama şart metninde "Sera Yatırımlarında" diye geçiyor;
        # sadece tanımda arayınca "sera" sorgusu 0 sonuç dönüyordu.
        havuz = kucult(k["tanim"]) + " " + kucult(k.get("sartlar") or "")
        # Türkçe ek soyma: "çağrı merkezi" sorgusu, metindeki "çağrı
        # merkezlerinin" ifadesine ham hâliyle eşleşmiyordu.
        terimler = [t for t in aranan.split() if t]
        metin_eslesme = bool(terimler) and all(
            t in havuz or govde(t) in havuz for t in terimler
        )
        if aranan in k["kod"] or metin_eslesme:
            sonuclar.append(k)
    return {
        "sorgu": q,
        "bulunan": len(sonuclar),
        "kaynak": kaynak_bilgisi(),
        "kayitlar": sonuclar[:40],
        "not": "Bu liste YATIRIM TEŞVİK BELGESİ kapsamındaki yatırım "
               "konularını gösterir. KOSGEB hibeleri, TÜBİTAK proje "
               "destekleri ve Tarım Bakanlığı'nın dekar/hayvan başı ödemeleri "
               "ayrı programlardır ve bu listeye tabi değildir.",
    }


@app.get("/api/nace/uygunluk", dependencies=[Depends(ip_hiz_siniri(30))])
def nace_uygunluk(
    kod: str = SorguParam(..., max_length=12, description="NACE Rev.2.1 kodu, ör. 01.19.99"),
    il: str | None = SorguParam(None, max_length=40),
    olcek: float | None = SorguParam(None, ge=0, description="Dekar veya adet/dönem"),
):
    """Bir NACE kodu 9903 EK-3 kapsamında mı, ve ölçeğiniz asgari şartı tutuyor mu?

    Yapılandırılmış ölçek kontrolü yalnızca tarım (EK-3 bölüm A) kodları için
    yapılır; diğer kodlarda şartlar asgari sabit yatırım tutarı gibi burada
    bilinmeyen verilere dayandığı için yalnızca resmî şart metni döner.
    """
    bolge = il_bolgesi(il)
    if not ek3_yuklendi_mi():
        # Liste okunamadiysa "kapsamda degil" DEMEYIZ: bu, kullaniciya
        # yanlis bir olumsuz hukum vermek olur (bkz. app/nace_9903.py).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="9903 EK-3 listesi şu an okunamıyor; uygunluk sorgusu "
                   "yanıtlanamıyor. Sunucu günlüklerini kontrol edin.",
        )

    kayit = ek3_kaydi(kod)
    yanit = {
        "kod": kod,
        "ek3_kapsaminda": kayit is not None,
        "il": il,
        "bolge": bolge,
        "kaynak": kaynak_bilgisi(),
    }
    if kayit is None:
        yanit["aciklama"] = (
            f"'{kod}' 9903 sayılı Karar'ın EK-3 listesinde yok. Bu, yatırım "
            "teşvik belgesi kapsamında DESTEKLENMEYEN bir yatırım konusu "
            "olduğu anlamına gelir. KOSGEB/TÜBİTAK gibi diğer programlar "
            "ayrıdır; onlar için /api/eslesme kullanın."
        )
        return yanit

    yanit["bolum"] = kayit["bolum"]
    yanit["bolum_ad"] = kayit["bolum_ad"]
    yanit["tanim"] = kayit["tanim"]
    yanit["resmi_sart_metni"] = kayit["sartlar"] or None
    yanit["bolum_duzeyi_sart"] = bolum_sarti(kayit["bolum"])

    degerlendirme = olcek_uygunlugu(kod, il, olcek)
    if degerlendirme is None:
        yanit["olcek_degerlendirmesi"] = None
        yanit["not"] = (
            "Bu yatırım konusu için sayısal ölçek kontrolü yapılmıyor; "
            "şartlar asgari sabit yatırım tutarı gibi profilde bulunmayan "
            "verilere dayanıyor. Yukarıdaki resmî şart metnini esas alın."
        )
    else:
        yanit["olcek_degerlendirmesi"] = {
            "durum": degerlendirme.durum,
            "asgari": degerlendirme.asgari,
            "birim": degerlendirme.birim,
            "sizin_olceginiz": degerlendirme.kullanici_olcegi,
            "aciklama": degerlendirme.aciklama,
            "ek_not": degerlendirme.ek_not or None,
        }
    return yanit


# ============ VERI TAZELIGI ============

@app.get("/api/veri-durumu", dependencies=[Depends(ip_hiz_siniri(30))])
def veri_durumu(db: Session = Depends(get_db)):
    """Uygulamanin dayandigi veri kaynaklarinin ne zaman guncellendigi.

    Kimlik dogrulamasi istemiyor: kullanicinin uye olmadan once "bu verilere
    guvenebilir miyim" sorusunu cevaplayabilmesi gerekiyor. Hicbir kisisel
    veri veya kayit icerigi donmuyor, sadece toplu sayac ve tarih.
    """
    rapor = tazelik_raporu(db)
    return {
        "genel_durum": genel_durum(rapor),
        "olcum_zamani": datetime.now(timezone.utc).isoformat(),
        "kaynaklar": [t.sozluk() for t in rapor],
    }


# ============ HEALTH CHECK ============

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    # Saglik kontrolu veri tazeligini de bildiriyor ki izleme sistemi
    # scraper'lar sessizce durdugunda haberdar olsun.
    try:
        durum = genel_durum(tazelik_raporu(db))
    except Exception:
        logger.exception("Saglik kontrolunde veri tazeligi okunamadi")
        durum = "bilinmiyor"
    return {"status": "ok", "version": "2.0.0", "veri_durumu": durum}
