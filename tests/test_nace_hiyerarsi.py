"""NACE hiyerarşisi, şema göçü, backfill ve canlı eşleşme testleri."""
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.matching import esles
from app.models import FinancialProfile, Tesvik, TesvikNace
from app.nace_hiyerarsi import normalize_nace, sector_fit, sector_match

KOK = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------ normalizasyon
@pytest.mark.parametrize("ham,beklenen", [
    ("C", "C"), ("c", "C"), (" I ", "I"),
    ("C.10.71", "10.71"), ("C10.71", "10.71"), ("c.10", "10"),
    ("1071", "10.71"), ("10.71", "10.71"), ("10.7", "10.7"),
    ("10.71.01", "10.71.01"), ("55.10.01", "55.10.01"), ("01.19.99", "01.19.99"),
])
def test_normalizasyon_gecerli_biçimler(ham, beklenen):
    assert normalize_nace(ham) == beklenen


@pytest.mark.parametrize("ham", [None, "", "  ", "Z", "1", "A.10", "C.01", "98x", "00", "ABC"])
def test_normalizasyon_gecersiz(ham):
    assert normalize_nace(ham) is None, "harf bölümle uyuşmuyorsa da reddedilmeli"


# --------------------------------------------------------------- sektör uyumu
def test_C10_profili_C_tesvikiyle_tam_eslesir():
    assert sector_fit("C.10", ["C"]) == 1.0
    assert sector_fit("C.10.71", ["C"]) == 1.0
    assert sector_match("C.10.71", ["C"]).durum == "tam"


def test_A01_profili_C_tesvikinden_sifir_alir():
    assert sector_fit("A.01", ["C"]) == 0.0
    assert sector_match("A.01", ["C"]).durum == "uyumsuz"


def test_kod_girilmemis_profilde_yatay_haric_sektor_puani_duser():
    nace_yok = sector_match(None, ["C"])
    assert nace_yok.skor == 0.0 and nace_yok.durum == "nace_yok"
    yatay = sector_match(None, [])
    assert yatay.skor == 0.4 and yatay.durum == "yatay"


def test_10_71e_ozgu_tesvik_tam_ve_kismi_puan():
    assert sector_fit("10.71", ["10.71"]) == 1.0                 # tam
    assert 0 < sector_fit("10", ["10.71"]) < 1.0                 # işletme daha geniş: kısmi
    assert sector_fit("10", ["10.71"]) > sector_fit("10.72", ["10.71"]) > 0   # aynı bölüm daha düşük
    assert sector_fit("11.01", ["10.71"]) == 0.0


def test_birden_cok_program_kodundan_en_iyisi_alinir():
    assert sector_fit("55.10", ["01", "I"]) == 1.0


def test_skor_aralik_ve_saflik():
    for c in ["A", "C", "10", "10.71", None]:
        for p in (["C"], ["10.71"], ["A", "55"], []):
            assert 0.0 <= sector_fit(c, p) <= 1.0
    assert sector_fit("10.71", ["C"]) == sector_fit("10.71", ["C"])


# --------------------------------------------------------------- şema göçü
def _alembic_cfg(monkeypatch, db_yolu):
    from app import models
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db_yolu}")
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "migrations"))
    return cfg


def test_gocun_upgrade_ve_downgrade(tmp_path, monkeypatch):
    db_yolu = tmp_path / "gecici.db"
    cfg = _alembic_cfg(monkeypatch, db_yolu)
    motor = create_engine(f"sqlite:///{db_yolu}")

    command.upgrade(cfg, "head")
    ic = inspect(motor)
    assert "tesvik_nace_association" in ic.get_table_names()
    assert "nace_kodu" in {c["name"] for c in ic.get_columns("financial_profiles")}
    indeksler = {i["name"] for i in ic.get_indexes("tesvik_nace_association")}
    assert "ix_tesvik_nace_association_nace_prefix" in indeksler

    command.downgrade(cfg, "b7c1d3e5f901")
    ic = inspect(motor)
    assert "tesvik_nace_association" not in ic.get_table_names()
    assert "nace_kodu" not in {c["name"] for c in ic.get_columns("financial_profiles")}
    assert "ozellikler" in {c["name"] for c in ic.get_columns("financial_profiles")}, \
        "yalnızca bu göç geri alınmalı"

    command.upgrade(cfg, "head")   # geri alındıktan sonra yeniden uygulanabilir
    assert "tesvik_nace_association" in inspect(motor).get_table_names()


# ------------------------------------------------------------------ backfill
@pytest.fixture
def backfill():
    sys.path.insert(0, str(KOK))
    return importlib.import_module("scripts.backfill_nace_kriterleri")


def _t(baslik, kriter=None):
    return SimpleNamespace(baslik=baslik, uygunluk_kriterleri=kriter or {})


