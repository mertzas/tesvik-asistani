"""JWT iptali: parola sıfırlama ve "tüm oturumları kapat" önceki belirteçleri geçersiz kılar (2026-10-08)."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.auth import create_access_token
from app.email import EmailService
from app.models import User

KOK = Path(__file__).resolve().parent.parent
GONDERILEN = []


@pytest.fixture(autouse=True)
def eposta_yakala(monkeypatch):
    GONDERILEN.clear()
    monkeypatch.setattr(EmailService, "send_password_reset_email", lambda self, e, n, b: GONDERILEN.append(b) or True)
    monkeypatch.setattr(EmailService, "send_verification_email", lambda self, e, n, b: True)


def _kayit_ve_giris(client, org):
    assert client.post("/api/auth/signup", json=org).status_code == 200
    r = client.post("/api/auth/login", json={"email": org["email"], "password": org["password"]})
    assert r.status_code == 200
    return r.json()["access_token"]


def _me(client, token):
    return client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})


def _sifirla(client, email, yeni="yeniParola9"):
    GONDERILEN.clear()
    client.post("/api/auth/sifre-unuttum", json={"email": email})
    tok = GONDERILEN[0].split("#t=", 1)[1]
    assert client.post("/api/auth/sifre-sifirla", json={"token": tok, "new_password": yeni}).status_code == 200


def test_sifirlama_eski_belirtecleri_iptal_eder(client, test_org_data):
    eski = _kayit_ve_giris(client, test_org_data)
    assert _me(client, eski).status_code == 200
    _sifirla(client, test_org_data["email"])
    r = _me(client, eski)
    assert r.status_code == 401 and "yeniden giriş" in r.json()["detail"]
    yeni = client.post("/api/auth/login", json={"email": test_org_data["email"], "password": "yeniParola9"})
    assert _me(client, yeni.json()["access_token"]).status_code == 200


def test_sv_talebi_olmayan_eski_belirtec_gocte_gecerli_sifirlamada_gecersiz(client, db_session, test_org_data):
    _kayit_ve_giris(client, test_org_data)
    u = db_session.query(User).filter(User.email == test_org_data["email"]).one()
    eski_bicim = create_access_token({"sub": str(u.id), "org_id": str(u.org_id)})  # göç öncesi biçim
    assert _me(client, eski_bicim).status_code == 200, "göç anında kimse oturumdan atılmamalı"
    _sifirla(client, test_org_data["email"])
    assert _me(client, eski_bicim).status_code == 401


def test_tum_oturumlari_kapat(client, test_org_data):
    a = _kayit_ve_giris(client, test_org_data)
    b = client.post("/api/auth/login", json={"email": test_org_data["email"],
                                             "password": test_org_data["password"]}).json()["access_token"]
    r = client.post("/api/auth/tum-oturumlari-kapat", headers={"Authorization": f"Bearer {a}"})
    assert r.status_code == 200
    yeni = r.json()["access_token"]
    assert _me(client, a).status_code == 401 and _me(client, b).status_code == 401
    assert _me(client, yeni).status_code == 200, "isteği yapan cihaz yeni belirteçle devam eder"


def test_kurcalanmis_sv_reddedilir(client, db_session, test_org_data):
    _kayit_ve_giris(client, test_org_data)
    u = db_session.query(User).filter(User.email == test_org_data["email"]).one()
    for sv in ("abc", None, 5):
        tok = create_access_token({"sub": str(u.id), "org_id": str(u.org_id), "sv": sv})
        assert _me(client, tok).status_code == 401, sv


def test_goc_oturum_surumu_upgrade_downgrade(tmp_path, monkeypatch):
    from app import models
    db_yolu = tmp_path / "o.db"
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db_yolu}")
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "migrations"))
    motor = create_engine(f"sqlite:///{db_yolu}")
    command.upgrade(cfg, "head")
    assert "oturum_surumu" in {c["name"] for c in inspect(motor).get_columns("users")}
    command.downgrade(cfg, "g4b6c8d0e456")
    assert "oturum_surumu" not in {c["name"] for c in inspect(motor).get_columns("users")}
    command.upgrade(cfg, "head")
