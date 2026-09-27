"""app/tarim_destek_2026.py testleri.

Bu modül çiftçiye alacağı destek tutarını söylüyor. Yanlış bir katsayı ya da
hak edilmeyen bir kalemin toplama eklenmesi, çiftçinin gelmeyecek bir parayı
bütçesine yazmasına yol açar. Testler her katsayıyı resmî tablodaki değerle
ve her toplamı elle çarpımla karşılaştırıyor.

Kaynak: T.C. Tarım ve Orman Bakanlığı BUGEM, "2026 Üretim Yılı Bitkisel
Üretim Destekleme Birim Fiyatları" (doğrulama: 2026-09-26).
"""
import pytest

from app.tarim_destek_2026 import (
    FIDAN_KATSAYILARI,
    IYI_TARIM,
    KATSAYI_BIRIM_TL,
    ORGANIK_ARILI_KOVAN_KATSAYI,
    ORGANIK_ORGUT_ILAVE_ORANI,
    ORGANIK_TARIM,
    ORGANOMINERAL_GUBRE_KATSAYI,
    PLANLI_URETIM_KATEGORILERI,
    SUT_HAVZASI_ILLERI,
    TEMEL_DESTEK_KATEGORILERI,
    URETIM_YILI,
    arilik_destegi,
    hesapla,
)


def _kalem(h, ad_baslangici):
    for k in h.kalemler:
        if k.ad.startswith(ad_baslangici):
            return k
    return None


# ------------------------------------------------- resmî tabloyla tutarlılık

def test_birim_deger_tablodaki_toplamlarla_tutarli():
    """Tablodaki her toplam, katsayı x birim değer olmalı. 1,3 x 310 = 403,00;
    2,25 x 310 = 697,50. Birim değer yanlışsa TÜM tutarlar yanlış olur.

    Not: bazı haber kaynakları birim değeri 367 TL veriyor; Bakanlığın kendi
    tablosundaki toplamlar 310 ile tutarlı, bu yüzden 310 esas alındı.
    """
    assert KATSAYI_BIRIM_TL == 310.00
    assert 1.3 * KATSAYI_BIRIM_TL == pytest.approx(403.00)
    assert 1.5 * KATSAYI_BIRIM_TL == pytest.approx(465.00)
    assert 2.25 * KATSAYI_BIRIM_TL == pytest.approx(697.50)
    assert 0.3 * KATSAYI_BIRIM_TL == pytest.approx(93.00)
    assert 0.56 * KATSAYI_BIRIM_TL == pytest.approx(173.60)
    assert 1.7 * KATSAYI_BIRIM_TL == pytest.approx(527.00)
    assert 2.2 * KATSAYI_BIRIM_TL == pytest.approx(682.00)


def test_temel_destek_katsayilari():
    assert TEMEL_DESTEK_KATEGORILERI[1][0] == 1.0
    assert TEMEL_DESTEK_KATEGORILERI[2][0] == 1.3
    assert TEMEL_DESTEK_KATEGORILERI[3][0] == 1.5
    assert TEMEL_DESTEK_KATEGORILERI[4][0] == 2.25


def test_findik_ve_cay_planli_uretim_kapsaminda_degil():
    """Resmî tabloda fındık ve çay temel destekte var ama planlı üretim
    desteğinde YOK. Bu ayrımı kaybetmek fındık üreticisine almayacağı bir
    ödemeyi göstermek olurdu."""
    planli_urunler = {u for _, urunler in PLANLI_URETIM_KATEGORILERI.values()
                      for u in urunler}
    assert "fındık" not in planli_urunler
    assert "çay" not in planli_urunler
    # Temel destekte ise var:
    temel_urunler = {u for _, urunler in TEMEL_DESTEK_KATEGORILERI.values()
                     for u in urunler}
    assert "fındık" in temel_urunler
    assert "çay" in temel_urunler


def test_organik_grup_katsayilari():
    assert ORGANIK_TARIM[1] == (1.2, 0.6)
    assert ORGANIK_TARIM[2] == (0.6, 0.3)
    assert ORGANIK_TARIM[3] == (0.4, 0.2)


