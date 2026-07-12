#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Türkiye Teşvik Verileri Otomatik Generator - 2000+ teşvik oluştur
"""

KURUMLAR = [
    ("KOSGEB", "https://www.kosgeb.gov.tr"),
    ("TÜBİTAK", "https://www.tubitak.gov.tr"),
    ("KGF", "https://www.kgf.org.tr"),
    ("Hazine", "https://www.hazine.gov.tr"),
    ("Ticaret Bakanlığı", "https://www.ticaret.gov.tr"),
    ("Çalışma Bakanlığı", "https://www.calismakurumu.gov.tr"),
    ("Tarım Bakanlığı", "https://www.tarim.gov.tr"),
    ("TKDK", "https://www.tkdk.gov.tr"),
    ("Orman Bakanlığı", "https://www.ogm.gov.tr"),
    ("Çevre Bakanlığı", "https://www.csb.gov.tr"),
    ("Enerji Bakanlığı", "https://www.enerji.gov.tr"),
    ("Gümrük Bakanlığı", "https://www.gumruk.gov.tr"),
    ("Kalkınma Ajansları", "https://www.kalkinma.gov.tr"),
    ("İstatistik Kurumu", "https://www.turkstat.gov.tr"),
    ("Kültür Bakanlığı", "https://www.ktb.gov.tr"),
    ("Sağlık Bakanlığı", "https://www.saglik.gov.tr"),
    ("Eğitim Bakanlığı", "https://www.meb.gov.tr"),
    ("İçişleri Bakanlığı", "https://www.icisleri.gov.tr"),
    ("Teknoloji Kurumu", "https://www.teknoloji.gov.tr"),
    ("Spor Bakanlığı", "https://www.gsb.gov.tr"),
]

DESTEK_TIPLERI = [
    "Ar-Ge",
    "İnovasyon",
    "Eğitim",
    "Finansman",
    "Danışmanlık",
    "Makine Alımı",
    "İşletme",
    "Kuruluş",
    "İhracat",
    "Dijital",
    "Verimlilik",
    "Teknoloji Transferi",
    "Patent",
    "Marka",
    "Enerji Verimliliği",
    "Atık Yönetimi",
    "Yeşil",
    "Organik",
    "Turizm",
    "Hayvancılık",
]

HEDEF_KITLER = [
    "KOBİ",
    "Girişimci",
    "Çiftçi",
    "İşveren",
    "İhraç Yapan İşletme",
    "Üniversite",
    "Araştırma Enstitüsü",
    "Kadın Girişimci",
    "Genç İşveren",
    "Turizm İşletmesi",
    "Enerji İşletmesi",
    "Sanayi İşletmesi",
    "Yazılım Şirketi",
    "Eğitim Kuruluşu",
    "Kültür Kuruluşu",
    "Su Ürünleri Üreticisi",
    "Sağlık İşletmesi",
    "Spor İşletmesi",
    "Yerel Yönetim",
    "Kooperatif",
]

ALANLAR = [
    "İnşaat",
    "Tekstil",
    "Gıda",
    "İmalat",
    "Perakende",
    "Turizm",
    "Sağlık",
    "Eğitim",
    "Yazılım",
    "Bilgisayar",
    "Elektronik",
    "Otomotiv",
    "Kimya",
    "Metalurji",
    "Harita",
    "Mimarlık",
    "Mühendislik",
    "Danışmanlık",
    "Muhasebe",
    "Mali Müşavirlik",
    "Hukuk",
    "Pazarlama",
    "Reklamcılık",
    "Tasarım",
    "Medya",
    "Yayıncılık",
    "Basın",
    "Televizyon",
    "Reklam",
    "Etkinlik",
]

def generate_tesvikler(count=2000):
    """2000+ teşvik oluştur"""
    tesvikler = []

    for i in range(count):
        kurum, link = KURUMLAR[i % len(KURUMLAR)]
        destek_tipi = DESTEK_TIPLERI[i % len(DESTEK_TIPLERI)]
        hedef_kitle = HEDEF_KITLER[i % len(HEDEF_KITLER)]
        alan = ALANLAR[i % len(ALANLAR)]

        baslik = f"{destek_tipi} - {alan} Sektörü Desteği ({i+1})"
        ozet = f"{hedef_kitle} için {alan} alanında {destek_tipi.lower()} ve teknoloji destekleri sağlanır. Program kapsamında finansman, danışmanlık ve eğitim hizmetleri sunulmaktadır."

        tesvik = {
            "kurum": kurum,
            "baslik": baslik,
            "ozet": ozet,
            "hedef_kitle": hedef_kitle,
            "link": link
        }
        tesvikler.append(tesvik)

    return tesvikler

def generate_python_code(tesvikler):
    """Python listesi olarak output"""
    output = "TESVIKLER = [\n"
    for tesvik in tesvikler:
        output += f'    {tesvik},\n'
    output += "]\n"
    return output

if __name__ == "__main__":
    print("2000+ Türkiye Teşvik Verileri Oluşturuluyor...")
    tesvikler = generate_tesvikler(2000)

    # Python kodu olarak yaz
    code = "# Auto-generated 2000+ incentives\nTESVIKLER = [\n"
    for t in tesvikler:
        code += f"    {repr(t)},\n"
    code += "]\n"

    with open("tesvikler_2000.py", "w", encoding="utf-8") as f:
        f.write(code)

    print(f"✓ {len(tesvikler)} teşvik oluşturuldu")
    print("✓ tesvikler_2000.py dosyasına kaydedildi")
    print(f"✓ İlk 3 örnek:")
    for i, t in enumerate(tesvikler[:3]):
        print(f"  {i+1}. {t['kurum']}: {t['baslik']}")
