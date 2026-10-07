import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List

import stripe
from fastapi import BackgroundTasks, FastAPI, HTTPException, Depends, Request, status
# DIKKAT: bu modulde `Query` adi SQLAlchemy modeli (app.models.Query) icin
# kullaniliyor. FastAPI'nin sorgu parametresi bu yuzden takma adla alindi;
# dogrudan `Query(...)` yazmak sorgu parametresi yerine veritabani modelini
# cagirir ve endpoint sessizce yanlis davranir.
from fastapi import Query as SorguParam
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import (init_db, get_db, Organization, User, Query, FinancialProfile, PlanType,
                        MacroIndicator, IkasBaglanti, BasvuruTakibi, settings)
from app.models_cilek import Parsel, SogukZincirOkuma
from app.dogrulama_mesajlari import turkce_hatalar
from app import hata_izleme
from app.auth import (
    get_current_user,
    get_current_org,
    hash_password,
    oturum_belirteci,
    oturumlari_gecersiz_kil,
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
    OrganizationResponse,
    PlanUpgrade,
    QueryResponse,
    AiRizaGuncelle,
    HesapSilme,
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
from app.rag import answer, answer_akis, profil_sozlugu, retrieve
from app.billing import create_checkout_session, confirm_checkout_session, cancel_subscription, handle_webhook, get_plan_limits
from app.admin import router as admin_router
from app.matching import esles, toplam_tahmini_destek, tutari_tahmini_hesapla
from app.budget import hesapla as butce_hesapla
from app.cilek_panel import router as cilek_router
from app.ikas_panel import router as ikas_router
from app.basvuru_listesi import router as basvuru_listesi_router
from app.hesap_belirtec import belirtec_uret, belirtec_tuket, SIFIRLAMA, DOGRULAMA
from app.email import EmailService
from app.schemas import SifreUnuttum, SifreSifirla, BelirtecGirdi
from app.eticaret_destek_hesaplayici import eticaret_destek_hesapla
from app.rate_limit import org_hiz_siniri, ip_hiz_siniri, sayac as hiz_sayaci
from sqlalchemy import text
from app.logging_setup import kur as gunluklemeyi_kur
from app.veri_tazeligi import tazelik_raporu, genel_durum
from app.nace_9903 import (
    bolum_sarti, ek3_kaydi, ek3_kayitlari, ek3_yuklendi_mi, il_bolgesi,
    kaynak_bilgisi,
    olcek_uygunlugu,
)
from app.urun_sektor_anahtarlari import govde, kucult
from app.tarim_destek_2026 import (
    KAYNAK as TARIM_KAYNAK,
    KAYNAK_URL as TARIM_KAYNAK_URL,
    arilik_destegi as tarim_arilik_destegi,
    hesapla as tarim_destek_hesapla,
)
from app.tesvik_9903_hesap import (
    hesapla as tesvik_9903_hesapla,
    programlari_karsilastir as tesvik_9903_karsilastir,
)

gunluklemeyi_kur()
logger = logging.getLogger(__name__)
from app.scheduler import scheduler_kilidi_al, setup_scheduler

# Global scheduler instance
_scheduler = None


@asynccontextmanager
async def yasam_dongusu(_app: FastAPI):
    """Açılış/kapanış (on_event yerine; FastAPI'de on_event kullanımdan kalktı). Adlar çağrı anında çözülür:
    on_startup/on_shutdown aşağıda tanımlıdır ve testlerde yamanabilir."""
    on_startup()
    try:
        yield
    finally:
        on_shutdown()


app = FastAPI(
    title="Teşvik Asistanı SaaS",
    description="Devlet teşviklerini bulmanın en kolay yolu",
    version="2.0.0",
    lifespan=yasam_dongusu,
)

VARSAYILAN_SECRET_KEY = "your-super-secret-key"


def izinli_originler() -> list[str]:
    """CORS izinli origin'ler: ALLOWED_ORIGINS (virgülle) yoksa APP_URL + yerel adresler.
    Denetim 2026-10-07: "*" + allow_credentials=True idi; tarayıcı bunu zaten reddeder ama
    kimliksiz uç noktalar (nace/kobi hesapları) her siteden çağrılabiliyordu."""
    ham = [o.strip().rstrip("/") for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
    if ham:
        return ham
    return sorted({settings.APP_URL.rstrip("/"), "http://localhost:8000", "http://127.0.0.1:8000"})


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=izinli_originler(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


GUVENLIK_BASLIKLARI = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


# Content-Security-Policy. script-src yalnızca 'self': sayfa betikleri app/static/js/ altında, olay yöneticileri
# data-tikla/data-degisim/data-gonder ile tek dinleyiciye bağlı (2026-10-08). Enjekte edilmiş satır içi betik ve
# onclick/onerror gibi öznitelikler çalışmaz; çilek panelinin Tailwind'i önceden derlenmiş CSS (dış kaynak yok).
# style-src'de 'unsafe-inline' BİLEREK kalıyor: panelde yüzlerce style="" özniteliği var; stil enjeksiyonu betik
# çalıştıramaz ve connect-src/img-src 'self' ile dışarı veri taşıyamaz (bilinen, düşük kalan risk).
# Ayrıca: <base> ile yön değiştirme, form hedefi değiştirme, <object>/<embed> ve çerçeveleme engellenir.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
# Swagger/ReDoc CDN'den script yükler; CSP'ye alınmaz (yalnızca HTML paneller ve sayfalar kapsanır).
CSP_MUAF_YOLLAR = ("/docs", "/redoc")


@app.middleware("http")
async def guvenlik_basliklari(request: Request, call_next):
    """Her yanıta temel güvenlik başlıkları (clickjacking, MIME sniffing, referrer sızıntısı);
    HTML yanıtlara ayrıca Content-Security-Policy."""
    response = await call_next(request)
    for k, v in GUVENLIK_BASLIKLARI.items():
        response.headers.setdefault(k, v)
    if (response.headers.get("content-type", "").startswith("text/html")
            and not request.url.path.startswith(CSP_MUAF_YOLLAR)):
        response.headers.setdefault("Content-Security-Policy", CSP)
    # Sayfa betikleri/CSS'i sürüm numarasız sunulur; önbellek yönergesi yokken tarayıcı sezgisel önbellekle eski
    # betiği kullanmaya devam ediyordu (2026-10-08). no-cache: her açılışta ETag ile doğrula (değişmediyse 304).
    if request.url.path.startswith("/static/") or response.headers.get("content-type", "").startswith("text/html"):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response

DB_MESGUL_YANITI = {"detail": "Veritabanı şu anda meşgul. Lütfen birkaç saniye sonra tekrar deneyin."}


def _hata_kimligi() -> str:
    return uuid.uuid4().hex[:12]


@app.exception_handler(OperationalError)
async def veritabani_hatasi(request: Request, exc: OperationalError):
    """SQLite kilidi (yazan bir scraper ile çakışma) düz metin 500 "Internal Server Error" yerine JSON 503 +
    Retry-After döner (Denetim 2 / Aşama D bulgusu). Başka işletim hataları JSON 500 + hata kimliği."""
    ham = str(getattr(exc, "orig", exc)).lower()
    if "locked" in ham or "busy" in ham:
        logger.warning("Veritabanı kilitli: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=DB_MESGUL_YANITI,
                            headers={"Retry-After": "5"})
    kimlik = _hata_kimligi()
    logger.error("Veritabanı hatası [%s] %s %s: %s", kimlik, request.method, request.url.path, exc)
    hata_izleme.bildir(exc, kimlik)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={"detail": "Veritabanı hatası oluştu.", "hata_kimligi": kimlik})


@app.exception_handler(RequestValidationError)
async def dogrulama_hatasi(request: Request, exc: RequestValidationError):
    """422: aynı yapı ({detail: [{loc, msg, type}]}), Türkçe mesaj; gönderilen değer yanıta yansıtılmaz
    (varsayılan işleyici parola politikasına takılan parolayı "input" alanında geri döndürüyordu)."""
    return JSONResponse(status_code=422, content={"detail": turkce_hatalar(exc.errors())})


@app.exception_handler(Exception)
async def beklenmeyen_hata(request: Request, exc: Exception):
    """Yakalanmamış her hata: kullanıcıya JSON + kısa hata kimliği, günlüğe aynı kimlikle tam yığın. Destek
    talebindeki kimlik günlükte doğrudan aranabilir (harici hata izleme servisi bağlanana kadar asgari iz)."""
    kimlik = _hata_kimligi()
    logger.error("Beklenmeyen hata [%s] %s %s", kimlik, request.method, request.url.path,
                 exc_info=(type(exc), exc, exc.__traceback__))
    hata_izleme.bildir(exc, kimlik)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={"detail": "Beklenmeyen bir hata oluştu. Sorun sürerse bu kimlikle bize ulaşın: "
                                           f"{kimlik}", "hata_kimligi": kimlik})


# Include admin routes
app.include_router(admin_router)
app.include_router(cilek_router)
app.include_router(ikas_router)
app.include_router(basvuru_listesi_router)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def secret_key_kontrolu() -> None:
    """Varsayılan SECRET_KEY ile JWT'ler herkes tarafından üretilebilir; açılışta durdur.
    Yerel geliştirmede ALLOW_INSECURE_SECRET=true ile (uyarıyla) geçilebilir."""
    if settings.SECRET_KEY != VARSAYILAN_SECRET_KEY and len(settings.SECRET_KEY) >= 32:
        return
    if settings.ALLOW_INSECURE_SECRET:
        logger.critical("SECRET_KEY varsayılan/kısa! Yalnızca yerel geliştirme için kabul edildi "
                        "(ALLOW_INSECURE_SECRET=true). Canlıda .env'e en az 32 karakterlik rastgele anahtar yazın.")
        return
    raise RuntimeError("SECRET_KEY tanımsız/varsayılan/kısa: .env'e en az 32 karakterlik rastgele bir anahtar "
                       "yazın (python -c \"import secrets; print(secrets.token_urlsafe(48))\"). "
                       "Yerel geliştirme için ALLOW_INSECURE_SECRET=true.")


def on_startup():
    global _scheduler
    secret_key_kontrolu()
    hata_izleme.kur(settings.SENTRY_DSN, settings.SENTRY_ORTAM)
    init_db()
    # Cok iscili dagitimda yalnizca kilidi alan isci scraper islerini calistirir.
    if settings.SCHEDULER_ENABLED and scheduler_kilidi_al():
        _scheduler = setup_scheduler()
        _scheduler.start()
    else:
        logger.info("Zamanlayici bu surecte kapali (SCHEDULER_ENABLED=%s)", settings.SCHEDULER_ENABLED)


def on_shutdown():
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()


# ============ AUTH ENDPOINTS ============

# Kayıtlı olmayan adreste de bir bcrypt karşılaştırması yapılır: yanıt süresi hesabın varlığını sızdırmasın.
_SAHTE_PAROLA_OZETI = hash_password("zamanlama-esitleme-icin-kullanilmayan-parola")
KAYIT_YANITI = {"mesaj": "Kaydınızı tamamlamak için e-posta adresinize gönderdiğimiz bağlantıya tıklayın. "
                         "Birkaç dakika içinde gelmezse spam klasörünü kontrol edin."}
EPOSTA_BASINA_KAYIT_BILDIRIMI = 3  # saatte; "bu adresle hesabınız var" postası bombardımana dönmesin


@app.post("/api/auth/signup", response_model=TokenResponse,
          responses={202: {"description": "Doğrulama zorunlu kayıt: hesap var/yok fark etmeksizin aynı yanıt"}},
          dependencies=[Depends(ip_hiz_siniri(10, ad="signup"))])
def signup(request: UserSignup, arka_plan: BackgroundTasks, db: Session = Depends(get_db)):
    """Yeni hesap oluştur. E-posta doğrulama bağlantısı arka planda gönderilir (SMTP yoksa atlanır).

    KAYIT_EPOSTA_DOGRULAMA_ZORUNLU açıkken yanıt her durumda 202 + KAYIT_YANITI'dır ve belirteç içermez:
    adres kayıtlıysa hesaba dokunulmaz, sahibine bildirim postası gider. Kapalıyken kayıt hemen oturum açar
    (bu durumda var olan adrese 400 dönmek kaçınılmazdır; numaralandırmaya karşı tek koruma IP hız sınırı)."""
    zorunlu = settings.KAYIT_EPOSTA_DOGRULAMA_ZORUNLU
    mevcut = db.query(User).filter(User.email == request.email).first()
    if mevcut is not None:
        if not zorunlu:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu email zaten kullanımda"
            )
        hash_password(request.password)  # yeni kayıt yolundaki bcrypt maliyetini eşitle
        izin, _ = hiz_sayaci.izin_ver(f"kayit-mevcut-eposta:{request.email.lower()}",
                                      EPOSTA_BASINA_KAYIT_BILDIRIMI, 3600)
        if mevcut.is_active and izin:
            arka_plan.add_task(_eposta_gonder, EmailService().send_existing_account_email, mevcut.email,
                               mevcut.full_name or "", f"{settings.APP_URL}/", f"{settings.APP_URL}/sifre-sifirla")
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=KAYIT_YANITI)

    # Organization oluştur
    org = Organization(
        name=request.company_name,
        email=request.email,
        ai_yurtdisi_riza=request.ai_yurtdisi_riza,
        ai_riza_tarihi=(datetime.now(timezone.utc)
                        if request.ai_yurtdisi_riza else None),
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
    _dogrulama_postasi_planla(db, user, arka_plan)
    if zorunlu:
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=KAYIT_YANITI)

    token = oturum_belirteci(user)

    return TokenResponse(
        access_token=token,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "email_dogrulandi": False,
        }
    )


