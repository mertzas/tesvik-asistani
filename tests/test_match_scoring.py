"""app/match_scoring.py testleri (saf fonksiyonlar; veritabanı/ağ yok)."""
import pytest

from app.match_scoring import (
    CompanyProfile,
    IncentiveProgram,
    calculate_matches,
    hard_filter,
)

KGF_SAVUNMA = IncentiveProgram(
    id="kgf-savunma", name="KGF Savunma Sanayii Tedarikçi Destek Programı",
    institution="KGF", support_type="kefalet",
    exclusive_target_group=True, target_group_tags={"savunma_sanayii"},
)
GENEL_KOBI = IncentiveProgram(
    id="kobi-genel", name="Genel KOBİ Destek Paketi", support_type="hibe",
)
TURIZM = IncentiveProgram(
    id="turizm", name="Turizm Yatırım Teşviki", support_type="hibe",
    nace_codes=["55.10.01"], priority_regions=[4],
)
MIKRO_KREDI = IncentiveProgram(
    id="mikro", name="Mikro İşletme Kredisi", support_type="kredi",
    min_employees=1, max_employees=9,
)


def _ids(sonuc):
    return [m.program_id for m in sonuc]


# ------------------------------------------------------------ Senaryo A
def test_tarim_isletmesi_kgf_savunmada_elenir():
    tarim = CompanyProfile(province="Konya", employees=6, nace_codes=["01.11"])
    sebepler, _ = hard_filter(tarim, KGF_SAVUNMA)
    assert any("hedef kitle" in s for s in sebepler)

    sonuc = calculate_matches(tarim, [KGF_SAVUNMA, GENEL_KOBI])
    assert "kgf-savunma" not in _ids(sonuc), "elenen program skorlanmamalı"
    assert _ids(sonuc) == ["kobi-genel"]


def test_savunma_etiketli_isletme_kgf_savunmayi_gorur():
    firma = CompanyProfile(province="Ankara", tags={"Savunma_Sanayii"})
    assert _ids(calculate_matches(firma, [KGF_SAVUNMA])) == ["kgf-savunma"]


# ------------------------------------------------------------ Senaryo B
def test_otel_sektorel_turizm_genel_kobiden_yuksek_skorlu():
    otel = CompanyProfile(province="Van", employees=30, nace_codes=["55.10.01"])
    sonuc = {m.program_id: m for m in calculate_matches(otel, [GENEL_KOBI, TURIZM])}

    assert sonuc["turizm"].breakdown["sektor"].score == 100.0
    assert sonuc["kobi-genel"].breakdown["sektor"].score == 40.0
    assert sonuc["turizm"].total_score > sonuc["kobi-genel"].total_score
    # Van 6. bölge; turizm programı 4. bölgeyi önceliklendiriyor -> ulusal puan
    assert sonuc["turizm"].breakdown["bolge"].score == 50.0

    sirali = calculate_matches(otel, [GENEL_KOBI, TURIZM])
    assert _ids(sirali)[0] == "turizm"


def test_oncelikli_bolgede_bolge_puani_yuzdur():
    otel = CompanyProfile(province="Antalya", region=4, nace_codes=["55.10.01"])
    m = calculate_matches(otel, [TURIZM])[0]
    assert m.breakdown["bolge"].score == 100.0
    assert "4. Bölge" in " ".join(m.match_reasons)


# ------------------------------------------------------------ Senaryo C
def test_elli_calisanli_firma_mikro_krediden_elenir():
    firma = CompanyProfile(province="İzmir", employees=50)
    sebepler, _ = hard_filter(firma, MIKRO_KREDI)
    assert any("azami 9" in s for s in sebepler)
    assert calculate_matches(firma, [MIKRO_KREDI, GENEL_KOBI]) \
        and "mikro" not in _ids(calculate_matches(firma, [MIKRO_KREDI, GENEL_KOBI]))


# ------------------------------------------------------- diğer davranışlar
def test_il_kisitli_program_dis_ildeki_isletmeyi_eler():
    prog = IncentiveProgram(id="doğu", name="Doğu Kalkınma", eligible_regions=[5, 6],
                            eligible_provinces=["Van"])
    assert calculate_matches(CompanyProfile(province="İzmir"), [prog]) == []
    assert _ids(calculate_matches(CompanyProfile(province="Van"), [prog])) == ["doğu"]
    # il yazımı/aksan farkı elemeye yol açmamalı
    assert _ids(calculate_matches(CompanyProfile(province="VAN"), [prog])) == ["doğu"]


def test_bilinmeyen_il_elemez_ama_dogrulanamadi_diye_isaretler():
    prog = IncentiveProgram(id="doğu", name="Doğu Kalkınma", eligible_regions=[6])
    m = calculate_matches(CompanyProfile(), [prog])[0]
    assert any("il/bölge" in u for u in m.unverified)


def test_bolge_ilden_turetilir():
    p = CompanyProfile(province="Van")
    assert p.effective_region == 6


