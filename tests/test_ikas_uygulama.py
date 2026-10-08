"""İKAS App Store uyumu (2026-10-08): kurulum (Senaryo A), uygulamadan bağlanma (Senaryo B), imzalı açılış,
imzalı webhook, token yenileme, bağlantı kesme, çerçeveleme başlıkları, sipariş eşleme kuralları.
Hepsi mock modda (IKAS_CLIENT_ID boş): ağ çağrısı yok; imzalar mock sırıyla üretilir."""
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from app import ikas_integration, ikas_panel
from app.ikas_integration import (SiparisSatiri, TokenSonucu, giris_imzasi_uret, uygulama_siri,
                                  webhook_imzasi_uret)
from app.ikas_veri_esleme import baglam_alanlari, siparislerden_ozet_cikar
from app.models import FinancialProfile, IkasBaglanti, Organization, settings

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def mock_mod(monkeypatch):
    monkeypatch.setattr(settings, "IKAS_MOCK_MODE", True)
    monkeypatch.setattr(settings, "IKAS_CLIENT_ID", "")


def _kur(client, store="demo"):
    """Senaryo A: kurulum adresi -> İKAS authorize (taklit) -> callback. Callback yanıtını döner."""
    r = client.get(f"/api/oauth/authorize/ikas?storeName={store}", follow_redirects=False)
    assert r.status_code == 302, r.text
    hedef = urlparse(r.headers["location"])
    assert hedef.netloc == f"{store}.myikas.com" and hedef.path == "/api/admin/oauth/authorize"
    q = parse_qs(hedef.query)
    assert q["redirect_uri"] == [f"{settings.APP_URL}/api/oauth/callback/ikas"]
    return client.get(f"/api/oauth/callback/ikas?code=kod&state={q['state'][0]}&storeName={store}",
                      follow_redirects=False)


def _acilis_parametreleri(yanit) -> dict:
    hedef = urlparse(yanit.headers["location"])
    assert hedef.path == "/ikas"
    return {k: v[0] for k, v in parse_qs(hedef.query).items()}


def _imzali_webhook(client, govde_ek: dict, veri: dict | None = None, imza: str | None = None):
    data = json.dumps(veri or {"id": "o-1"})
    govde = {"id": "w-1", "data": data, "signature": imza or webhook_imzasi_uret(data, uygulama_siri()), **govde_ek}
    return client.post("/api/ikas/webhook", json=govde)


# ------------------------------------------------------------------------------------------------ kurulum

def test_kurulum_hesap_acar_senkronlar_ve_imzali_acilisla_giris_yapilir(client, db_session):
    r = _kur(client)
    assert r.status_code == 302, r.text
    p = _acilis_parametreleri(r)
    assert p["storeName"] == "demo" and p["authorizedAppId"] == "mock-app-demo"

    org = db_session.query(Organization).one()
    assert org.name == "demo Ltd. Şti." and org.email == "demo@example.com"
    b = db_session.query(IkasBaglanti).one()
    assert (b.org_id, b.baglanti_durumu, b.merchant_id, b.webhook_kaydi) == (org.id, "bagli", "mock-merchant-demo",
                                                                             "kayitli")
    assert b.oauth_state is None
    # Arka plan senkronu (TestClient yanıt sonrası çalıştırır): profil ve özet dolu, yurt dışı -> ihracat hedefi.
    assert b.son_ozet["siparis_sayisi"] > 0 and b.son_ozet["yurt_disi_siparis"] > 0 and b.senkron_bekliyor is False
    profil = db_session.query(FinancialProfile).one()
    assert profil.yillik_ciro == b.son_ozet["yillik_ciro"] > 0 and profil.bolge == "İstanbul"
    assert "ihracat" in profil.hedefler and profil.sektor == "e-ticaret"

    r2 = client.post("/api/ikas/oturum", json=p)
    assert r2.status_code == 200, r2.text
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r2.json()['access_token']}"})
    assert me.json()["email"] == "demo@example.com"


