"""app/eticaret_destek_hesaplayici.py testleri (5986 sayılı E-İhracat Destekleri Kararı).

Bu modül kullanıcıya PARA tutarı söylüyor; sessiz bir hesap hatası doğrudan yanlış finansal beklenti üretir.
Testler karar metnindeki kuralları sabitliyor (2026-10-08, Karar son değişiklik RG 17.01.2026):
  m.4 reklam ve m.6 fulfillment hedef ülkede +20 puan; m.8 ve m.9'a ilave puan YOK (m.16/3);
  m.9 ve m.8 yalnız hedef ülkelerde; m.10/1 Türk ürünü payı; m.16/4 %75 tavanı; 2026 üst limitleri.
Önceki sürüm komisyona da %70 uyguluyor ve statüsüz şirkete m.3/m.7 kalemlerini hesaplıyordu.
"""
import pytest

from app.eticaret_destek_hesaplayici import (
    BOLUM_LIMITI_2026,
    KALEMLER,
    EihracatDurumu,
    EihracatGirdisi,
    hesapla,
)

TAM = EihracatDurumu(sirket_turu="limited", birlik_uyesi=True, madrid_marka=True, onceki_yil_ihracat_usd=2_000_000,
                     perakende_statusu=True)


def _h(giderler, durum=TAM, **k):
    return hesapla(EihracatGirdisi(giderler=giderler, **k), durum)


@pytest.mark.parametrize("kalem,hedef,beklenen", [
    ("pazaryeri_reklam", 0.0, 50_000), ("pazaryeri_reklam", 1.0, 70_000), ("pazaryeri_reklam", 0.5, 60_000),
    ("siparis_karsilama", 1.0, 70_000), ("site_tanitim", 1.0, 70_000),
    ("pazaryeri_komisyon", 1.0, 50_000), ("pazaryeri_komisyon", 0.4, 20_000), ("pazaryeri_komisyon", 0.0, 0),
    ("cevrim_ici_magaza", 1.0, 50_000), ("cevrim_ici_magaza", 0.0, 0),
])
def test_oran_ve_hedef_ulke_kurali(kalem, hedef, beklenen):
    s = _h({kalem: 100_000}, hedef_ulke_payi=hedef)
    assert s.kalemler[0].tahmini_destek_tl == beklenen and s.kalemler[0].durum == "uygun"


def test_satis_tavanlari():
    """m.4: reklam gideri reklamdan dönen satışın %20'sini, m.6: fulfillment ülke satışının %10'unu aşamaz."""
    s = _h({"pazaryeri_reklam": 100_000, "siparis_karsilama": 100_000}, yurt_disi_satis_tl=300_000)
    r = {k.kod: k for k in s.kalemler}
    assert r["pazaryeri_reklam"].desteklenebilir_gider_tl == 60_000 and r["pazaryeri_reklam"].tahmini_destek_tl == 30_000
    assert r["siparis_karsilama"].desteklenebilir_gider_tl == 30_000 and r["siparis_karsilama"].tahmini_destek_tl == 15_000


def test_satis_girilmezse_tavan_uyarisi():
    assert any("Satış girilmedi" in n for n in _h({"pazaryeri_reklam": 10_000}).kalemler[0].notlar)


def test_kalem_ve_bolum_ust_limiti():
    assert _h({"pazaryeri_komisyon": 1e8}, hedef_ulke_payi=1.0).simdi_tl == KALEMLER["pazaryeri_komisyon"].limit_2026
    s = _h({"pazaryeri_reklam": 2e8, "siparis_karsilama": 2e8, "pazaryeri_komisyon": 1e8}, hedef_ulke_payi=1.0)
    assert abs(s.simdi_tl - BOLUM_LIMITI_2026) < 1 and any("m.10/2" in n for n in s.notlar)


def test_turk_urun_payi():
    assert _h({"pazaryeri_reklam": 100_000}, turk_urun_payi=0.5).simdi_tl == 25_000


@pytest.mark.parametrize("tur,simdi,hazirlik,adim", [("sahis", 0, 50_000, ["sirket"]), ("yok", 0, 50_000, ["sirket"]),
                                                     ("limited", 50_000, 0, []), ("kooperatif", 50_000, 0, [])])
