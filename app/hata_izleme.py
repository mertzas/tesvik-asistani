"""Harici hata izleme (Sentry) — isteğe bağlı, SENTRY_DSN boşsa hiçbir şey yapmaz (2026-10-08).

Kişisel veri: istek gövdesi (parola, profil), çerezler ve Authorization başlığı ASLA gönderilmez; kullanıcı IP'si
gönderilmez (send_default_pii=False). Sentry ABD/AB bölgesinde barınır: KVKK açısından yurt dışı aktarım olduğu için
AB bölgesi (de.sentry.io) veya kendi barındırılan kurulum tercih edilmeli ve aydınlatma metnine eklenmeli.

Destek kimliği: app.main beklenmeyen_hata işleyicisinin kullanıcıya gösterdiği 12 haneli kimlik, olaya
"hata_kimligi" etiketi olarak eklenir; destek talebindeki kimlik Sentry'de doğrudan aranır.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
_ETKIN = False
_GIZLI_BASLIKLAR = {"authorization", "cookie", "x-ikas-token"}


def _temizle(olay: dict, _ipucu: dict | None = None) -> dict:
    """before_send: istek gövdesini, çerezleri ve kimlik başlıklarını olaydan siler."""
    istek = olay.get("request") or {}
    istek.pop("data", None)
    istek.pop("cookies", None)
    if isinstance(istek.get("headers"), dict):
        istek["headers"] = {k: ("[silindi]" if k.lower() in _GIZLI_BASLIKLAR else v)
                            for k, v in istek["headers"].items()}
    if istek.get("query_string"):
        istek["query_string"] = "[silindi]"  # belirteç/e-posta sorgu dizesinde taşınabilir
    return olay


def kur(dsn: str | None, ortam: str = "production", transport=None) -> bool:
    """DSN varsa Sentry'yi başlatır ve True döner; yoksa (ya da paket kurulu değilse) False."""
    global _ETKIN
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logger.warning("SENTRY_DSN tanımlı ama sentry-sdk kurulu değil; hata izleme kapalı")
        return False
    # Otomatik entegrasyonlar KAPALI: hatalar yalnızca bildir() ile (app.main işleyicilerinden, destek kimliğiyle)
    # gider. Açık olsaydı logging entegrasyonu her logger.error'u ikinci kez olay yapar, Starlette/FastAPI
    # entegrasyonu da istek gövdesini eklemeye çalışırdı.
    secenek = dict(dsn=dsn, environment=ortam, send_default_pii=False, max_request_body_size="never",
                   traces_sample_rate=0.0, before_send=_temizle,
                   default_integrations=False, auto_enabling_integrations=False,
                   # Yığın çerçevelerinin yerel değişkenleri GÖNDERİLMEZ: giriş/kayıt çerçevesinde parola, profil
                   # çerçevesinde ciro gibi değerler yerel değişkendir (test bunu yakaladı, 2026-10-08).
                   include_local_variables=False)
    if transport is not None:
        secenek["transport"] = transport
    sentry_sdk.init(**secenek)
    _ETKIN = True
    logger.info("Hata izleme açık (Sentry, ortam=%s)", ortam)
    return True


def bildir(hata: BaseException, kimlik: str) -> None:
    """Yakalanan hatayı destek kimliğiyle Sentry'ye gönderir (kapalıysa hiçbir şey yapmaz)."""
    if not _ETKIN:
        return
    import sentry_sdk
    with sentry_sdk.new_scope() as kapsam:
        kapsam.set_tag("hata_kimligi", kimlik)
        sentry_sdk.capture_exception(hata)


def etkin_mi() -> bool:
    return _ETKIN
