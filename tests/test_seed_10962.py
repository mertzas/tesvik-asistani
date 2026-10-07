"""scripts/seed_hizmet_ihracati_10962.py: 10962 bilişim destekleri + iki kapalı KOSGEB programı."""
import importlib
import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app import rag
from app.ihtiyac import program_ihtiyaclari
from app.matching import esles
from app.models import FinancialProfile, Tesvik, TesvikNace

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture
def betik():
    sys.path.insert(0, str(KOK))
    return importlib.import_module("scripts.seed_hizmet_ihracati_10962")


def test_dry_run_yazmaz_uygula_idempotent(betik, db_session):
    assert betik.calistir(db_session, dry_run=True)["eklenen"] and db_session.query(Tesvik).count() == 0
    ilk = betik.calistir(db_session)
    assert len(ilk["eklenen"]) == 3 and db_session.query(Tesvik).count() == 3
    ikinci = betik.calistir(db_session)
    assert ikinci["eklenen"] == [] and len(ikinci["guncellenen"]) == 3
    assert db_session.query(Tesvik).count() == 3
    assert db_session.query(TesvikNace).count() == 3, "NACE satırları çoğalmamalı"


def test_kayit_icerikleri_kaynakli(betik, db_session):
    betik.calistir(db_session)
    k = {t.kurum: t for t in db_session.query(Tesvik)}
    bilisim = db_session.query(Tesvik).filter(Tesvik.baslik.like("%10962%")).one()
    assert bilisim.aktif_mi is True and "MADDE 50" in bilisim.durum_notu and "5448" in bilisim.durum_notu
    for madde in ("MADDE 16", "MADDE 17", "MADDE 22", "MADDE 31"):
        assert madde in bilisim.detay
    assert "50.000.000" in bilisim.detay and "%50" in bilisim.detay
    assert any("TTK" in s and "şirketleşmemiş" in s for s in bilisim.basvuru_sartlari)
    assert {r.nace_prefix for r in bilisim.nace_kayitlari} == {"62", "63", "58.2"}
    assert {"ihracat", "dijital"} <= program_ihtiyaclari(bilisim)
    for t in db_session.query(Tesvik).filter(Tesvik.kurum == "KOSGEB"):
        assert t.aktif_mi is False and "Yürürlükten Kaldırılan Destekler" in t.durum_notu
        assert "yürürlükten kaldırıldı" in t.baslik


def test_kapali_programlar_eslesmeye_girmez_bilisim_girer(betik, db_session):
    betik.calistir(db_session)
    yazilim = FinancialProfile(sektor="arge", bolge="Ankara", calisan_sayisi=5, yillik_ciro=3e6, nace_kodu="62.01")
    basliklar = [s.tesvik.baslik for s in esles(yazilim, db_session)]
    assert any("10962" in b for b in basliklar)
    assert not any("yürürlükten kaldırıldı" in b for b in basliklar)


def test_arama_kapali_programlari_sona_atar(betik, db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    betik.calistir(db_session)
    sonuc = rag.retrieve("KOBİGEL ve Ar-Ge Ür-Ge desteğine başvurabilir miyim?", limit=3)
    assert sonuc, "kapalı program sorulduğunda kayıt yine gelmeli (danışman 'kapandı' diyebilsin)"
    assert all(t.aktif_mi is False for t in sonuc if "yürürlükten" in t.baslik)
