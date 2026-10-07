"""Danışman bağlamına giden kayıt metni: mevzuat kayıtlarının madde listesi kesilmemeli,
kazıma gürültüsü ayıklanmalı."""
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
