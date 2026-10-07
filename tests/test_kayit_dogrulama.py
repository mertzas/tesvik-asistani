"""Doğrulama zorunlu kayıt (KAYIT_EPOSTA_DOGRULAMA_ZORUNLU): e-posta numaralandırma yok, hesabın önceden ele
geçirilmesine karşı etkinleştirmede parola, doğrulanmamış hesap giriş yapamaz (2026-10-08)."""
import pytest

from app.email import EmailService
from app.models import User, settings

GONDERILEN = []


@pytest.fixture(autouse=True)
def eposta_yakala(monkeypatch):
    GONDERILEN.clear()
    monkeypatch.setattr(EmailService, "send_verification_email",
                        lambda self, e, n, b: GONDERILEN.append(("dogrulama", e, b)) or True)
    monkeypatch.setattr(EmailService, "send_password_reset_email",
                        lambda self, e, n, b: GONDERILEN.append(("sifirlama", e, b)) or True)
    monkeypatch.setattr(EmailService, "send_existing_account_email",
                        lambda self, e, n, g, s: GONDERILEN.append(("mevcut", e, s)) or True)


@pytest.fixture
def zorunlu(monkeypatch):
    monkeypatch.setattr(settings, "KAYIT_EPOSTA_DOGRULAMA_ZORUNLU", True)


def _belirtec(tur="dogrulama"):
    return [g for g in GONDERILEN if g[0] == tur][-1][2].split("#t=", 1)[1]


def _giris(client, email, parola):
    return client.post("/api/auth/login", json={"email": email, "password": parola})


def test_kayit_yaniti_hesap_var_yok_ayni(client, zorunlu, test_org_data):
    yeni = client.post("/api/auth/signup", json=test_org_data)
    tekrar = client.post("/api/auth/signup", json={**test_org_data, "password": "baskaParola9",
                                                   "full_name": "Saldırgan"})
    assert yeni.status_code == tekrar.status_code == 202
    assert yeni.json() == tekrar.json(), "yanıt hesabın varlığını sızdırmamalı"
    assert "access_token" not in yeni.json()
    turler = [g[:2] for g in GONDERILEN]
    assert turler == [("dogrulama", test_org_data["email"]), ("mevcut", test_org_data["email"])]


def test_mevcut_adrese_kayit_hesabi_degistirmez(client, db_session, zorunlu, test_org_data):
    client.post("/api/auth/signup", json=test_org_data)
    ozet = db_session.query(User).filter(User.email == test_org_data["email"]).one().hashed_password
    client.post("/api/auth/signup", json={**test_org_data, "password": "baskaParola9", "full_name": "X"})
    db_session.expire_all()
    u = db_session.query(User).filter(User.email == test_org_data["email"]).one()
    assert u.hashed_password == ozet and u.full_name == test_org_data["full_name"]
    assert db_session.query(User).count() == 1


def test_mevcut_hesap_bildirimi_saatte_3(client, zorunlu, test_org_data):
    client.post("/api/auth/signup", json=test_org_data)
    for _ in range(5):
        assert client.post("/api/auth/signup", json=test_org_data).status_code == 202
    assert len([g for g in GONDERILEN if g[0] == "mevcut"]) == 3


def test_dogrulanmamis_hesap_giremez_ve_baglanti_yeniden_gider(client, zorunlu, test_org_data):
    client.post("/api/auth/signup", json=test_org_data)
    GONDERILEN.clear()
    r = _giris(client, test_org_data["email"], test_org_data["password"])
    assert r.status_code == 403 and "doğrulanmadı" in r.json()["detail"]
    assert [g[:2] for g in GONDERILEN] == [("dogrulama", test_org_data["email"])]
    # yanlış parolada bağlantı gönderilmez ve 401 döner (hesap durumu sızmaz)
    GONDERILEN.clear()
    assert _giris(client, test_org_data["email"], "yanlisParola9").status_code == 401
    assert GONDERILEN == []


def test_etkinlestirme_parola_ister_ve_oturum_acar(client, zorunlu, test_org_data):
    client.post("/api/auth/signup", json=test_org_data)
    tok = _belirtec()
    assert client.post("/api/auth/eposta-dogrula", json={"token": tok}).status_code == 428
    yanlis = client.post("/api/auth/eposta-dogrula", json={"token": tok, "password": "yanlisParola9"})
    assert yanlis.status_code == 400 and "Şifremi unuttum" in yanlis.json()["detail"]
    # yanlış parola belirteci yakmadı: doğru parolayla aynı bağlantı çalışır
    r = client.post("/api/auth/eposta-dogrula", json={"token": tok, "password": test_org_data["password"]})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["email_dogrulandi"] is True
    assert _giris(client, test_org_data["email"], test_org_data["password"]).status_code == 200


def test_onceden_ele_gecirme_engellenir(client, zorunlu, test_org_data):
    """Saldırgan kurbanın adresiyle kendi parolasıyla kayıt açar; doğrulama postası kurbana gider. Kurban kendi
    parolasıyla etkinleştiremez, saldırgan bağlantıyı göremez; kurban sıfırlamayla hesabı alır."""
    saldirgan = {**test_org_data, "password": "saldirganParola9"}
    client.post("/api/auth/signup", json=saldirgan)
    tok = _belirtec()
    kurban = client.post("/api/auth/eposta-dogrula", json={"token": tok, "password": test_org_data["password"]})
    assert kurban.status_code == 400
    assert _giris(client, saldirgan["email"], saldirgan["password"]).status_code == 403, "doğrulanmadı"
    client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]})
    assert client.post("/api/auth/sifre-sifirla", json={"token": _belirtec("sifirlama"),
                                                        "new_password": "kurbanYeni9"}).status_code == 200
    assert _giris(client, test_org_data["email"], "kurbanYeni9").status_code == 200
    assert _giris(client, saldirgan["email"], saldirgan["password"]).status_code == 401


def test_kapaliyken_eski_akis(client, test_org_data):
    assert settings.KAYIT_EPOSTA_DOGRULAMA_ZORUNLU is False, "varsayılan kapalı (SMTP kurulana kadar)"
    r = client.post("/api/auth/signup", json=test_org_data)
    assert r.status_code == 200 and r.json()["access_token"]
    assert client.post("/api/auth/signup", json=test_org_data).status_code == 400
    assert client.post("/api/auth/eposta-dogrula", json={"token": _belirtec()}).status_code == 200


def test_giriste_kayitsiz_adres_de_bcrypt_calistirir(client, monkeypatch):
    """Zamanlama sızıntısı: kayıtlı olmayan adreste de parola karşılaştırması yapılır."""
    from app import main
    cagrilar = []
    gercek = main.verify_password
    monkeypatch.setattr(main, "verify_password", lambda p, h: cagrilar.append(h) or gercek(p, h))
    assert _giris(client, "yok@example.com", "herhangiParola9").status_code == 401
    assert cagrilar == [main._SAHTE_PAROLA_OZETI]


def test_mevcut_hesap_postasi_icerik(monkeypatch):
    monkeypatch.undo()
    giden = []
    monkeypatch.setattr(EmailService, "send_email",
                        lambda self, to, konu, govde, html=None: giden.append((to, konu, govde, html)) or True)
    assert EmailService().send_existing_account_email("a@b.com", "<i>Ad</i>", "https://x/", "https://x/sifre-sifirla")
    to, konu, govde, html = giden[0]
    assert "zaten" in konu and "https://x/sifre-sifirla" in govde and "değişiklik yapılmadı" in govde
    assert "&lt;i&gt;Ad" in html