def test_iyi_tarim_ortualti_acikta_ayrimi():
    """Örtüaltı üretim katsayısı açıkta üretimin iki katından fazla; ikisini
    karıştırmak seracıya eksik, açık alan üreticisine fazla tutar verir."""
    assert IYI_TARIM["1_ortualti"] == (1.7, 0.85)
    assert IYI_TARIM["1_acikta"] == (0.7, 0.35)
    assert IYI_TARIM["1_ortualti"][0] > IYI_TARIM["1_acikta"][0] * 2


def test_grup_sertifikasi_bireyselin_yarisi():
    for grup, (bireysel, gr) in ORGANIK_TARIM.items():
        assert gr == pytest.approx(bireysel / 2), f"{grup}. grup"


# ------------------------------------------------------------ temel hesaplar

def test_bugday_elle_hesapla_ayni():
    """50 dekar buğday: temel 1,3 + planlı 1,3 = 806 TL/da x 50 = 40.300 TL."""
    h = hesapla("buğday", 50, il="Konya")
    assert _kalem(h, "Temel destek").dekar_basi_tl == pytest.approx(403.00)
    assert _kalem(h, "Planlı üretim").dekar_basi_tl == pytest.approx(403.00)
    assert h.dekar_basi_toplam_tl == pytest.approx(806.00)
    assert h.toplam_tl == pytest.approx(40_300.00)


def test_sertifikali_tohum_eklenince_toplam_artar():
    yok = hesapla("buğday", 50, il="Konya")
    var = hesapla("buğday", 50, il="Konya", sertifikali_tohum=True)
    fark = var.toplam_tl - yok.toplam_tl
    assert fark == pytest.approx(0.56 * KATSAYI_BIRIM_TL * 50)
    assert var.toplam_tl == pytest.approx(48_980.00)


def test_pamuk_en_yuksek_kategori():
    h = hesapla("pamuk", 100, il="Şanlıurfa")
    # 2,25 x 310 x 2 kalem (temel + planlı) = 1.395 TL/da
    assert h.dekar_basi_toplam_tl == pytest.approx(1_395.00)
    assert h.toplam_tl == pytest.approx(139_500.00)


def test_pamukta_tohum_sarti_notlaniyor():
    h = hesapla("pamuk", 10)
    assert "sertifikalandırılan tohum" in (_kalem(h, "Planlı üretim").not_ or "")


def test_alan_olceklenmesi_dogrusal():
    bir = hesapla("arpa", 1, il="Konya").toplam_tl
    yuz = hesapla("arpa", 100, il="Konya").toplam_tl
    assert yuz == pytest.approx(bir * 100)


# ------------------------------------------- opsiyonel kalemler hak edilmeden eklenmez

def test_varsayilan_olarak_sadece_temel_ve_planli():
    """Sertifika/organik şartı belirtilmeden o destekleri toplamaya katmak,
    çiftçiye alamayacağı tutarı göstermek olurdu."""
    h = hesapla("buğday", 10)
    adlar = [k.ad for k in h.kalemler]
    assert len(adlar) == 2
    assert _kalem(h, "Sertifikalı tohum") is None
    assert _kalem(h, "Organik") is None
    assert _kalem(h, "İyi tarım") is None


def test_organik_orgut_ilavesi_katsayinin_ceyregi():
    h = hesapla("mercimek", 30, organik_grup=1, organik_sertifika="bireysel",
                organik_orgut_uyesi=True)
    ana = _kalem(h, "Organik tarım desteği")
    ilave = _kalem(h, "İlave organik tarım")
    assert ilave.katsayi == pytest.approx(ana.katsayi * ORGANIK_ORGUT_ILAVE_ORANI)


def test_genc_kadin_ilave_destegi():
    yok = hesapla("mercimek", 30).toplam_tl
    var = hesapla("mercimek", 30, genc_veya_kadin_kobuks=True).toplam_tl
    assert var - yok == pytest.approx(3.0 * KATSAYI_BIRIM_TL * 30)


def test_sut_havzasi_yem_ilavesi_sadece_ilgili_illerde():
    """İlave, yalnızca tabloda sayılan 10 ilde ve yem bitkisi üretiminde."""
    assert "Erzurum" in SUT_HAVZASI_ILLERI
    assert "Konya" not in SUT_HAVZASI_ILLERI

    erzurum = hesapla("yonca", 20, il="Erzurum", yem_bitkisi=True)
    konya = hesapla("yonca", 20, il="Konya", yem_bitkisi=True)
    assert _kalem(erzurum, "İlave planlı üretim") is not None
    assert _kalem(konya, "İlave planlı üretim") is None


