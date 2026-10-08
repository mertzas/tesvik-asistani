"""Hazırlık yol haritası ve kalıcı e-ihracat girdisi (app/hazirlik.py, GET/PUT /api/hazirlik), 2026-10-08."""
from pathlib import Path

import pytest

from app.models import FinancialProfile, Tesvik

KOK = Path(__file__).resolve().parent.parent
TICARET_SARTLARI = ["Şirket olmak (TTK md.124)", "Bir ihracatçı birliğine üye olmak",
                    "Ticaret Bakanlığı Destek Yönetim Sistemi (DYS) kaydı",
                    "Ön onay için WIPO Madrid Sistemi'ne taraf en az bir ülkede tescilli yurt dışı marka",
                    "Destekten önce ön onay alınmalı"]


@pytest.fixture
def kayitlar(db_session):
    db_session.add_all([
        Tesvik(id=21, kurum="Ticaret Bakanlığı", baslik="Dijital Pazaryeri Tanıtım Desteği", ozet="o", detay="ihracat",
               aktif_mi=True, kaynak_url="https://t/21", basvuru_sartlari=TICARET_SARTLARI,
               uygunluk_kriterleri={"sektorler": ["e-ticaret", "ihracat"], "sirket_turleri": ["limited", "anonim"]}),
        Tesvik(id=22, kurum="KOSGEB", baslik="Girişimci Destek Programı", ozet="o", detay="e-ticaret",
               aktif_mi=True, kaynak_url="https://t/22", basvuru_sartlari=["KOBİ olmak"],
               uygunluk_kriterleri={"sektorler": ["e-ticaret"]}),
    ])
    db_session.commit()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _profil(client, h, **k):
    r = client.put("/api/profil", headers=h, json={"sektor": "e-ticaret", "calisan_sayisi": 3, **k})
    assert r.status_code == 200, r.text


def test_profilsiz(client, test_user_token, kayitlar):
    h = _h(test_user_token)
    d = client.get("/api/hazirlik", headers=h).json()
    assert d["yol_haritasi"]["adimlar"] == [] and d["eihracat"] is None and len(d["kalemler"]) == 5
    assert client.put("/api/hazirlik", headers=h, json={"durumlar": {"dys_kaydi": True}}).status_code == 409


def test_sahis_isletmesine_sirket_adimi_ve_acilan_programlar(client, test_user_token, kayitlar):
    h = _h(test_user_token)
    _profil(client, h, sirket_turu="sahis")
    adimlar = client.get("/api/hazirlik", headers=h).json()["yol_haritasi"]["adimlar"]
    assert adimlar[0]["kod"] == "sirket" and [p["id"] for p in adimlar[0]["acar"]] == [21]
    assert {a["kod"] for a in adimlar} == {"sirket", "kosgeb_kaydi"}  # Ticaret kaydı şahısa kapalı: şartları sayılmaz


def test_limited_sirkete_ticaret_on_sartlari(client, test_user_token, kayitlar):
    h = _h(test_user_token)
    _profil(client, h, sirket_turu="limited")
    adimlar = {a["kod"]: a for a in client.get("/api/hazirlik", headers=h).json()["yol_haritasi"]["adimlar"]}
    assert set(adimlar) == {"birlik_uyeligi", "dys_kaydi", "madrid_marka", "on_onay", "kosgeb_kaydi"}
    assert [p["id"] for p in adimlar["madrid_marka"]["gerekli"]] == [21]


def test_isaretleme_kalici_ve_null_siler(client, test_user_token, kayitlar):
    h = _h(test_user_token)
    _profil(client, h, sirket_turu="limited")
    d = client.put("/api/hazirlik", headers=h, json={"durumlar": {"dys_kaydi": True, "madrid_marka": False}}).json()
    adimlar = d["yol_haritasi"]["adimlar"]
    assert [a["kod"] for a in adimlar if a["tamam"]] == ["dys_kaydi"] and adimlar[-1]["kod"] == "dys_kaydi"
    d = client.put("/api/hazirlik", headers=h, json={"durumlar": {"madrid_marka": None}}).json()
    assert d["hazirlik"]["durumlar"] == {"dys_kaydi": True}
    # Profil yeniden kaydedilince hazırlık bilgisi silinmez (giderler alanından ayrı sütun).
    _profil(client, h, sirket_turu="limited", giderler={"toplam": 1000})
    assert client.get("/api/hazirlik", headers=h).json()["hazirlik"]["durumlar"] == {"dys_kaydi": True}


def test_taninmayan_alan_reddedilir(client, test_user_token, kayitlar):
    h = _h(test_user_token)
    _profil(client, h)
    assert client.put("/api/hazirlik", headers=h, json={"durumlar": {"uydurma": True}}).status_code == 422
    assert client.put("/api/hazirlik", headers=h, json={"eihracat": {"giderler": {"depo": 1}}}).status_code == 422
    assert client.put("/api/hazirlik", headers=h, json={"eihracat": {"giderler": {"pazaryeri_reklam": -5}}}).status_code == 422
    assert client.put("/api/hazirlik", headers=h, json={"eihracat": {"giderler": {}, "hedef_ulke_payi": 2}}).status_code == 422


def test_eihracat_kaydi_hesap_ve_ana_sayfa(client, test_user_token, kayitlar):
    h = _h(test_user_token)
    _profil(client, h, sirket_turu="limited")
    d = client.put("/api/hazirlik", headers=h, json={
        "durumlar": {"birlik_uyeligi": True, "madrid_marka": False},
        "eihracat": {"giderler": {"pazaryeri_reklam": 240_000, "pazaryeri_komisyon": 120_000}, "hedef_ulke_payi": 1}}).json()
    e = d["eihracat"]
    assert e["simdi_tl"] == 0 and e["hazirlikla_tl"] == 168_000 + 60_000 and e["adimlar"] == ["madrid_marka"]
    client.put("/api/hazirlik", headers=h, json={"durumlar": {"madrid_marka": True}})
    o = client.get("/api/ozet", headers=h).json()["hazirlik"]
    assert o["eihracat"]["simdi_tl"] == 228_000 and o["eihracat"]["aylik_bekleme_tl"] == 19_000
    assert o["eihracat_ilgili"] is True and o["ilk_adim"]["kod"] in {"birlik_uyeligi", "dys_kaydi", "on_onay",
                                                                      "kosgeb_kaydi"}


def test_sahis_icin_ana_sayfa_ilk_adim_sirket(client, test_user_token, kayitlar):
    h = _h(test_user_token)
    _profil(client, h, sirket_turu="sahis")
    o = client.get("/api/ozet", headers=h).json()["hazirlik"]
    assert o["ilk_adim"] == {"kod": "sirket", "baslik": "Limited/anonim şirkete geçiş", "program_sayisi": 1}


def test_karsi_olgu_veritabanina_yazmaz(db_session, kayitlar):
    from app.hazirlik import yol_haritasi
    p = FinancialProfile(sektor="e-ticaret", sirket_turu="sahis", calisan_sayisi=3)
    db_session.add(p)
    db_session.commit()
    yol_haritasi(p, db_session)
    db_session.commit()
    assert db_session.query(FinancialProfile).count() == 1 and p.sirket_turu == "sahis"


def test_goc_hazirlik_sutunu(tmp_path, monkeypatch):
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
    assert "hazirlik" in {c["name"] for c in inspect(motor).get_columns("financial_profiles")}
    command.downgrade(cfg, "l9a1c3e5f901")
    assert "hazirlik" not in {c["name"] for c in inspect(motor).get_columns("financial_profiles")}
    command.upgrade(cfg, "head")