def test_sektor_kilitli_program_eslesmeyen_sektorde_elenir():
    otel = CompanyProfile(nace_codes=["55.10.01"])
    tarim_prog = IncentiveProgram(id="tarim", name="Tarım Destek", nace_codes=["01.11"])
    assert calculate_matches(otel, [tarim_prog]) == []
    assert _ids(calculate_matches(otel, [tarim_prog], strict_sector=False)) == ["tarim"]


@pytest.mark.parametrize("program_kodu,beklenen", [
    ("55.10.01", 100.0),   # eşit
    ("55.10", 100.0),      # program üst düzey: işletmeyi kapsar
    ("55.1", 100.0),
    ("55", 100.0),
    ("I", 100.0),          # tüm kısım
    ("55.10.02", 30.0),    # aynı bölüm, farklı dal
    ("56.10", 0.0),        # başka bölüm (aynı kısım olsa da)
])
def test_nace_hiyerarsi_puanlari(program_kodu, beklenen):
    prog = IncentiveProgram(id="p", name="P", nace_codes=[program_kodu])
    sonuc = calculate_matches(CompanyProfile(nace_codes=["55.10.01"]), [prog], strict_sector=False)
    assert sonuc[0].breakdown["sektor"].score == beklenen


def test_olcek_puani_sinira_yaklastikca_azalir():
    prog = IncentiveProgram(id="p", name="P", min_employees=10, max_employees=50)
    orta = calculate_matches(CompanyProfile(employees=30), [prog])[0]
    sinir = calculate_matches(CompanyProfile(employees=50), [prog])[0]
    assert orta.breakdown["olcek"].score == 100.0
    assert sinir.breakdown["olcek"].score == pytest.approx(50.0)
    assert orta.total_score > sinir.total_score


def test_destek_turu_tercihi_puani_belirler():
    firma = CompanyProfile(preferred_support_types=["hibe", "kredi"])
    hibe = IncentiveProgram(id="h", name="H", support_type="hibe")
    kredi = IncentiveProgram(id="k", name="K", support_type="kredi")
    kefalet = IncentiveProgram(id="f", name="F", support_type="kefalet")
    p = {m.program_id: m.breakdown["destek_turu"].score
         for m in calculate_matches(firma, [hibe, kredi, kefalet])}
    assert p == {"h": 100.0, "k": 75.0, "f": 25.0}


def test_esik_puan_filtreler_ve_sonuc_azalan_siralidir():
    otel = CompanyProfile(province="Antalya", region=4, nace_codes=["55.10.01"])
    hepsi = calculate_matches(otel, [GENEL_KOBI, TURIZM])
    assert [m.total_score for m in hepsi] == sorted(
        (m.total_score for m in hepsi), reverse=True)
    esik = hepsi[0].total_score
    assert _ids(calculate_matches(otel, [GENEL_KOBI, TURIZM], min_score=esik)) == _ids(hepsi)[:1]


def test_agirliklar_toplami_bir_ve_kirilim_toplama_esit():
    m = calculate_matches(CompanyProfile(nace_codes=["55.10.01"]), [TURIZM])[0]
    assert sum(c.weight for c in m.breakdown.values()) == pytest.approx(1.0)
    assert sum(c.weighted for c in m.breakdown.values()) == pytest.approx(m.total_score, abs=0.1)


def test_deterministik():
    firma = CompanyProfile(province="Van", employees=30, nace_codes=["55.10.01"])
    progs = [GENEL_KOBI, TURIZM, MIKRO_KREDI, KGF_SAVUNMA]
    a = calculate_matches(firma, progs)
    assert a == calculate_matches(firma, list(reversed(progs)))


# ------------------------------------------------------------- adaptör
def test_adaptor_tesvik_kriterlerini_program_modeline_cevirir():
    from app.match_adapter import company_from_profile, program_from_tesvik
    from app.models import FinancialProfile, Tesvik

    t = Tesvik(id=7, kurum="KGF", baslik="X", uygunluk_kriterleri={
        "tutar_niteligi": "kredi_kefalet", "exclusive_target_group": True,
        "target_group_tags": ["Savunma_Sanayii"], "max_employees": 9,
        "bolge_kisitli": ["hatay"]})
    p = program_from_tesvik(t)
    assert p.support_type == "kefalet" and p.max_employees == 9
    assert p.target_group_tags == {"savunma_sanayii"} and p.eligible_provinces == ["hatay"]

    c = company_from_profile(FinancialProfile(bolge="Ege", calisan_sayisi=3, ozellikler=["kadin_girisimci"]))
    assert c.province is None, "il olmayan serbest metin il kısıtıyla elemeye yol açmamalı"
    assert c.tags == {"kadin_girisimci"}
    assert company_from_profile(FinancialProfile(bolge="Van")).effective_region == 6


def test_profil_ozellikleri_gecersiz_etiketi_reddeder(client):
    from app.schemas import FinancialProfileCreate
    with pytest.raises(ValueError):
        FinancialProfileCreate(sektor="tarim", ozellikler=["uydurma_etiket"])
    assert FinancialProfileCreate(sektor="tarim", ozellikler=["genc_girisimci", "genc_girisimci"]
                                  ).ozellikler == ["genc_girisimci"]
