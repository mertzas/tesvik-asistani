"""scripts/verify_aktiflik.py ve scripts/check_kaynak_linkleri.py testleri.

Bu iki script veritabanına HÜKÜM yazıyor: "bu program kapandı", "bu link ölü".
Yanlış bir "kapandı" kararı, açık bir programı kullanıcıdan gizler; yanlış bir
"açık" kararı kullanıcıyı kapanmış programa başvurmaya gönderir. Bu yüzden
karar mantığı ağ erişimi olmadan, metin üzerinden test ediliyor.

Testlerin ağ erişimi YOK: `_degerlendir` saf bir fonksiyon, sayfa metnini
argüman olarak alıyor.
"""
from datetime import date

import pytest

from scripts.check_kaynak_linkleri import _ayni_sayfa
from scripts.verify_aktiflik import _degerlendir


# ------------------------------------------------- yanlış pozitif koruması

def test_acik_kapali_kelimeleri_tek_basina_karar_vermez():
    """GERÇEK OLAY: TÜBİTAK 4005 sayfasında "Açık ve kapalı uçlu deney"
    ifadesi geçiyor. Düz anahtar kelime araması bu programı kapanmış
    işaretliyordu. Kelime düzeyinde eşleşme kabul EDİLMEMELİ.
    """
    metin = ("Program kapsamında desteklenen etkinlikler: Açık ve kapalı uçlu "
             "deney, animasyon ve benzetim, argümantasyon, artırılmış gerçeklik.")
    karar, _, _ = _degerlendir(metin)
    assert karar == "kararsiz", "tek kelime eşleşmesi karar vermemeli"


@pytest.mark.parametrize("metin", [
    "Bilim Festivali kapsamında verilecek destek miktarı açıkça belirtilir.",
    "Sisteme yüklenen dosyaların açıldığından emin olunması gerekir.",
    "Kapalı alanda yapılacak etkinlikler de desteklenir.",
])
def test_baglamsiz_kelimeler_karar_uretmez(metin):
    karar, _, _ = _degerlendir(metin)
    assert karar == "kararsiz", f"yanlış karar üretildi: {metin!r}"


# --------------------------------------------------------- kapalı kararı

@pytest.mark.parametrize("metin", [
    "1513 Programında açık bir çağrı bulunmadığından şu an için programa "
    "başvuru alınmamaktadır.",
    "Ulusal patent başvurularına verilen destek başvuruya kapalıdır.",
    "2026 yılı çağrısı kapanmıştır.",
    "Program 7 Temmuz 2018 itibarıyla başvuruya kapatılmıştır.",
    "İlgili karar yürürlükten kaldırılmıştır.",
])
def test_yuksek_guvenli_kapali_kaliplari(metin):
    karar, kanit, ayrinti = _degerlendir(metin)
    assert karar == "kapali", f"{metin!r} kapalı sayılmalıydı ({ayrinti})"
    assert kanit, "karar için kanıt parçası saklanmalı"


# ----------------------------------------------------------- açık kararı

@pytest.mark.parametrize("metin", [
    "DUYURU (08.06.2026): 2026 yılı 2. dönem çağrısı başvuruya açılmıştır.",
    "1702 Patent Lisans Çağrısı Açıldı",
    "2026 Çağrısı açıldı. Program çerçevesinde açılan çağrılar ile...",
    "Başvurular başladı, PRODIS üzerinden yapılabilir.",
])
def test_yuksek_guvenli_acik_kaliplari(metin):
    karar, kanit, _ = _degerlendir(metin)
    assert karar == "acik", f"{metin!r} açık sayılmalıydı"
    assert kanit


def test_gelecek_tarihli_son_basvuru_acik_sayilir():
    metin = "Program için son başvuru tarihi 31.12.2026 olarak belirlenmiştir."
    karar, _, ayrinti = _degerlendir(metin, bugun=date(2026, 9, 27))
    assert karar == "acik"
    assert "2026-12-31" in ayrinti


def test_gecmis_tarihli_son_basvuru_acik_saymaz():
    """Geçmiş tarihli bir son başvuru tarihi, programın açık olduğunu
    göstermez - o dönem kapanmıştır."""
    metin = "Son başvuru tarihi 01.03.2026 idi."
    karar, _, _ = _degerlendir(metin, bugun=date(2026, 9, 27))
    assert karar == "kararsiz"


def test_gelecek_tarihli_basvuru_donemi_acik_sayilir():
    """KOSGEB sayfalarındaki "Program başvuru tarihleri: 1 Eylül-31 Ekim 2026"
    biçimi."""
    metin = "Program başvuru tarihleri: 1 Eylül-31 Ekim 2026"
    karar, _, ayrinti = _degerlendir(metin, bugun=date(2026, 9, 27))
    assert karar == "acik"
    assert "2026-10-31" in ayrinti


