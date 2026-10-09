"""Profil uygunluk alanları (2026-10-10): kurucu yaşı, başka şirkette ortaklık, ürün sertifikası.

Kayıtta yapılandırılmış şart (uygunluk_kriterleri.kurucu_yasi_max / ortaklik_yasagi_sirketsiz / gerekli_sertifika) ve
profilde bilgi varsa eşleştirme karar verir; ikisinden biri yoksa elemez (bilinmeyen bilgi ihlal değildir)."""
import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.matching import esles, uygunluk_engeli
from app.models import FinancialProfile, Tesvik
from app.schemas import FinancialProfileCreate

KOK = Path(__file__).resolve().parent.parent
YENI = {"kurucu_yasi", "baska_sirkette_ortak", "sertifikalar"}


def _tesvik(kriter, **k):
    return Tesvik(kurum=k.pop("kurum", "Halkbank"), baslik=k.pop("baslik", "Genç Girişimci Kredisi"), ozet="o",
                  detay="kredi", aktif_mi=True, kaynak_url="https://t/k", uygunluk_kriterleri=kriter, **k)


# ------------------------------------------------------------------ şema
def test_sema_alanlari():
    p = FinancialProfileCreate(sektor="genel", kurucu_yasi=27, baska_sirkette_ortak=False,
                               sertifikalar=["organik_sertifika", "iyi_tarim_sertifikasi", "organik_sertifika"])
    assert p.kurucu_yasi == 27 and p.baska_sirkette_ortak is False
    assert p.sertifikalar == ["iyi_tarim_sertifikasi", "organik_sertifika"]
    assert FinancialProfileCreate(sektor="genel", sertifikalar=[]).sertifikalar is None
    assert FinancialProfileCreate(sektor="genel").kurucu_yasi is None


@pytest.mark.parametrize("alanlar", [{"kurucu_yasi": 14}, {"kurucu_yasi": 101}, {"sertifikalar": ["iso9001"]},
                                     {"sertifikalar": ["hicbiri", "organik_sertifika"]}])
def test_sema_gecersiz(alanlar):
    with pytest.raises(ValueError):
        FinancialProfileCreate(sektor="genel", **alanlar)


# ------------------------------------------------------------------ eşleştirme kuralları
@pytest.mark.parametrize("yas,kapali", [(25, False), (29, False), (30, True), (None, False)])
def test_kurucu_yas_siniri(yas, kapali):
    engel = uygunluk_engeli(_tesvik({"sektorler": ["genel"], "kurucu_yasi_max": 29}),
                            FinancialProfile(sektor="genel", kurucu_yasi=yas))
    assert (engel is not None) == kapali, engel
    if kapali:
        assert "en çok 29 yaşında" in engel


def test_yas_siniri_olmayan_kayit_etkilenmez():
    assert uygunluk_engeli(_tesvik({"sektorler": ["genel"]}), FinancialProfile(sektor="genel", kurucu_yasi=70)) is None


@pytest.mark.parametrize("tur,ortak,kapali", [("yok", True, True), ("yok", False, False), ("yok", None, False),
                                              ("limited", True, False)])
def test_ortaklik_yasagi_yalniz_sirketsiz_girisimciye(tur, ortak, kapali):
    t = _tesvik({"sektorler": ["arge", "genel"], "ortaklik_yasagi_sirketsiz": True}, kurum="TÜBİTAK",
                baslik="1812 Yatırım Tabanlı Girişimcilik Destek Programı")
    engel = uygunluk_engeli(t, FinancialProfile(sektor="arge", sirket_turu=tur, baska_sirkette_ortak=ortak))
    assert (engel is not None and "ortak olmamak" in engel) == kapali, engel


@pytest.mark.parametrize("sertifikalar,kapali", [(["organik_sertifika"], False), (["hicbiri"], True),
                                                 (["iyi_tarim_sertifikasi"], True), (None, False)])
def test_gerekli_sertifika(sertifikalar, kapali):
    t = _tesvik({"sektorler": ["tarim"], "gerekli_sertifika": "organik_sertifika"}, kurum="Tarım ve Orman Bakanlığı",
                baslik="Organik Tarım Desteği")
    engel = uygunluk_engeli(t, FinancialProfile(sektor="tarim", sertifikalar=sertifikalar))
    assert (engel is not None) == kapali, engel
    if kapali:
        assert "gerekir" in engel


def test_eslesmede_yasi_asan_profile_gelmez(db_session):
    db_session.add(_tesvik({"sektorler": ["genel"], "kurucu_yasi_max": 29}, id=601))
    db_session.commit()
    genc = esles(FinancialProfile(sektor="genel", kurucu_yasi=26), db_session)
    yasli = esles(FinancialProfile(sektor="genel", kurucu_yasi=45), db_session)
    bilinmeyen = esles(FinancialProfile(sektor="genel"), db_session)
    assert 601 in {e.tesvik.id for e in genc} and 601 in {e.tesvik.id for e in bilinmeyen}
    assert 601 not in {e.tesvik.id for e in yasli}


# ------------------------------------------------------------------ uç nokta ve veri koruma
def test_profil_ucu_alanlari_kaydeder_ve_danismana_gondermez(client, monkeypatch):
    import app.main as anamodul
    gorulen = {}
    monkeypatch.setattr(anamodul, "answer", lambda soru, profil=None, llm_kullan=True, **kw: gorulen.update(profil=profil) or "y")
    r = client.post("/api/auth/signup", json={"email": "pu1@example.com", "password": "GucluSifre123",
                                              "full_name": "P", "company_name": "P", "ai_yurtdisi_riza": True})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.put("/api/profil", headers=h, json={"sektor": "tarim", "kurucu_yasi": 33, "baska_sirkette_ortak": True,
                                                   "sertifikalar": ["organik_sertifika"]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["kurucu_yasi"] == 33 and j["baska_sirkette_ortak"] is True and j["sertifikalar"] == ["organik_sertifika"]
    assert client.get("/api/profil", headers=h).json()["kurucu_yasi"] == 33
    r = client.put("/api/profil", headers=h, json={"sektor": "tarim", "sertifikalar": ["hicbiri", "organik_sertifika"]})
    assert r.status_code == 422
    client.post("/api/sor", json={"question": "organik tarım desteği"}, headers=h)
    metin = repr(gorulen["profil"])
    assert "33" not in metin and "ortak" not in metin and "sertifika" not in metin


def test_kvkk_metni_yeni_alanlari_sayiyor():
    html = (KOK / "app/static/kvkk.html").read_text(encoding="utf-8")
    assert ".kurucu_yasi" in html and ".baska_sirkette_ortak" in html and ".sertifikalar" in html


def test_goc_upgrade_downgrade(tmp_path, monkeypatch):
    from app import models
    db_yolu = tmp_path / "pu.db"
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db_yolu}")
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "migrations"))
    motor = create_engine(f"sqlite:///{db_yolu}")
    command.upgrade(cfg, "head")
    assert YENI <= {c["name"] for c in inspect(motor).get_columns("financial_profiles")}
    command.downgrade(cfg, "p3e5a7c9d456")
    assert not (YENI & {c["name"] for c in inspect(motor).get_columns("financial_profiles")})
    command.upgrade(cfg, "head")


def test_veri_betigi_self_test():
    import re
    r = subprocess.run([sys.executable, "scripts/fix_veri_2026_10_10_profil_sart_tur23.py", "--self-test"], cwd=KOK,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"self-test: (\d+)/(\d+) geçti", r.stdout)
    assert r.returncode == 0 and m and m.group(1) == m.group(2), r.stdout
