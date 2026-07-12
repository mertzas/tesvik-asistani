"""
İKAS Admin App entegrasyonu - OAuth2 Authorization Code Flow + Admin GraphQL
API ile mağaza verisinin (sipariş/ciro) salt-okunur çekilmesi.

KAYNAK DOĞRULAMASI: Bu modüldeki her URL/alan adı, @ikas/admin-api-client
npm paketinin (sürüm 2.1.0) derlenmiş kaynak kodundan ve kendi unit
testlerinden (dist/test/api/oauth.test.js, dist/api/oauth/index.js,
dist/api/admin/v2/generated/index.d.ts) 2026-07-12'de tek tek okunarak
doğrulanmıştır - resmi ikas.dev dokümantasyonu authorize taban URL'ini
açıkça vermediği için SDK'nın kendi derlenmiş kodu esas alındı. Hiçbir
endpoint/alan adı tahmin edilmedi.

MOCK MOD: Gerçek IKAS_CLIENT_ID/SECRET henüz yok - bunlar İKAS Builders
Dashboard'da uygulama kaydı yapılıp bir test mağazası atandıktan sonra
elde edilir (bkz. proje notları, Tesvik_Asistani_x_IKAS.pptx). O ana
kadar settings.IKAS_MOCK_MODE=True iken bu modül gerçek ağ çağrısı
YAPMAZ, gerçekçi sahte veri döner - böylece OAuth akışının ve veri
eşleme mantığının geri kalanı uçtan uca test edilebilir, gerçek
kimlik bilgisi geldiğinde sadece mock'u kapatmak yeterli olur.
"""
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

from app.models import settings

STORE_DOMAIN = ".myikas.com"
GRAPHQL_URL = "https://api.myikas.com/api/v2/admin/graphql"
REQUEST_TIMEOUT_SEC = 15


def _oauth_base_url(store_name: str) -> str:
    """SDK kaynağı: OAuthAPI.getOAuthUrl() -> `https://${storeName}${STORE_DOMAIN}/api/admin/oauth`"""
    return f"https://{store_name}{STORE_DOMAIN}/api/admin/oauth"


def yeni_state() -> str:
    """CSRF korumasi icin rastgele state - orijinal ornekteki Math.random()
    yerine kriptografik olarak guvenli secrets.token_urlsafe kullanildi."""
    return secrets.token_urlsafe(24)


def authorize_url_olustur(store_name: str, client_id: str, redirect_uri: str, state: str) -> str:
    """Kullanıcının tarayıcısının yönlendirileceği İKAS yetkilendirme URL'i."""
    base = _oauth_base_url(store_name)
    params = (
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={settings.IKAS_SCOPE.replace(' ', '%20')}"
        f"&state={state}"
    )
    return f"{base}/authorize{params}"


@dataclass
class TokenSonucu:
    basarili: bool
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    scope: str | None = None
    hata: str | None = None


def _mock_token_sonucu() -> TokenSonucu:
    return TokenSonucu(
        basarili=True,
        access_token="mock-access-token-" + secrets.token_hex(8),
        refresh_token="mock-refresh-token-" + secrets.token_hex(8),
        expires_in=14400,  # 4 saat - SDK testlerinde gozlenen deger
        scope=settings.IKAS_SCOPE,
    )


def kod_ile_token_al(store_name: str, code: str, redirect_uri: str) -> TokenSonucu:
    """Authorization code'u access/refresh token ile degistirir.
    IKAS_MOCK_MODE acikken (varsayilan, gercek client_id yokken) hicbir
    ag cagrisi yapmaz."""
    if settings.IKAS_MOCK_MODE or not settings.IKAS_CLIENT_ID:
        return _mock_token_sonucu()

    url = f"{_oauth_base_url(store_name)}/token"
    try:
        resp = requests.post(
            url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.IKAS_CLIENT_ID,
                "client_secret": settings.IKAS_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=REQUEST_TIMEOUT_SEC,
        )
        data = resp.json()
        if not resp.ok or "access_token" not in data:
            return TokenSonucu(basarili=False, hata=data.get("error_description") or data.get("error") or f"HTTP {resp.status_code}")
        return TokenSonucu(
            basarili=True,
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_in=data.get("expires_in"),
            scope=data.get("scope"),
        )
    except (requests.RequestException, ValueError) as e:
        return TokenSonucu(basarili=False, hata=str(e))