def test_kurulum_cerezsiz_tamamlanamaz(client, db_session):
    r = client.get("/api/oauth/authorize/ikas?storeName=demo", follow_redirects=False)
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    client.cookies.clear()
    r2 = client.get(f"/api/oauth/callback/ikas?code=k&state={state}", follow_redirects=False)
    assert r2.status_code == 400 and "tarayıcıda" in r2.json()["detail"]
    assert db_session.query(Organization).count() == 0


@pytest.mark.parametrize("ad", ["evil.com", "a/b", "-x", "BÜYÜK", ""])
def test_gecersiz_magaza_adi_reddedilir(client, ad):
    assert client.get(f"/api/oauth/authorize/ikas?storeName={ad}", follow_redirects=False).status_code in (400, 422)


def test_yeniden_kurulum_ayni_hesaba_doner(client, db_session):
    _kur(client)
    _kur(client)
    assert db_session.query(Organization).count() == 1 and db_session.query(IkasBaglanti).count() == 1


def test_eposta_baska_hesaptaysa_baglanmaz_ayri_hesap_acilir(client, db_session):
    client.post("/api/auth/signup", json={"email": "demo@example.com", "password": "Parola123", "full_name": "A",
                                          "company_name": "Mevcut"})
    _kur(client)
    mevcut = db_session.query(Organization).filter(Organization.name == "Mevcut").one()
    assert db_session.query(IkasBaglanti).filter(IkasBaglanti.org_id == mevcut.id).count() == 0
    yeni = db_session.query(IkasBaglanti).one()
    assert db_session.get(Organization, yeni.org_id).email == "ikas-demo@magaza.ikas.invalid"


def test_suresi_gecmis_state_reddedilir(client, db_session):
    r = client.get("/api/oauth/authorize/ikas?storeName=demo", follow_redirects=False)
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    b = db_session.query(IkasBaglanti).one()
    b.updated_at = datetime.now(timezone.utc) - timedelta(minutes=ikas_panel.STATE_OMRU_DK + 1)
    db_session.commit()
    r2 = client.get(f"/api/oauth/callback/ikas?code=k&state={state}", follow_redirects=False)
    assert r2.status_code == 400 and "süresi" in r2.json()["detail"]


def test_uygulamadan_baglanma_mevcut_kurulusa_baglar(client, db_session, test_user_token):
    h = {"Authorization": f"Bearer {test_user_token}"}
    r = client.get("/api/ikas/baglan?storeName=Benim-Magazam", headers=h)
    assert r.status_code == 200
    state = parse_qs(urlparse(r.json()["authorize_url"]).query)["state"][0]
    # Eski callback yolu da çalışır (geriye dönük); çerez gerekmez çünkü kayıt bir kuruluşa bağlı.
    client.cookies.clear()
    r2 = client.get(f"/api/ikas/callback-oauth?code=k&state={state}", follow_redirects=False)
    assert r2.status_code == 302
    assert db_session.query(Organization).count() == 1
    durum = client.get("/api/ikas/durum", headers=h).json()
    assert durum["baglanti_durumu"] == "bagli" and durum["store_name"] == "benim-magazam"
    assert durum["ozet"]["siparis_sayisi"] > 0


# ------------------------------------------------------------------------------------------- imzalı açılış

def test_oturum_imza_ve_kurulum_denetimi(client, db_session):
    p = _acilis_parametreleri(_kur(client))
    assert client.post("/api/ikas/oturum", json={**p, "signature": "0" * 64}).status_code == 401
    eski = str(int(time.time() * 1000) - 121_000)
    imza = giris_imzasi_uret("demo", p["merchantId"], eski, uygulama_siri())
    assert client.post("/api/ikas/oturum", json={**p, "timestamp": eski, "signature": imza}).status_code == 401
    assert client.post("/api/ikas/oturum", json={**p, "authorizedAppId": "baska"}).status_code == 404
    # Başka mağazanın geçerli imzası bu kuruluşa giriş açmaz.
    ts = str(int(time.time() * 1000))
    yabanci = {"storeName": "baska", "merchantId": p["merchantId"], "authorizedAppId": p["authorizedAppId"],
               "timestamp": ts, "signature": giris_imzasi_uret("baska", p["merchantId"], ts, uygulama_siri())}
    assert client.post("/api/ikas/oturum", json=yabanci).status_code == 404


