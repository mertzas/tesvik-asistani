"""Açık dışlama (haric_mi) uçtan uca: şema -> adaptör -> eleme -> canlı eşleşme."""
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.match_adapter import program_from_tesvik
from app.match_scoring import CompanyProfile, IncentiveProgram, calculate_matches, hard_filter
from app.matching import esles
from app.models import FinancialProfile, Tesvik, TesvikNace
from app.nace_hiyerarsi import exclusion_status

from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


# --------------------------------------------------------- dışlama durumu
@pytest.mark.parametrize("isletme,haric,beklenen", [
    ("12", ["12"], "haric"),            # tam eşit
    ("12.00", ["12"], "haric"),         # işletme hariç kolun altında
    ("25.40", ["25.4"], "haric"),
    ("10.71", ["12"], "degil"),
    ("C", ["12"], "belirsiz"),          # işletme geniş: hangi dalda olduğu bilinmiyor
    ("10", ["10.71"], "belirsiz"),
    (None, ["12"], "degil"),            # kod yoksa elenemez
    ("12", [], "degil"),
    ("62.01", ["K"], "haric"),          # kısım düzeyinde dışlama
])
def test_dislama_durumu(isletme, haric, beklenen):
    assert exclusion_status(isletme, haric) == beklenen


# ------------------------------------------------------------ eleme motoru
IMALAT_TUTUNSUZ = IncentiveProgram(
    id="imalat", name="İmalat Desteği (tütün ve silah hariç)",
    nace_codes=["C"], excluded_nace_codes=["12", "25.4"])


def test_tutun_ureticisi_imalat_programindan_elenir():
    """Sessiz regülasyon hatası: hariç kol bilinmediğinde tütün üreticisi C ile
    tam uyum skoru alıyordu."""
    tutun = CompanyProfile(nace_codes=["12.00"])
    sebepler, _ = hard_filter(tutun, IMALAT_TUTUNSUZ)
    assert any("hariç tutulmuş" in s for s in sebepler)
    assert calculate_matches(tutun, [IMALAT_TUTUNSUZ]) == []


def test_gida_ureticisi_ayni_programi_gorur():
    sonuc = calculate_matches(CompanyProfile(nace_codes=["10.71"]), [IMALAT_TUTUNSUZ])
    assert [m.program_id for m in sonuc] == ["imalat"]
    assert sonuc[0].breakdown["sektor"].score == 100.0


def test_genis_kodlu_isletme_elenmez_ama_dogrulanamadi_diye_isaretlenir():
    sonuc = calculate_matches(CompanyProfile(nace_codes=["C"]), [IMALAT_TUTUNSUZ])
    assert sonuc and any("hariç tutulan kol" in u for u in sonuc[0].unverified)


def test_yatay_programda_hariç_kol_de_elenir():
    prog = IncentiveProgram(id="y", name="Yatay (finans hariç)", excluded_nace_codes=["L"])
    assert calculate_matches(CompanyProfile(nace_codes=["64.19"]), [prog]) == []
    assert calculate_matches(CompanyProfile(nace_codes=["10.71"]), [prog])


def test_hari_kodu_gecersizse_model_hata_verir():
    with pytest.raises(ValueError):
        IncentiveProgram(id="x", name="x", excluded_nace_codes=["Z.99"])


# --------------------------------------------------------------- adaptör
def test_adaptor_hedef_ve_haric_satirlarini_ayirir():
    t = Tesvik(id=5, kurum="K", baslik="B", uygunluk_kriterleri={})
    t.nace_kayitlari = [TesvikNace(nace_prefix="C", haric_mi=False),
                        TesvikNace(nace_prefix="12", haric_mi=True)]
    p = program_from_tesvik(t)
    assert p.nace_codes == ["C"] and p.excluded_nace_codes == ["12"]


# ---------------------------------------------------------- canlı eşleşme
def _program(db):
    t = Tesvik(kurum="X", baslik="İmalat Desteği", ozet="o", detay="d", kaynak_url="https://t/h",
               uygunluk_kriterleri={"sektorler": ["genel"]})
    t.nace_kayitlari = [TesvikNace(nace_prefix="C", kaynak="llm_extraction"),
                        TesvikNace(nace_prefix="12", kaynak="llm_extraction", haric_mi=True)]
    db.add(t)
    db.commit()


def test_esles_tutun_profili_elenir_gida_profili_gorur(db_session):
    _program(db_session)
    tutun = [s.tesvik.baslik for s in esles(FinancialProfile(sektor="imalat", nace_kodu="12.00"), db_session)]
    gida = [s.tesvik.baslik for s in esles(FinancialProfile(sektor="imalat", nace_kodu="10.71"), db_session)]
    assert "İmalat Desteği" not in tutun and "İmalat Desteği" in gida


def test_esles_nace_girilmemisse_dislama_uyarisi(db_session):
    _program(db_session)
    sonuc = {s.tesvik.baslik: s for s in esles(FinancialProfile(sektor="imalat"), db_session)}
    assert any("kapsam dışıdır" in e and "12" in e for e in sonuc["İmalat Desteği"].eksik_kriterler)


# ------------------------------------------------------------------ göç
def test_haric_mi_gocu_upgrade_downgrade(tmp_path, monkeypatch):
    from app import models
    db_yolu = tmp_path / "g.db"
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db_yolu}")
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "migrations"))
    motor = create_engine(f"sqlite:///{db_yolu}")

    command.upgrade(cfg, "head")
    kolonlar = {c["name"]: c for c in inspect(motor).get_columns("tesvik_nace_association")}
    assert "haric_mi" in kolonlar and kolonlar["haric_mi"]["nullable"] is False

    command.downgrade(cfg, "c8d2e4f6a012")
    assert "haric_mi" not in {c["name"] for c in inspect(motor).get_columns("tesvik_nace_association")}
    command.upgrade(cfg, "head")
    assert "haric_mi" in {c["name"] for c in inspect(motor).get_columns("tesvik_nace_association")}