def refresh_token_yenile(store_name: str, refresh_token: str) -> TokenSonucu:
    if settings.IKAS_MOCK_MODE or not settings.IKAS_CLIENT_ID:
        return _mock_token_sonucu()

    url = f"{_oauth_base_url(store_name)}/token"
    try:
        resp = requests.post(
            url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.IKAS_CLIENT_ID,
                "client_secret": settings.IKAS_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=REQUEST_TIMEOUT_SEC,
        )
        data = resp.json()
        if not resp.ok or "access_token" not in data:
            return TokenSonucu(basarili=False, hata=data.get("error_description") or f"HTTP {resp.status_code}")
        return TokenSonucu(
            basarili=True,
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            expires_in=data.get("expires_in"),
            scope=data.get("scope"),
        )
    except (requests.RequestException, ValueError) as e:
        return TokenSonucu(basarili=False, hata=str(e))


# GraphQL sorgusu - alan adlari SDK'nin admin/v2/generated/index.d.ts
# dosyasindaki gercek `Order` tipinden alinmistir (orderedAt, totalFinalPrice,
# status, orderLineItems, orderPaymentStatus).
LIST_ORDER_QUERY = """
query ListOrder($pagination: PaginationInput) {
  listOrder(pagination: $pagination) {
    data {
      id
      orderNumber
      orderedAt
      status
      orderPaymentStatus
      totalFinalPrice
      currencyCode
      orderLineItems {
        productName
        finalPrice
        quantity
      }
    }
    count
    hasNext
  }
}
"""


@dataclass
class SiparisSatiri:
    id: str
    orderNumber: str | None
    orderedAt: str | None
    status: str | None
    orderPaymentStatus: str | None
    totalFinalPrice: float
    currencyCode: str
    urunler: list[dict]


def _mock_siparisler(adet: int = 40) -> list[SiparisSatiri]:
    """Gercekci sahte siparis verisi - mock modda Faz 2 (veri esleme) ve
    Faz 3 (panel) mantigini test edebilmek icin. Gercek magaza verisiyle
    ayni sekil (fields) kullanir, boylece gercek API'ye gecis sadece
    IKAS_MOCK_MODE=False yapmayi gerektirir, mapping kodu degismez."""
    import random
    urun_havuzu = ["Kadın Elbise", "Erkek Tişört", "Sneaker", "Sırt Çantası", "Kulaklık"]
    simdi = datetime.now(timezone.utc)
    siparisler = []
    for i in range(adet):
        gun_once = random.randint(0, 365)
        tutar = round(random.uniform(150, 3500), 2)
        siparisler.append(SiparisSatiri(
            id=f"mock-order-{i}",
            orderNumber=str(1001 + i),
            orderedAt=(simdi - timedelta(days=gun_once)).isoformat(),
            status="Confirmed",
            orderPaymentStatus="PAID",
            totalFinalPrice=tutar,
            currencyCode="TRY",
            urunler=[{"productName": random.choice(urun_havuzu), "finalPrice": tutar, "quantity": 1}],
        ))
    return siparisler


@dataclass
class SiparisSonucu:
    basarili: bool
    siparisler: list[SiparisSatiri]
    hata: str | None = None


def siparisleri_getir(store_name: str, access_token: str, sayfa_boyutu: int = 100) -> SiparisSonucu:
    """Magazanin siparislerini GraphQL Admin API'den ceker. Mock modda
    gercek ag cagrisi yapmaz, gercekci sahte veri doner."""
    if settings.IKAS_MOCK_MODE or not settings.IKAS_CLIENT_ID:
        return SiparisSonucu(basarili=True, siparisler=_mock_siparisler())

    try:
        resp = requests.post(
            GRAPHQL_URL,
            json={
                "query": LIST_ORDER_QUERY,
                "variables": {"pagination": {"limit": sayfa_boyutu}},
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "tesvik-asistani-ikas-app",
            },
            timeout=REQUEST_TIMEOUT_SEC,
        )
        data = resp.json()
        if not resp.ok or "errors" in data:
            hata = data.get("errors", [{}])[0].get("message", f"HTTP {resp.status_code}")
            return SiparisSonucu(basarili=False, siparisler=[], hata=hata)

        ham = data.get("data", {}).get("listOrder", {}).get("data", [])
        siparisler = [
            SiparisSatiri(
                id=o["id"],
                orderNumber=o.get("orderNumber"),
                orderedAt=o.get("orderedAt"),
                status=o.get("status"),
                orderPaymentStatus=o.get("orderPaymentStatus"),
                totalFinalPrice=o.get("totalFinalPrice", 0.0),
                currencyCode=o.get("currencyCode", "TRY"),
                urunler=o.get("orderLineItems", []),
            )
            for o in ham
        ]
        return SiparisSonucu(basarili=True, siparisler=siparisler)
    except (requests.RequestException, ValueError) as e:
        return SiparisSonucu(basarili=False, siparisler=[], hata=str(e))
