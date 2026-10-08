"""Güvenlik denetimi (Aşama 4, 2026-10-07): CORS, güvenlik başlıkları, kaba kuvvet sınırı,
parola politikası, legacy uç nokta, hata mesajı sızıntısı, SECRET_KEY nöbeti."""
import pytest

import app.main as m
from app.models import settings


def _hesap(client, email="g@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "GucluSifre123",
                                              "full_name": "G", "company_name": "G Ltd"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_guvenlik_basliklari_her_yanitta(client):
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in r.headers and "Permissions-Policy" in r.headers


def test_cors_yalnizca_izinli_origin(client):
    izinli = m.izinli_originler()[0]
    r = client.options("/api/kobi-sinifi", headers={"Origin": izinli, "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == izinli
    r = client.options("/api/kobi-sinifi", headers={"Origin": "https://kotu.example",
                                                    "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") is None


def test_izinli_originler_env_ile_kisitlanir(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://tesvik.example , https://www.tesvik.example/")
    assert m.izinli_originler() == ["https://tesvik.example", "https://www.tesvik.example"]
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "")
    assert "http://localhost:8000" in m.izinli_originler()


def test_login_kaba_kuvvet_siniri(client):
    _hesap(client)
    for _ in range(10):
        r = client.post("/api/auth/login", json={"email": "g@example.com", "password": "YanlisSifre1"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"email": "g@example.com", "password": "GucluSifre123"})
    assert r.status_code == 429 and "Retry-After" in r.headers


@pytest.mark.parametrize("sifre,sebep", [
    ("12345678", "rakam var harf yok"),
    ("sadeceharfler", "harf var rakam yok"),
    ("Kisa1", "8'den kısa"),
    ("a1" + "x" * 80, "72 bayttan uzun (bcrypt sınırı)"),
    (" Bosluk123 ", "baştaki/sondaki boşluk"),
])
def test_zayif_parola_reddedilir(client, sifre, sebep):
    r = client.post("/api/auth/signup", json={"email": "z@example.com", "password": sifre,
                                              "full_name": "Z", "company_name": "Z"})
    assert r.status_code == 422, sebep


def test_turkce_karakterli_parola_kabul(client):
    r = client.post("/api/auth/signup", json={"email": "t@example.com", "password": "Şifreİyi2026",
                                              "full_name": "T", "company_name": "T"})
    assert r.status_code == 200
    assert client.post("/api/auth/login", json={"email": "t@example.com", "password": "Şifreİyi2026"}).status_code == 200


def test_uzun_isim_reddedilir(client):
    r = client.post("/api/auth/signup", json={"email": "u@example.com", "password": "GucluSifre123",
                                              "full_name": "x" * 201, "company_name": "U"})
    assert r.status_code == 422


def test_legacy_sor_yok(client):
    assert client.post("/sor", json={"question": "KOSGEB"}).status_code in (404, 405)


def test_sor_ic_hata_metni_sizmaz(client, monkeypatch):
    def patlat(*a, **k):
        raise RuntimeError("sqlite3.OperationalError: no such table: gizli_tablo")

    monkeypatch.setattr(m, "answer", patlat)
    h = _hesap(client)
    r = client.post("/api/sor", json={"question": "KOSGEB desteği"}, headers=h)
    assert r.status_code == 500
    assert "gizli_tablo" not in r.text and r.json()["detail"] == m.GENEL_HATA


def test_sor_akis_ic_hata_metni_sizmaz(client, monkeypatch):
    def bozuk(*a, **k):
        yield "kayitlar", []
        raise RuntimeError("Traceback gizli yol C:/srv/app")

    monkeypatch.setattr(m, "answer_akis", bozuk)
    h = _hesap(client)
    r = client.post("/api/sor/akis", json={"question": "KOSGEB desteği"}, headers=h)
    assert "gizli yol" not in r.text and m.GENEL_HATA in r.text


def test_secret_key_nobeti(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", m.VARSAYILAN_SECRET_KEY)
    monkeypatch.setattr(settings, "ALLOW_INSECURE_SECRET", False)
    with pytest.raises(RuntimeError):
        m.secret_key_kontrolu()
    monkeypatch.setattr(settings, "ALLOW_INSECURE_SECRET", True)
    m.secret_key_kontrolu()  # uyarıyla geçer
    monkeypatch.setattr(settings, "SECRET_KEY", "k" * 31)
    monkeypatch.setattr(settings, "ALLOW_INSECURE_SECRET", False)
    with pytest.raises(RuntimeError):
        m.secret_key_kontrolu()
    monkeypatch.setattr(settings, "SECRET_KEY", "k" * 32)
    m.secret_key_kontrolu()


def test_html_sayfalara_csp_gelir_api_ve_docs_haric(client):
    for yol in ("/", "/dashboard", "/kvkk"):
        r = client.get(yol)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("text/html"):
            csp = r.headers["Content-Security-Policy"]
            # İKAS paneline gömülen sayfalar yalnızca İKAS kökeninden çerçevelenebilir (tests/test_ikas_uygulama.py).
            cerceve = "frame-ancestors 'self' https://*.myikas.com" if yol in ("/", "/dashboard") \
                else "frame-ancestors 'none'"
            assert cerceve in csp and "object-src 'none'" in csp
            assert "base-uri 'self'" in csp and "connect-src 'self'" in csp
    assert "Content-Security-Policy" not in client.get("/health").headers
    d = client.get("/docs")
    assert "Content-Security-Policy" not in d.headers, "Swagger CDN'den script yükler"


def test_csp_dis_script_kaynagi_yok():
    """Tailwind CDN kaldırıldı (önceden derlenmiş CSS); ayrıntılı denetim tests/test_csp.py'de."""
    from app.main import CSP
    script = [x for x in CSP.split("; ") if x.startswith("script-src")][0]
    assert script == "script-src 'self'"