# ------------------------------------------------------------------------------------------------- webhook

def test_webhook_imzasiz_ve_yanlis_imzali_reddedilir(client, db_session):
    _kur(client)
    assert _imzali_webhook(client, {"scope": "store/order/created", "authorizedAppId": "mock-app-demo"},
                           imza="f" * 64).status_code == 401
    assert client.post("/api/ikas/webhook", json={"scope": "store/order/created"}).status_code == 401


def test_webhook_siparis_yakin_senkronda_ertelenir_panel_tamamlar(client, db_session):
    _kur(client)
    r = _imzali_webhook(client, {"scope": "store/order/created", "authorizedAppId": "mock-app-demo"})
    assert r.json() == {"durum": "ertelendi"}
    db_session.expire_all()
    b = db_session.query(IkasBaglanti).one()
    assert b.senkron_bekliyor is True
    tok = client.post("/api/ikas/oturum", json=_acilis_parametreleri(_kur(client))).json()["access_token"]
    db_session.query(IkasBaglanti).update({"senkron_bekliyor": True})
    db_session.commit()
    assert client.get("/api/ikas/panel", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    db_session.expire_all()
    assert db_session.query(IkasBaglanti).one().senkron_bekliyor is False


def test_webhook_eski_senkronda_arka_planda_senkronlar(client, db_session):
    _kur(client)
    b = db_session.query(IkasBaglanti).one()
    b.son_senkron_zamani = datetime.now(timezone.utc) - timedelta(hours=1)
    b.son_ozet = None
    db_session.commit()
    r = _imzali_webhook(client, {"scope": "store/order/updated", "merchantId": "mock-merchant-demo"})
    assert r.json() == {"durum": "senkron_planlandi"}
    db_session.expire_all()
    assert db_session.query(IkasBaglanti).one().son_ozet["siparis_sayisi"] > 0


def test_webhook_uygulama_kaldirildi_belirtecleri_siler(client, db_session):
    _kur(client)
    r = _imzali_webhook(client, {"scope": "store/app/deleted", "authorizedAppId": "mock-app-demo"})
    assert r.json() == {"durum": "kaldirildi"}
    db_session.expire_all()
    b = db_session.query(IkasBaglanti).one()
    assert (b.access_token, b.refresh_token, b.son_ozet, b.baglanti_durumu) == (None, None, None, "kaldirildi")
    # Kaldırılmış kurulumla panelden açılış artık giriş vermez.
    ts = str(int(time.time() * 1000))
    p = {"storeName": "demo", "merchantId": "mock-merchant-demo", "authorizedAppId": "mock-app-demo",
         "timestamp": ts, "signature": giris_imzasi_uret("demo", "mock-merchant-demo", ts, uygulama_siri())}
    assert client.post("/api/ikas/oturum", json=p).status_code == 404


def test_webhook_bilinmeyen_kurulum_200_yok_sayilir(client):
    r = _imzali_webhook(client, {"scope": "store/order/created", "authorizedAppId": "yok"})
    assert r.status_code == 200 and r.json()["durum"] == "yok_sayildi"


# ------------------------------------------------------------------------------------- token / bağlantı kesme

def _oturumlu_kurulum(client):
    return {"Authorization": "Bearer " + client.post("/api/ikas/oturum",
                                                      json=_acilis_parametreleri(_kur(client))).json()["access_token"]}


def test_suresi_dolan_token_senkrondan_once_yenilenir(client, db_session, monkeypatch):
    h = _oturumlu_kurulum(client)
    b = db_session.query(IkasBaglanti).one()
    b.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    db_session.commit()
    cagri = []
    monkeypatch.setattr(ikas_panel, "refresh_token_yenile", lambda s, rt: cagri.append((s, rt)) or TokenSonucu(
        basarili=True, access_token="yeni-erisim", refresh_token="yeni-yenileme", expires_in=14400))
    assert client.post("/api/ikas/senkronize", headers=h).status_code == 200
    db_session.expire_all()
    b = db_session.query(IkasBaglanti).one()
    assert cagri and b.access_token == "yeni-erisim" and b.refresh_token == "yeni-yenileme"


def test_yenileme_basarisizsa_baglanti_hata_olur(client, db_session, monkeypatch):
    h = _oturumlu_kurulum(client)
    db_session.query(IkasBaglanti).update({"token_expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)})
    db_session.commit()
    monkeypatch.setattr(ikas_panel, "refresh_token_yenile",
                        lambda s, rt: TokenSonucu(basarili=False, hata="invalid_grant"))
    r = client.post("/api/ikas/senkronize", headers=h)
    assert r.status_code == 502 and "invalid_grant" in r.json()["detail"]
    db_session.expire_all()
    assert db_session.query(IkasBaglanti).one().baglanti_durumu == "hata"


def test_baglanti_kesme_belirtecleri_siler(client, db_session):
    h = _oturumlu_kurulum(client)
    r = client.delete("/api/ikas/baglanti", headers=h)
    assert r.status_code == 200 and "Uygulamalar" in r.json()["mesaj"]
    assert db_session.query(IkasBaglanti).count() == 0
    assert client.get("/api/ikas/durum", headers=h).json()["baglanti_durumu"] == "bagli_degil"


# ------------------------------------------------------------------------------------------- çerçeveleme

def test_yalnizca_gomulu_sayfalar_ikas_tarafindan_cercevelenebilir(client):
    for yol in ("/ikas", "/dashboard", "/"):
        r = client.get(yol)
        assert "frame-ancestors 'self' https://*.myikas.com" in r.headers["content-security-policy"], yol
        assert "x-frame-options" not in r.headers, yol
    r = client.get("/kvkk")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"


def test_cerceve_kaynagi_bossa_hicbir_sayfa_cercevelenmez(client, monkeypatch):
    monkeypatch.setattr(settings, "IKAS_CERCEVE_KAYNAKLARI", "")
    r = client.get("/dashboard")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"] and r.headers["x-frame-options"] == "DENY"


def test_ikas_sayfasi_satir_ici_betik_icermez():
    html = (KOK / "app/static/ikas.html").read_text(encoding="utf-8")
    assert '<script src="/static/js/ikas.js"></script>' in html and "<script>" not in html


# ------------------------------------------------------------------------------------------- veri eşleme

def _s(i, durum="CREATED", para="TRY", ulke="TR", tutar=100.0, gun=10):
    ms = int((datetime.now(timezone.utc) - timedelta(days=gun)).timestamp() * 1000)
    return SiparisSatiri(id=str(i), orderNumber=str(i), orderedAt=ms, status=durum, orderPaymentStatus="PAID",
                         totalFinalPrice=tutar, currencyCode=para, urunler=[{"productName": "x", "finalPrice": tutar}],
                         teslimat_ulkesi=ulke)


def test_eslemede_iptal_durumu_status_alanindan_dovizi_ayri_yurt_disini_sayar():
    ozet = siparislerden_ozet_cikar([
        _s(1), _s(2, durum="CANCELLED"), _s(3, durum="REFUNDED"), _s(4, durum="DRAFT"),
        _s(5, para="EUR", ulke="DE", tutar=50), _s(6, ulke="NL", tutar=200), _s(7, gun=400),
        _s(8, durum="PARTIALLY_REFUNDED", tutar=30),
    ])
    assert ozet.yillik_ciro == 330.0 and ozet.siparis_sayisi == 4 and ozet.haric_tutulan == 3
    assert ozet.doviz_toplamlari == {"EUR": 50.0}
    assert (ozet.yurt_disi_siparis, ozet.yurt_disi_ulkeler, ozet.yurt_disi_ciro_try) == (2, ["DE", "NL"], 200.0)
    notlar = " ".join(ozet.notlar)
    assert "3 iptal" in notlar and "kısmi" in notlar and "50,00 EUR" in notlar and "ETGB" in notlar
    g = ozet.gostergeler()
    assert g["yurt_disi_oran"] == 0.5 and json.dumps(g)  # JSON'a yazılabilir


def test_eski_iso_tarihli_siparis_de_okunur():
    s = _s(1)
    s.orderedAt = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    assert siparislerden_ozet_cikar([s]).siparis_sayisi == 1


def test_baglam_alanlari_yalnizca_toplamlar():
    assert baglam_alanlari(None) == {} and baglam_alanlari({"siparis_sayisi": 0}) == {}
    alanlar = baglam_alanlari(siparislerden_ozet_cikar([_s(1), _s(2, ulke="DE", para="EUR", tutar=9)]).gostergeler())
    metin = " ".join(alanlar.values())
    assert "2 satış siparişi" in metin and "DE" in metin and "9,00 EUR" in metin


def test_taslak_istemi_ikas_ozetini_icerir(client, db_session, monkeypatch):
    from app import basvuru_taslagi
    from app.models import PlanType, Tesvik
    istemler = []
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(basvuru_taslagi, "_claude_istek",
                        lambda s, k: istemler.append(k) or ("## 1. İşletme tanıtımı\nx", {"durma": "end_turn"}))
    h = _oturumlu_kurulum(client)
    org = db_session.query(Organization).one()
    org.plan, org.ai_yurtdisi_riza = PlanType.PRO, True
    db_session.add(Tesvik(id=7, kurum="Ticaret Bakanlığı", baslik="E-ihracat", ozet="o", detay="d", aktif_mi=True,
                          kaynak_url="https://t/7"))
    db_session.commit()
    assert client.post("/api/basvuru-listesi/7/taslak?yontem=yapay_zeka", headers=h).status_code == 200
    assert "e-ticaret satışları (İKAS mağaza verisi, son 12 ay)" in istemler[0]
    assert "yurt dışına teslim edilen siparişler (İKAS)" in istemler[0]
    assert "demo@example.com" not in istemler[0], "e-posta modele gitmemeli"
    # Varsayılan yapay zekâsız şablon da İKAS toplamlarını kaynağıyla taslağa yazar (ve modele gitmez).
    taslak = client.post("/api/basvuru-listesi/7/taslak", headers=h).json()["taslak"]
    assert len(istemler) == 1 and "E-ticaret mağaza kayıtlarına göre" in taslak
    assert "yurt dışına teslim edilen siparişler (İKAS)" in taslak and "demo@example.com" not in taslak


# ------------------------------------------------------------------------------------------- göç / self-test

def test_goc_ikas_sutunlari(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect
    from app import models
    db_yolu = tmp_path / "t.db"
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db_yolu}")
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "migrations"))
    motor = create_engine(f"sqlite:///{db_yolu}")
    command.upgrade(cfg, "head")
    sutunlar = {c["name"] for c in inspect(motor).get_columns("ikas_baglanti")}
    assert {"authorized_app_id", "merchant_id", "son_ozet", "senkron_bekliyor", "webhook_kaydi"} <= sutunlar
    command.downgrade(cfg, "j7e9a1b3c789")
    assert "merchant_id" not in {c["name"] for c in inspect(motor).get_columns("ikas_baglanti")}
    command.upgrade(cfg, "head")


def test_self_test_bayragi():
    import re
    r = subprocess.run([sys.executable, "-m", "app.ikas_integration", "--self-test"], cwd=KOK,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"self-test: (\d+)/(\d+) geçti", r.stdout)
    assert r.returncode == 0 and m and m.group(1) == m.group(2) and int(m.group(2)) >= 11


# --------------------------------------------------------------------------- Next.js kabuğu (AppBridge) uyumu

def _appbridge(client, belirtec, onek="JWT "):
    return client.post("/api/ikas/appbridge-oturum", headers={"Authorization": onek + belirtec})


def test_appbridge_belirteci_oturum_acar(client):
    _kur(client)
    from app.ikas_integration import appbridge_belirteci_uret
    r = _appbridge(client, appbridge_belirteci_uret("mock-merchant-demo", "mock-app-demo", uygulama_siri()))
    assert r.status_code == 200, r.text
    assert r.json()["store_name"] == "demo"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == "demo@example.com"


def test_appbridge_gecersiz_belirtecler_reddedilir(client, db_session):
    _kur(client)
    from app.ikas_integration import appbridge_belirteci_uret
    sir = uygulama_siri()
    assert _appbridge(client, appbridge_belirteci_uret("mock-merchant-demo", "mock-app-demo",
                                                       "baska-sir-0123456789abcdef0123456")).status_code == 401
    assert _appbridge(client, appbridge_belirteci_uret("mock-merchant-demo", "mock-app-demo", sir,
                                                       omur_sn=-5)).status_code == 401
    assert _appbridge(client, appbridge_belirteci_uret("mock-merchant-demo", "mock-app-demo", sir),
                      onek="Bearer ").status_code == 401
    assert client.post("/api/ikas/appbridge-oturum").status_code == 401
    # Başka mağazanın kimliği ya da kurulum kimliği eşleşmezse giriş yok.
    assert _appbridge(client, appbridge_belirteci_uret("baska-merchant", "mock-app-demo", sir)).status_code == 404
    assert _appbridge(client, appbridge_belirteci_uret("mock-merchant-demo", "yok", sir)).status_code == 404
    _imzali_webhook(client, {"scope": "store/app/deleted", "authorizedAppId": "mock-app-demo"})
    assert _appbridge(client, appbridge_belirteci_uret("mock-merchant-demo", "mock-app-demo", sir)).status_code == 404


def test_callback_kod_imzasi_varsa_dogrulanir(client, db_session):
    import hashlib
    import hmac
    for imza, beklenen in (("0" * 64, 400), (hmac.new(uygulama_siri().encode(), b"kod", hashlib.sha256).hexdigest(), 302)):
        client.cookies.clear()
        r = client.get("/api/oauth/authorize/ikas?storeName=demo", follow_redirects=False)
        state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
        r2 = client.get(f"/api/oauth/callback/ikas?code=kod&state={state}&signature={imza}", follow_redirects=False)
        assert r2.status_code == beklenen, r2.text


def test_uygulama_adresi_ayri_alan_adinda_olabilir(client, monkeypatch):
    monkeypatch.setattr(settings, "IKAS_UYGULAMA_URL", "https://ikas.tesvik.example/")
    r = client.get("/api/oauth/authorize/ikas?storeName=demo", follow_redirects=False)
    assert parse_qs(urlparse(r.headers["location"]).query)["redirect_uri"] == [
        "https://ikas.tesvik.example/api/oauth/callback/ikas"]
    assert ikas_panel._webhook_adresi() == "https://ikas.tesvik.example/api/ikas/webhook"


def test_yenileme_api_alanina_gider(monkeypatch):
    from unittest import mock
    monkeypatch.setattr(settings, "IKAS_MOCK_MODE", False)
    monkeypatch.setattr(settings, "IKAS_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "IKAS_CLIENT_SECRET", "sir")
    yanit = mock.Mock(ok=True)
    yanit.json.return_value = {"access_token": "a", "refresh_token": "r", "expires_in": 14400}
    with mock.patch("app.ikas_integration.requests.post", return_value=yanit) as post:
        assert ikas_integration.refresh_token_yenile("demo", "eski").basarili
    assert post.call_args.args[0] == "https://api.myikas.com/api/admin/oauth/token"


def test_canli_adreste_mock_mod_uyarisi(monkeypatch):
    from app import main
    monkeypatch.setattr(settings, "APP_URL", "https://tesvik.example")
    assert main.ikas_mod_uyarisi() is True
    monkeypatch.setattr(settings, "APP_URL", "http://localhost:8000")
    assert main.ikas_mod_uyarisi() is False


def test_mock_sir_gercek_modda_kullanilmaz(monkeypatch):
    monkeypatch.setattr(settings, "IKAS_MOCK_MODE", False)
    monkeypatch.setattr(settings, "IKAS_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "IKAS_CLIENT_SECRET", "gercek-sir")
    assert ikas_integration.uygulama_siri() == "gercek-sir"
