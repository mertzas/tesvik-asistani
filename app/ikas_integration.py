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

2026-10-08: @ikas/api-client 2.0.2 kaynağı ve builders.ikas.com belgesiyle yeniden doğrulandı ve genişletildi:
  - İKAS panelinden açılış imzası (helpers/auth-helpers.js validateAuthSignature)
  - webhook imzası (helpers/webhook-helpers.js validateIkasWebhookSignature), WebhookScope (models/webhook)
  - me / getMerchant / saveWebhook sorguları, listOrder sayfalama (PaginationInput limit 1-200, page) ve
    orderedAt (DateFilterInput, Timestamp) süzgeci, Order.status (OrderStatusEnum), shippingAddress.country.iso2

MOCK MOD: Gerçek IKAS_CLIENT_ID/SECRET henüz yok - bunlar İKAS Builders
Dashboard'da uygulama kaydı yapılıp bir test mağazası atandıktan sonra
elde edilir (bkz. proje notları, Tesvik_Asistani_x_IKAS.pptx). O ana
kadar settings.IKAS_MOCK_MODE=True iken bu modül gerçek ağ çağrısı
YAPMAZ, gerçekçi sahte veri döner - böylece OAuth akışının ve veri
eşleme mantığının geri kalanı uçtan uca test edilebilir, gerçek
kimlik bilgisi geldiğinde sadece mock'u kapatmak yeterli olur.

    python -m app.ikas_integration --self-test      (ağ yok)
