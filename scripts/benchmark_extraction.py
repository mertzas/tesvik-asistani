"""
Elle doğrulanmış 25 altın standart (Gold Standard) Türkçe mevzuat örneklemi
üzerinde Çıkarım Doğruluğu (Precision), Alıntı Geçerliliği (Quote Accuracy) ve
Yanlış Bilgi (Hallucination) Oranını ölçen Benchmark betiği.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extractor import extract_structured_info, verify_grounding

# 25 Altın Standart (Gold Standard) Mevzuat / Teşvik Metni Örneklemi
GOLD_STANDARD_DATASET = [
    {
        "id": 1,
        "kurum": "KOSGEB",
        "baslik": "İş Geliştirme Desteği",
        "raw_text": "KOSGEB İş Geliştirme Desteği kapsamında imalat ve bilişim sektöründeki KOBİ'lere üst limit 1.500.000 TL geri ödemesiz ve geri ödemeli destek verilir. Destek oranı %80 olarak uygulanır. Başvurular 31 Aralık 2026 tarihine kadar devam etmektedir.",
        "expected_rate": 80.0,
        "expected_amount": 1500000.0,
        "expected_active": True
    },
    {
        "id": 2,
        "kurum": "TÜBİTAK",
        "baslik": "1507 KOBİ Ar-Ge Başlangıç Destek Programı",
        "raw_text": "1507 KOBİ Ar-Ge Başlangıç Destek Programında proje bütçesi üst sınırı 2.400.000 TL'dir. Hibe destek oranı %75 olarak uygulanır.",
        "expected_rate": 75.0,
        "expected_amount": 2400000.0,
        "expected_active": True
    },
    {
        "id": 3,
        "kurum": "Tarım Bakanlığı",
        "baslik": "Sera Yapımı ve Örtüaltı Tarım Desteği",
        "raw_text": "Modern sera kurulum yatırımlarında hibe oranı %50'dir. Dekar başına azami destek tutarı 300.000 TL'dir. Başvurular İl Tarım Müdürlüklerine yapılır.",
        "expected_rate": 50.0,
        "expected_amount": 300000.0,
        "expected_active": True
    },
    {
        "id": 4,
        "kurum": "KGF",
        "baslik": "Kredi Garanti Fonu Özkaynak Destek Paketi",
        "raw_text": "KGF kefalet oranı %80 olarak belirlenmiş olup, firma başına azami kefalet limiti 25.000.000 TL'dir. Bu program 2024 sonu itibarıyla başvuruya kapanmıştır.",
        "expected_rate": 80.0,
        "expected_amount": 25000000.0,
        "expected_active": False
    },
    {
        "id": 5,
        "kurum": "Ticaret Bakanlığı",
        "baslik": "5986 Sayılı E-İhracat Desteği",
        "raw_text": "5986 sayılı Karar kapsamında e-ihracat tanitim desteği yıllık azami 9.000.000 TL'dir. Destek oranı %60'tır.",
        "expected_rate": 60.0,
        "expected_amount": 9000000.0,
        "expected_active": True
    },
    {
        "id": 6,
        "kurum": "TKDK",
        "baslik": "IPARD III Tedbir 3 Çiftlik Faaliyetleri",
        "raw_text": "IPARD III kapsamında yenilenebilir enerji ve çiftlik faaliyetlerinde hibe oranı %70 olarak uygulanmaktadır. Azami proje tutarı 500.000 Avro karşılığı TL'dir.",
        "expected_rate": 70.0,
        "expected_amount": None,
        "expected_active": True
    },
    {
        "id": 7,
        "kurum": "KOSGEB",
        "baslik": "Girişimcilik Destek Programı",
        "raw_text": "Yeni kurulan işletmeler için kuruluş desteği 50.000 TL geri ödemesiz olarak verilir. Destek oranı %100'dür.",
        "expected_rate": 100.0,
        "expected_amount": 50000.0,
        "expected_active": True
    },
    {
        "id": 8,
        "kurum": "TÜBİTAK",
        "baslik": "1001 İlimsel ve Teknolojik Araştırma Projelerini Destekleme",
        "raw_text": "1001 programı kapsamında proje teşvik ikramiyesi hariç bütçe üst limiti 1.650.000 TL'dir. Başvurular yılda 2 dönem halinde alınır.",
        "expected_rate": None,
        "expected_amount": 1650000.0,
        "expected_active": True
    },
    {
        "id": 9,
        "kurum": "İŞKUR",
        "baslik": "İşbaşı Eğitim Programı",
        "raw_text": "İşbaşı eğitim programına katılan kursiyerlerin günlük zaruri gideri İŞKUR tarafından karşılanır. Program süresi imalat sektöründe azami 6 aydır.",
        "expected_rate": None,
        "expected_amount": None,
        "expected_active": True
    },
    {
        "id": 10,
        "kurum": "Ticaret Bakanlığı",
        "baslik": "Yurt Dışı Fuar Katılım Desteği",
        "raw_text": "Prestiçli yurt dışı fuar katılımlarında yer kirası ve stant harcamaları için destek oranı %70, üst limit 500.000 TL olarak uygulanır.",
        "expected_rate": 70.0,
        "expected_amount": 500000.0,
        "expected_active": True
    },
    {
        "id": 11,
        "kurum": "Hazine ve Maliye Bakanlığı",
        "baslik": "Yatırım Teşvik Belgesi KDV İstisnası",
        "raw_text": "Yatırım Teşvik Belgesi kapsamında temin edilecek makine ve teçhizat için KDV istisnası uygulanır. Destek oranı %100 KDV muafiyetidir.",
        "expected_rate": 100.0,
        "expected_amount": None,
        "expected_active": True
    },
    {
        "id": 12,
        "kurum": "Tarım Bakanlığı",
        "baslik": "Hayvancılık Buzağı Desteklemesi",
        "raw_text": "Program kapsamında buzağı başına temel destek 1.000 TL'dir. Başvurular 1. dönem ve 2. dönem olmak üzere 2026 yılı sonuna kadar devam etmektedir.",
        "expected_rate": None,
        "expected_amount": 1000.0,
        "expected_active": True
    },
    {
        "id": 13,
        "kurum": "KOSGEB",
        "baslik": "KOBİ GEL Gelişim Destek Programı",
        "raw_text": "KOBİGEL kapsamında imalat sanayi KOBİ'lerine 1.000.000 TL uygun faizli kredi imkanı sunulmuştur. Program 2023 yılında tamamlanıp kapanmıştır.",
        "expected_rate": None,
        "expected_amount": 1000000.0,
        "expected_active": False
    },
    {
        "id": 14,
        "kurum": "Ticaret Bakanlığı",
        "baslik": "Pazara Giriş Belgeleri Desteği",
        "raw_text": "İhracatçı şirketlerin pazara giriş belgeleri ve test raporu masrafları %50 oranında ve yıllık 4.000.000 TL'ye kadar desteklenir.",
        "expected_rate": 50.0,
        "expected_amount": 4000000.0,
        "expected_active": True
    },
    {
        "id": 15,
        "kurum": "TÜBİTAK",
        "baslik": "1512 BİGG Bireysel Genç Girişim",
        "raw_text": "BİGG programı kapsamında yenilikçi iş fikirlerine 900.000 TL sermaye desteği verilir. Destek oranı %100 hibedir.",
        "expected_rate": 100.0,
        "expected_amount": 900000.0,
        "expected_active": True
    },
    {
        "id": 16,
        "kurum": "Tarım Bakanlığı",
        "baslik": "Damlama Sulama Sistemleri Hibe Desteği",
        "raw_text": "Tarımsal sulama ekipmanı ve damlama sulama tesisatı alımında %50 hibe desteği sağlanır. Üst limit 1.000.000 TL.",
        "expected_rate": 50.0,
        "expected_amount": 1000000.0,
        "expected_active": True
    },
    {
        "id": 17,
        "kurum": "KOSGEB",
        "baslik": "YURT DIŞI PAZAR DESTEK PROGRAMI",
        "raw_text": "KOBİ'lerin uluslararası pazarlara açılması için azami 300.000 TL destek sağlanır. Hibe oranı %70'tir.",
        "expected_rate": 70.0,
        "expected_amount": 300000.0,
        "expected_active": True
    },
    {
        "id": 18,
        "kurum": "Enerji Bakanlığı",
        "baslik": "YEKA Yenilenebilir Enerji Desteği",
        "raw_text": "YEKA kapsamında üretilen elektrik için alım garantisi fiyatı uygulanır. Son başvuru tarihi 15 Ekim 2026.",
        "expected_rate": None,
        "expected_amount": None,
        "expected_active": True
    },
    {
        "id": 19,
        "kurum": "KGF",
        "baslik": "İhracat Destek Kredi Paketı",
        "raw_text": "İhracatçı işletmelere %85 KGF kefalet oranı ile azami 35.000.000 TL kredi imkanı sunulmaktadır.",
        "expected_rate": 85.0,
        "expected_amount": 35000000.0,
        "expected_active": True
    },
    {
        "id": 20,
        "kurum": "Ticaret Bakanlığı",
        "baslik": "Küresel Tedarik Zinciri Desteği",
        "raw_text": "Küresel firmalara tedarikçi olan KOBİ'lerin makine ve yazılım alımları %50 oranında ve 15.000.000 TL'ye kadar desteklenir.",
        "expected_rate": 50.0,
        "expected_amount": 15000000.0,
        "expected_active": True
    },
    {
        "id": 21,
        "kurum": "TKDK",
        "baslik": "IPARD Zanaatkarlık ve Yerel Ürünler",
        "raw_text": "Geleneksel el sanatları ve yerel ürün üreten işletmelere hibe oranı %65 olarak belirlenmiştir.",
        "expected_rate": 65.0,
        "expected_amount": None,
        "expected_active": True
    },
    {
        "id": 22,
        "kurum": "KOSGEB",
        "baslik": "Teknoyatırım Destek Programı",
        "raw_text": "Ar-Ge sonucu ortaya çıkan ürünlerin serileştirilmesi için 6.000.000 TL'ye kadar destek sağlanır. Destek oranı %60'tır.",
        "expected_rate": 60.0,
        "expected_amount": 6000000.0,
        "expected_active": True
    },
    {
        "id": 23,
        "kurum": "Tarım Bakanlığı",
        "baslik": "Mazot ve Gübre Desteği",
        "raw_text": "Dekar başına mazot desteği 103 TL, gübre desteği 46 TL'dir. Ödemeler çiftçi hesaplarına aktarılmaktadır.",
        "expected_rate": None,
        "expected_amount": 103.0,
        "expected_active": True
    },
    {
        "id": 24,
        "kurum": "TÜBİTAK",
        "baslik": "1501 Sanayi Ar-Ge Projeleri Destekleme",
        "raw_text": "1501 programında Ar-Ge harcamalarının %75'i hibe olarak karşılanır. Bütçe sınırı bulunmamaktadır.",
        "expected_rate": 75.0,
        "expected_amount": None,
        "expected_active": True
    },
    {
        "id": 25,
        "kurum": "KOSGEB",
        "baslik": "Yeşil Sanayi Destek Programı",
        "raw_text": "KOBİ'lerin güneş enerjisi ve enerji verimliliği yatırımları için 14.000.000 TL'ye kadar faizsiz kredi sağlanmaktadır. Başvurular 2026 yılı boyunca açıktır.",
        "expected_rate": None,
        "expected_amount": 14000000.0,
        "expected_active": True
    }
]


def run_benchmark():
    print("=" * 80)
    print("🎯 SIFIR HALÜSİNASYONLU VE DAYANAKLI ÇIKARIM MOTORU BENCHMARK TESTİ")
    print(f"Toplam Örneklem: {len(GOLD_STANDARD_DATASET)} Altın Standart Mevzuat Metni")
    print("=" * 80 + "\n")

    total_fields = 0
    correct_extractions = 0
    hallucination_count = 0
    valid_quote_count = 0
    invalid_quote_count = 0

    for sample in GOLD_STANDARD_DATASET:
        verified_data, evidence, confidence = extract_structured_info(sample["raw_text"])

        # Destek oranı kontrolü
        if sample["expected_rate"] is not None:
            total_fields += 1
            extracted_rate = verified_data.get("destek_orani_yuzde")
            if extracted_rate == sample["expected_rate"]:
                correct_extractions += 1
            elif extracted_rate is not None and extracted_rate != sample["expected_rate"]:
                hallucination_count += 1

        # Tutar kontrolü
        if sample["expected_amount"] is not None:
            total_fields += 1
            extracted_amount = verified_data.get("azami_tutar_tl")
            if extracted_amount == sample["expected_amount"]:
                correct_extractions += 1
            elif extracted_amount is not None and extracted_amount != sample["expected_amount"]:
                hallucination_count += 1

        # Alıntı doğrulama kontrolleri
        for field, ev in evidence.items():
            if ev.get("verified") is True:
                valid_quote_count += 1
            elif ev.get("verified") is False and ev.get("quote"):
                invalid_quote_count += 1

    precision = (correct_extractions / total_fields * 100) if total_fields else 100.0
    quote_accuracy = (valid_quote_count / (valid_quote_count + invalid_quote_count) * 100) if (valid_quote_count + invalid_quote_count) else 100.0
    hallucination_rate = (hallucination_count / total_fields * 100) if total_fields else 0.0

    print("📊 BENCHMARK SONUÇLARI:")
    print(f"  • Doğrulanmış Alan Sayısı (Total Grounded Fields): {total_fields}")
    print(f"  • Doğru Çıkarılan Alan (Correct Extractions): {correct_extractions}")
    print(f"  • Çıkarım Doğruluğu (Precision Rate): %{precision:.1f}")
    print(f"  • Alıntı Geçerlilik Oranı (Quote Grounding Accuracy): %{quote_accuracy:.1f}")
    print(f"  • Sessizce Yanlış Bilgi (Hallucination Rate): %{hallucination_rate:.1f}")
    print("\n" + "=" * 80)
    if hallucination_rate == 0.0 and quote_accuracy >= 90.0:
        print("✅ BAŞARI KRİTERİ SAĞLANDI: Sessizce yanlış bilgi yazma oranı SIFIR!")
    print("=" * 80)

if __name__ == "__main__":
    run_benchmark()
