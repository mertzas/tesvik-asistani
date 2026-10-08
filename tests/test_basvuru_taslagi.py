"""Başvuru ön taslağı (app/basvuru_taslagi.py + POST /api/basvuru-listesi/{id}/taslak), 2026-10-08.
Gerçek Claude çağrısı YOK: _claude_istek her testte yamalanır."""
import subprocess
import sys
from pathlib import Path

import pytest

from app import basvuru_taslagi
from app.models import BasvuruTakibi, FinancialProfile, Organization, PlanType, Tesvik, User, settings

KOK = Path(__file__).resolve().parent.parent
CAGRILAR = []


@pytest.fixture(autouse=True)
def sahte_claude(monkeypatch):
    CAGRILAR.clear()
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-anahtari")

    def _sahte(sistem, kullanici):
        CAGRILAR.append((sistem, kullanici))
        return ("## 1. İşletme tanıtımı\nMetin [DOLDURUN: kuruluş yılı]\n## 2. Projenin amacı ve gerekçesi\nx",
                {"giris": 1200, "cikis": 400, "durma": "end_turn"})
    monkeypatch.setattr(basvuru_taslagi, "_claude_istek", _sahte)


@pytest.fixture
def hazir(client, db_session):
    """PRO plan, rızalı, profilli kullanıcı + belge listeli teşvik. (başlık, kurum) döner."""
    db_session.add(Tesvik(id=9, kurum="KOSGEB", baslik="Küresel Rekabetçilik", ozet="o", detay="d", aktif_mi=True,
                          kaynak_url="https://t/9", uygunluk_kriterleri={"sektorler": ["genel"]},
                          basvuru_sartlari=["KOBİ olmak"], gerekli_belgeler=["Proje Başvuru Formu"],
                          basvuru_yeri="KBS"))
    db_session.commit()
    r = client.post("/api/auth/signup", json={"email": "a@example.com", "password": "Parola123", "full_name": "A",
                                              "company_name": "B", "ai_yurtdisi_riza": True})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    org = db_session.query(Organization).join(User, User.org_id == Organization.id).filter(
        User.email == "a@example.com").one()
    org.plan = PlanType.PRO
    db_session.add(FinancialProfile(org_id=org.id, sektor="imalat", bolge="Bursa", calisan_sayisi=18,
                                    yillik_ciro=32e6, nace_kodu="25.62"))
    db_session.commit()
    return h, org


def _olustur(client, h):
    return client.post("/api/basvuru-listesi/9/taslak", headers=h)


def test_taslak_uretilir_saklanir_ve_belgeler_listeden_gelir(client, db_session, hazir):
    h, _ = hazir
    r = _olustur(client, h)
    assert r.status_code == 200, r.text
    taslak = r.json()["taslak"]
    assert taslak.startswith("> **Ön taslak — resmi başvuru formu değildir.**")
    assert "## 6. Hazırlanacak belgeler ve şartlar" in taslak and "- [ ] Proje Başvuru Formu" in taslak
    assert r.json()["taslak_tarihi"] and r.json()["takipte"] is True
    # profil ve program bilgisi istemde; boş profil alanı yok
    _, kullanici = CAGRILAR[0]
    assert "Küresel Rekabetçilik" in kullanici and "sektör: imalat" in kullanici and "TRL" not in kullanici
    # GET'te geri gelir (tekrar ücret ödenmez)
    assert client.get("/api/basvuru-listesi/9", headers=h).json()["taslak"] == taslak
    assert db_session.query(BasvuruTakibi).one().taslak_model == settings.CLAUDE_MODEL[:60]


def test_free_plan_rizasiz_ve_profilsiz_cagri_yapilmaz(client, db_session, hazir):
    h, org = hazir
    org.plan = PlanType.FREE
    db_session.commit()
    assert _olustur(client, h).status_code == 403
    org.plan = PlanType.PRO
    org.ai_yurtdisi_riza = False
    db_session.commit()
    r = _olustur(client, h)
    assert r.status_code == 403 and "rıza" in r.json()["detail"]
    org.ai_yurtdisi_riza = True
    db_session.query(FinancialProfile).delete()
    db_session.commit()
    assert _olustur(client, h).status_code == 404
    assert CAGRILAR == [], "koşullar sağlanmadan ücretli çağrı yapılmamalı"


def test_servis_yoksa_503_ve_hata_kaydi_bozmaz(client, db_session, hazir, monkeypatch):
    h, _ = hazir
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    assert _olustur(client, h).status_code == 503
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-anahtari")

    def _patla(sistem, kullanici):
        raise RuntimeError("kredi bitti")
    monkeypatch.setattr(basvuru_taslagi, "_claude_istek", _patla)
    r = _olustur(client, h)
    assert r.status_code == 503 and "kredi" not in r.json()["detail"], "iç hata ayrıntısı sızmamalı"
    assert db_session.query(BasvuruTakibi).count() == 0


def test_gunluk_sinir(client, hazir):
    h, _ = hazir
    for _ in range(5):
        assert _olustur(client, h).status_code == 200
    r = _olustur(client, h)
    assert r.status_code == 429 and len(CAGRILAR) == 5


def test_max_tokens_kesilmesi_bildirilir(client, hazir, monkeypatch):
    h, _ = hazir
    monkeypatch.setattr(basvuru_taslagi, "_claude_istek",
                        lambda s, k: ("## 1. İşletme tanıtımı\nyarım", {"durma": "max_tokens"}))
    assert "uzunluk sınırında kesildi" in _olustur(client, h).json()["taslak"]


def test_hesap_silmede_taslak_da_silinir(client, db_session, hazir):
    h, _ = hazir
    _olustur(client, h)
    r = client.request("DELETE", "/api/organizations/me", headers=h, json={"password": "Parola123", "onay": True})
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.query(BasvuruTakibi).count() == 0


def test_goc_taslak_sutunlari(tmp_path, monkeypatch):
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
    sutunlar = {c["name"] for c in inspect(motor).get_columns("basvuru_takipleri")}
    assert {"taslak", "taslak_tarihi", "taslak_model"} <= sutunlar
    command.downgrade(cfg, "i6d8f0a2b678")
    assert "taslak" not in {c["name"] for c in inspect(motor).get_columns("basvuru_takipleri")}
    command.upgrade(cfg, "head")


def test_kvkk_metni_taslak_aktarimini_ve_saklamayi_soyler():
    html = (KOK / "app/static/kvkk.html").read_text(encoding="utf-8")
    assert "ön taslağı yazılması için de gönderilir" in html and "basvuru_takipleri.taslak" in html


def test_self_test_bayragi():
    r = subprocess.run([sys.executable, "-m", "app.basvuru_taslagi", "--self-test"], cwd=KOK,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "6/6 geçti" in r.stdout
