"""Parola sıfırlama ve e-posta doğrulama (Denetim 2 / Aşama E)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.email import EmailService
from app.models import HesapBelirteci, User

GONDERILEN = []


@pytest.fixture(autouse=True)
def eposta_yakala(monkeypatch):
    """SMTP'ye gitmez; gönderilecek (tür, alıcı, bağlantı) üçlülerini toplar."""
    GONDERILEN.clear()
    monkeypatch.setattr(EmailService, "send_password_reset_email", lambda self, e, n, b: GONDERILEN.append(("sifirlama", e, b)) or True)
    monkeypatch.setattr(EmailService, "send_verification_email", lambda self, e, n, b: GONDERILEN.append(("dogrulama", e, b)) or True)


def _belirtec(baglanti: str) -> str:
    assert "#t=" in baglanti, "belirteç fragment'te taşınmalı (sunucu günlüğüne/Referer'a gitmesin)"
    return baglanti.split("#t=", 1)[1]


def _kayit(client, org):
    assert client.post("/api/auth/signup", json=org).status_code == 200


def _giris(client, email, parola):
    return client.post("/api/auth/login", json={"email": email, "password": parola})


def test_sifre_unuttum_ayni_yanit_ve_yalniz_kayitliya_posta(client, test_org_data):
    _kayit(client, test_org_data)
    GONDERILEN.clear()
    a = client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]})
    b = client.post("/api/auth/sifre-unuttum", json={"email": "yok@example.com"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json(), "e-posta numaralandırma yok"
    assert [g[:2] for g in GONDERILEN] == [("sifirlama", test_org_data["email"])]


def test_tam_akis_yeni_parola_eski_gecersiz(client, test_org_data):
    _kayit(client, test_org_data)
    GONDERILEN.clear()
    client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]})
    tok = _belirtec(GONDERILEN[0][2])
    r = client.post("/api/auth/sifre-sifirla", json={"token": tok, "new_password": "yeniParola9"})
    assert r.status_code == 200
    assert _giris(client, test_org_data["email"], "yeniParola9").status_code == 200
    assert _giris(client, test_org_data["email"], test_org_data["password"]).status_code == 401


def test_belirtec_tek_kullanimlik(client, test_org_data):
    _kayit(client, test_org_data)
    GONDERILEN.clear()
    client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]})
    tok = _belirtec(GONDERILEN[0][2])
    assert client.post("/api/auth/sifre-sifirla", json={"token": tok, "new_password": "yeniParola9"}).status_code == 200
    assert client.post("/api/auth/sifre-sifirla", json={"token": tok, "new_password": "baskaParola9"}).status_code == 400


def test_yeni_istek_oncekini_gecersiz_kilar(client, test_org_data):
    _kayit(client, test_org_data)
    GONDERILEN.clear()
    client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]})
    client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]})
    eski, yeni = _belirtec(GONDERILEN[0][2]), _belirtec(GONDERILEN[1][2])
    assert client.post("/api/auth/sifre-sifirla", json={"token": eski, "new_password": "yeniParola9"}).status_code == 400
    assert client.post("/api/auth/sifre-sifirla", json={"token": yeni, "new_password": "yeniParola9"}).status_code == 200


def test_suresi_dolan_belirtec_reddedilir(client, db_session, test_org_data):
    _kayit(client, test_org_data)
    GONDERILEN.clear()
    client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]})
    tok = _belirtec(GONDERILEN[0][2])
    kayit = db_session.query(HesapBelirteci).filter(HesapBelirteci.amac == "sifre_sifirlama").one()
    kayit.bitis = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    db_session.commit()
    assert client.post("/api/auth/sifre-sifirla", json={"token": tok, "new_password": "yeniParola9"}).status_code == 400


def test_zayif_parola_ve_sahte_belirtec(client, test_org_data):
    _kayit(client, test_org_data)
    assert client.post("/api/auth/sifre-sifirla", json={"token": "x" * 40, "new_password": "yeniParola9"}).status_code == 400
    GONDERILEN.clear()
    client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]})
    tok = _belirtec(GONDERILEN[0][2])
    r = client.post("/api/auth/sifre-sifirla", json={"token": tok, "new_password": "sadeceharf"})
    assert r.status_code == 422, "parola politikası sıfırlamada da geçerli"
    # politika reddi belirteci yakmaz (422 doğrulama aşamasında)
    assert client.post("/api/auth/sifre-sifirla", json={"token": tok, "new_password": "yeniParola9"}).status_code == 200


def test_ham_belirtec_dbde_yok_yalniz_ozet(client, db_session, test_org_data):
    _kayit(client, test_org_data)
    GONDERILEN.clear()
    client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]})
    tok = _belirtec(GONDERILEN[0][2])
    kayit = db_session.query(HesapBelirteci).filter(HesapBelirteci.amac == "sifre_sifirlama").one()
    assert tok != kayit.belirtec_ozeti and len(kayit.belirtec_ozeti) == 64