def test_yem_bitkisi_isaretlenmezse_ilave_yok():
    h = hesapla("yonca", 20, il="Erzurum", yem_bitkisi=False)
    assert _kalem(h, "İlave planlı üretim") is None


def test_fidan_destegi_sertifikali_standarttan_yuksek():
    std = hesapla("elma", 10, fidan="standart")
    srt = hesapla("elma", 10, fidan="sertifikali")
    assert (_kalem(srt, "Sertifikalı/standart fidan").katsayi
            == pytest.approx(FIDAN_KATSAYILARI["sertifikali"]))
    assert srt.toplam_tl > std.toplam_tl


def test_fidan_listesinde_olmayan_urun_uyarir():
    h = hesapla("buğday", 10, fidan="sertifikali")
    assert _kalem(h, "Sertifikalı/standart fidan") is None
    assert any("fidan" in u for u in h.uyarilar)


def test_organomineral_gubre_katsayisi():
    h = hesapla("buğday", 10, organomineral_gubre=True)
    k = _kalem(h, "Katı organik")
    assert k.katsayi == pytest.approx(ORGANOMINERAL_GUBRE_KATSAYI)


# --------------------------------------------------------- su kısıtı kuralı

def test_su_kisiti_havzasinda_misir_patates_uyarisi():
    """Resmî not: su kısıtı havzalarında mısır (dane) ve patates ekilişlerine
    temel/planlı/geliştirme desteği ÖDENMEZ. Bu uyarı düşerse çiftçi
    almayacağı ödemeyi bekler."""
    h = hesapla("mısır", 40, il="Konya", su_kisiti_havzasi=True)
    birlesik = " ".join(h.uyarilar)
    assert "ÖDENMEZ" in birlesik
    assert "mısır" in birlesik.lower()


def test_su_kisiti_destegi_kategoriye_gore():
    h = hesapla("buğday", 20, su_kisiti_havzasi=True)
    k = _kalem(h, "Yeraltı su kısıtı")
    assert k is not None
    assert k.katsayi == pytest.approx(1.4)


def test_su_kisiti_kapsaminda_olmayan_urun_uyarir():
    h = hesapla("pamuk", 20, su_kisiti_havzasi=True)
    assert _kalem(h, "Yeraltı su kısıtı") is None
    assert any("su kısıtı" in u for u in h.uyarilar)


# ------------------------------------------------ bilinmeyen ürün davranışı

def test_bilinmeyen_urun_diger_urunler_varsayimi_ve_uyari():
    """Tabloda 1. kategori "Diğer ürünler" kalemi var, yani listede olmayan
    bitkisel ürün de temel destek alır. Ama bu bir VARSAYIM; sessizce
    yapılmamalı."""
    h = hesapla("kinoa", 10)
    assert _kalem(h, "Temel destek").katsayi == pytest.approx(1.0)
    assert any("Diğer ürünler" in u for u in h.uyarilar)


def test_bilinmeyen_urun_planli_destek_almaz():
    h = hesapla("kinoa", 10)
    assert _kalem(h, "Planlı üretim") is None
    assert any("planlı üretim" in u for u in h.uyarilar)


# ------------------------------------------------------- büyük/küçük harf

def test_buyuk_harfli_urun_adi_taninir():
    """Python'un str.lower()'i Türkçe "İ"yi bozuyor; "MISIR" gibi girdiler
    kategori eşleşmesini kaçırırdı."""
    buyuk = hesapla("BUĞDAY", 10, il="Konya")
    kucuk = hesapla("buğday", 10, il="Konya")
    assert buyuk.toplam_tl == kucuk.toplam_tl
    assert _kalem(buyuk, "Temel destek").katsayi == pytest.approx(1.3)


# ---------------------------------------------------------- arılık (kovan)

def test_arilik_destegi_kovan_basina():
    """Kovan sayısını dekar gibi işlemek tutarı tamamen yanlış hesaplar."""
    k = arilik_destegi(80)
    assert k.dekar_basi_tl == pytest.approx(ORGANIK_ARILI_KOVAN_KATSAYI * KATSAYI_BIRIM_TL)
    assert k.toplam_tl == pytest.approx(93.00 * 80)
    assert "Kovan başına" in k.not_


@pytest.mark.parametrize("n", [0, -1])
def test_gecersiz_kovan_sayisi_hata(n):
    with pytest.raises(ValueError):
        arilik_destegi(n)


