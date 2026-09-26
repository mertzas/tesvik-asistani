"""app/eticaret_destek_hesaplayici.py testleri.

Bu modül kullanıcıya PARA tutarı söylüyor ("tahmini geri ödeme"); sessiz bir
hesap hatası doğrudan yanlış finansal beklenti üretir. Testler hem aritmetiği
hem de zorunlu uyarıların kaybolmamasını sabitliyor — uyarılar burada
süsleme değil: bu destek yalnızca ihracatçı birliği üyelerine açık ve üst
limitler her yıl değişiyor, uyarı düşerse kullanıcı hak etmediği bir tutarı
kesinmiş gibi okur.
"""
import pytest

from app.eticaret_destek_hesaplayici import (
    DESTEKLENEN_GIDER_KALEMLERI,
    GIDER_KALEMI_ETIKETLERI,
    HEDEF_ULKE_ORAN,
    STANDART_ORAN,
    eticaret_destek_hesapla,
)


def test_standart_oran_yuzde_elli():
    s = eticaret_destek_hesapla({"pazaryeri_komisyon": 100_000})
    assert s.uygulanan_oran == STANDART_ORAN == 0.50
    assert s.hedef_ulke_mi is False
    assert s.toplam_yillik_gider_tl == 100_000
    assert s.toplam_tahmini_geri_odeme_tl == 50_000


def test_hedef_ulke_orani_yuzde_yetmis():
    s = eticaret_destek_hesapla({"pazaryeri_komisyon": 100_000}, hedef_ulke_mi=True)
    assert s.uygulanan_oran == HEDEF_ULKE_ORAN == 0.70
    assert s.toplam_tahmini_geri_odeme_tl == 70_000


def test_birden_fazla_kalem_toplaniyor():
    s = eticaret_destek_hesapla({
        "pazara_giris_raporu": 50_000,
        "yurt_disi_depo_kirasi": 120_000,
        "pazaryeri_entegrasyon": 30_000,
    })
    assert len(s.kalemler) == 3
    assert s.toplam_yillik_gider_tl == 200_000
    assert s.toplam_tahmini_geri_odeme_tl == 100_000
    # Kalem bazlı toplam, genel toplamla tutarlı olmalı.
    assert round(sum(k.tahmini_geri_odeme_tl for k in s.kalemler), 2) == \
        s.toplam_tahmini_geri_odeme_tl


def test_taninmayan_kalem_sessizce_atlanir_ama_digerleri_hesaplanir():
    """Yazım hatası bütün hesabı çökertmemeli; ama atlanan tutar toplama
    da girmemeli - girseydi kullanıcı olmayan bir desteği görürdü."""
    s = eticaret_destek_hesapla({
        "pazaryeri_komisyon": 100_000,
        "olmayan_kalem": 999_999,
    })
    assert len(s.kalemler) == 1
    assert s.toplam_yillik_gider_tl == 100_000
    assert s.toplam_tahmini_geri_odeme_tl == 50_000


@pytest.mark.parametrize("tutar", [0, -1, -50_000, None])
def test_sifir_ve_negatif_tutarlar_atlanir(tutar):
    """Negatif gider, negatif "geri ödeme" üretip toplamı düşürürdü."""
    s = eticaret_destek_hesapla({"pazaryeri_komisyon": tutar})
    assert s.kalemler == []
    assert s.toplam_tahmini_geri_odeme_tl == 0.0
    assert any("Hiçbir desteklenen gider kalemi girilmedi" in n for n in s.notlar)


def test_bos_girdi_coksmez():
    for girdi in ({}, None):
        s = eticaret_destek_hesapla(girdi)
        assert s.kalemler == []
        assert s.toplam_yillik_gider_tl == 0.0


def test_ihracatci_birligi_uyesi_degilse_net_uyari_var():
    s = eticaret_destek_hesapla(
        {"pazaryeri_komisyon": 100_000}, ihracatci_birligi_uyesi_mi=False)
    uyarilar = " ".join(s.notlar)
    assert "KABUL EDİLMEZ" in uyarilar
    # Tahmin yine hesaplanıyor ama hangi senaryo için olduğu söylenmeli.
    assert s.toplam_tahmini_geri_odeme_tl == 50_000


def test_uyelik_bilinmiyorsa_teyit_uyarisi_var():
    s = eticaret_destek_hesapla(
        {"pazaryeri_komisyon": 100_000}, ihracatci_birligi_uyesi_mi=None)
    assert any("üyeliğiniz bilinmiyor" in n for n in s.notlar)


def test_uye_ise_uyelik_uyarisi_eklenmez():
    s = eticaret_destek_hesapla(
        {"pazaryeri_komisyon": 100_000}, ihracatci_birligi_uyesi_mi=True)
    assert not any("KABUL EDİLMEZ" in n or "bilinmiyor" in n for n in s.notlar)


def test_tahmin_oldugu_ve_ust_limit_uyarisi_her_zaman_var():
    """Bu iki uyarı hiçbir senaryoda düşmemeli: hesaplanan tutar Bakanlık'ın
    yıllık üst limitini aşabilir ve o durumda gerçek geri ödeme limitle
    sınırlı kalır."""
    for hedef in (True, False):
        s = eticaret_destek_hesapla({"pazaryeri_komisyon": 5_000_000},
                                    hedef_ulke_mi=hedef)
        birlesik = " ".join(s.notlar)
        assert "TAHMİNDİR" in birlesik
        assert "üst limit" in birlesik


def test_etiketler_tum_kalemleri_kapsiyor():
    """Etiketi olmayan bir kalem eklenirse hesaplama KeyError ile çökerdi."""
    assert set(DESTEKLENEN_GIDER_KALEMLERI) == set(GIDER_KALEMI_ETIKETLERI)
    for kalem in DESTEKLENEN_GIDER_KALEMLERI:
        s = eticaret_destek_hesapla({kalem: 1_000})
        assert len(s.kalemler) == 1
        assert s.kalemler[0].etiket == GIDER_KALEMI_ETIKETLERI[kalem]


def test_kurusa_yuvarlama():
    """Yuvarlanmamış kayan noktalı tutar arayüzde 12 haneli görünürdü."""
    s = eticaret_destek_hesapla({"pazaryeri_komisyon": 33_333.33})
    assert s.kalemler[0].tahmini_geri_odeme_tl == round(33_333.33 * 0.5, 2)
    assert s.toplam_tahmini_geri_odeme_tl == \
        round(s.toplam_tahmini_geri_odeme_tl, 2)
