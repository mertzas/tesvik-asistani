"""Girişim modu: HUKS ön skoru (kodda, uydurmasız), mod tespiti, danışman entegrasyonu,
profil alanları ve göç."""
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app import rag
from app.girisim import (
    GIRISIM_PROMPT_EKI, VERITABANINDA_OLMAYAN_PROGRAMLAR, girisim_baglam_metni, girisim_modu_mu, huks,
)
from app.models import FinancialProfile
from app.schemas import FinancialProfileCreate

KOK = Path(__file__).resolve().parent.parent
BUGUN = date(2026, 10, 7)


def _p(**kw):
    return FinancialProfile(**kw)


# ------------------------------------------------------------------ HUKS
def test_bos_profilde_hicbir_bilesen_puanlanmaz():
    s = huks(_p(sektor="arge"), BUGUN)
    assert s.azami == 0 and s.puan == 0 and s.normalize is None
    assert set(s.eksikler) == {"NACE kodu & şirket statüsü", "Teknoloji hazırlık seviyesi (TRL)",
                               "Finansal & nakit akışı uyumu", "Ekip & Ar-Ge niteliği"}


def test_ekip_bileseni_asla_puanlanmaz():
    s = huks(_p(sektor="arge", sirket_turu="limited", nace_kodu="62.01", trl=5, yillik_ciro=2e6), BUGUN)
    assert "Ekip & Ar-Ge niteliği" in s.eksikler
    assert s.azami == 75 and s.puan == 25 + 25 + 15 and s.normalize == 87


def test_sirketlesmemis_girisim_dusuk_statu_ve_nakit_puani():
    s = {b.ad: b for b in huks(_p(sektor="arge", sirket_turu="yok", trl=3), BUGUN).bilesenler}
    assert s["NACE kodu & şirket statüsü"].puan == 10 and "1812" in s["NACE kodu & şirket statüsü"].gerekce
    assert s["Teknoloji hazırlık seviyesi (TRL)"].puan == 12
    assert s["Finansal & nakit akışı uyumu"].puan == 5


@pytest.mark.parametrize("tur,nace,beklenen", [
    ("limited", "62.01", 25), ("anonim", None, 20), ("sahis", "62.01", 15), ("kooperatif", None, 10),
])
def test_statu_puanlari(tur, nace, beklenen):
    s = {b.ad: b for b in huks(_p(sektor="arge", sirket_turu=tur, nace_kodu=nace), BUGUN).bilesenler}
    assert s["NACE kodu & şirket statüsü"].puan == beklenen


def test_sirket_yasi_gerekceye_yazilir():
    genc = huks(_p(sektor="arge", sirket_turu="limited", nace_kodu="62.01", kurulus_tarihi=date(2025, 1, 1)), BUGUN)
    eski = huks(_p(sektor="arge", sirket_turu="limited", nace_kodu="62.01", kurulus_tarihi=date(2015, 1, 1)), BUGUN)
    assert "0-3 yaş pencereli" in genc.bilesenler[0].gerekce
    assert "kapalı olabilir" in eski.bilesenler[0].gerekce


@pytest.mark.parametrize("trl,beklenen", [(1, 12), (3, 12), (4, 25), (6, 25), (7, 15), (9, 15)])
def test_trl_puanlari(trl, beklenen):
    assert huks(_p(sektor="arge", trl=trl), BUGUN).bilesenler[1].puan == beklenen


def test_finans_puanlari():
    f = lambda **kw: {b.ad: b for b in huks(_p(sektor="imalat", sirket_turu="limited", **kw), BUGUN).bilesenler}[
        "Finansal & nakit akışı uyumu"]
    assert f().puan is None
    assert f(yillik_ciro=5e6).puan == 15
    assert f(yillik_ciro=5e6, giderler={"toplam": 3e6}).puan == 25
    assert f(yillik_ciro=5e6, giderler={"toplam": 6e6}).puan == 10
    assert f(yillik_ciro=5e6, giderler={"toplam": 3e6}, ilk_yil_mi=True).puan == 20
    assert f(yillik_ciro=0).puan == 5


def test_metin_puan_ve_eksikleri_gosterir():
    m = huks(_p(sektor="arge", sirket_turu="yok", trl=4), BUGUN).metin()
    assert "HUKS ÖN SKORU" in m and "/75" in m and "değerlendirilemeyen bileşenler" in m


# ------------------------------------------------------------ mod tespiti
@pytest.mark.parametrize("profil,soru,beklenen", [
    (_p(sektor="arge", sirket_turu="yok"), "destek var mı", True),
    (_p(sektor="arge", trl=5), "destek var mı", True),
    (_p(sektor="imalat", sirket_turu="limited"), "makine alacağım", False),
    (None, "Yazılım girişimim için BiGG'e başvurabilir miyim?", True),
    (None, "prototip geliştiriyoruz, startup hibesi", True),
    (None, "buğday için dekar desteği", False),
])
def test_girisim_modu_tespiti(profil, soru, beklenen):
    assert girisim_modu_mu(profil, soru) is beklenen


def test_baglam_metni_huks_ve_eksik_program_listesi_icerir():
    m = girisim_baglam_metni(_p(sektor="arge", sirket_turu="yok", trl=4), BUGUN)
    assert "GİRİŞİM MODU BİLGİLERİ" in m and "HUKS ÖN SKORU" in m
    assert "SİSTEMDE KAYDI OLMAYAN PROGRAMLAR" in m and "5448" in m and "KOBİGEL" in m
    assert all(p.split(" (")[0] in m for p in VERITABANINDA_OLMAYAN_PROGRAMLAR)