@app.post("/api/auth/login", response_model=TokenResponse,
          dependencies=[Depends(ip_hiz_siniri(10, ad="login"))])
def login(request: UserLogin, arka_plan: BackgroundTasks, db: Session = Depends(get_db)):
    """Giriş yap. IP başına dakikada 10 deneme (parola kaba kuvvet koruması; denetim 2026-10-07).
    Kayıtlı olmayan adreste de bcrypt çalışır (yanıt süresi hesabın varlığını sızdırmaz)."""
    user = db.query(User).filter(User.email == request.email).first()
    parola_dogru = verify_password(request.password, user.hashed_password if user else _SAHTE_PAROLA_OZETI)

    if not user or not parola_dogru:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya şifre yanlış"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap deaktif"
        )

    # Doğrulama zorunluyken doğrulanmamış hesap giremez. Parola doğru olduğu için (kimlik kanıtlandı) bağlantı
    # yeniden gönderilir; e-posta başına saatte 3.
    if settings.KAYIT_EPOSTA_DOGRULAMA_ZORUNLU and user.email_dogrulama_zamani is None:
        izin, _ = hiz_sayaci.izin_ver(f"dogrulama-eposta:{user.email.lower()}", EPOSTA_BASINA_KAYIT_BILDIRIMI, 3600)
        if izin:
            _dogrulama_postasi_planla(db, user, arka_plan)
        # HTTPException fırlatılsaydı arka plan görevi (posta) hiç çalışmazdı: görevler yanıta bağlıdır.
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "E-posta adresiniz henüz doğrulanmadı. Doğrulama bağlantısını e-postanıza yeniden "
                               "gönderdik; bağlantıya tıklayıp parolanızla hesabınızı etkinleştirin."},
            background=arka_plan,
        )

    token = oturum_belirteci(user)

    return TokenResponse(
        access_token=token,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "email_dogrulandi": user.email_dogrulama_zamani is not None,
        }
    )