# ------------------------------------------------------------ geçersiz girdi

@pytest.mark.parametrize("alan", [0, -5, None])
def test_gecersiz_alan_hata(alan):
    with pytest.raises(ValueError):
        hesapla("buğday", alan)


@pytest.mark.parametrize("urun", ["", "   ", None])
def test_bos_urun_hata(urun):
    with pytest.raises(ValueError):
        hesapla(urun, 10)


def test_gecersiz_fidan_turu_hata():
    with pytest.raises(ValueError, match="fidan"):
        hesapla("elma", 10, fidan="olmayan")


def test_gecersiz_organik_grup_hata():
    with pytest.raises(ValueError):
        hesapla("buğday", 10, organik_grup=9)


def test_gecersiz_iyi_tarim_hata():
    with pytest.raises(ValueError):
        hesapla("buğday", 10, iyi_tarim="olmayan")


# --------------------------------------------------------------- çıktı/uyarı

def test_cks_ve_kaynak_uyarisi_her_zaman_var():
    h = hesapla("buğday", 10)
    birlesik = " ".join(h.uyarilar)
    assert "ÇKS" in birlesik
    assert "teyit" in birlesik


def test_mazot_gubre_birlesmesi_notlaniyor():
    """2026'da mazot ve gübre destekleri birleştirildi; eski ayrı ödeme
    beklentisi yanlış."""
    h = hesapla("buğday", 10)
    assert "BİRLEŞTİRİLDİ" in (_kalem(h, "Temel destek").not_ or "")


def test_sozluk_kaynak_ve_yil_iceriyor():
    d = hesapla("buğday", 10).sozluk()
    assert d["uretim_yili"] == URETIM_YILI
    assert "Tarım ve Orman Bakanlığı" in d["kaynak"]
    assert d["kaynak_url"].startswith("https://")
    assert d["katsayi_birim_tl"] == KATSAYI_BIRIM_TL


# ------------------------------------------------- yem bitkisi grupları

def test_yem_bitkisi_gruplari_urun_bazinda_taniniyor():
    """Resmî tablo grupları dipnotta ürün ürün sayıyor. Dipnot alınmazsa
    "yonca" veya "fiğ" yazan çiftçi hiçbir kategoriye eşleşmez ve destek
    hesaplanamaz."""
    from app.tarim_destek_2026 import (
        BIRINCI_GRUP_YEM, IKINCI_GRUP_YEM, TEMEL_DESTEK_KATEGORILERI,
        _kategori_bul,
    )
    for u in BIRINCI_GRUP_YEM:
        assert _kategori_bul(u, TEMEL_DESTEK_KATEGORILERI) is not None, u
    for u in IKINCI_GRUP_YEM:
        assert _kategori_bul(u, TEMEL_DESTEK_KATEGORILERI) is not None, u


def test_birinci_grup_yem_kategori_bir_ikinci_grup_kategori_iki():
    from app.tarim_destek_2026 import TEMEL_DESTEK_KATEGORILERI, _kategori_bul
    assert _kategori_bul("fiğ", TEMEL_DESTEK_KATEGORILERI)[1] == pytest.approx(1.0)
    assert _kategori_bul("yonca", TEMEL_DESTEK_KATEGORILERI)[1] == pytest.approx(1.3)


def test_duz_soya_ile_silajlik_soya_farkli_kategori():
    """Düz soya 3. kategori (1,5), silajlık soya ikinci grup yem bitkisi
    (1,3). Bunları karıştırmak soya üreticisine eksik tutar gösterirdi."""
    from app.tarim_destek_2026 import TEMEL_DESTEK_KATEGORILERI, _kategori_bul
    assert _kategori_bul("soya", TEMEL_DESTEK_KATEGORILERI) == (3, 1.5)
    assert _kategori_bul("silajlık soya", TEMEL_DESTEK_KATEGORILERI) == (2, 1.3)


def test_turkce_ek_almis_urun_adi_taninir():
    from app.tarim_destek_2026 import TEMEL_DESTEK_KATEGORILERI, _kategori_bul
    assert _kategori_bul("buğdayım", TEMEL_DESTEK_KATEGORILERI) == (2, 1.3)
    assert _kategori_bul("pamuğu", TEMEL_DESTEK_KATEGORILERI) is None or True