def test_gecmis_basvuru_donemi_acik_saymaz():
    metin = "Program başvuru tarihleri: 1 Ocak-28 Şubat 2026"
    karar, _, _ = _degerlendir(metin, bugun=date(2026, 9, 27))
    assert karar == "kararsiz"


# ------------------------------------------------------------- çelişki

def test_celiski_varsa_karar_verilmez():
    """Sayfada hem açık hem kapalı işareti varsa tahmin etmek yerine elle
    kontrole bırakılmalı."""
    metin = ("2025 yılı çağrısı kapanmıştır. DUYURU: 2026 yılı 1. dönem "
             "çağrısı başvuruya açılmıştır.")
    karar, _, ayrinti = _degerlendir(metin)
    assert karar == "kararsiz"
    assert "elle kontrol" in ayrinti


def test_sadece_sonuc_duyurusu_karar_vermez():
    """"Başvuru sonuçları açıklandı" o dönemin bittiğini söyler ama programın
    kapandığını göstermez."""
    metin = "DUYURU (11.09.2026): 2026 yılı 2. dönem çağrısının başvuru "\
            "sonuçları açıklandı."
    karar, _, ayrinti = _degerlendir(metin)
    assert karar == "kararsiz"
    assert "sonuç" in ayrinti.lower() or "değerlendirme" in ayrinti.lower()


def test_bos_metin_karar_vermez():
    karar, kanit, _ = _degerlendir("")
    assert karar == "kararsiz"
    assert kanit == ""


# --------------------------------------------- kanonik link yönlendirmesi

@pytest.mark.parametrize("a,b", [
    ("https://www.tubitak.gov.tr/tr/destekler/x", "https://tubitak.gov.tr/tr/destekler/x"),
    ("http://kurum.gov.tr/sayfa/", "https://kurum.gov.tr/sayfa"),
    ("https://KURUM.gov.tr/sayfa", "https://kurum.gov.tr/sayfa"),
])
def test_kanonik_yonlendirme_sorun_sayilmaz(a, b):
    """Ölçüm (2026-09-27): 67 "yönlendirme" uyarısının TAMAMI
    www.tubitak.gov.tr -> tubitak.gov.tr idi; hepsini "adres güncellenmeli"
    diye bildirmek raporu kullanışsız kılıyordu."""
    assert _ayni_sayfa(a, b) is True


@pytest.mark.parametrize("a,b", [
    ("https://kurum.gov.tr/eski-sayfa", "https://kurum.gov.tr/yeni-sayfa"),
    ("https://kgf.com.tr/index.php/tr/urunlerimiz/x",
     "https://kgf.com.tr/index.php?option=com_content&view=article&id=1"),
    ("https://a.gov.tr/x", "https://b.gov.tr/x"),
])
def test_yol_veya_alan_degisirse_ayni_sayfa_degil(a, b):
    assert _ayni_sayfa(a, b) is False


# ------------------------------- KOSGEB "Yürürlükte Olan Çağrılar" bölümü

def test_yururlukteki_cagri_varsa_acik():
    """KOSGEB program sayfalarında bu başlığın ALTINDA bir çağrı adı varsa
    program başvuruya açıktır."""
    for metin in [
        "Yürürlükte Olan Çağrılar 2026-01 COP31 Hızlandırma Çağrısı İlan Metni",
        "Yürürlükte Olan Çağrılar 2026 Yılı 1. Başvuru Dönemi Proje Teklif Çağrısı",
    ]:
        assert _degerlendir(metin)[0] == "acik", metin


def test_bos_cagri_bolumu_acik_saymaz():
    """Başlık var ama altında çağrı yoksa program açık demek DEĞİLDİR;
    içerik şartı olmadan bu başlık her sayfada açık kararı üretirdi."""
    karar, _, _ = _degerlendir("Yürürlükte Olan Çağrılar  Duyurular İletişim")
    assert karar == "kararsiz"


def test_basliksiz_sayfa_kapali_saymaz():
    """Bazı KOSGEB sayfalarında bu bölüm hiç yok ama program açık olabilir
    (ör. Girişimci Destek Programı). Başlığın YOKLUĞU kapalı demek değildir."""
    karar, _, _ = _degerlendir(
        "Programın Amacı İşletmelerin rekabet gücünü artırmaktır. "
        "Başvuru Şartları KOSGEB Veri Tabanında kayıtlı olmak.")
    assert karar == "kararsiz"


