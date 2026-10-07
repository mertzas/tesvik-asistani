"""Danışman bağlamına giden kayıt metni: mevzuat kayıtlarının madde listesi kesilmemeli,
kazıma gürültüsü ayıklanmalı, menü dökümü yerine içerik gövdesi gönderilmeli."""
from app import rag
from app.models import Tesvik


def _t(detay, baslik="Program"):
    return Tesvik(kurum="X", baslik=baslik, ozet="o", detay=detay, kaynak_url="https://t/x")


def test_uzun_mevzuat_detayi_kesilmez():
    """GERÇEK OLAY: 10962 kaydında MADDE 22 (platform komisyonu) 500 karakterlik kesmenin
    dışında kalıyor, model 'madde numarası bağlamda yok' diyordu."""
    detay = " ".join(f"Destek {i} (MADDE {i}): giderler %50, yıllık en fazla {i}.000.000 TL." for i in range(13, 32))
    assert len(detay) > 500
    m = rag._tesvik_detay_metni(_t(detay))
    assert "MADDE 22" in m and "MADDE 31" in m


def test_tesvil_tutari_alani_baglama_yazilir():
    """GERÇEK OLAY (Denetim 2 / Aşama C): DB'de kaynakla doğrulanmış tutar metni (tesvil_tutari)
    vardı ama bağlama yazılmıyordu; model 'vade/limit elimde yok' diyordu."""
    t = _t("d")
    t.tesvil_tutari = "Kredi 500.000 – 5.000.000 TL; vade 24 ay (ilk 12 ay ödemesiz)"
    t.tutari_max = 5000000.0
    m = rag._tesvik_detay_metni(t)
    assert "Tutar/oran: Kredi 500.000 – 5.000.000 TL; vade 24 ay (ilk 12 ay ödemesiz)" in m
    assert "Azami tutar" not in m, "tesvil_tutari varken ASCII azami tutar satırı tekrarlanmaz"


def test_tutar_alanlari_oncelik_sirasi():
    t = _t("d")
    t.tutari_hesaplama_formulu = "ciro x %5"
    assert "Tutar/oran" not in rag._tesvik_detay_metni(t) and "Hesaplama: ciro x %5" in rag._tesvik_detay_metni(t)
    t2 = _t("d")
    t2.tutari_max = 1000000.0
    assert "Azami tutar: ₺1,000,000" in rag._tesvik_detay_metni(t2)


def test_detay_ust_siniri_korunur():
    m = rag._tesvik_detay_metni(_t("Uzun bir cümle burada yer alıyor. " * 300))
    assert len(m) <= rag.DETAY_KARAKTER + 300


def test_menu_gurultusu_baglama_gitmez():
    detay = ("— Özkaynak Kefaletlerimiz\n—— Banka Kredileri >\n" + "\n".join(
        ["Kefalet Süreçleri", "Vadeler ve Limitler", "Bilgi Merkezi", "Rakamlarla KGF", "Faaliyet Raporları",
         "Kaynaklarımız", "Hazine Fonu"]) + "\nÇerez Politikası\nÜrün Açıklaması\nİmalatçı KOBİ'lere kefalet verilir.")
    m = rag._tesvik_detay_metni(_t(detay, baslik="Paket"))
    assert "İmalatçı KOBİ'lere kefalet verilir." in m
    assert "Özkaynak Kefaletlerimiz" not in m and "Çerez Politikası" not in m


def test_icerik_basligi_oncesi_menu_dokumu_atilir_alt_bilgi_kesilir():
    """GERÇEK OLAY: KGF 2024 Dijital Dönüşüm kaydında 8.900 karakterlik menü dökümü içerikten
    önce geliyordu; satır bazlı temizleyici her satırı yakalayamıyordu."""
    menu = "\n".join(f"Paket {i} Destek Programı Ürünlerimiz Kefalet" for i in range(40))
    detay = (menu + "\nÖzkaynak Kefaletlerimiz Banka Kredileri\nÜrün Açıklaması\n"
             "Dijital dönüşüm yatırımı yapan KOBİ'lere kefalet verilir.\nKefalet İçin Kullanılan Kaynak\nHazine Fonu\n"
             "Buradasınız: Anasayfa / Ürünlerimiz / Hazine Destekli Kefaletler\nSöğütözü Mah. Ankara")
    m = rag._tesvik_detay_metni(_t(detay, baslik="2024 Dijital Dönüşüm Destek Paketi"))
    assert "Dijital dönüşüm yatırımı yapan KOBİ'lere kefalet verilir." in m and "Hazine Fonu" in m
    assert "Özkaynak Kefaletlerimiz" not in m and "Paket 3 Destek" not in m
    assert "Söğütözü" not in m, "alt bilgi (adres) kesilmeli"


def test_icerik_basligi_yoksa_metin_aynen_kalir():
    assert rag._icerik_govdesi("Düz bir açıklama metni.") == "Düz bir açıklama metni."
    assert rag._icerik_govdesi(None) == ""
    # başlık en başta ise (konum 0) kesme yapılmaz
    assert rag._icerik_govdesi("Programın Amacı: x. Buradasınız: y").startswith("Programın Amacı")
