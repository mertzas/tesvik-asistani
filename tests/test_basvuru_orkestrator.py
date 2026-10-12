"""Deterministik e-ihracat başvuru orkestratörü (app/basvuru_orkestrator.py)."""
from datetime import date
from types import SimpleNamespace as N

from app import basvuru_orkestrator as bo


def _program(kalem, baslik, tutar):
    return bo.program_kaydindan(kalem, N(id=1, baslik=baslik, tesvil_tutari=tutar, kontrol_listesi=[]))


def test_self_test_gecer():
    assert bo._self_test() == 0


def test_kayittan_oran_ve_tavan_okunur_hedef_orani_yalniz_yaziliysa():
    p = _program("siparis_karsilama", "Sipariş Karşılama (5986 sayılı Karar m.6)",
                 "%50 (hedef ülkelerde %70); ülkedeki e-ticaret satışlarının %10'una kadar; 2026 şirketler için yıllık "
                 "36.993.646 TL; ülke başına 3 yıl")
    assert (p.oran, p.hedef_oran, p.tavan_try) == (50, 70, 36993646.0)
    k = _program("pazaryeri_komisyon", "Komisyon (5986 sayılı Karar m.9)", "%50; 2026 şirketler için yıllık 3.698.274 TL")
    assert k.hedef_oran is None


def test_siparis_karsilama_ulke_satisinin_yuzde_onu():
    p = {"siparis_karsilama": _program("siparis_karsilama", "x", "%50 (hedef ülkelerde %70); 2026 yıllık 36.993.646 TL")}
    h = [bo.Harcama(1, "FBA", "siparis_karsilama", 100000, "TRY", False, 0.2, None, date(2026, 9, 1), "Almanya", None,
                    "sirket_banka", False, None, 100000.0)]
    k, _ = bo.hesapla({"ulke_eticaret_satis_try": {"Almanya": 500000}}, h, p, ["Almanya"])
    assert k[0]["talep_edilen_hakedis_try"] == 50000.0 and "%10" in k[0]["not"]


def test_cok_para_birimli_kalem_tl_olarak_raporlanir():
    p = {"pazaryeri_komisyon": _program("pazaryeri_komisyon", "x", "%50; 2026 yıllık 3.698.274 TL")}
    h = [bo.Harcama(1, "k", "pazaryeri_komisyon", 100, "USD", False, 0.2, 40, date(2026, 9, 1), None, None,
                    "sirket_banka", False, None, 4000.0),
         bo.Harcama(2, "k2", "pazaryeri_komisyon", 1000, "TRY", False, 0.2, None, date(2026, 9, 2), None, None,
                    "sirket_banka", False, None, 1000.0)]
    k, _ = bo.hesapla({}, h, p, [])
    assert k[0]["harcama_para_birimi"] == "TRY" and k[0]["harcama_tutari_orijinal"] == 5000.0


def test_statusuz_site_reklami_ret_ve_rota():
    p = {"site_tanitim": _program("site_tanitim", "x", "%50 (hedef ülkelerde %70); 2026 yıllık 123.315.792 TL")}
    h = [bo.Harcama(1, "Google Ads", "site_tanitim", 1000, "TRY", False, 0.2, None, date(2026, 9, 1), None, None,
                    "sirket_kart", False, None, 1000.0)]
    bo.mevzuat_esle({"sirket_turu": "limited"}, h, p, "", date(2026, 10, 12))
    k, _ = bo.hesapla({}, h, p, [])
    assert k[0]["onay_durumu"] == "RET" and any("statüsüz kalemler" in r for r in bo.onarim_rotalari(k))


def test_json_semasi_alanlari():
    alanlar = {"kalem_adi", "harcama_tutari_orijinal", "harcama_para_birimi", "harcama_tutari_try", "destek_orani_yuzde",
               "hedef_ulke_ilave_puani", "net_destek_orani", "mevzuat_tavan_try", "talep_edilen_hakedis_try",
               "onay_durumu", "not"}
    p = {"pazaryeri_komisyon": _program("pazaryeri_komisyon", "x", "%50; 2026 yıllık 3.698.274 TL")}
    h = [bo.Harcama(1, "k", "pazaryeri_komisyon", 100, "TRY", False, 0.2, None, date(2026, 9, 1), None, None,
                    "sirket_banka", False, None, 100.0)]
    k, _ = bo.hesapla({}, h, p, [])
    assert set(k[0]) == alanlar and k[0]["onay_durumu"] in ("UYGUN", "SARTLI", "RET")