def test_sirket_turu(tur, simdi, hazirlik, adim):
    s = _h({"pazaryeri_reklam": 100_000}, EihracatDurumu(sirket_turu=tur, birlik_uyesi=True, madrid_marka=True))
    assert (s.simdi_tl, s.hazirlikla_tl, s.adimlar) == (simdi, hazirlik, adim)
    if tur == "sahis":
        assert "Konsorsiyumu" in s.kalemler[0].engeller[0]


def test_birlik_ve_madrid_hazirlik_adimi():
    s = _h({"pazaryeri_reklam": 100_000, "cevrim_ici_magaza": 100_000}, hedef_ulke_payi=1.0,
           durum=EihracatDurumu(sirket_turu="limited", birlik_uyesi=False, madrid_marka=False,
                                onceki_yil_ihracat_usd=2_000_000))
    r = {k.kod: k for k in s.kalemler}
    assert r["pazaryeri_reklam"].durum == "hazirlik" and s.adimlar == ["birlik_uyeligi", "madrid_marka"]
    # Çevrim içi mağazada (m.8) Madrid şartı yok; birlik üyeliği var.
    assert not any("Madrid" in e for e in r["cevrim_ici_magaza"].engeller)


def test_bilinmeyen_durum_teyit():
    s = _h({"pazaryeri_reklam": 100_000}, durum=None)
    assert s.kalemler[0].durum == "teyit" and s.teyitle_tl == 50_000 and s.simdi_tl == 0
    assert s.aylik_bekleme_tl == round(50_000 / 12, 2)


def test_esik_kapatir():
    d = EihracatDurumu(sirket_turu="limited", birlik_uyesi=True, madrid_marka=True, onceki_yil_ihracat_usd=400_000)
    s = _h({"cevrim_ici_magaza": 100_000, "site_tanitim": 100_000}, d, hedef_ulke_payi=1.0)
    assert {k.kod: (k.durum, k.tahmini_destek_tl) for k in s.kalemler} == {
        "cevrim_ici_magaza": ("kapali", 0), "site_tanitim": ("kapali", 0)}
    assert "5973 m.12" in s.kalemler[1].engeller[0]


def test_taninmayan_ve_eski_kalemler_hesaba_girmez():
    """m.3 pazara giriş raporu ve m.7 entegrasyon yalnız statü sahiplerine; depo kirası 5973'te."""
    s = _h({"pazara_giris_raporu": 50_000, "pazaryeri_entegrasyon": 30_000, "yurt_disi_depo_kirasi": 1,
            "pazaryeri_reklam": 10_000})
    assert [k.kod for k in s.kalemler] == ["pazaryeri_reklam"]


@pytest.mark.parametrize("tutar", [0, -1, -50_000, None])
def test_sifir_ve_negatif_tutarlar_atlanir(tutar):
    s = _h({"pazaryeri_reklam": tutar})
    assert s.kalemler == [] and s.simdi_tl == 0.0
    assert any("Hiçbir desteklenen gider kalemi girilmedi" in n for n in s.notlar)


def test_bos_girdi_coksmez():
    assert hesapla(EihracatGirdisi(giderler=None)).kalemler == []


def test_ileriye_donuk_ve_kademe_notlari_her_zaman_var():
    for s in (_h({"pazaryeri_reklam": 5_000_000}), _h({})):
        birlesik = " ".join(s.notlar)
        assert "Ön onaydan önceki harcama desteklenmez" in birlesik and "kademe" in birlesik


def test_kurusa_yuvarlama():
    s = _h({"pazaryeri_reklam": 33_333.33})
    assert s.kalemler[0].tahmini_destek_tl == round(33_333.33 * 0.5, 2)


def test_api_ucu(client, test_user_token):
    h = {"Authorization": f"Bearer {test_user_token}"}
    r = client.post("/api/eticaret/destek-hesapla", headers=h, json={
        "giderler": {"pazaryeri_reklam": 120_000, "pazaryeri_komisyon": 60_000}, "hedef_ulke_payi": 1,
        "sirket_turu": "limited", "ihracatci_birligi_uyesi_mi": True, "madrid_marka_tescili_var_mi": True})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["simdi_tl"] == 84_000 + 30_000 and d["aylik_bekleme_tl"] == 9_500
    assert client.post("/api/eticaret/destek-hesapla", headers=h,
                       json={"giderler": {"pazara_giris_raporu": 1}}).status_code == 422