# ============ PAROLA SIFIRLAMA / E-POSTA DOGRULAMA ============
# Bağlantılar URL'nin # (fragment) kısmında taşınır: fragment sunucuya, günlüklere ve Referer'a gitmez.

SIFIRLAMA_YANITI = {"mesaj": "Bu e-posta adresi kayıtlıysa parola sıfırlama bağlantısı gönderildi. "
                             "Birkaç dakika içinde gelmezse spam klasörünü kontrol edin."}
EPOSTA_BASINA_SIFIRLAMA_LIMITI = 3  # saatte; posta bombardımanını önler


def _eposta_gonder(islem, *args) -> None:
    """Arka plan görevi: SMTP yavaş/hatalı olsa da istek süresini ve yanıtı etkilemesin."""
    try:
        if not islem(*args):
            logger.warning("E-posta gönderilemedi (SMTP yapılandırılmamış ya da hata): %s", islem.__name__)
    except Exception:
        logger.exception("E-posta gönderimi başarısız: %s", getattr(islem, "__name__", islem))


def _dogrulama_postasi_planla(db: Session, user: User, arka_plan: BackgroundTasks) -> None:
    ham = belirtec_uret(db, user, DOGRULAMA)
    arka_plan.add_task(_eposta_gonder, EmailService().send_verification_email, user.email,
                       user.full_name or "", f"{settings.APP_URL}/eposta-dogrula#t={ham}")