@pytest.mark.parametrize("baslik,beklenen", [
    ("İmalat Sanayii Destek Paketi", ["C"]),
    ("İMALATA DAYALI İTHAL İKAMESİ DESTEK PAKETİ", ["C"]),
    ("TARIM KEFALET DESTEK PROGRAMI", ["A"]),
    ("Hayvancılık Destekleri", ["A"]),
    ("Sera/Örtüaltı Tarım Destekleri", ["A"]),
    ("TURİZM DESTEK PAKETİ", ["I"]),
    ("KGF Genel Destek Programı", []),
    ("Seramik İşletmeleri Kredisi", []),            # "sera" başka bir kelimenin parçası
    ("ÇAY ALIMI DESTEK PAKETİ", []),                # emin olunmayan: dokunulmaz
    ("Girişimci Destek Programı", []),
])
def test_anahtar_kelime_eslemesi(backfill, baslik, beklenen):
    assert [p for p, _ in backfill.dikeyleri_bul(_t(baslik))] == beklenen


def _tesvik(baslik, url):
    return Tesvik(kurum="X", baslik=baslik, ozet="o", detay="d", kaynak_url=url,
                  uygunluk_kriterleri={"sektorler": ["genel"]})


def test_backfill_dry_run_yazmaz_ve_idempotenttir(backfill, db_session):
    db_session.add_all([_tesvik("İmalat Sanayii Destek Paketi", "https://t/a"),
                        _tesvik("Hayvancılık Destekleri", "https://t/b"),
                        _tesvik("Genel Destek", "https://t/c")])
    db_session.commit()

    kuru = backfill.calistir(db_session, dry_run=True)
    assert kuru["eklenen"] == 2 and db_session.query(TesvikNace).count() == 0

    ilk = backfill.calistir(db_session)
    assert ilk["eklenen"] == 2 and db_session.query(TesvikNace).count() == 2

    ikinci = backfill.calistir(db_session)
    assert ikinci["eklenen"] == 0 and ikinci["zaten_var"] == 2
    assert db_session.query(TesvikNace).count() == 2


def test_backfill_elle_girilen_kaydi_bozmaz_ve_geri_alinabilir(backfill, db_session):
    t = _tesvik("İmalat Sanayii Destek Paketi", "https://t/a")
    db_session.add(t)
    db_session.commit()
    db_session.add(TesvikNace(tesvik_id=t.id, nace_prefix="10", kaynak="elle"))
    db_session.commit()

    backfill.calistir(db_session)
    kaynaklar = {r.nace_prefix: r.kaynak for r in db_session.query(TesvikNace)}
    assert kaynaklar["10"] == "elle" and kaynaklar["C"].startswith("otomatik:")

    backfill.calistir(db_session, geri_al=True)
    kalan = {r.nace_prefix for r in db_session.query(TesvikNace)}
    assert kalan == {"10"}, "yalnızca otomatik eklenenler silinmeli"


# ----------------------------------------------------- canlı eşleşme (esles)
def _imalat_programi(db, baslik="Imalat Destegi", url="https://t/i"):
    t = Tesvik(kurum="X", baslik=baslik, ozet="o", detay="d", kaynak_url=url,
               uygunluk_kriterleri={"sektorler": ["genel"]})
    t.nace_kayitlari = [TesvikNace(nace_prefix="C", kaynak="elle")]
    db.add(t)
    db.add(Tesvik(kurum="X", baslik="Yatay Destek", ozet="o", detay="d",
                  kaynak_url="https://t/y", uygunluk_kriterleri={"sektorler": ["genel"]}))
    db.commit()


def test_esles_C10_profili_imalat_programini_gorur(db_session):
    _imalat_programi(db_session)
    sonuc = {s.tesvik.baslik: s for s in esles(
        FinancialProfile(sektor="imalat", nace_kodu="10"), db_session)}
    assert "Imalat Destegi" in sonuc
    assert any("tam sektör eşleşmesi" in g for g in sonuc["Imalat Destegi"].gerekce)


def test_esles_A01_profili_imalat_programindan_elenir(db_session):
    _imalat_programi(db_session)
    basliklar = [s.tesvik.baslik for s in esles(
        FinancialProfile(sektor="imalat", nace_kodu="01"), db_session)]
    assert "Imalat Destegi" not in basliklar and "Yatay Destek" in basliklar


def test_esles_nace_girilmemisse_sektorlu_programda_uyari_yataylarda_yok(db_session):
    _imalat_programi(db_session)
    sonuc = {s.tesvik.baslik: s for s in esles(FinancialProfile(sektor="imalat"), db_session)}
    assert any("NACE" in e for e in sonuc["Imalat Destegi"].eksik_kriterler)
    assert not any("NACE" in e for e in sonuc["Yatay Destek"].eksik_kriterler)


# -------------------------------------------------------------------- şema
def test_profil_semasi_nace_kodunu_normalize_eder_ve_gecersizi_reddeder():
    from app.schemas import FinancialProfileCreate
    assert FinancialProfileCreate(sektor="imalat", nace_kodu="C.10.71").nace_kodu == "10.71"
    assert FinancialProfileCreate(sektor="imalat", nace_kodu="  ").nace_kodu is None
    with pytest.raises(ValueError):
        FinancialProfileCreate(sektor="imalat", nace_kodu="A.10")