def test_eposta_basina_saatte_3_sifirlama_postasi(client, test_org_data):
    _kayit(client, test_org_data)
    GONDERILEN.clear()
    for _ in range(5):
        assert client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]}).status_code == 200
    assert len([g for g in GONDERILEN if g[0] == "sifirlama"]) == 3


def test_pasif_hesaba_sifirlama_postasi_gitmez(client, db_session, test_org_data):
    _kayit(client, test_org_data)
    db_session.query(User).filter(User.email == test_org_data["email"]).one().is_active = False
    db_session.commit()
    GONDERILEN.clear()
    assert client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]}).status_code == 200
    assert GONDERILEN == []


def test_kayitta_dogrulama_postasi_ve_dogrulama(client, test_org_data):
    _kayit(client, test_org_data)
    assert [g[:2] for g in GONDERILEN] == [("dogrulama", test_org_data["email"])]
    giris = _giris(client, test_org_data["email"], test_org_data["password"]).json()
    assert giris["user"]["email_dogrulandi"] is False
    h = {"Authorization": f"Bearer {giris['access_token']}"}
    assert client.get("/api/auth/me", headers=h).json()["email_dogrulandi"] is False
    r = client.post("/api/auth/eposta-dogrula", json={"token": _belirtec(GONDERILEN[0][2])})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=h).json()["email_dogrulandi"] is True
    assert _giris(client, test_org_data["email"], test_org_data["password"]).json()["user"]["email_dogrulandi"] is True


def test_dogrulama_belirteci_sifirlamada_kullanilamaz(client, test_org_data):
    """Belirteçler amaca bağlı: e-posta doğrulama belirteciyle parola değiştirilemez."""
    _kayit(client, test_org_data)
    tok = _belirtec(GONDERILEN[0][2])
    assert client.post("/api/auth/sifre-sifirla", json={"token": tok, "new_password": "yeniParola9"}).status_code == 400


def test_dogrulama_yeniden_gonder_ve_zaten_dogrulanmis(client, test_org_data):
    _kayit(client, test_org_data)
    giris = _giris(client, test_org_data["email"], test_org_data["password"]).json()
    h = {"Authorization": f"Bearer {giris['access_token']}"}
    GONDERILEN.clear()
    assert client.post("/api/auth/dogrulama-gonder", headers=h).status_code == 200
    assert len(GONDERILEN) == 1
    client.post("/api/auth/eposta-dogrula", json={"token": _belirtec(GONDERILEN[0][2])})
    GONDERILEN.clear()
    r = client.post("/api/auth/dogrulama-gonder", headers=h)
    assert "zaten" in r.json()["mesaj"] and GONDERILEN == []


def test_sifirlama_dogrulanmamis_epostayi_dogrulanmis_yapar(client, test_org_data):
    _kayit(client, test_org_data)
    GONDERILEN.clear()
    client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]})
    client.post("/api/auth/sifre-sifirla", json={"token": _belirtec(GONDERILEN[0][2]), "new_password": "yeniParola9"})
    assert _giris(client, test_org_data["email"], "yeniParola9").json()["user"]["email_dogrulandi"] is True


def test_smtp_yoksa_istek_yine_de_basarili(client, test_org_data, monkeypatch):
    """SMTP yapılandırılmamışken uç noktalar hata vermez; yalnızca günlüğe uyarı düşer."""
    monkeypatch.undo()  # e-posta yakalayıcıyı geri al: gerçek EmailService, SMTP ayarsız
    _kayit(client, test_org_data)
    assert client.post("/api/auth/sifre-unuttum", json={"email": test_org_data["email"]}).status_code == 200


def test_sayfalar_servis_edilir(client):
    for yol in ("/sifre-sifirla", "/eposta-dogrula"):
        r = client.get(yol)
        assert r.status_code == 200 and "text/html" in r.headers["content-type"]
        assert "Content-Security-Policy" in r.headers


def test_gercek_eposta_servisi_imzalari_ve_icerik(monkeypatch):
    """Gerçek EmailService yöntemleri çağrılabilir (yakalayıcı olmadan) ve bağlantı/ad içeriğini taşır."""
    monkeypatch.undo()
    gonderilen = []
    monkeypatch.setattr(EmailService, "send_email", lambda self, to, konu, govde, html=None: gonderilen.append((to, konu, govde, html)) or True)
    assert EmailService().send_password_reset_email("a@b.com", "<b>Ad</b>", "https://x/sifre-sifirla#t=ABC")
    to, konu, govde, html = gonderilen[0]
    assert "https://x/sifre-sifirla#t=ABC" in govde and "1 saat" in govde
    assert "&lt;b&gt;Ad" in html, "ad HTML-kaçışlanmalı"
    assert EmailService().send_verification_email("a@b.com", "Ad", "https://x/eposta-dogrula#t=ZZZ")
    assert "48 saat" in gonderilen[1][2]
