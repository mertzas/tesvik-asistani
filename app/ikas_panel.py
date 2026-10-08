"""
İKAS Admin App entegrasyon router'ı - Faz 1 (OAuth bağlantı), Faz 2
(otomatik veri eşleme) ve Faz 3'ün (gömülü panel + webhook bildirimi)
API yüzeyi.

İKAS App Store akışları (builders.ikas.com, 2026-10-08; ikisi de yayın şartı):
  A. İKAS panelinden kurulum: İKAS, uygulamanın "Kurulum Adresi"ni ?storeName=X ile açar
     -> GET /api/oauth/authorize/ikas?storeName=X  (oturum gerekmez; state + tarayıcı çerezi)
     -> İKAS onay ekranı -> GET /api/oauth/callback/ikas?code&state
     -> token, me (authorizedAppId), getMerchant; hesap yoksa mağaza adına oluşturulur; webhook kaydı
     -> https://{storeName}.myikas.com/admin/authorized-app/{authorizedAppId} adresine dönülür
  B. Uygulamadan bağlanma: oturum açmış kullanıcı GET /api/ikas/baglan?storeName=X -> authorize_url (JSON)
     -> aynı callback; bu kez mevcut kuruluşa bağlanır.
  İKAS panelinden açılış: İKAS uygulama adresini authorizedAppId, merchantId, signature, storeName, timestamp
  ile açar -> /ikas sayfası -> POST /api/ikas/oturum (imza doğrulama) -> bizim JWT.

Faz 2: POST /api/ikas/senkronize - saklı token ile siparişleri çeker,
FinancialProfile'ı otomatik doldurur (elle giriş yok).

Faz 3: GET /api/ikas/panel - teşvik eşleşmesi + bütçe önerisini tek
çağrıda döner (İKAS admin paneline gömülecek iframe/ekran için).
POST /api/ikas/webhook - İKAS'ın imzalı webhook'u (sipariş oluştu/güncellendi, uygulama kaldırıldı).
"""
import base64
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import (FinancialProfile, IkasBaglanti, Organization, SessionLocal, User, get_db, settings)
from app.auth import get_current_org, hash_password, oturum_belirteci
from app.rate_limit import org_hiz_siniri, ip_hiz_siniri
from app.ikas_integration import (
    authorize_url_olustur, giris_imzasi_dogrula, kod_ile_token_al, magaza_adi_gecerli_mi, magaza_bilgisi_getir,
    refresh_token_yenile, siparisleri_getir, uygulama_siri, webhook_imzasi_dogrula, webhook_kaydet, yeni_state,
    _mock_mu,
)
from app.ikas_veri_esleme import profili_ikas_verisiyle_guncelle
from app.matching import esles
from app.budget import hesapla as butce_hesapla

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ikas", tags=["ikas-entegrasyon"])
# İKAS'ın belgelediği sabit yollar (/api/oauth/authorize/ikas, /api/oauth/callback/ikas): ayrı router.
oauth_router = APIRouter(tags=["ikas-oauth"])

KURULUM_CEREZI = "ikas_kurulum"
STATE_OMRU_DK = 15                 # authorize -> callback arası en çok
WEBHOOK_SENKRON_ARALIGI_DK = 10    # webhook olayları bundan sık gelirse tam senkron ertelenir
TOKEN_YENILEME_PAYI_SN = 300       # süresi 5 dk içinde dolacak token önceden yenilenir


