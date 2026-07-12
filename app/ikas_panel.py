"""
İKAS Admin App entegrasyon router'ı - Faz 1 (OAuth bağlantı), Faz 2
(otomatik veri eşleme) ve Faz 3'ün (gömülü panel + webhook bildirimi)
API yüzeyi.

Faz 1 akışı:
  1. GET /api/ikas/baglan?storeName=X  (bizim JWT ile auth'lu kullanıcı çağırır)
     -> IkasBaglanti satırı "beklemede" durumunda oluşturulur, authorize_url döner
  2. Tarayıcı authorize_url'e gider, mağaza sahibi İKAS'ta onaylar
  3. İKAS, GET /api/oauth/callback/ikas?code=...&state=...&storeName=... çağırır
     (bu adımda bizim JWT'imiz YOK - state ile eşleştirme yapılır)
  4. Callback, code'u token ile değiştirir, IkasBaglanti "bagli" olur

Faz 2: POST /api/ikas/senkronize - saklı token ile siparişleri çeker,
FinancialProfile'ı otomatik doldurur (elle giriş yok).

Faz 3: GET /api/ikas/panel - teşvik eşleşmesi + bütçe önerisini tek
çağrıda döner (İKAS admin paneline gömülecek iframe/ekran için).
POST /api/ikas/webhook/order-created - yeni sipariş geldiğinde İKAS'ın
çağıracağı webhook, otomatik yeniden senkronizasyonu tetikler.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.models import Organization, IkasBaglanti, get_db, settings
from app.auth import get_current_org
from app.ikas_integration import (
    authorize_url_olustur, yeni_state, kod_ile_token_al, siparisleri_getir,
)
from app.ikas_veri_esleme import profili_ikas_verisiyle_guncelle
from app.matching import esles
from app.budget import hesapla as butce_hesapla
from app.models import FinancialProfile

router = APIRouter(prefix="/api/ikas", tags=["ikas-entegrasyon"])


def _redirect_uri() -> str:
    return f"{settings.APP_URL}/api/oauth/callback/ikas"


@router.get("/baglan")
def ikas_baglan(
    storeName: str = Query(..., description="İKAS mağaza alt alan adı (ör. 'benim-magazam')"),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Faz 1 - adım 1: bağlantıyı başlatır, tarayıcının gideceği authorize URL'ini döner."""
    state = yeni_state()

    baglanti = db.query(IkasBaglanti).filter(IkasBaglanti.org_id == current_org.id).first()
    if baglanti is None:
        baglanti = IkasBaglanti(org_id=current_org.id)
        db.add(baglanti)

    baglanti.store_name = storeName
    baglanti.oauth_state = state
    baglanti.baglanti_durumu = "beklemede"
    db.commit()

    url = authorize_url_olustur(
        store_name=storeName,
        client_id=settings.IKAS_CLIENT_ID or "MOCK_CLIENT_ID",
        redirect_uri=_redirect_uri(),
        state=state,
    )
    return {
        "authorize_url": url,
        "mock_mode": settings.IKAS_MOCK_MODE or not settings.IKAS_CLIENT_ID,
        "not": (
            "IKAS_CLIENT_ID henüz tanımlı değil - bu URL gerçek İKAS'a "
            "yönlendirilirse çalışmaz. Gerçek bağlantı için İKAS Builders "
            "Dashboard'da uygulama kaydı ve test mağazası ataması gerekir."
            if not settings.IKAS_CLIENT_ID else None
        ),
    }


@router.get("/callback-oauth")
def ikas_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    storeName: str = Query(None),
    db: Session = Depends(get_db),
):
    """Faz 1 - adım 2: İKAS'ın çağıracağı callback. JWT auth YOK - eşleştirme
    'state' üzerinden yapılır (adım 1'de saklanan CSRF token'ı).

    NOT: Gerçek İKAS route yolu 'api/oauth/callback/ikas' olmalı (SDK
    örneklerinde bu şekilde) - burada çakışmayı önlemek için
    '/api/ikas/callback-oauth' kullanıldı, gerçek İKAS kaydında
    redirect_uri bu path'e göre ayarlanmalı."""
    baglanti = db.query(IkasBaglanti).filter(IkasBaglanti.oauth_state == state).first()
    if baglanti is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz veya süresi dolmuş state - bağlantıyı tekrar başlatın.")

    if storeName and storeName != baglanti.store_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mağaza adı uyuşmuyor.")

    sonuc = kod_ile_token_al(baglanti.store_name, code, _redirect_uri())
    if not sonuc.basarili:
        baglanti.baglanti_durumu = "hata"
        baglanti.son_senkron_hata = sonuc.hata
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Token alınamadı: {sonuc.hata}")

    baglanti.access_token = sonuc.access_token
    baglanti.refresh_token = sonuc.refresh_token
    baglanti.scope = sonuc.scope
    baglanti.token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=sonuc.expires_in)
        if sonuc.expires_in else None
    )
    baglanti.baglanti_durumu = "bagli"
    baglanti.oauth_state = None  # tek kullanımlık - kullanıldıktan sonra temizlenir
    db.commit()

    return {"status": "bagli", "store_name": baglanti.store_name}