# --------------------------- KGF breadcrumb tabanlı kategori (Hazine Destekli)

def test_kgf_gecmis_programlar_breadcrumb_kapali():
    """KGF ürün sayfalarında açık/kapalı diyen bir cümle genelde hiç
    geçmiyor; gezinme çubuğundaki (breadcrumb) kategori kullanılıyor."""
    metin = ("Buradasınız: Anasayfa / Ürünlerimiz / Hazine Destekli "
             "Kefaletler / Geçmiş Programlar > / Soğuk Hava Ünitesi Ve "
             "Frigorifik Araçlar Destek Paketi Ürün Açıklaması ...")
    karar, kanit, ayrinti = _degerlendir(metin)
    assert karar == "kapali"
    assert kanit


def test_kgf_aktif_destek_paketleri_breadcrumb_acik():
    metin = ("Buradasınız: Anasayfa / Ürünlerimiz / Hazine Destekli "
             "Kefaletler / Aktif Destek Paketleri > / Yatırım-İşletme "
             "Destek Paketi Ürün Açıklaması ...")
    karar, _, _ = _degerlendir(metin)
    assert karar == "acik"


def test_kgf_diger_kategorilerde_breadcrumb_karar_vermez():
    """"KOSGEB Destekli Kefaletler" gibi diğer alt kategorilerde bu ayrım
    yok; tahmin etmek yerine kararsız kalınmalı."""
    metin = ("Buradasınız: Anasayfa / Ürünlerimiz / KOSGEB Destekli "
             "Kefaletler / Kapasite Geliştirme Destek Paketi "
             "Ürün Açıklaması İşletmelerin verimliliğini artırmaya "
             "yönelik finansman desteği sağlanması amaçlanmaktadır.")
    karar, _, _ = _degerlendir(metin)
    assert karar == "kararsiz"


def test_breadcrumb_yoksa_karar_vermez():
    assert _degerlendir("Ürün Açıklaması ... Özel Şartlar ...")[0] == "kararsiz"


def test_cagrisi_sonuclandi_kararsiz_sayilir():
    """"X. Çağrısı Sonuçlandı!" o DÖNEMİN bittiğini söyler, programın
    TAMAMEN kapandığını değil - yeni bir çağrı açılabilir."""
    karar, kanit, _ = _degerlendir("4005 YENİLİKÇİ EĞİTİM UYGULAMALARI 13. ÇAĞRISI SONUÇLANDI!")
    assert karar == "kararsiz"
    assert kanit


# ------------------------------ TÜBİTAK "Başvuru Tarihleri": sürekli açık programlar

@pytest.mark.parametrize("metin", [
    "Başvuru Tarihleri 1515 - Öncül Ar-Ge Laboratuvarları Destekleme Programı sürekli olarak başvuruya açık bir programdır.",
    "Başvuru Tarihleri Başvurular sürekli açıktır ve yılın her günü eteydeb.tubitak.gov.tr adresinden online olarak yapılabilir.",
    "Başvuru Tarihleri 2515 COST Aksiyon Üyeleri Ar-Ge Destek Programı başvuruya sürekli açıktır.",
    "\"2501 Araştırma\" çağrıları için başvuru sistemi sürekli olarak açıktır.",
    "Başvuru Tarihleri Başvurularda herhangi bir zaman kısıtlaması yoktur. Yıl boyunca başvuru yapılabilir.",
    "Başvuru Tarihleri Program 365 gün başvuruya açıktır.",
])
def test_tubitak_surekli_acik_ifadeleri_acik_sayilir(metin):
    """Ölçüm (2026-10-07): 46 kararsız TÜBİTAK kaydının 17'si sayfasında kurumun kendi
    beyanıyla 'sürekli açık'; doğrulayıcı bunları tanımadığı için hepsi kararsız kalıyordu."""
    karar, kanit, _ = _degerlendir(metin)
    assert karar == "acik", metin
    assert kanit


def test_surekli_acik_degil_olumsuzu_acik_saymaz():
    karar, _, _ = _degerlendir("Program sürekli açık değildir; çağrı dönemleri ayrıca ilan edilir.")
    assert karar == "kararsiz"


def test_gecmis_donem_tarihi_surekli_acik_sayilmaz():
    """2223-D ABD sayfası: 'Başvuru Tarihleri 2015 yılı için başvurular 6 Nisan - 8 Mayıs 2015'"""
    karar, _, _ = _degerlendir("Başvuru Tarihleri 2015 yılı için başvurular 6 Nisan - 8 Mayıs 2015 tarihleri arasında yapılabilecektir.",
                               bugun=date(2026, 10, 7))
    assert karar == "kararsiz"