@app.post("/api/auth/sifre-unuttum", dependencies=[Depends(ip_hiz_siniri(5, ad="sifre-unuttum"))])
def sifre_unuttum(request: SifreUnuttum, arka_plan: BackgroundTasks, db: Session = Depends(get_db)):
    """Parola sıfırlama bağlantısı iste. Hesap var olsun olmasın AYNI yanıt döner (e-posta numaralandırma yok).
    IP başına dakikada 5, e-posta başına saatte 3 istek."""
    user = db.query(User).filter(User.email == request.email).first()
    izin, _ = hiz_sayaci.izin_ver(f"sifre-unuttum-eposta:{request.email.lower()}", EPOSTA_BASINA_SIFIRLAMA_LIMITI, 3600)
    if user is not None and user.is_active and izin:
        ham = belirtec_uret(db, user, SIFIRLAMA)
        arka_plan.add_task(_eposta_gonder, EmailService().send_password_reset_email, user.email,
                           user.full_name or "", f"{settings.APP_URL}/sifre-sifirla#t={ham}")
    return SIFIRLAMA_YANITI


@app.post("/api/auth/sifre-sifirla", dependencies=[Depends(ip_hiz_siniri(10, ad="sifre-sifirla"))])
def sifre_sifirla(request: SifreSifirla, db: Session = Depends(get_db)):
    """Tek kullanımlık belirteçle yeni parola belirle. Önceden verilmiş tüm oturum belirteçleri geçersizleşir
    (parolayı ele geçiren biri açık oturumla devam edemesin)."""
    user = belirtec_tuket(db, request.token, SIFIRLAMA)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Bağlantı geçersiz veya süresi dolmuş; yeni bir sıfırlama bağlantısı isteyin")
    user.hashed_password = hash_password(request.new_password)
    oturumlari_gecersiz_kil(user)
    if user.email_dogrulama_zamani is None:  # e-postaya erişimini kanıtladı
        user.email_dogrulama_zamani = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"mesaj": "Parolanız güncellendi. Yeni parolanızla giriş yapabilirsiniz."}


@app.post("/api/auth/eposta-dogrula", dependencies=[Depends(ip_hiz_siniri(10, ad="eposta-dogrula"))])
def eposta_dogrula(request: BelirtecGirdi, db: Session = Depends(get_db)):
    """E-posta doğrulama. Doğrulama zorunlu kayıtta parola da istenir ve başarıda oturum açılır: başkasının
    adresiyle (kendi parolasıyla) kayıt açan biri, adres sahibi bağlantıya tıklasa bile hesabı ele geçiremez.
    Parola yanlışsa belirteç YAKILMAZ (geri alınır), doğru parolayla yeniden denenebilir."""
    zorunlu = settings.KAYIT_EPOSTA_DOGRULAMA_ZORUNLU
    if zorunlu and not request.password:
        raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                            detail="Hesabınızı etkinleştirmek için kayıtta belirlediğiniz parolayı girin.")
    user = belirtec_tuket(db, request.token, DOGRULAMA)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Bağlantı geçersiz veya süresi dolmuş. Giriş yapmayı deneyin; hesabınız "
                                   "doğrulanmamışsa yeni bağlantı gönderilir.")
    if zorunlu and not verify_password(request.password, user.hashed_password):
        db.rollback()  # belirteç tüketilmemiş sayılır
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Parola bu kayıtla eşleşmiyor. Kaydı siz başlatmadıysanız ya da parolanızı "
                                   "hatırlamıyorsanız 'Şifremi unuttum' ile yeni parola belirleyin.")
    if user.email_dogrulama_zamani is None:
        user.email_dogrulama_zamani = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    yanit = {"mesaj": "E-posta adresiniz doğrulandı."}
    if zorunlu:
        yanit["mesaj"] = "E-posta adresiniz doğrulandı, hesabınız etkinleştirildi."
        yanit["access_token"] = oturum_belirteci(user)
    return yanit


@app.get("/api/auth/me")
def auth_me(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email, "full_name": current_user.full_name,
            "email_dogrulandi": current_user.email_dogrulama_zamani is not None}


