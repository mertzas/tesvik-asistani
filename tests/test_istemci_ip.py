"""
IP basina hiz sinirinda istemci adresi (app/rate_limit.py istemci_ip).

Uretimde istekler nginx kapsayicisindan gelir. Onceden request.client.host dogrudan anahtar
yapiliyordu: her ziyaretci nginx'in IP'sini paylasti, login 10/dk TUM kullanicilar icin ortak
sayaca dustu (tek saldirgan herkesi kilitleyebiliyordu). Duzeltme: vekil basliklari yalnizca
dogrudan bagli taraf TRUSTED_PROXIES icindeyse okunur; aksi halde istemcinin yazdigi
X-Forwarded-For yok sayilir.
"""
import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from starlette.requests import Request
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.main import app
from app.models import settings
from app.rate_limit import istemci_ip, sayac

NGINX = "10.231.57.10"
KOK = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _temiz(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "")
    sayac.temizle()
    yield
    sayac.temizle()


def _istek(es: str | None, basliklar: list[tuple[str, str]] = ()) -> Request:
    scope = {
        "type": "http", "method": "GET", "path": "/", "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in basliklar],
        "client": (es, 40000) if es is not None else None,
    }
    return Request(scope)


# --- birim: guvenilmeyen dogrudan taraf -----------------------------------------------------

def test_varsayilan_hicbir_vekile_guvenmez_basliklar_yok_sayilir():
    r = _istek(NGINX, [("X-Forwarded-For", "1.2.3.4"), ("X-Real-IP", "1.2.3.4")])
    assert istemci_ip(r) == NGINX


