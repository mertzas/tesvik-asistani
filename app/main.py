import os
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.models import init_db, get_db, Organization, User, Query, Tesvik, settings
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
)
from app.rag import answer
from app.billing import create_subscription, cancel_subscription, handle_webhook, get_plan_limits
from app.admin import router as admin_router

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

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@app.on_event("startup")
def on_startup():
    init_db()


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
        # Mevcut RAG sistemini çalıştır
        answer_text = answer(request.question)

        # Veritabanından alakalı teşvikleri bul
        # Basit keyword matching (ileri sürümlerde embedding kullanacağız)
        keywords = request.question.lower().split()
        tesvikler = db.query(Tesvik).filter(
            Tesvik.detay.ilike(f"%{' '.join(keywords)}%")
        ).limit(10).all()

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
    """Plan yükselt."""
    try:
        result = create_subscription(str(current_org.id), request.plan, db)
        return result
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
def stripe_webhook(request: dict, db: Session = Depends(get_db)):
    """Stripe webhooks."""
    handle_webhook(request, db)
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


if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ============ HEALTH CHECK ============

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}
