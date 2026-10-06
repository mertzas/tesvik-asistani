"""KOBİ ölçek sınıflandırması, eleme kuralı, backfill ve endpoint."""
import importlib
import sys
from pathlib import Path

import pytest

from app.kobi import kobi_sinifi
from app.match_scoring import CompanyProfile, IncentiveProgram, calculate_matches, hard_filter
from app.matching import esles
from app.models import FinancialProfile, Tesvik

KOK = Path(__file__).resolve().parent.parent
M = 1_000_000


@pytest.mark.parametrize("calisan,ciro,sinif,kesin", [
    (5, 3 * M, "mikro", True),
    (9, 10 * M, "mikro", True),            # limit dahil
    (9, 10 * M + 1, "kucuk", True),        # çalışan <10 ama ciro >10M -> küçük
    (10, 3 * M, "kucuk", True),            # çalışan eşik DIŞI (10'dan az değil)
    (49, 100 * M, "kucuk", True),
    (49, 101 * M, "orta", True),
    (249, 1000 * M, "orta", True),
    (250, 1 * M, "buyuk", True),           # 250 çalışan -> KOBİ değil
    (200, 2000 * M, "buyuk", False),       # ciro limiti aşıyor ama bilanço bilinmiyor
])
def test_siniflandirma(calisan, ciro, sinif, kesin):
    s = kobi_sinifi(calisan, ciro)
    assert (s.sinif, s.kesin) == (sinif, kesin)


def test_bilanco_dusukse_ciro_asimi_kobiyi_bozmaz():
    """Kural 'ciro VEYA bilanço': bilanço limit altındaysa KOBİ."""
    s = kobi_sinifi(200, 2000 * M, bilanco=900 * M)
    assert (s.sinif, s.kesin, s.kobi_mi) == ("orta", True, True)
    assert kobi_sinifi(200, 2000 * M, bilanco=1500 * M).kobi_mi is False


def test_eksik_veri_siniflandirmaz():
    assert kobi_sinifi(None, 5 * M).sinif is None
    assert kobi_sinifi(5, None).sinif is None
    assert kobi_sinifi(5, None).kobi_mi is None
    with pytest.raises(ValueError):
        kobi_sinifi(-1, 1)


# ------------------------------------------------------------ eleme
KOBI_PROGRAM = IncentiveProgram(id="k", name="KOBİ Programı", max_scale="orta")
MIKRO_PROGRAM = IncentiveProgram(id="m", name="Mikro Paketi", max_scale="mikro")


def test_buyuk_isletme_kobi_programindan_elenir():
    sebepler, _ = hard_filter(CompanyProfile(employees=300, annual_revenue=50 * M), KOBI_PROGRAM)
    assert any("ölçek uygun değil" in s for s in sebepler)
    assert calculate_matches(CompanyProfile(employees=300, annual_revenue=50 * M), [KOBI_PROGRAM]) == []


def test_orta_isletme_kobi_programini_gorur_mikro_programindan_elenir():
    firma = CompanyProfile(employees=120, annual_revenue=300 * M)
    assert [m.program_id for m in calculate_matches(firma, [KOBI_PROGRAM, MIKRO_PROGRAM])] == ["k"]


def test_ciro_asimi_kesin_degilse_elenmez_isaretlenir():
    firma = CompanyProfile(employees=200, annual_revenue=2000 * M)
    sonuc = calculate_matches(firma, [KOBI_PROGRAM])
    assert sonuc and any("ölçek" in u for u in sonuc[0].unverified)


def test_eksik_veri_elemez_isaretler():
    sonuc = calculate_matches(CompanyProfile(), [KOBI_PROGRAM])
    assert sonuc and any("KOBİ sınıfı belirlenemedi" in u for u in sonuc[0].unverified)


def test_olcek_sartsiz_program_etkilenmez():
    yatay = IncentiveProgram(id="y", name="Genel")
    assert calculate_matches(CompanyProfile(employees=900, annual_revenue=5000 * M), [yatay])


# ------------------------------------------------------- canlı eşleşme
def test_esles_buyuk_isletmeye_kobi_programini_gostermez(db_session):
    db_session.add_all([
        Tesvik(kurum="X", baslik="KOBİ Desteği", ozet="o", detay="d", kaynak_url="https://t/k",
               uygunluk_kriterleri={"sektorler": ["genel"], "max_olcek": "orta"}),
        Tesvik(kurum="X", baslik="Genel Destek", ozet="o", detay="d", kaynak_url="https://t/g",
               uygunluk_kriterleri={"sektorler": ["genel"]}),
    ])
    db_session.commit()
    buyuk = [s.tesvik.baslik for s in esles(
        FinancialProfile(sektor="imalat", calisan_sayisi=400, yillik_ciro=2_000 * M), db_session)]
    kobi = [s.tesvik.baslik for s in esles(
        FinancialProfile(sektor="imalat", calisan_sayisi=30, yillik_ciro=20 * M), db_session)]
    assert "KOBİ Desteği" not in buyuk and "Genel Destek" in buyuk
    assert "KOBİ Desteği" in kobi


# --------------------------------------------------------------- backfill
@pytest.fixture
def betik():
    sys.path.insert(0, str(KOK))
    return importlib.import_module("scripts.backfill_olcek_kriterleri")


@pytest.mark.parametrize("baslik,beklenen", [
    ("KOBİ Dijital Dönüşüm Destek Programı", "orta"),
    ("1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç Destek Programı", "orta"),
    ("COSME – İŞLETMELERİN VE KOBİ'LERİN REKABET EDEBİLİRLİĞİ PROGRAMI", "orta"),
    ("MİKRO İŞLETMELER DESTEK PAKETİ", "mikro"),
    ("Küçük İşletme Can Suyu Kredisi", "kucuk"),
    ("Yatırım Destek Paketi", None),
    ("Girişimci Destek Programı", None),
    ("Destek (KOBİ ve KOBİ Dışı İşletmeler)", None),   # KOBİ dışını da kabul eder
])
def test_baslik_esleme(betik, baslik, beklenen):
    sonuc = betik.olcek_bul(baslik)
    assert (sonuc[0] if sonuc else None) == beklenen


def test_backfill_dry_run_yazmaz_ve_idempotent(betik, db_session):
    t = Tesvik(kurum="K", baslik="KOBİ Finansman Programı", ozet="o", detay="d", kaynak_url="https://t/b",
               uygunluk_kriterleri={"sektorler": ["genel"], "tutar_niteligi": "hibe"})
    db_session.add(t)
    db_session.commit()
    assert betik.calistir(db_session, dry_run=True)["degisen"] == 1
    db_session.refresh(t)
    assert "max_olcek" not in t.uygunluk_kriterleri
    assert betik.calistir(db_session)["degisen"] == 1
    db_session.refresh(t)
    assert t.uygunluk_kriterleri["max_olcek"] == "orta" and t.uygunluk_kriterleri["tutar_niteligi"] == "hibe"
    ikinci = betik.calistir(db_session)
    assert ikinci["degisen"] == 0 and ikinci["zaten_var"] == 1


# --------------------------------------------------------------- endpoint
def test_kobi_endpoint(client):
    r = client.get("/api/kobi-sinifi", params={"calisan": 30, "ciro": 80_000_000})
    assert r.status_code == 200
    d = r.json()
    assert d["sinif"] == "kucuk" and d["kobi_mi"] is True and d["esikler"]["orta"]["mali_limit_tl"] == 1e9
    assert client.get("/api/kobi-sinifi", params={"calisan": -1}).status_code == 422