def ikas_webhook_belirteci(store_name: str) -> str:
    """Eski (imzasız) webhook adresi için mağazaya özgü belirteç: HMAC-SHA256(SECRET_KEY, mağaza).
    İKAS webhook'ları HMAC-SHA256(client_secret, data) ile imzalar (SDK validateIkasWebhookSignature);
    yeni kayıtlar imzalı POST /api/ikas/webhook adresini kullanır. Bu adres elle kaydedilmiş eski webhook'lar
    için korunuyor."""
    ozet = hmac.new(settings.SECRET_KEY.encode(), f"ikas-webhook:{store_name}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(ozet).decode().rstrip("=")


def _redirect_uri() -> str:
    return f"{settings.APP_URL}/api/oauth/callback/ikas"


def _webhook_adresi() -> str:
    return f"{settings.APP_URL}/api/ikas/webhook"


def oturum_ac() -> Session:
    """Arka plan senkronu için yeni oturum (istek oturumu yanıtla kapanır). Testler bunu yamar."""
    return SessionLocal()


def _naif_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _simdi() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _magaza_adi(storeName: str) -> str:
    ad = (storeName or "").strip().lower()
    if not magaza_adi_gecerli_mi(ad):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Geçersiz İKAS mağaza adı: yalnızca küçük harf, rakam ve tire (ör. 'benim-magazam').")
    return ad


# ------------------------------------------------------------------------------------------------ OAuth akışları

@router.get("/baglan", dependencies=[Depends(org_hiz_siniri(10))])
def ikas_baglan(
    storeName: str = Query(..., description="İKAS mağaza alt alan adı (ör. 'benim-magazam')"),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Senaryo B - oturum açmış kullanıcı mağazasını bağlar: tarayıcının gideceği authorize URL'ini döner."""
    store = _magaza_adi(storeName)
    state = yeni_state()

    baglanti = db.query(IkasBaglanti).filter(IkasBaglanti.org_id == current_org.id).first()
    if baglanti is None:
        baglanti = IkasBaglanti(org_id=current_org.id)
        db.add(baglanti)

    baglanti.store_name = store
    baglanti.oauth_state = state
    if baglanti.baglanti_durumu != "bagli":
        baglanti.baglanti_durumu = "beklemede"
    baglanti.updated_at = datetime.now(timezone.utc)
    db.commit()

    url = authorize_url_olustur(
        store_name=store,
        client_id=settings.IKAS_CLIENT_ID or "MOCK_CLIENT_ID",
        redirect_uri=_redirect_uri(),
        state=state,
    )
    return {
        "authorize_url": url,
        "mock_mode": _mock_mu(),
        "not": (
            "IKAS_CLIENT_ID henüz tanımlı değil - bu URL gerçek İKAS'a "
            "yönlendirilirse çalışmaz. Gerçek bağlantı için İKAS Builders "
            "Dashboard'da uygulama kaydı ve test mağazası ataması gerekir."
            if not settings.IKAS_CLIENT_ID else None
        ),
    }


@oauth_router.get("/api/oauth/authorize/ikas", dependencies=[Depends(ip_hiz_siniri(20, ad="ikas-kurulum"))])
def ikas_kurulum_baslat(storeName: str = Query(...), db: Session = Depends(get_db)):
    """Senaryo A - İKAS panelinden kurulum ("Kurulum Adresi"). Oturum gerekmez: kuruluşsuz bir bekleyen kayıt
    açılır, state tarayıcıya httpOnly çerezle de yazılır (callback aynı tarayıcıda tamamlanmalı: login CSRF'e
    karşı). Süresi geçmiş kuruluşsuz bekleyen kayıtlar temizlenir."""
    store = _magaza_adi(storeName)
    esik = _simdi() - timedelta(minutes=STATE_OMRU_DK)
    db.query(IkasBaglanti).filter(IkasBaglanti.org_id.is_(None), IkasBaglanti.updated_at < esik).delete(
        synchronize_session=False)
    state = yeni_state()
    db.add(IkasBaglanti(org_id=None, store_name=store, oauth_state=state, baglanti_durumu="beklemede"))
    db.commit()
    yanit = RedirectResponse(authorize_url_olustur(store, settings.IKAS_CLIENT_ID or "MOCK_CLIENT_ID",
                                                   _redirect_uri(), state), status_code=status.HTTP_302_FOUND)
    yanit.set_cookie(KURULUM_CEREZI, state, max_age=STATE_OMRU_DK * 60, httponly=True,
                     secure=settings.APP_URL.startswith("https://"), samesite="lax", path="/api/oauth")
    return yanit


def _ikas_hesabi_olustur(db: Session, bilgi, store: str) -> Organization:
    """Kurulumla gelen mağaza için kuruluş + kullanıcı. Mağaza e-postası başka bir hesapta kayıtlıysa o hesaba
    BAĞLANMAZ (İKAS e-postasının sahipliği bizim için kanıtlanmış değil): yer tutucu adresle ayrı hesap açılır;
    kullanıcı isterse uygulamadan "İKAS'a bağlan" ile mevcut hesabına bağlar. Parola rastgeledir; giriş İKAS
    panelinden (imzalı açılış) ya da e-posta mağazanınsa "Şifremi unuttum" ile yapılır."""
    eposta = (bilgi.eposta or "").strip().lower()
    if not eposta or db.query(User).filter(User.email == eposta).first() is not None \
            or db.query(Organization).filter(Organization.email == eposta).first() is not None:
        eposta = f"ikas-{store}@magaza.ikas.invalid"
    org = Organization(name=(bilgi.magaza_unvani or store)[:200], email=eposta)
    db.add(org)
    db.flush()
    db.add(User(email=eposta, hashed_password=hash_password(secrets.token_urlsafe(32)),
                full_name=bilgi.magaza_unvani or store, org_id=org.id))
    if bilgi.il and (bilgi.ulke_iso2 or "TR").upper() == "TR":
        db.add(FinancialProfile(org_id=org.id, sektor="e-ticaret", bolge=bilgi.il))
    db.flush()
    return org


def _oauth_callback(code: str, state: str, storeName: str | None, request: Request, db: Session,
                    arka_plan: BackgroundTasks):
    baglanti = db.query(IkasBaglanti).filter(IkasBaglanti.oauth_state == state).first()
    if baglanti is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz veya süresi dolmuş state - bağlantıyı tekrar başlatın.")
    kurulum = baglanti.org_id is None
    if kurulum and not hmac.compare_digest(request.cookies.get(KURULUM_CEREZI, ""), state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Kurulum bu tarayıcıda başlatılmamış; İKAS panelinden tekrar kurun.")
    zaman = _naif_utc(baglanti.updated_at or baglanti.created_at)
    if zaman is not None and zaman < _simdi() - timedelta(minutes=STATE_OMRU_DK):
        baglanti.oauth_state = None
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bağlantı isteğinin süresi doldu; tekrar başlatın.")
    if storeName and storeName.lower() != baglanti.store_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mağaza adı uyuşmuyor.")

    sonuc = kod_ile_token_al(baglanti.store_name, code, _redirect_uri())
    if not sonuc.basarili:
        baglanti.baglanti_durumu = "hata"
        baglanti.son_senkron_hata = sonuc.hata
        baglanti.oauth_state = None
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Token alınamadı: {sonuc.hata}")

    bilgi, bilgi_hatasi = magaza_bilgisi_getir(sonuc.access_token, baglanti.store_name)
    if bilgi is None:
        baglanti.baglanti_durumu = "hata"
        baglanti.son_senkron_hata = f"Mağaza bilgisi alınamadı: {bilgi_hatasi}"
        baglanti.oauth_state = None
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="İKAS mağaza bilgisi alınamadı; birkaç dakika sonra tekrar deneyin.")

    # Aynı mağaza (merchantId) başka bir kayda bağlıysa: kurulumda o kuruluşa dönülür (yeniden kurulum),
    # uygulamadan bağlanmada eski bağ kaldırılır (bir mağaza tek kuruluşa bağlıdır).
    ayni = []
    if bilgi.merchant_id:
        ayni = db.query(IkasBaglanti).filter(IkasBaglanti.merchant_id == bilgi.merchant_id,
                                             IkasBaglanti.id != baglanti.id).all()
    if kurulum:
        mevcut = next((b for b in ayni if b.org_id is not None), None)
        if mevcut is not None:
            db.delete(baglanti)
            baglanti = mevcut
            ayni = [b for b in ayni if b.id != mevcut.id]
        else:
            baglanti.org_id = _ikas_hesabi_olustur(db, bilgi, baglanti.store_name).id
    for eski in ayni:
        db.delete(eski)

    baglanti.access_token = sonuc.access_token
    baglanti.refresh_token = sonuc.refresh_token
    baglanti.scope = sonuc.scope
    baglanti.token_expires_at = (_simdi() + timedelta(seconds=sonuc.expires_in)) if sonuc.expires_in else None
    baglanti.authorized_app_id = bilgi.authorized_app_id
    baglanti.merchant_id = bilgi.merchant_id
    baglanti.baglanti_durumu = "bagli"
    baglanti.oauth_state = None  # tek kullanımlık - kullanıldıktan sonra temizlenir
    baglanti.son_senkron_hata = None
    baglanti.senkron_bekliyor = True
    tamam, hata = webhook_kaydet(sonuc.access_token, _webhook_adresi())
    baglanti.webhook_kaydi = "kayitli" if tamam else (hata or "bilinmeyen hata")[:300]
    db.commit()
    arka_plan.add_task(_arka_plan_senkron, baglanti.id)

    if _mock_mu():
        # Mock: İKAS paneli yok; panelden açılışı yerelde taklit et (imza mock sırıyla, 120 sn geçerli).
        from app.ikas_integration import giris_imzasi_uret
        ts = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        imza = giris_imzasi_uret(baglanti.store_name, baglanti.merchant_id or "", ts, uygulama_siri())
        hedef = "/ikas?" + urlencode({"storeName": baglanti.store_name, "merchantId": baglanti.merchant_id or "",
                                      "authorizedAppId": baglanti.authorized_app_id, "timestamp": ts,
                                      "signature": imza})
    else:
        hedef = f"https://{baglanti.store_name}.myikas.com/admin/authorized-app/{baglanti.authorized_app_id}"
    yanit = RedirectResponse(hedef, status_code=status.HTTP_302_FOUND)
    yanit.delete_cookie(KURULUM_CEREZI, path="/api/oauth")
    return yanit


@oauth_router.get("/api/oauth/callback/ikas", dependencies=[Depends(ip_hiz_siniri(20, ad="ikas-callback"))])
def ikas_oauth_callback(request: Request, arka_plan: BackgroundTasks, code: str = Query(...),
                        state: str = Query(...), storeName: str = Query(None), db: Session = Depends(get_db)):
    """İKAS'ın çağırdığı callback (redirect_uri, partner panelindeki kayıtla birebir aynı olmalı). JWT YOK:
    eşleştirme 'state' ile; kurulum akışında ayrıca tarayıcı çereziyle."""
    return _oauth_callback(code, state, storeName, request, db, arka_plan)


@router.get("/callback-oauth", include_in_schema=False)
def ikas_oauth_callback_eski(request: Request, arka_plan: BackgroundTasks, code: str = Query(...),
                             state: str = Query(...), storeName: str = Query(None), db: Session = Depends(get_db)):
    """Eski yol (redirect_uri /api/oauth/callback/ikas'a taşındı); geriye dönük uyumluluk için."""
    return _oauth_callback(code, state, storeName, request, db, arka_plan)


# --------------------------------------------------------------------------------- İKAS panelinden imzalı açılış

class IkasOturumGirdi(BaseModel):
    storeName: str = Field(..., max_length=63)
    merchantId: str = Field(..., max_length=64)
    authorizedAppId: str = Field(..., max_length=64)
    timestamp: str = Field(..., max_length=20)
    signature: str = Field(..., max_length=128)


@router.post("/oturum", dependencies=[Depends(ip_hiz_siniri(30, ad="ikas-oturum"))])
def ikas_oturum(girdi: IkasOturumGirdi, db: Session = Depends(get_db)):
    """İKAS uygulamayı panelde açarken adrese imzalı parametreler ekler; /ikas sayfası bunları buraya gönderir.
    İmza HMAC-SHA256(uygulama sırrı, storeName+merchantId+timestamp) ve en çok 120 sn eski olmalı. Doğruysa ve
    mağaza bu kurulumla bağlıysa kuruluşun kullanıcısı için oturum belirteci döner."""
    if not giris_imzasi_dogrula(girdi.storeName, girdi.merchantId, girdi.timestamp, girdi.signature,
                                uygulama_siri()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="İKAS oturum imzası geçersiz veya süresi dolmuş; uygulamayı İKAS panelinden yeniden açın.")
    baglanti = db.query(IkasBaglanti).filter(
        IkasBaglanti.store_name == girdi.storeName, IkasBaglanti.authorized_app_id == girdi.authorizedAppId,
        IkasBaglanti.baglanti_durumu == "bagli", IkasBaglanti.org_id.isnot(None)).first()
    if baglanti is None or (baglanti.merchant_id and baglanti.merchant_id != girdi.merchantId):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Bu mağaza için kurulum bulunamadı; uygulamayı İKAS panelinden yeniden kurun.")
    user = db.query(User).filter(User.org_id == baglanti.org_id, User.is_active.is_(True)).order_by(
        User.created_at).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu mağazanın hesabı etkin değil.")
    return {"access_token": oturum_belirteci(user), "token_type": "bearer",
            "senkron_bekliyor": bool(baglanti.senkron_bekliyor or baglanti.son_senkron_zamani is None)}


# ------------------------------------------------------------------------------------------------- senkron

def _gecerli_token(db: Session, baglanti: IkasBaglanti) -> str | None:
    """Süresi dolmak üzere olan erişim belirtecini refresh_token ile yeniler (SDK refreshToken). Yenileme
    başarısızsa bağlantı 'hata' olur ve None döner (kullanıcı yeniden bağlanmalı)."""
    bitis = _naif_utc(baglanti.token_expires_at)
    if bitis is None or bitis - timedelta(seconds=TOKEN_YENILEME_PAYI_SN) > _simdi():
        return baglanti.access_token
    if not baglanti.refresh_token:
        baglanti.baglanti_durumu = "hata"
        baglanti.son_senkron_hata = "Erişim belirtecinin süresi doldu ve yenileme belirteci yok; yeniden bağlanın."
        db.commit()
        return None
    sonuc = refresh_token_yenile(baglanti.store_name, baglanti.refresh_token)
    if not sonuc.basarili:
        baglanti.baglanti_durumu = "hata"
        baglanti.son_senkron_hata = f"Belirteç yenilenemedi: {sonuc.hata}"
        db.commit()
        return None
    baglanti.access_token = sonuc.access_token
    baglanti.refresh_token = sonuc.refresh_token
    baglanti.token_expires_at = (_simdi() + timedelta(seconds=sonuc.expires_in)) if sonuc.expires_in else None
    db.commit()
    return baglanti.access_token


def _senkronize_et(db: Session, baglanti: IkasBaglanti):
    """Siparişleri çek, profili ve son_ozet'i güncelle. (özet | None, hata | None)."""
    token = _gecerli_token(db, baglanti)
    if token is None:
        return None, baglanti.son_senkron_hata
    sonuc = siparisleri_getir(baglanti.store_name, token)
    if not sonuc.basarili:
        baglanti.son_senkron_hata = sonuc.hata
        db.commit()
        return None, sonuc.hata
    ozet = profili_ikas_verisiyle_guncelle(db, baglanti.org_id, sonuc.siparisler)
    if sonuc.kismi:
        ozet.notlar.append("Sipariş sayısı tek senkron sınırını aştı; en yeni siparişler kullanıldı, yıllık ciro "
                           "eksik olabilir.")
    baglanti.son_ozet = ozet.gostergeler()
    baglanti.son_senkron_zamani = _simdi()
    baglanti.son_senkron_hata = None
    baglanti.senkron_bekliyor = False
    db.commit()
    return ozet, None


def _arka_plan_senkron(baglanti_id) -> None:
    db = oturum_ac()
    try:
        baglanti = db.get(IkasBaglanti, baglanti_id)
        if baglanti is not None and baglanti.baglanti_durumu == "bagli" and baglanti.org_id is not None:
            _senkronize_et(db, baglanti)
    except Exception:
        logger.exception("İKAS arka plan senkronu başarısız (baglanti=%s)", baglanti_id)
    finally:
        db.close()


@router.get("/durum")
def ikas_baglanti_durumu(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    baglanti = db.query(IkasBaglanti).filter(IkasBaglanti.org_id == current_org.id).first()
    if baglanti is None:
        return {"baglanti_durumu": "bagli_degil", "mock_mode": _mock_mu()}
    return {
        "baglanti_durumu": baglanti.baglanti_durumu,
        "store_name": baglanti.store_name,
        "son_senkron_zamani": baglanti.son_senkron_zamani,
        "son_senkron_hata": baglanti.son_senkron_hata,
        "senkron_bekliyor": bool(baglanti.senkron_bekliyor),
        "webhook_kaydi": baglanti.webhook_kaydi,
        "ozet": baglanti.son_ozet,
        "mock_mode": _mock_mu(),
        # Elle kayıt için eski belirteçli adres (imzasız); İKAS kurulumunda imzalı /api/ikas/webhook kaydedilir.
        "webhook_url": f"{settings.APP_URL}/api/ikas/webhook/order-created/{ikas_webhook_belirteci(baglanti.store_name)}",
    }


# Disa API cagrisi + DB yazimi yapar - en pahali endpoint, siki limit.
@router.post("/senkronize", dependencies=[Depends(org_hiz_siniri(5))])
def ikas_senkronize(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Faz 2 - saklı access_token ile siparişleri çeker, FinancialProfile'ı
    (yıllık ciro, sektör) otomatik doldurur. Elle giriş gerektirmez."""
    baglanti = db.query(IkasBaglanti).filter(IkasBaglanti.org_id == current_org.id).first()
    if baglanti is None or baglanti.baglanti_durumu != "bagli":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="İKAS mağazası bağlı değil - önce GET /api/ikas/baglan ile bağlanın.",
        )

    ozet, hata = _senkronize_et(db, baglanti)
    if ozet is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Sipariş verisi çekilemedi: {hata}")

    return {
        "yillik_ciro": ozet.yillik_ciro,
        "siparis_sayisi": ozet.siparis_sayisi,
        "en_cok_satan_urunler": [{"urun": u, "ciro": c} for u, c in ozet.en_cok_satan_urun_kategorileri],
        "doviz_toplamlari": ozet.doviz_toplamlari,
        "yurt_disi_siparis": ozet.yurt_disi_siparis,
        "yurt_disi_ulkeler": ozet.yurt_disi_ulkeler,
        "notlar": ozet.notlar,
    }


@router.delete("/baglanti", dependencies=[Depends(org_hiz_siniri(5))])
def ikas_baglantiyi_kes(current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Bağlantıyı keser: saklı erişim/yenileme belirteçleri ve mağaza özeti silinir (KVKK: amaç sona erdi).
    Profildeki ciro kullanıcının profil verisi olarak kalır. Uygulama İKAS panelinde kurulu kalırsa oradan da
    kaldırılmalıdır (İKAS'ın uygulama tarafından kaldırma API'si belgelenmemiş)."""
    silinen = db.query(IkasBaglanti).filter(IkasBaglanti.org_id == current_org.id).delete(synchronize_session=False)
    db.commit()
    return {"mesaj": "İKAS bağlantısı kaldırıldı. Uygulamayı İKAS panelinizdeki Uygulamalar bölümünden de kaldırın."
            if silinen else "Bağlı bir İKAS mağazası yok."}


@router.get("/panel", dependencies=[Depends(org_hiz_siniri(30))])
def ikas_gomulu_panel(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Faz 3 - İKAS admin paneline gömülecek ekran için tek çağrıda
    teşvik eşleşmesi + bütçe önerisini döner. Webhook'la ertelenmiş senkron varsa önce tamamlanır."""
    baglanti = db.query(IkasBaglanti).filter(IkasBaglanti.org_id == current_org.id).first()
    if baglanti is not None and baglanti.baglanti_durumu == "bagli" and baglanti.senkron_bekliyor:
        _senkronize_et(db, baglanti)

    profil = db.query(FinancialProfile).filter(FinancialProfile.org_id == current_org.id).first()
    if profil is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil yok - önce POST /api/ikas/senkronize çağrılmalı.",
        )

    eslesmeler = esles(profil, db)

    butce = None
    butce_hatasi = None
    try:
        butce = butce_hesapla(profil, db).__dict__
    except ValueError as e:
        butce_hatasi = str(e)

    return {
        "magaza": baglanti.store_name if baglanti else None,
        "son_senkron_zamani": baglanti.son_senkron_zamani if baglanti else None,
        "yillik_ciro": profil.yillik_ciro,
        "sektor": profil.sektor,
        "ozet": baglanti.son_ozet if baglanti else None,
        "eslesen_teşvikler": [
            {
                "id": e.tesvik.id,
                "kurum": e.tesvik.kurum,
                "baslik": e.tesvik.baslik,
                "skor": e.skor,
                "gerekce": e.gerekce,
            }
            for e in eslesmeler
        ] if eslesmeler else [],
        "butce_onerisi": butce,
        "butce_hatasi": butce_hatasi,
    }


# ------------------------------------------------------------------------------------------------- webhook'lar

@router.post("/webhook", dependencies=[Depends(ip_hiz_siniri(120, ad="ikas-webhook"))])
async def ikas_webhook(request: Request, arka_plan: BackgroundTasks, db: Session = Depends(get_db)):
    """İKAS'ın imzalı webhook'u (kurulumda saveWebhook ile kaydedilir). Gövde: {id, scope, merchantId,
    authorizedAppId, data (JSON metni), signature}; imza HMAC-SHA256(client_secret, data). İmza geçersizse 401.
    - store/order/created|updated: tam senkron arka planda; son senkron 10 dk'dan yeniyse ertelenir
      (senkron_bekliyor) ve panel açıldığında tamamlanır. Yanıt hemen döner.
    - store/app/deleted: belirteçler ve mağaza özeti silinir, bağlantı 'kaldirildi' olur."""
    try:
        govde = await request.json()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz gövde")
    if not isinstance(govde, dict) or not webhook_imzasi_dogrula(govde, uygulama_siri()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz webhook imzası")

    kapsam = govde.get("scope")
    sorgu = db.query(IkasBaglanti).filter(IkasBaglanti.org_id.isnot(None))
    baglanti = None
    if govde.get("authorizedAppId"):
        baglanti = sorgu.filter(IkasBaglanti.authorized_app_id == str(govde["authorizedAppId"])).first()
    if baglanti is None and govde.get("merchantId"):
        baglanti = sorgu.filter(IkasBaglanti.merchant_id == str(govde["merchantId"])).first()
    if baglanti is None:
        # İKAS'ın tekrar denemesini önlemek için 200: kurulum bizde yok (kaldırılmış olabilir).
        return {"durum": "yok_sayildi", "neden": "kurulum bulunamadı"}

    if kapsam == "store/app/deleted":
        baglanti.access_token = None
        baglanti.refresh_token = None
        baglanti.token_expires_at = None
        baglanti.son_ozet = None
        baglanti.baglanti_durumu = "kaldirildi"
        baglanti.senkron_bekliyor = False
        db.commit()
        return {"durum": "kaldirildi"}
    if kapsam in ("store/order/created", "store/order/updated"):
        if baglanti.baglanti_durumu != "bagli":
            return {"durum": "yok_sayildi", "neden": "bağlantı etkin değil"}
        son = _naif_utc(baglanti.son_senkron_zamani)
        if son is not None and son > _simdi() - timedelta(minutes=WEBHOOK_SENKRON_ARALIGI_DK):
            baglanti.senkron_bekliyor = True
            db.commit()
            return {"durum": "ertelendi"}
        arka_plan.add_task(_arka_plan_senkron, baglanti.id)
        return {"durum": "senkron_planlandi"}
    return {"durum": "yok_sayildi", "neden": f"kapsam işlenmiyor: {kapsam}"}


# Eski: imza yerine mağazaya özgü adres belirteci (bkz. ikas_webhook_belirteci); ayrıca IP başına oran sınırı.
@router.post("/webhook/order-created/{belirtec}", dependencies=[Depends(ip_hiz_siniri(60))])
def ikas_webhook_order_created(
    belirtec: str,
    payload: dict | None = None,
    db: Session = Depends(get_db),
):
    """Elle kaydedilmiş eski webhook adresi. Adresteki belirteçten bağlı mağaza bulunur ve senkron
    tetiklenir; geçersiz belirteç 401 döner. Yeni kurulumlar imzalı POST /api/ikas/webhook kullanır."""
    baglanti = None
    for b in db.query(IkasBaglanti).filter(IkasBaglanti.baglanti_durumu == "bagli").all():
        if hmac.compare_digest(belirtec, ikas_webhook_belirteci(b.store_name)):
            baglanti = b
            break
    if baglanti is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz webhook adresi")

    sonuc = siparisleri_getir(baglanti.store_name, baglanti.access_token)
    if sonuc.basarili:
        profili_ikas_verisiyle_guncelle(db, baglanti.org_id, sonuc.siparisler)
        baglanti.son_senkron_zamani = datetime.now(timezone.utc)
        baglanti.son_senkron_hata = None
    else:
        baglanti.son_senkron_hata = sonuc.hata
    db.commit()

    return {"status": "senkronize_edildi" if sonuc.basarili else "hata", "detay": sonuc.hata}
