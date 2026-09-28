"""scripts/extract_basvuru_sartlari.py testleri.

Bu script veritabanına "bu teşvike başvurmak için şu şartlar gerekir" diye
YAZIYOR. Yanlış bir şart kullanıcıyı hak ettiği teşvikten vazgeçirebilir ya
da boşuna başvurmaya gönderebilir. Testler ağ erişimi olmadan, saf metin
üzerinden karar mantığını sınar.
"""
import pytest

from scripts.extract_basvuru_sartlari import (
    _bolum_bul,
    _kontrol_et,
    _maddelere_ayir,
)

KOSGEB_ORNEK = (
    "Programın Amacı İşletmelerin rekabet gücünü artırmaktır. "
    "Başvuru Şartları Başvuru yapacak işletmenin; KOSGEB Veri Tabanında "
    "kayıtlı, aktif durumda ve İşletme Beyanının güncel olması, "
    "Türk Ticaret Kanunu'nda tanımlı gerçek veya tüzel kişi statüsünde "
    "faaliyet göstermesi gerekmektedir. "
    "Destek Oranı Program kapsamında %60 destek verilir."
)


def test_bolum_baslikla_bulunur():
    bulgu = _bolum_bul(KOSGEB_ORNEK)
    assert bulgu is not None
    baslik, bolum = bulgu
    assert baslik == "Başvuru Şartları"
    assert "KOSGEB Veri Tabanında" in bolum


def test_kapanis_ifadesinde_kesilir():
    """Şart listesi "gerekmektedir." ile biter; sonrası program detayıdır.

    GERÇEK OLAY: KOSGEB İstihdamı Koruma sayfasında şartlar 250 karakterde
    bitiyor ama başlıktan sonraki metin 3836 karakter sürüyor (kredi
    limitleri, kefalet kuruluşları). Hepsini "şart" diye yazmak kullanıcıya
    yanlış bilgi vermek olurdu.
    """
    _, bolum = _bolum_bul(KOSGEB_ORNEK)
    assert bolum.rstrip().endswith("gerekmektedir.")
    assert "Destek Oranı" not in bolum
    assert "%60" not in bolum


def test_sonraki_baslik_sinir_olarak_kullanilir():
    metin = ("Başvuru Şartları İşletmenin kayıtlı ve aktif durumda olması "
             "Destek Unsurları Makine teçhizat desteği verilir.")
    _, bolum = _bolum_bul(metin)
    assert "Makine teçhizat" not in bolum


def test_baslik_yoksa_none():
    assert _bolum_bul("Programın Amacı ... Destek Oranı ...") is None


# ------------------------------------------------------------ maddeleme

def test_turkce_gerund_ekinden_boluner():
    """Düz virgülden bölmek "kayıtlı, aktif durumda ve ... olması" ifadesini
    parçalardı; Türkçe şart listeleri "-ması/-mesi," ekiyle ayrılır."""
    _, bolum = _bolum_bul(KOSGEB_ORNEK)
    maddeler = _maddelere_ayir(bolum)
    assert len(maddeler) == 2
    assert "kayıtlı, aktif durumda" in maddeler[0], "virgülden bölünmemeli"
    assert maddeler[1].startswith("Türk Ticaret Kanunu")


def test_kapanis_parcasi_madde_sayilmaz():
    """"gerekmektedir." tek başına bir madde değildir; listeye girdiğinde
    kullanıcı bunu şart sanıp okuyor."""
    maddeler = _maddelere_ayir(
        "İşletmenin kayıtlı olması, aktif durumda olması, gerekmektedir.")
    assert not any(m.strip(" .").lower() == "gerekmektedir" for m in maddeler)


def test_cok_kisa_parcalar_atilir():
    maddeler = _maddelere_ayir("ve, ile, İşletmenin KOSGEB'e kayıtlı olması")
    assert all(len(m) >= 20 for m in maddeler)


# -------------------------------------------------------------- kontrol

def test_cok_uzun_bolum_reddedilir():
    uzun = "İşletmenin kayıtlı olması. " * 90
    assert _kontrol_et(uzun, ["İşletmenin kayıtlı olması"]) is not None


def test_cok_kisa_bolum_reddedilir():
    assert _kontrol_et("kısa", []) is not None


def test_ileri_isaret_eden_tek_madde_reddedilir():
    """GERÇEK OLAY: "Başvuruda bulunabilecek kuruluşlarının aşağıdaki
    tanımlara uyması gerekmektedir." tek başına şart olarak yazılıyordu -
    kullanıcıya hiçbir şey söylemeyen, kendini işaret eden bir cümle.
    İçermediği bir içeriği vaat ettiği için yazmak yerine reddedilmeli.
    """
    madde = ("Başvuruda bulunabilecek kuruluşlarının aşağıdaki tanımlara "
             "uyması gerekmektedir.")
    sebep = _kontrol_et(madde * 3, [madde])
    assert sebep is not None
    assert "ileri işaret" in sebep


def test_ileri_isaret_birden_fazla_madde_varsa_kabul():
    """İleri işaret eden bir cümle, ASIL liste de çıkarıldıysa sorun değil."""
    maddeler = [
        "Başvuru yapacak işletmenin aşağıdaki şartları sağlaması",
        "KOSGEB Veri Tabanında kayıtlı ve aktif durumda olması",
        "Türk Ticaret Kanununda tanımlı statüde faaliyet göstermesi",
    ]
    assert _kontrol_et(" ".join(maddeler), maddeler) is None


def test_gecerli_bolum_kabul_edilir():
    _, bolum = _bolum_bul(KOSGEB_ORNEK)
    maddeler = _maddelere_ayir(bolum)
    assert _kontrol_et(bolum, maddeler) is None
