"""uygunluk_kriterleri.sirket_turleri: kayıtta açık şirket türü listesi varsa eşleştirme bunu uygular (2026-10-08).
İlk kullanım: 5973 sayılı İhracat Destekleri Kararı m.2 "şirket" tanımı (TTK md.124 + kooperatif; şahıs işletmesi yok)."""
import subprocess
import sys
from pathlib import Path

import pytest

from app.matching import esles, uygunluk_engeli
from app.models import FinancialProfile, Tesvik

KOK = Path(__file__).resolve().parent.parent


def _tesvik(**k):
    return Tesvik(kurum="Ticaret Bakanlığı", baslik="Yurt Dışı Marka Tescil Desteği", ozet="o", detay="ihracat",
                  aktif_mi=True, kaynak_url="https://t/m4", uygunluk_kriterleri={
                      "sektorler": ["ihracat", "e-ticaret"], "sirket_turleri": ["limited", "anonim", "kooperatif"]}, **k)


@pytest.mark.parametrize("tur,kapali", [("sahis", True), ("yok", True), ("limited", False), ("anonim", False),
                                        ("kooperatif", False), (None, False)])
def test_sirket_turu_listesi(tur, kapali):
    p = FinancialProfile(sektor="e-ticaret", hedefler=["ihracat"], sirket_turu=tur)
    engel = uygunluk_engeli(_tesvik(), p)
    assert (engel is not None) == kapali, engel
    if kapali:
        assert "kapsam dışı" in engel


def test_listesiz_kayit_etkilenmez():
    t = _tesvik()
    t.uygunluk_kriterleri = {"sektorler": ["ihracat"]}
    assert uygunluk_engeli(t, FinancialProfile(sektor="e-ticaret", sirket_turu="sahis")) is None


def test_eslesmede_sahis_isletmesine_gelmez(db_session):
    db_session.add(_tesvik(id=501))
    db_session.commit()
    ltd = esles(FinancialProfile(sektor="e-ticaret", hedefler=["ihracat"], sirket_turu="limited"), db_session)
    sahis = esles(FinancialProfile(sektor="e-ticaret", hedefler=["ihracat"], sirket_turu="sahis"), db_session)
    assert 501 in {e.tesvik.id for e in ltd} and 501 not in {e.tesvik.id for e in sahis}


@pytest.mark.parametrize("betik,asgari", [("scripts/fix_veri_2026_10_08_cagrilar_tur10.py", 6),
                                          ("scripts/fix_veri_2026_10_08_ihracat_5973_tur11.py", 8)])
def test_veri_betikleri_self_test(betik, asgari):
    import re
    r = subprocess.run([sys.executable, betik, "--self-test"], cwd=KOK, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"self-test: (\d+)/(\d+) geçti", r.stdout)
    assert r.returncode == 0 and m and m.group(1) == m.group(2) and int(m.group(2)) >= asgari, r.stdout