@router.get("/durum")
def ikas_baglanti_durumu(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    baglanti = db.query(IkasBaglanti).filter(IkasBaglanti.org_id == current_org.id).first()
    if baglanti is None:
        return {"baglanti_durumu": "bagli_degil"}
    return {
        "baglanti_durumu": baglanti.baglanti_durumu,
        "store_name": baglanti.store_name,
        "son_senkron_zamani": baglanti.son_senkron_zamani,
        "son_senkron_hata": baglanti.son_senkron_hata,
    }


@router.post("/senkronize")
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

    sonuc = siparisleri_getir(baglanti.store_name, baglanti.access_token)
    if not sonuc.basarili:
        baglanti.son_senkron_hata = sonuc.hata
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Sipariş verisi çekilemedi: {sonuc.hata}")

    ozet = profili_ikas_verisiyle_guncelle(db, current_org.id, sonuc.siparisler)

    baglanti.son_senkron_zamani = datetime.now(timezone.utc)
    baglanti.son_senkron_hata = None
    db.commit()

    return {
        "yillik_ciro": ozet.yillik_ciro,
        "siparis_sayisi": ozet.siparis_sayisi,
        "en_cok_satan_urunler": [{"urun": u, "ciro": c} for u, c in ozet.en_cok_satan_urun_kategorileri],
        "notlar": ozet.notlar,
    }


@router.get("/panel")
def ikas_gomulu_panel(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Faz 3 - İKAS admin paneline gömülecek ekran için tek çağrıda
    teşvik eşleşmesi + bütçe önerisini döner."""
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

    baglanti = db.query(IkasBaglanti).filter(IkasBaglanti.org_id == current_org.id).first()

    return {
        "magaza": baglanti.store_name if baglanti else None,
        "son_senkron_zamani": baglanti.son_senkron_zamani if baglanti else None,
        "yillik_ciro": profil.yillik_ciro,
        "sektor": profil.sektor,
        "eslesen_teşvikler": [
            {
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


@router.post("/webhook/order-created")
def ikas_webhook_order_created(
    payload: dict,
    db: Session = Depends(get_db),
):
    """Faz 3 - İKAS'ın yeni sipariş oluştuğunda çağıracağı webhook.
    storeName ile ilgili org'u bulup otomatik yeniden senkronizasyon
    tetikler - kullanıcı elle 'yenile' demeden ciro güncel kalır.

    NOT: Bu bir İSKELET'tir - gerçek İKAS webhook imza doğrulaması
    (HMAC vb.) İKAS'ın webhook dokümantasyonunda tanımlanan yönteme göre
    eklenmeli, burada henüz uygulanmadı (gerçek webhook secret'ı olmadan
    doğrulanamaz)."""
    store_name = payload.get("storeName") or payload.get("merchantId")
    if not store_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="storeName eksik")

    baglanti = db.query(IkasBaglanti).filter(IkasBaglanti.store_name == store_name).first()
    if baglanti is None or baglanti.baglanti_durumu != "bagli":
        return {"status": "ignored", "reason": "magaza bagli degil"}

    sonuc = siparisleri_getir(baglanti.store_name, baglanti.access_token)
    if sonuc.basarili:
        profili_ikas_verisiyle_guncelle(db, baglanti.org_id, sonuc.siparisler)
        baglanti.son_senkron_zamani = datetime.now(timezone.utc)
        baglanti.son_senkron_hata = None
    else:
        baglanti.son_senkron_hata = sonuc.hata
    db.commit()

    return {"status": "senkronize_edildi" if sonuc.basarili else "hata", "detay": sonuc.hata}