@app.post("/api/auth/tum-oturumlari-kapat", response_model=TokenResponse,
          dependencies=[Depends(org_hiz_siniri(5))])
def tum_oturumlari_kapat(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Kullanıcının tüm cihazlardaki oturumlarını kapatır. İsteği yapan cihaz yeni belirteçle devam eder."""
    oturumlari_gecersiz_kil(current_user)
    db.commit()
    return TokenResponse(
        access_token=oturum_belirteci(current_user),
        user={
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "email_dogrulandi": current_user.email_dogrulama_zamani is not None,
        },
    )


@app.post("/api/auth/dogrulama-gonder", dependencies=[Depends(org_hiz_siniri(3))])
def dogrulama_yeniden_gonder(arka_plan: BackgroundTasks, current_user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    if current_user.email_dogrulama_zamani is not None:
        return {"mesaj": "E-posta adresiniz zaten doğrulanmış."}
    _dogrulama_postasi_planla(db, current_user, arka_plan)
    return {"mesaj": "Doğrulama bağlantısı e-posta adresinize gönderildi."}


# ============ MAIN API ENDPOINTS ============

RIZA_YOK_NOTU = (
    "\n\n---\n"
    "*Yapay zekâ danışmanı kapalı: bu yanıt yalnızca "
    "veritabanındaki kayıtlardan üretildi. AI destekli yorum için "
    "işletme profilinizin Anthropic'e (ABD) aktarılmasına açık "
    "rıza vermeniz gerekiyor - `POST /api/organizations/ai-riza` "
    "ile açabilir, istediğiniz zaman geri alabilirsiniz. "
    "Ayrıntı: /kvkk*"
)


@app.post("/api/sor", response_model=AskResponse, dependencies=[Depends(org_hiz_siniri(20))])
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
        # KVKK: acik riza YOKSA profil Anthropic'e gonderilmez ve LLM hic
        # cagrilmaz - sorunun METNI de kisisel veridir. Kullanici yine
        # bos ekran gormez; gercek kayitlarin liste formatini alir.
        riza_var = bool(current_org.ai_yurtdisi_riza)

        profil_row = db.query(FinancialProfile).filter(FinancialProfile.org_id == current_org.id).first()
        # Dışarı giden sözlük tek yerde tanımlı: app/rag.profil_sozlugu (ölçüm
        # betikleri ve testler aynı sözlüğü kullanır).
        profil = profil_sozlugu(profil_row) if (riza_var and profil_row is not None) else None

        # Mevcut RAG sistemini çalıştır
        answer_text = answer(request.question, profil, llm_kullan=riza_var,
                             profil_kaydi=profil_row)
        if not riza_var:
            answer_text += RIZA_YOK_NOTU

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
        tesvikler = retrieve(request.question, limit=10, profil_kaydi=profil_row)

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

    except Exception:
        # İç hata metni (SQL, dosya yolu, kütüphane mesajı) kullanıcıya sızmaz; günlüğe yazılır.
        logger.exception("/api/sor başarısız")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=GENEL_HATA)


GENEL_HATA = "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin; sorun sürerse destek ile iletişime geçin."


def _sse(tip: str, veri) -> str:
    return f"event: {tip}\ndata: {json.dumps(veri, ensure_ascii=False)}\n\n"


@app.post("/api/sor/akis", dependencies=[Depends(org_hiz_siniri(20))])
def sor_akis(
    request: AskQuestion,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """/api/sor'un akış (SSE) sürümü: danışman yanıtı üretilirken parça parça gönderilir.

    Olaylar: ``kayitlar`` (danışmanın gördüğü kayıt listesi) → ``parca`` (metin) … →
    ``son`` ({query_id}). Hata olursa ``hata`` ({detail}). Yetki, kota, rıza ve sorgu
    kaydı kuralları /api/sor ile aynıdır; LLM rıza yoksa hiç çağrılmaz.

    Ölçüm 2026-10-07: tam danışman yanıtı 35-60 sn sürüyor; panel o süre boyunca yalnızca
    spinner gösteriyordu (ve yanıtı hiç render etmiyordu).
    """
    if not check_rate_limit(current_org, db):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Aylık sorgulama limitini aştınız. Upgrading düşünün."
        )

    riza_var = bool(current_org.ai_yurtdisi_riza)
    profil_row = db.query(FinancialProfile).filter(FinancialProfile.org_id == current_org.id).first()
    profil = profil_sozlugu(profil_row) if (riza_var and profil_row is not None) else None

    # İlk olay (kayıtlar) akış başlamadan üretilir: sorgu kaydı istek oturumuyla,
    # yanıt gönderilmeden önce yazılır (akış sırasında oturumun ömrü garanti değil).
    uretec = answer_akis(request.question, profil, llm_kullan=riza_var, profil_kaydi=profil_row)
    try:
        _tip, kayitlar = next(uretec)
    except Exception:
        logger.exception("/api/sor/akis hazırlık başarısız")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=GENEL_HATA)
    results = [
        SearchResult(id=t.id, kurum=t.kurum, baslik=t.baslik, ozet=t.ozet, hedef_kitle=t.hedef_kitle,
                     baslama_tarihi=t.baslama_tarihi, bitis_tarihi=t.bitis_tarihi).model_dump(mode="json")
        for t in kayitlar
    ]
    query = Query(org_id=current_org.id, question=request.question, results=results,
                  tokens_used=len(request.question.split()))
    db.add(query)
    db.commit()
    query_id, tokens_used = str(query.id), query.tokens_used

    def uret():
        yield _sse("kayitlar", results)
        try:
            for _tip, parca in uretec:
                yield _sse("parca", {"metin": parca})
            if not riza_var:
                yield _sse("parca", {"metin": RIZA_YOK_NOTU})
            yield _sse("son", {"query_id": query_id, "tokens_used": tokens_used})
        except Exception:
            logger.exception("sor_akis: akış sırasında hata")
            yield _sse("hata", {"detail": GENEL_HATA})

    return StreamingResponse(uret(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ============ FINANCIAL PROFILE / MATCHING / BUDGET (PRO+) ============

ONIZLEME_ADEDI = 3  # FREE planda gösterilen eşleşme sayısı


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
    profil.nace_kodu = request.nace_kodu
    profil.ozellikler = request.ozellikler
    profil.sirket_turu = request.sirket_turu
    profil.kurulus_tarihi = request.kurulus_tarihi
    profil.trl = request.trl

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
    """Finansal profile göre uygun teşvikleri skorlayıp sıralar.

    FREE plan: tam liste yerine ilk ONIZLEME_ADEDI eşleşme (önizleme) döner; toplam sayı
    bildirilir. Denetim 2026-10-07: FREE kullanıcı 403 alıyor, ürünün ana değerini hiç
    görmeden plan yükseltmesi isteniyordu."""
    profil = db.query(FinancialProfile).filter(FinancialProfile.org_id == current_org.id).first()
    if profil is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Önce finansal profil oluşturun (PUT /api/profil)")

    sonuclar = esles(profil, db)
    tahmini_min, tahmini_max = toplam_tahmini_destek(sonuclar, profil)
    onizleme = current_org.plan == PlanType.FREE
    toplam = len(sonuclar)
    if onizleme:
        sonuclar = sonuclar[:ONIZLEME_ADEDI]

    return TesvikEslesmeResponse(
        onizleme=onizleme,
        toplam_eslesme=toplam,
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

@app.post("/api/organizations/ai-riza", response_model=dict,
          dependencies=[Depends(org_hiz_siniri(10))])
def ai_riza_guncelle(
    request: AiRizaGuncelle,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Yapay zekâ danışmanı için yurt dışına aktarım rızasını ver/geri al.

    KVKK açık rızası her zaman GERİ ALINABİLİR olmalıdır; bu uç nokta
    rızayı kapatmak için de kullanılır. Rıza kapatıldığında /api/sor
    Anthropic'e hiçbir şey göndermez, liste formatına döner.
    """
    current_org.ai_yurtdisi_riza = request.riza
    current_org.ai_riza_tarihi = datetime.now(timezone.utc) if request.riza else None
    db.commit()
    return {
        "ai_yurtdisi_riza": current_org.ai_yurtdisi_riza,
        "tarih": (current_org.ai_riza_tarihi.isoformat()
                  if current_org.ai_riza_tarihi else None),
        "mesaj": ("Açık rıza alındı; yapay zekâ danışmanı etkin."
                  if request.riza else
                  "Rıza geri alındı; işletme profiliniz artık yurt dışına "
                  "aktarılmayacak. Yanıtlar veritabanı kayıtlarından "
                  "üretilecek."),
        "aydinlatma_metni": "/kvkk",
    }


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


# ============ HESAP SİLME (KVKK m.11) ============

@app.delete("/api/organizations/me", dependencies=[Depends(org_hiz_siniri(5))])
def hesabi_sil(
    request: HesapSilme,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Hesabı ve organizasyona ait TÜM kişisel verileri kalıcı olarak siler (KVKK m.11/ç).

    Denetim 2026-10-07: aydınlatma metni "hesabınızı sildirdiğinizde silinir" diyordu ama
    kullanıcının kendi başına kullanabileceği bir silme yolu yoktu (yalnızca admin). Parola
    teyidi ve açık onay ister; varsa Stripe aboneliği iptal edilir; silinenler: finansal profil,
    sorgu geçmişi, başvuru kontrol listeleri, İKAS bağlantısı, çilek paneli verileri, kullanıcılar, organizasyon.
    """
    if not request.onay:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Silme için açık onay (onay=true) gerekir.")
    if not verify_password(request.password, current_user.hashed_password):
        # 403: oturum geçerli, yalnızca teyit parolası yanlış. 401 dönseydi panel bunu "oturum bitti" sanıp
        # kullanıcıyı çıkışa yönlendirirdi (401 yalnızca geçersiz/iptal edilmiş belirteç içindir).
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Parola yanlış.")

    org_id = current_org.id
    if current_org.stripe_subscription_id:
        try:
            cancel_subscription(str(org_id), db)
        except Exception:
            # Abonelik iptali başarısız olsa da silme hakkı bekletilmez; günlüğe düşülür.
            logger.exception("Hesap silme: Stripe aboneliği iptal edilemedi (org %s)", org_id)

    db.query(FinancialProfile).filter(FinancialProfile.org_id == org_id).delete(synchronize_session=False)
    db.query(BasvuruTakibi).filter(BasvuruTakibi.org_id == org_id).delete(synchronize_session=False)
    db.query(IkasBaglanti).filter(IkasBaglanti.org_id == org_id).delete(synchronize_session=False)
    db.query(SogukZincirOkuma).filter(SogukZincirOkuma.org_id == org_id).delete(synchronize_session=False)
    for parsel in db.query(Parsel).filter(Parsel.org_id == org_id).all():
        db.delete(parsel)  # ORM cascade: sensör/sulama/ilaçlama/hasat/gider kayıtları
    db.delete(current_org)  # ORM cascade: users, queries
    db.commit()
    logger.info("Hesap silindi (org %s)", org_id)
    return {"message": "Hesabınız ve tüm verileriniz kalıcı olarak silindi."}


# ============ BILLING WEBHOOK ============

@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhooks. İmza doğrulaması zorunlu; secret yoksa endpoint kapalıdır."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if settings.STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz webhook imzası")
    else:
        # Imza dogrulanamayan webhook'a guvenilmez: secret yokken herkes
        # sahte checkout.session.completed ile org'u PRO yapabilirdi.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook kapalı: STRIPE_WEBHOOK_SECRET tanımlı değil",
        )

    handle_webhook(event, db)
    return {"status": "ok"}


# Legacy POST /sor (kimliksiz, kotasız, ücretli LLM çağrısı yapan uç nokta) güvenlik denetiminde
# kaldırıldı (2026-10-07): hiçbir sayfa kullanmıyordu; herkes API kotasını tüketebilirdi.


# ============ STATIC FILES ============

@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/kvkk")
def kvkk_aydinlatma():
    """KVKK aydınlatma metni.

    Veri envanteri uygulamanın kendi şemasından çıkarıldı; şirket bilgileri
    (unvan, adres, VERBİS) sayfada DOLDURULACAK olarak işaretli - şirket
    kuruluşu tamamlanmadan doldurulamaz ve o alanlar dolmadan metin
    yayına hazır değildir.
    """
    return FileResponse(os.path.join(STATIC_DIR, "kvkk.html"))


@app.get("/dashboard")
def dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "dashboard.html"))


@app.get("/sifre-sifirla")
def sifre_sifirla_sayfasi():
    return FileResponse(os.path.join(STATIC_DIR, "sifre_sifirla.html"))


@app.get("/eposta-dogrula")
def eposta_dogrula_sayfasi():
    return FileResponse(os.path.join(STATIC_DIR, "eposta_dogrula.html"))


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


@app.get("/api/kobi-sinifi", dependencies=[Depends(ip_hiz_siniri(30))])
def kobi_sinifi_endpoint(
    calisan: int = SorguParam(..., ge=0, le=1_000_000),
    ciro: float | None = SorguParam(None, ge=0, le=1e13, description="Yıllık net satış hasılatı (TL)"),
    bilanco: float | None = SorguParam(None, ge=0, le=1e13, description="Mali bilanço toplamı (TL)"),
):
    """Ölçek sınıfı: mikro/küçük/orta/büyük (7 Ağustos 2025 KOBİ tanımı)."""
    from app.kobi import KAYNAK as KOBI_KAYNAK, SINIFLAR, kobi_sinifi
    sonuc = kobi_sinifi(calisan, ciro, bilanco)
    return {"sinif": sonuc.sinif, "kesin": sonuc.kesin, "kobi_mi": sonuc.kobi_mi,
            "aciklama": sonuc.aciklama, "esikler": {k: {"calisan_alti": v[0], "mali_limit_tl": v[1]}
                                                    for k, v in SINIFLAR.items()},
            "kaynak": KOBI_KAYNAK}


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


@app.get("/api/nace/9903-hesap", dependencies=[Depends(ip_hiz_siniri(20))])
def nace_9903_hesap(
    il: str = SorguParam(..., max_length=40),
    sabit_yatirim_tl: float = SorguParam(..., gt=0, le=1e12,
        description="Teşvik belgesine kaydedilecek sabit yatırım tutarı"),
    program: str | None = SorguParam(None,
        description="Tek program için; boş bırakılırsa beşi karşılaştırılır"),
    makine_techizat_tl: float | None = SorguParam(None, ge=0,
        description="Birim fiyatı 2 milyon TL üzerindeki makine bedeli"),
    kredi_tl: float | None = SorguParam(None, ge=0),
    ilave_istihdam: int | None = SorguParam(None, ge=0),
    asgari_ucret_isveren_primi_tl: float | None = SorguParam(None, ge=0,
        description="SGK'nın ilgili yıl için ilan ettiği aylık tutar"),
    db: Session = Depends(get_db),
):
    """9903 sayılı Karar kapsamında azami destek tutarını hesaplar.

    Bu endpoint, teşvik kayıtlarının %92'sinde tutar bilgisi olmamasının
    sebebini çözüyor: yatırım teşvik desteklerinin tutarı kayıt başına sabit
    bir TL değeri değil, yatırımın büyüklüğüne bağlı bir fonksiyondur.

    TCMB repo oranı veritabanındaki makro göstergeden alınır; yoksa faiz
    desteği hesaplanmaz ve eksik bilgi olarak bildirilir.
    """
    if il_bolgesi(il) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{il}' tanınan bir il adı değil; bölge belirlenemedi.",
        )
    repo = None
    satir = db.query(MacroIndicator).filter(
        MacroIndicator.anahtar == "tcmb_politika_faizi").first()
    if satir is not None:
        repo = satir.deger

    ortak = dict(
        makine_techizat_tl=makine_techizat_tl, kredi_tl=kredi_tl,
        ilave_istihdam=ilave_istihdam,
        aylik_asgari_ucret_isveren_primi_tl=asgari_ucret_isveren_primi_tl,
        repo_faiz_orani=repo,
    )
    try:
        if program:
            hesaplar = [tesvik_9903_hesapla(program, il, sabit_yatirim_tl, **ortak)]
        else:
            hesaplar = tesvik_9903_karsilastir(il, sabit_yatirim_tl, **ortak)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "il": il,
        "bolge": il_bolgesi(il),
        "sabit_yatirim_tl": sabit_yatirim_tl,
        "repo_faiz_orani": repo,
        "repo_kaynagi": ("Veritabanındaki TCMB politika faizi (bir hafta vadeli "
                         "repo) göstergesi" if repo else None),
        "hesaplar": [h.sozluk() for h in hesaplar],
    }


@app.get("/api/tarim/destek-hesap", dependencies=[Depends(ip_hiz_siniri(30))])
def tarim_destek_hesap(
    urun: str = SorguParam(..., max_length=60),
    alan_dekar: float = SorguParam(..., gt=0),
    il: str | None = SorguParam(None, max_length=40),
    planli_uretim: bool = SorguParam(True),
    sertifikali_tohum: bool = SorguParam(False),
    yerli_sertifikali_tohum: bool = SorguParam(False),
    fidan: str | None = SorguParam(None, description="standart | sertifikali"),
    organik_grup: int | None = SorguParam(None, ge=1, le=3),
    organik_sertifika: str = SorguParam("bireysel", description="bireysel | grup"),
    organik_orgut_uyesi: bool = SorguParam(False),
    iyi_tarim: str | None = SorguParam(None,
        description="1_ortualti | 1_acikta | 2 | 3"),
    iyi_tarim_sertifika: str = SorguParam("bireysel"),
    organomineral_gubre: bool = SorguParam(False),
    genc_veya_kadin_kobuks: bool = SorguParam(False),
    su_kisiti_havzasi: bool = SorguParam(False),
    yem_bitkisi: bool = SorguParam(False),
):
    """2026 bitkisel üretim desteklerini ürün ve alana göre hesaplar.

    Bakanlık desteği dekar başına ve katsayı sistemiyle veriyor; tutar kayda
    değil ürüne ve alana bağlı olduğu için burada hesaplanıyor. Kimlik
    doğrulaması istemiyor: birim fiyatlar kamuya açık resmî tablodan geliyor,
    kişisel veri dönmüyor.
    """
    try:
        h = tarim_destek_hesapla(
            urun, alan_dekar, il=il, planli_uretim=planli_uretim,
            sertifikali_tohum=sertifikali_tohum,
            yerli_sertifikali_tohum=yerli_sertifikali_tohum, fidan=fidan,
            organik_grup=organik_grup, organik_sertifika=organik_sertifika,
            organik_orgut_uyesi=organik_orgut_uyesi, iyi_tarim=iyi_tarim,
            iyi_tarim_sertifika=iyi_tarim_sertifika,
            organomineral_gubre=organomineral_gubre,
            genc_veya_kadin_kobuks=genc_veya_kadin_kobuks,
            su_kisiti_havzasi=su_kisiti_havzasi, yem_bitkisi=yem_bitkisi,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return h.sozluk()


@app.get("/api/tarim/arilik-destek", dependencies=[Depends(ip_hiz_siniri(30))])
def tarim_arilik_destek(kovan_sayisi: int = SorguParam(..., gt=0)):
    """Organik arılı kovan desteği - KOVAN başına ödenir, dekar başına değil."""
    try:
        k = tarim_arilik_destegi(kovan_sayisi)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "kovan_sayisi": kovan_sayisi, "ad": k.ad, "katsayi": k.katsayi,
        "kovan_basi_tl": k.dekar_basi_tl, "toplam_tl": k.toplam_tl,
        "not": k.not_, "kaynak": TARIM_KAYNAK, "kaynak_url": TARIM_KAYNAK_URL,
    }


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
    # Veritabanina gercekten dokunulur: baglanti kopuksa 503 (compose/izleme healthcheck'i
    # bunu okur; onceki hali DB olmadan da "ok" diyordu).
    # Gerçek bir tablo okunur: SQLite'ta "SELECT 1" dosyaya hiç dokunmadığından kilitli DB'yi
    # yakalamıyordu; dayanıklılık deneyinde (2026-10-07) kilit altında /health 35 sn sonra
    # "veri_yok" ile 200 dönüyordu (her kaynak 5 sn busy_timeout bekledi).
    try:
        db.execute(text("SELECT 1 FROM tesvikler LIMIT 1"))
    except Exception:
        logger.exception("Saglik kontrolu: veritabanina ulasilamiyor")
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={"status": "db_erisilemiyor", "version": "2.0.0"})
    try:
        durum = genel_durum(tazelik_raporu(db))
    except Exception:
        logger.exception("Saglik kontrolunde veri tazeligi okunamadi")
        durum = "bilinmiyor"
    return {"status": "ok", "version": "2.0.0", "veri_durumu": durum,
            "hiz_siniri": "redis" if type(hiz_sayaci).__name__ == "_RedisSayac" else "surec_ici",
            "zamanlayici": bool(_scheduler is not None and getattr(_scheduler, "running", False))}