def test_prompt_eki_korumalari_iceriyor():
    for ifade in ["BÖLÜM 1", "BÖLÜM 2", "BÖLÜM 3", "BÖLÜM 4", "HUKS ÖN SKORUNU aynen aktar",
                  "kendin skor hesaplama", "bağlamda yok", "ASLA tahmini rakam", "garanti onay",
                  "SİSTEMDE KAYDI OLMAYAN PROGRAMLAR", "iki kuruma sunulamaz"]:
        assert ifade in GIRISIM_PROMPT_EKI, ifade


# ------------------------------------------------- danışman entegrasyonu
def test_answer_girisim_modunda_sistem_eki_ve_huks_blogu_gonderir(monkeypatch):
    kayit = FinancialProfile(sektor="arge", sirket_turu="yok", trl=4)
    gorulen = {}

    def sahte(query, matches, profil, notlar=None, elenen="", sistem_eki=""):
        gorulen.update(elenen=elenen, sistem_eki=sistem_eki)
        return "yanıt"

    monkeypatch.setattr(rag, "_claude_cevap", sahte)
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5, **kw: [rag.Tesvik(kurum="TUBITAK", baslik="1812", ozet="o")])
    rag.answer("Yazılım girişimim için hangi hibeler var?", {"sektör": "arge"}, profil_kaydi=kayit)
    assert gorulen["sistem_eki"] == GIRISIM_PROMPT_EKI
    assert "HUKS ÖN SKORU" in gorulen["elenen"] and "SİSTEMDE KAYDI OLMAYAN" in gorulen["elenen"]


def test_answer_normal_modda_sistem_eki_gondermez(monkeypatch):
    gorulen = {}

    def sahte(query, matches, profil, notlar=None, elenen="", sistem_eki=""):
        gorulen["sistem_eki"] = sistem_eki
        return "yanıt"

    monkeypatch.setattr(rag, "_claude_cevap", sahte)
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5, **kw: [rag.Tesvik(kurum="X", baslik="Y", ozet="o")])
    rag.answer("buğday için dekar desteği", {"sektör": "tarim"},
               profil_kaydi=FinancialProfile(sektor="tarim", sirket_turu="sahis"))
    assert gorulen["sistem_eki"] == ""


def test_riza_yokken_girisim_modu_llm_cagirmaz(monkeypatch):
    cagrildi = []
    monkeypatch.setattr(rag, "_claude_cevap", lambda *a, **k: cagrildi.append(1) or "x")
    monkeypatch.setattr(rag, "retrieve", lambda q, limit=5, **kw: [rag.Tesvik(kurum="X", baslik="Y", ozet="o")])
    rag.answer("startup hibesi", None, llm_kullan=False, profil_kaydi=FinancialProfile(sektor="arge", sirket_turu="yok"))
    assert cagrildi == []


# --------------------------------------------------------- şema ve uç nokta
def test_sema_dogrulama():
    p = FinancialProfileCreate(sektor="arge", sirket_turu=" Limited ", kurulus_tarihi="2024-03-01", trl=5)
    assert p.sirket_turu == "limited" and p.kurulus_tarihi == date(2024, 3, 1)
    assert FinancialProfileCreate(sektor="arge", sirket_turu="").sirket_turu is None
    with pytest.raises(ValueError):
        FinancialProfileCreate(sektor="arge", sirket_turu="holding")
    with pytest.raises(ValueError):
        FinancialProfileCreate(sektor="arge", trl=10)
    with pytest.raises(ValueError):
        FinancialProfileCreate(sektor="arge", kurulus_tarihi="2099-01-01")


def test_profil_ucu_alanlari_kaydeder_ve_danismana_tasir(client, monkeypatch):
    import app.main as anamodul
    gorulen = {}
    monkeypatch.setattr(anamodul, "answer", lambda soru, profil=None, llm_kullan=True, **kw: gorulen.update(profil=profil) or "y")
    r = client.post("/api/auth/signup", json={"email": "g1@example.com", "password": "GucluSifre123",
                                              "full_name": "G", "company_name": "G", "ai_yurtdisi_riza": True})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.put("/api/profil", headers=h, json={"sektor": "arge", "sirket_turu": "yok", "trl": 4,
                                                   "kurulus_tarihi": "2025-05-01"})
    assert r.status_code == 200 and r.json()["sirket_turu"] == "yok" and r.json()["trl"] == 4
    client.post("/api/sor", json={"question": "girişim hibesi"}, headers=h)
    assert gorulen["profil"]["şirket türü"] == "yok" and gorulen["profil"]["TRL (teknoloji hazırlık seviyesi)"] == 4
    assert gorulen["profil"]["kuruluş tarihi"] == "2025-05-01"


def test_kvkk_metni_yeni_alanlari_sayiyor():
    html = (KOK / "app/static/kvkk.html").read_text(encoding="utf-8")
    assert "sirket_turu" in html and "TRL" in html


def test_goc_upgrade_downgrade(tmp_path, monkeypatch):
    from app import models
    db_yolu = tmp_path / "g.db"
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db_yolu}")
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "migrations"))
    motor = create_engine(f"sqlite:///{db_yolu}")
    yeni = {"sirket_turu", "kurulus_tarihi", "trl"}
    command.upgrade(cfg, "head")
    assert yeni <= {c["name"] for c in inspect(motor).get_columns("financial_profiles")}
    command.downgrade(cfg, "e1f4a6b8c234")
    assert not (yeni & {c["name"] for c in inspect(motor).get_columns("financial_profiles")})
    command.upgrade(cfg, "head")
