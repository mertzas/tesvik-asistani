"""scripts/extract_basvuru_sartlari.py testleri.

Bu script veritabanına "bu teşvike başvurmak için şu şartlar gerekir" diye
YAZIYOR. Yanlış bir şart kullanıcıyı hak ettiği teşvikten vazgeçirebilir ya
da boşuna başvurmaya gönderebilir. Testler ağ erişimi olmadan, saf metin
üzerinden karar mantığını sınar.
"""

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
    maddeler, _ = _maddelere_ayir(bolum)
    assert len(maddeler) == 2
    assert "kayıtlı, aktif durumda" in maddeler[0], "virgülden bölünmemeli"
    assert maddeler[1].startswith("Türk Ticaret Kanunu")


def test_kapanis_parcasi_madde_sayilmaz():
    """"gerekmektedir." tek başına bir madde değildir; listeye girdiğinde
    kullanıcı bunu şart sanıp okuyor."""
    maddeler, _ = _maddelere_ayir(
        "İşletmenin kayıtlı olması, aktif durumda olması, gerekmektedir.")
    assert not any(m.strip(" .").lower() == "gerekmektedir" for m in maddeler)


def test_cok_kisa_parcalar_atilir():
    maddeler, _ = _maddelere_ayir("ve, ile, İşletmenin KOSGEB'e kayıtlı olması")
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
    maddeler, _ = _maddelere_ayir(bolum)
    assert _kontrol_et(bolum, maddeler) is None


# ---------------------------------------------------- KGF "Özel Şartlar"

KGF_TIRE_ORNEK = (
    "KAPASİTE GELİŞTİRME DESTEK PAKETİ Özel Şartlar "
    "- Paketten, Kapasite Geliştirme Destek Programı başvurusu KOSGEB "
    "tarafından onaylanan KOBİ'ler yararlanabilecektir. "
    "- Paket kapsamındaki krediler Türk Lirası cinsinden kullandırılacaktır. "
    "- Tüm harcamalar sözleşme veya fatura ile belgelendirilecektir. "
    "Buradasınız: Anasayfa / Ürünlerimiz / KOSGEB Destekli Kefaletler"
)

KGF_DUZ_CUMLE_ORNEK = (
    "SOĞUK HAVA ÜNİTESİ VE FRİGORİFİK ARAÇLAR DESTEK PAKETİ Özel Şartlar "
    "Yatırımlar sözleşme veya fatura ile belgelendirilecek, bu belgeler "
    "yalnızca soğuk hava ünitesi ve frigorifik araç alımına yönelik olacaktır. "
    "Buradasınız: Anasayfa / Ürünlerimiz / Hazine Destekli Kefaletler"
)


def test_kgf_ozel_sartlar_basligi_bulunur():
    bulgu = _bolum_bul(KGF_TIRE_ORNEK)
    assert bulgu is not None
    baslik, bolum = bulgu
    assert baslik == "Özel Şartlar"


def test_kgf_buradasiniz_sinir_olarak_kullanilir():
    """"Buradasınız:" gezinme çubuğu sınır olmadan sayfanın adres/iletişim
    bilgisi de "şart" diye yazılıyordu."""
    _, bolum = _bolum_bul(KGF_TIRE_ORNEK)
    assert "Anasayfa" not in bolum
    assert "Buradasınız" not in bolum


def test_kgf_tire_ile_ayrilmis_maddeler_dogru_bolunur():
    """KGF "Özel Şartlar" bölümü genellikle "- " ile başlayan gerçek madde
    işaretleri kullanır; bu, Türkçe gerund-eki bölmesinden ÖNCE denenmeli."""
    _, bolum = _bolum_bul(KGF_TIRE_ORNEK)
    maddeler, _ = _maddelere_ayir(bolum)
    assert len(maddeler) == 3
    assert maddeler[0].startswith("Paketten")
    assert maddeler[1].startswith("Paket kapsamındaki krediler Türk Lirası")
    assert maddeler[2].startswith("Tüm harcamalar")