"""
import hashlib
import hmac
import random
import re
import secrets
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import requests

from app.models import settings

STORE_DOMAIN = ".myikas.com"
GRAPHQL_URL = "https://api.myikas.com/api/v2/admin/graphql"
REQUEST_TIMEOUT_SEC = 15
# @ikas/api-client 2.0.2 validateAuthSignature: imza en çok 120 sn eski olabilir.
IMZA_PENCERESI_SN = 120
SAYFA_LIMITI = 200          # PaginationInput.limit üst sınırı (SDK)
EN_COK_SAYFA = 50           # bir senkronda en çok 10.000 sipariş; büyük mağazada süreyi sınırlar
# Kurulumda kaydedilen webhook kapsamları (WebhookScope, SDK models/webhook).
WEBHOOK_KAPSAMLARI = ["store/order/created", "store/order/updated", "store/app/deleted"]
# Mock modda imzaları üretip doğrulamak için kullanılan anahtar (gerçek modda IKAS_CLIENT_SECRET).
_MOCK_SIR_ETIKETI = b"ikas-mock-app-secret"


def _mock_mu() -> bool:
    return settings.IKAS_MOCK_MODE or not settings.IKAS_CLIENT_ID


def uygulama_siri() -> str:
    """İmza anahtarı: İKAS uygulama sırrı (client secret). Mock modda SECRET_KEY'den türetilmiş yerel sır;
    böylece imzalı açılış ve webhook yolları gerçek kimlik bilgisi olmadan da uçtan uca denenebilir."""
    if not _mock_mu():
        return settings.IKAS_CLIENT_SECRET
    return hmac.new(settings.SECRET_KEY.encode(), _MOCK_SIR_ETIKETI, hashlib.sha256).hexdigest()


def giris_imzasi_uret(store_name: str, merchant_id: str, timestamp: str, secret: str) -> str:
    return hmac.new(secret.encode(), f"{store_name}{merchant_id}{timestamp}".encode(), hashlib.sha256).hexdigest()


def giris_imzasi_dogrula(store_name: str, merchant_id: str, timestamp: str, signature: str,
                         secret: str, simdi_ms: int | None = None) -> bool:
    """İKAS panelinden açılışta adrese eklenen imza (SDK validateAuthSignature ile birebir):
    hex(HMAC-SHA256(app_secret, storeName + merchantId + timestamp)), timestamp ms ve en çok 120 sn eski.
    SDK gelecekteki zaman damgasını sınırsız kabul ediyor; burada saat kayması için yalnızca 30 sn tolerans."""
    if not (secret and store_name and merchant_id and timestamp and signature):
        return False
    try:
        fark_sn = ((simdi_ms if simdi_ms is not None else int(time.time() * 1000)) - int(timestamp)) / 1000
    except ValueError:
        return False
    if not -30 <= fark_sn < IMZA_PENCERESI_SN:
        return False
    return hmac.compare_digest(giris_imzasi_uret(store_name, merchant_id, timestamp, secret), signature)


def webhook_imzasi_uret(veri: str, secret: str) -> str:
    return hmac.new(secret.encode(), veri.encode("utf-8"), hashlib.sha256).hexdigest()


def webhook_imzasi_dogrula(govde: dict, secret: str) -> bool:
    """İKAS webhook gövdesi {id, scope, merchantId, authorizedAppId, data(str), signature}; imza
    hex(HMAC-SHA256(client_secret, data)) (SDK validateIkasWebhookSignature)."""
    veri, imza = govde.get("data"), govde.get("signature")
    if not (secret and isinstance(veri, str) and isinstance(imza, str)):
        return False
    return hmac.compare_digest(webhook_imzasi_uret(veri, secret), imza)


def _graphql(access_token: str, sorgu: str, degiskenler: dict | None = None) -> tuple[dict | None, str | None]:
    """Tek GraphQL çağrısı: (data, hata)."""
    try:
        resp = requests.post(
            GRAPHQL_URL, json={"query": sorgu, "variables": degiskenler or {}},
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {access_token}",
                     "User-Agent": "tesvik-asistani-ikas-app"},
            timeout=REQUEST_TIMEOUT_SEC)
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        return None, str(e)
    if not resp.ok or data.get("errors"):
        return None, (data.get("errors") or [{}])[0].get("message", f"HTTP {resp.status_code}")
    return data.get("data") or {}, None


@dataclass
class MagazaBilgisi:
    authorized_app_id: str
    merchant_id: str | None = None
    eposta: str | None = None
    magaza_unvani: str | None = None
    il: str | None = None
    ulke_iso2: str | None = None


ME_QUERY = "query me { me { id email name } }"
MERCHANT_QUERY = ("query getMerchant { getMerchant { id email merchantName storeName "
                  "address { company title city { name } country { iso2 } } } }")
SAVE_WEBHOOK_MUTATION = ("mutation saveWebhook($input: WebhookInput!) { saveWebhook(input: $input) "
                         "{ id endpoint scope } }")


def magaza_bilgisi_getir(access_token: str, store_name: str) -> tuple[MagazaBilgisi | None, str | None]:
    """me (authorizedAppId) + getMerchant (e-posta, unvan, il). Mock modda sabit örnek döner."""
    if _mock_mu():
        return MagazaBilgisi(authorized_app_id=f"mock-app-{store_name}", merchant_id=f"mock-merchant-{store_name}",
                             eposta=f"{store_name}@example.com", magaza_unvani=f"{store_name} Ltd. Şti.",
                             il="İstanbul", ulke_iso2="TR"), None
    me, hata = _graphql(access_token, ME_QUERY)
    if hata or not ((me or {}).get("me") or {}).get("id"):
        return None, hata or "me sorgusu kimlik döndürmedi"
    merchant, hata2 = _graphql(access_token, MERCHANT_QUERY)
    m = (merchant or {}).get("getMerchant") or {}
    adres = m.get("address") or {}
    return MagazaBilgisi(
        authorized_app_id=me["me"]["id"], merchant_id=m.get("id"), eposta=m.get("email") or me["me"].get("email"),
        magaza_unvani=adres.get("title") or adres.get("company") or m.get("merchantName"),
        il=(adres.get("city") or {}).get("name"), ulke_iso2=(adres.get("country") or {}).get("iso2"),
    ), hata2


def webhook_kaydet(access_token: str, endpoint: str) -> tuple[bool, str | None]:
    """saveWebhook mutasyonu (SDK default-gqls). Uç nokta https olmalı (WebhookInput belgesi)."""
    if _mock_mu():
        return True, None
    if not endpoint.startswith("https://"):
        return False, "İKAS webhook adresi https olmalı (APP_URL https değil)"
    _, hata = _graphql(access_token, SAVE_WEBHOOK_MUTATION,
                       {"input": {"endpoint": endpoint, "scopes": WEBHOOK_KAPSAMLARI}})
    return hata is None, hata


def _oauth_base_url(store_name: str) -> str:
    """SDK kaynağı: OAuthAPI.getOAuthUrl() -> `https://${storeName}${STORE_DOMAIN}/api/admin/oauth`"""
    return f"https://{store_name}{STORE_DOMAIN}/api/admin/oauth"


def yeni_state() -> str:
    """CSRF korumasi icin rastgele state - orijinal ornekteki Math.random()
    yerine kriptografik olarak guvenli secrets.token_urlsafe kullanildi."""
    return secrets.token_urlsafe(24)


def magaza_adi_gecerli_mi(store_name: str | None) -> bool:
    """İKAS mağaza adı alt alan adıdır ({ad}.myikas.com). Adrese (authorize/token URL'i) girdiği için yalnızca
    küçük harf, rakam ve tire kabul edilir: "evil.com/x" gibi bir değerle istek başka bir ana bilgisayara gidemez."""
    return bool(store_name) and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", store_name) is not None


def authorize_url_olustur(store_name: str, client_id: str, redirect_uri: str, state: str) -> str:
    """Kullanıcının tarayıcısının yönlendirileceği İKAS yetkilendirme URL'i (parametreler kodlanmış)."""
    sorgu = urlencode({"client_id": client_id, "redirect_uri": redirect_uri, "scope": settings.IKAS_SCOPE,
                       "state": state}, quote_via=quote)
    return f"{_oauth_base_url(store_name)}/authorize?{sorgu}"


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


def _token_istegi(store_name: str, form: dict, eski_refresh: str | None = None) -> TokenSonucu:
    """POST {oauth}/token (x-www-form-urlencoded), SDK OAuthAPI ile aynı uç. Yanıt OAuthTokenResponse."""
    try:
        resp = requests.post(
            f"{_oauth_base_url(store_name)}/token",
            data={**form, "client_id": settings.IKAS_CLIENT_ID, "client_secret": settings.IKAS_CLIENT_SECRET},
            headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=REQUEST_TIMEOUT_SEC)
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        return TokenSonucu(basarili=False, hata=str(e))
    if not resp.ok or "access_token" not in data:
        return TokenSonucu(basarili=False,
                           hata=data.get("error_description") or data.get("error") or f"HTTP {resp.status_code}")
    return TokenSonucu(basarili=True, access_token=data["access_token"],
                       refresh_token=data.get("refresh_token") or eski_refresh,
                       expires_in=data.get("expires_in"), scope=data.get("scope"))


def kod_ile_token_al(store_name: str, code: str, redirect_uri: str) -> TokenSonucu:
    """Authorization code'u access/refresh token ile degistirir.
    IKAS_MOCK_MODE acikken (varsayilan, gercek client_id yokken) hicbir
    ag cagrisi yapmaz."""
    if _mock_mu():
        return _mock_token_sonucu()
    return _token_istegi(store_name, {"grant_type": "authorization_code", "code": code,
                                      "redirect_uri": redirect_uri})


def refresh_token_yenile(store_name: str, refresh_token: str) -> TokenSonucu:
    if _mock_mu():
        return _mock_token_sonucu()
    return _token_istegi(store_name, {"grant_type": "refresh_token", "refresh_token": refresh_token},
                         eski_refresh=refresh_token)


# GraphQL sorgusu - alan adları SDK'nın admin/generated/index.d.ts dosyasındaki Order ve QuerylistOrderArgs
# tiplerinden alınmıştır. orderedAt bir Timestamp'tir (ms); süzgeç sunucuda uygulanır, sayfalar hasNext'e göre gezilir.
LIST_ORDER_QUERY = """
query ListOrder($pagination: PaginationInput, $orderedAt: DateFilterInput) {
  listOrder(pagination: $pagination, orderedAt: $orderedAt) {
    data {
      id
      orderNumber
      orderedAt
      status
      orderPaymentStatus
      totalFinalPrice
      currencyCode
      shippingAddress { country { iso2 name } }
      orderLineItems {
        finalPrice
        quantity
        variant { name }
      }
    }
    count
    hasNext
    page
  }
}
"""


@dataclass
class SiparisSatiri:
    id: str
    orderNumber: str | None
    orderedAt: str | int | float | None   # İKAS: ms Timestamp; eski mock/testler ISO metin
    status: str | None
    orderPaymentStatus: str | None
    totalFinalPrice: float
    currencyCode: str
    urunler: list[dict]
    teslimat_ulkesi: str | None = None    # shippingAddress.country.iso2 (dijital üründe adres olmayabilir)


def _mock_siparisler(adet: int = 40, tohum: str = "mock") -> list[SiparisSatiri]:
    """Gercekci sahte siparis verisi - mock modda Faz 2 (veri esleme) ve
    Faz 3 (panel) mantigini test edebilmek icin. Gercek magaza verisiyle
    ayni sekil (fields) kullanir, boylece gercek API'ye gecis sadece
    IKAS_MOCK_MODE=False yapmayi gerektirir, mapping kodu degismez.
    Mağaza adına göre tohumlanır (aynı mağaza her senkronda aynı veriyi görür); örneklem bilerek iptal/iade,
    taslak, yurt dışı teslimat ve döviz cinsinden sipariş içerir ki eşleme kuralları mock'ta da sınansın."""
    r = random.Random(tohum)
    urun_havuzu = ["Kadın Elbise", "Erkek Tişört", "Sneaker", "Sırt Çantası", "Kulaklık"]
    simdi_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    siparisler = []
    for i in range(adet):
        tutar = round(r.uniform(150, 3500), 2)
        yurt_disi = i % 8 == 3           # ~%12,5 yurt dışı teslimat
        doviz = "EUR" if i % 16 == 3 else "TRY"
        durum = {5: "CANCELLED", 11: "REFUNDED", 17: "DRAFT"}.get(i, "CREATED")
        siparisler.append(SiparisSatiri(
            id=f"mock-order-{i}",
            orderNumber=str(1001 + i),
            orderedAt=simdi_ms - r.randint(0, 364) * 86_400_000,
            status=durum,
            orderPaymentStatus="PAID" if durum == "CREATED" else "REFUNDED" if durum == "REFUNDED" else "WAITING",
            totalFinalPrice=tutar,
            currencyCode=doviz,
            urunler=[{"productName": r.choice(urun_havuzu), "finalPrice": tutar, "quantity": 1}],
            teslimat_ulkesi=r.choice(["DE", "NL", "AZ", "US"]) if yurt_disi else "TR",
        ))
    return siparisler


@dataclass
class SiparisSonucu:
    basarili: bool
    siparisler: list[SiparisSatiri]
    hata: str | None = None
    kismi: bool = False   # EN_COK_SAYFA sınırına takıldı: daha eski siparişler okunmadı


def _satir(o: dict) -> SiparisSatiri:
    kalemler = [{"productName": ((k.get("variant") or {}).get("name") or "Diğer"),
                 "finalPrice": k.get("finalPrice") or 0.0, "quantity": k.get("quantity")}
                for k in (o.get("orderLineItems") or [])]
    ulke = (((o.get("shippingAddress") or {}).get("country")) or {}).get("iso2")
    return SiparisSatiri(id=o["id"], orderNumber=o.get("orderNumber"), orderedAt=o.get("orderedAt"),
                         status=o.get("status"), orderPaymentStatus=o.get("orderPaymentStatus"),
                         totalFinalPrice=o.get("totalFinalPrice") or 0.0, currencyCode=o.get("currencyCode") or "TRY",
                         urunler=kalemler, teslimat_ulkesi=ulke)


def siparisleri_getir(store_name: str, access_token: str, gun_sayisi: int = 365) -> SiparisSonucu:
    """Son `gun_sayisi` günün siparişlerini GraphQL Admin API'den sayfa sayfa çeker (limit 200, hasNext).
    Mock modda ağ çağrısı yapmaz, mağazaya özgü kararlı sahte veri döner."""
    if _mock_mu():
        return SiparisSonucu(basarili=True, siparisler=_mock_siparisler(tohum=store_name))

    esik_ms = int((datetime.now(timezone.utc) - timedelta(days=gun_sayisi)).timestamp() * 1000)
    siparisler: list[SiparisSatiri] = []
    for sayfa in range(1, EN_COK_SAYFA + 1):
        data, hata = _graphql(access_token, LIST_ORDER_QUERY,
                              {"pagination": {"limit": SAYFA_LIMITI, "page": sayfa}, "orderedAt": {"gte": esik_ms}})
        if hata:
            return SiparisSonucu(basarili=False, siparisler=[], hata=hata)
        liste = (data or {}).get("listOrder") or {}
        siparisler += [_satir(o) for o in (liste.get("data") or []) if o.get("id")]
        if not liste.get("hasNext"):
            return SiparisSonucu(basarili=True, siparisler=siparisler)
    return SiparisSonucu(basarili=True, siparisler=siparisler, kismi=True)


# ---------------------------------------------------------------------------------------------------- self-test

def _self_test() -> int:
    from unittest import mock
    sonuc: list[tuple[str, bool]] = []

    def kontrol(ad, kosul):
        sonuc.append((ad, bool(kosul)))

    sir, simdi = "uygulama-siri", 1_760_000_000_000
    ts = str(simdi - 5_000)
    imza = giris_imzasi_uret("magaza", "m-1", ts, sir)
    kontrol("giriş imzası doğru", giris_imzasi_dogrula("magaza", "m-1", ts, imza, sir, simdi_ms=simdi))
    kontrol("başka mağaza reddedilir", not giris_imzasi_dogrula("baska", "m-1", ts, imza, sir, simdi_ms=simdi))
    kontrol("120 sn'den eski reddedilir", not giris_imzasi_dogrula(
        "magaza", "m-1", str(simdi - 121_000), giris_imzasi_uret("magaza", "m-1", str(simdi - 121_000), sir),
        sir, simdi_ms=simdi))
    kontrol("boş sır reddedilir", not giris_imzasi_dogrula("magaza", "m-1", ts, imza, "", simdi_ms=simdi))
    govde = {"data": '{"id":"o-1"}', "signature": webhook_imzasi_uret('{"id":"o-1"}', sir)}
    kontrol("webhook imzası doğru", webhook_imzasi_dogrula(govde, sir))
    kontrol("değişmiş veri reddedilir", not webhook_imzasi_dogrula({**govde, "data": '{"id":"o-2"}'}, sir))
    kontrol("mağaza adı süzgeci", magaza_adi_gecerli_mi("benim-magazam")
            and not magaza_adi_gecerli_mi("evil.com/x") and not magaza_adi_gecerli_mi("-a"))
    url = authorize_url_olustur("magaza", "cid", "https://x.example/api/oauth/callback/ikas", "s t")
    kontrol("authorize adresi kodlanmış", url.startswith("https://magaza.myikas.com/api/admin/oauth/authorize?")
            and "redirect_uri=https%3A%2F%2Fx.example" in url and "state=s%20t" in url)

    # Gerçek mod sayfalama: 2 sayfa, ikinci istekte page=2 ve tarih süzgeci gider.
    istekler = []

    def sahte_post(url, json=None, **_k):
        istekler.append(json["variables"])
        sayfa = json["variables"]["pagination"]["page"]
        yanit = mock.Mock(ok=True)
        yanit.json.return_value = {"data": {"listOrder": {"hasNext": sayfa == 1, "data": [
            {"id": f"o{sayfa}", "orderedAt": 1, "status": "CREATED", "totalFinalPrice": 10.0, "currencyCode": "TRY",
             "shippingAddress": {"country": {"iso2": "DE"}},
             "orderLineItems": [{"finalPrice": 10.0, "quantity": 1, "variant": {"name": "Ürün"}}]}]}}}
        return yanit
    with mock.patch.object(settings, "IKAS_MOCK_MODE", False), mock.patch.object(settings, "IKAS_CLIENT_ID", "c"), \
            mock.patch("app.ikas_integration.requests.post", sahte_post):
        s = siparisleri_getir("magaza", "tok")
    kontrol("sayfalama hasNext'e göre durur", s.basarili and [x.id for x in s.siparisler] == ["o1", "o2"]
            and [i["pagination"]["page"] for i in istekler] == [1, 2] and "gte" in istekler[0]["orderedAt"])
    kontrol("ülke ve ürün adı ayrıştırılır", s.siparisler[0].teslimat_ulkesi == "DE"
            and s.siparisler[0].urunler[0]["productName"] == "Ürün")
    m1, m2 = _mock_siparisler(tohum="a"), _mock_siparisler(tohum="a")
    kontrol("mock veri kararlı ve geçerli durum kodlu", [x.totalFinalPrice for x in m1] == [x.totalFinalPrice for x in m2]
            and {x.status for x in m1} <= {"CREATED", "CANCELLED", "REFUNDED", "DRAFT"})

    for ad, ok in sonuc:
        print(("  ✓ " if ok else "  ✗ ") + ad)
    gecen = sum(ok for _, ok in sonuc)
    print(f"self-test: {gecen}/{len(sonuc)} geçti")
    return 0 if gecen == len(sonuc) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print("Kullanım: python -m app.ikas_integration --self-test")