def test_guvenilmeyen_taraf_sahte_xff_ile_sayac_degistiremez(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", NGINX)
    r = _istek("203.0.113.9", [("X-Forwarded-For", "1.2.3.4"), ("X-Real-IP", "5.6.7.8")])
    assert istemci_ip(r) == "203.0.113.9"


def test_client_yoksa_bilinmiyor():
    assert istemci_ip(_istek(None)) == "bilinmiyor"


# --- birim: guvenilir vekil -------------------------------------------------------------------

def test_guvenilir_vekilde_xff_sondaki_adres_alinir(monkeypatch):
    """nginx $proxy_add_x_forwarded_for istemcinin yazdiginin SONUNA gercek adresi ekler."""
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", NGINX)
    r = _istek(NGINX, [("X-Forwarded-For", "6.6.6.6, 198.51.100.7")])
    assert istemci_ip(r) == "198.51.100.7"


def test_guvenilir_zincir_sagdan_atlanir(monkeypatch):
    """Ondeki baska bir guvenilir vekil (orn. yuk dengeleyici) atlanir, ilk guvenilmeyen alinir."""
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", f"{NGINX}, 10.0.0.0/8")
    r = _istek(NGINX, [("X-Forwarded-For", "6.6.6.6, 198.51.100.7, 10.1.2.3")])
    assert istemci_ip(r) == "198.51.100.7"


def test_birden_cok_xff_basligi_birlestirilir(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", NGINX)
    r = _istek(NGINX, [("X-Forwarded-For", "6.6.6.6"), ("X-Forwarded-For", "198.51.100.7")])
    assert istemci_ip(r) == "198.51.100.7"


def test_xff_yoksa_x_real_ip(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", NGINX)
    assert istemci_ip(_istek(NGINX, [("X-Real-IP", "198.51.100.7")])) == "198.51.100.7"


def test_bozuk_xff_girdisinde_soldakine_guvenilmez_x_real_ip_kullanilir(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", NGINX)
    r = _istek(NGINX, [("X-Forwarded-For", "6.6.6.6, bozuk<>"), ("X-Real-IP", "198.51.100.7")])
    assert istemci_ip(r) == "198.51.100.7"


def test_baslik_hic_yoksa_vekilin_kendi_adresi(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", NGINX)
    assert istemci_ip(_istek(NGINX)) == NGINX


def test_cidr_ve_ipv6_eslemeli_vekil(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "10.231.57.0/24")
    r = _istek("::ffff:10.231.57.10", [("X-Forwarded-For", "2001:db8::1")])
    assert istemci_ip(r) == "2001:db8::1"


def test_gecersiz_ve_yildiz_girdisi_guven_vermez(monkeypatch):
    """'*' ve bozuk girdiler yok sayilir: hepsine guvenmek sahte XFF'yi kabul etmek demek."""
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "*, nginx, 10.231.57.999")
    r = _istek(NGINX, [("X-Forwarded-For", "1.2.3.4")])
    assert istemci_ip(r) == NGINX


# --- uctan uca: /api/auth/login (10/dk) -------------------------------------------------------
# Bos govde 422 doner (bcrypt calismaz, hizli); hiz siniri bagimliligi govdeden once calisir.

def _login(c: TestClient, xff: str | None = None) -> int:
    h = {"X-Forwarded-For": xff} if xff else {}
    return c.post("/api/auth/login", json={}, headers=h).status_code


def test_nginx_arkasinda_her_istemcinin_kendi_sayaci_var(monkeypatch):
    """Saldirgan kendi sayacini doldurur; baska istemci girisi etkilenmez (onceki hata: herkes 429)."""
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", NGINX)
    c = TestClient(app, client=(NGINX, 40000))
    saldirgan = [_login(c, "198.51.100.66") for _ in range(11)]
    assert saldirgan[:10] == [422] * 10 and saldirgan[10] == 429
    assert _login(c, "198.51.100.7") == 422


def test_istemci_xff_yazarak_kendi_limitini_asamaz(monkeypatch):
    """nginx istemcinin XFF'sine gercek adresi ekler; soldaki sahte adresi degistirmek sayac acmaz."""
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", NGINX)
    c = TestClient(app, client=(NGINX, 40000))
    kodlar = [_login(c, f"10.9.9.{i}, 198.51.100.66") for i in range(11)]
    assert kodlar[-1] == 429


def test_dogrudan_baglanan_sahte_xff_ile_limiti_asamaz(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", NGINX)
    c = TestClient(app, client=("203.0.113.9", 40000))
    kodlar = [_login(c, f"198.51.100.{i}") for i in range(11)]
    assert kodlar[-1] == 429


# --- uretim zinciri: uvicorn ProxyHeadersMiddleware + uygulama ayni ayarla ----------------------

def test_uvicorn_vekil_katmaniyla_birlikte_tutarli(monkeypatch):
    """Dockerfile.prod'da uvicorn --forwarded-allow-ips ile client'i once kendisi duzeltir; uygulama
    katmani bundan sonra gercek istemciyi gorur ve baslik okumaz. Sonuc ayni anahtar olmali."""
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", NGINX)
    sarili = ProxyHeadersMiddleware(app, trusted_hosts=NGINX)

    nginx_arkasi = TestClient(sarili, client=(NGINX, 40000))
    assert [_login(nginx_arkasi, "6.6.6.6, 198.51.100.66") for _ in range(11)][-1] == 429
    assert _login(nginx_arkasi, "198.51.100.7") == 422

    dogrudan = TestClient(sarili, client=("203.0.113.9", 40000))
    assert [_login(dogrudan, f"198.51.100.{i}") for i in range(11)][-1] == 429


# --- yapilandirma: compose / Dockerfile ayni adrese guvenmeli ---------------------------------

def test_compose_yalniz_nginx_ipsine_guvenir_ve_web_disariya_kapali():
    d = yaml.safe_load((KOK / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    web, nginx = d["services"]["web"], d["services"]["nginx"]
    assert "ports" not in web, "web host'a acilirsa sahte XFF dogrudan ulasabilir"
    assert web["environment"]["TRUSTED_PROXIES"] == nginx["networks"]["default"]["ipv4_address"]
    alt_ag = d["networks"]["default"]["ipam"]["config"][0]["subnet"]
    import ipaddress
    varsayilan = lambda s: s.split(":-", 1)[1].rstrip("}")  # noqa: E731
    assert ipaddress.ip_address(varsayilan(nginx["networks"]["default"]["ipv4_address"])) in \
        ipaddress.ip_network(varsayilan(alt_ag))


def test_dockerfile_uvicorn_ayni_degiskenle_vekil_basligina_guvenir():
    satir = next(s for s in (KOK / "Dockerfile.prod").read_text(encoding="utf-8").splitlines()
                 if s.startswith("CMD "))
    komut = json.loads(satir[4:])[2]
    assert "--proxy-headers" in komut
    assert '--forwarded-allow-ips "${TRUSTED_PROXIES:-127.0.0.1}"' in komut