def test_kgf_tiresiz_duz_cumle_tek_madde_olarak_kabul_edilir():
    """Bazı KGF sayfalarında madde işareti (tire) hiç yok, tek bir düz
    cümle var. Bölünemiyor diye reddetmek, kullanıcıya bilgiyi hiç
    göstermemek olurdu; tek madde olarak kabul edilmeli."""
    _, bolum = _bolum_bul(KGF_DUZ_CUMLE_ORNEK)
    maddeler, _ = _maddelere_ayir(bolum)
    assert len(maddeler) == 1
    assert "soğuk hava ünitesi" in maddeler[0].lower()
    assert _kontrol_et(bolum, maddeler) is None


# ---------------------------------------- harf-numarali (a./b./c.) listeler

TUBITAK_HARF_ORNEK = (
    "2223-C Çok Katılımlı Uluslararası Etkinlik Düzenleme Desteği "
    "Başvuru Koşulları "
    "a. Başvurunun, etkinlik yürütücüsü tarafından yapılması, "
    "b. Etkinlik yürütücüsünün görev yaptığı kurumdan resmi yazı alınması, "
    "c. Etkinliğin en az 3'üncüsünün düzenlenecek olması, "
    "gerekmektedir. Başvuru Formları için tıklayınız."
)


def test_harf_madde_listesi_dogru_bolunur():
    """TÜBİTAK 2223 serisi etkinlik programlarında şartlar "a. ... b. ...
    c. ..." harf-numaralı liste halinde geliyor; bu, tire kadar güvenilir
    bir sınırdır."""
    _, bolum = _bolum_bul(TUBITAK_HARF_ORNEK)
    maddeler, yapisal = _maddelere_ayir(bolum)
    assert yapisal is True
    assert len(maddeler) == 3
    assert maddeler[0].startswith("Başvurunun")
    assert maddeler[1].startswith("Etkinlik yürütücüsünün")
    assert maddeler[2].startswith("Etkinliğin en az")


def test_harf_madde_parcalari_tek_karakter_kalinti_birakmaz():
    """re.split yakalama grubunu (tek harf: 'a', 'b', 'c') da sonuca
    ekliyor; bunlar madde metni değildir ve listeye sızmamalı."""
    _, bolum = _bolum_bul(TUBITAK_HARF_ORNEK)
    maddeler, _ = _maddelere_ayir(bolum)
    assert not any(len(m) <= 2 for m in maddeler)


def test_yapisal_bolum_gevsek_uzunluk_sinirinda_kabul_edilir():
    """Harf-madde ile net ayrılmış bir bölüm, genel 1800 karakter sınırını
    aşabilir (gerçek örnek: 2223-C sayfası 3783 karakter); bunu reddetmek
    kullanıcıya değerli bir şart listesini hiç göstermemek olurdu."""
    uzun_bolum = " ".join(
        f"{chr(97+i)}. Madde {i} için gereken şart burada uzunca anlatılıyor "
        "ve metnin genel 1800 karakter sınırını aşmasını sağlıyor."
        for i in range(20)
    )
    maddeler, yapisal = _maddelere_ayir(uzun_bolum)
    assert yapisal is True
    assert len(uzun_bolum) > 1800
    assert _kontrol_et(uzun_bolum, maddeler, yapisal) is None


def test_yapisal_olmayan_uzun_bolum_hala_reddedilir():
    """Madde işareti yoksa (tek uzun serbest metin) gevşek sınır
    uygulanmamalı; bu hâlâ "yanlış bölüm yakalandı" riski taşır."""
    uzun_bolum = "Bu şartların hiçbiri madde işaretiyle ayrılmamış. " * 60
    maddeler, yapisal = _maddelere_ayir(uzun_bolum)
    assert yapisal is False
    assert _kontrol_et(uzun_bolum, maddeler, yapisal) is not None
