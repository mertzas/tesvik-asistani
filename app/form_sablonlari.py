"""Program bazında resmi başvuru formu şablonları (2026-10-09): sihirbaz soruları formun kendi bölümleri olur.

Kaynaklar 2026-10-08/09'da indirildi; başlık ve açıklamaların formdaki birebir karşılıkları
docs/olcum/2026-10-09-formlar/kanit.json'da denetlenir:
  1501 ve 1507 (TÜBİTAK): "1501_1507 Proje Öneri Bilgileri Formu Hazırlama Kılavuzu (AGY100-101)" — PRODİS'te
     doldurulan A-E bölümleri (B: Endüstriyel Ar-Ge içeriği, teknoloji düzeyi ve yenilikçi yön; C: Proje planı ve
     kuruluş altyapısı; D: Ekonomik yarar ve ulusal kazanım; E: Risk ve finansman).
  KOSGEB Kapasite Geliştirme (8): "Kapasite Geliştirme Destek Programı Proje Başvuru Formu II. Bölüm" 2.11-2.20
     (açıklama metinleri formdan kısaltılarak); 2.3-2.10 tablo bölümleri taslakta "doldurulacak tablolar" olarak listelenir.
Form güncellenirse burası ve kanıt dosyası birlikte güncellenir; ipuçları formun ifadesinden ayrılmaz.

    python -m app.form_sablonlari --self-test
"""
from __future__ import annotations

import sys

AGY100 = "https://www.tubitak.gov.tr/sites/default/files/2024-09/1501_1507_proje_oneri_bilgileri_formu_hazirlama_kilavuzu_agy100-101.pdf"
KOSGEB_KG_FORM = ("https://webdosya.kosgeb.gov.tr/Content/Upload/Dosya/KAPAS%C4%B0TE%20GEL%C4%B0ST%C4%B0RME/2026/2026.08.21/"
                  "02b-Kapasite_Gelis%CC%A7tirme_Destek_Program%C4%B1_Proje_Bas%CC%A7vuru_Formu_II.Bo%CC%88lu%CC%88m.pdf")

_TUBITAK = {
    "ad": "TÜBİTAK Proje Öneri Bilgileri Formu (AGY100/AGY101, PRODİS)",
    "kaynak": AGY100,
    "bolumler": [
        ("A3", "A.3 Proje Kısa Tanıtımı", "Projenin konusu, amacı ve beklenen çıktısı (kısa)"),
        ("B1", "B.1 Projenin Çağrı Konusuyla İlişkisi ve Hedefleri", "Proje çağrı konusuna nasıl karşılık geliyor; hedefler"),
        ("B2", "B.2 Projenin Teknoloji Düzeyi", "Tekniğin/teknolojinin bilinen güncel durumu (ulusal ve uluslararası) ve "
                                                 "projenin özgün katkısı"),
        ("B3", "B.3 Projenin Somut / Ölçülebilir Hedeflerle Tanıtımı ve Çözüm Yaklaşımları (Ar-Ge Sistematiği)",
         "Proje çıktısının ölçülebilir başarı ölçütleri ve hedef değerleri; çözüm yaklaşımı ve yöntem"),
        ("B4", "B.4 Projenin Yenilikçi Yönleri", "Benzer ürün/sistemlerle karşılaştırma; yenilik düzeyi (firma, ülke ya da "
                                                  "dünya için yeni)"),
        ("C1", "C.1 İş Planı", "İş paketleri, süreleri ve her paketin maliyet unsurları"),
        ("C2", "C.2 Proje Yönetimi ve Organizasyonu", "Proje ekibi, görev dağılımı, yönetim ve izleme"),
        ("C3", "C.3 Kuruluş Altyapısı", "Ar-Ge yapılanması, ekipman, deneyim"),
        ("D1", "D.1 Ekonomik Öngörüler", "Ticari başarı potansiyeli, hedef pazar ve müşteriler, ithal ürün ikamesi, "
                                          "ekonomik getiri tahmini"),
        ("D2", "D.2 Ulusal Kazanımlar", "Bilgi birikimine katkı, patent/lisans beklentisi, üniversite-sanayi işbirliği, "
                                         "yeni istihdam"),
        ("E1", "E.1 Risk ve Finansman Yönetimi", "Teknik/ticari riskler, önlemler ve projenin finansmanı"),
    ],
    "tablolar": ["Proje bütçesi: M011 Personel, M012 Seyahat, M013 Alet/Teçhizat/Yazılım/Yayın, M014 Ar-Ge ve test "
                 "kuruluşlarına yaptırılan işler, M015 Hizmet alımı, M016 Malzeme", "M030 Dönemsel giderler tablosu"],
}
_KOSGEB_KG = {
    "ad": "KOSGEB Kapasite Geliştirme Destek Programı Proje Başvuru Formu (II. Bölüm)",
    "kaynak": KOSGEB_KG_FORM,
    "bolumler": [
        ("2.11", "2.11 İşletmenin Tarihçesi, Mevcut Faaliyetleri, Ortakları ve Proje Deneyimleri",
         "Tarihçe, ürün/ürün grupları, proje deneyimleri, ortakların deneyimi; ortak olunan diğer firmalar"),
        ("2.12", "2.12 Proje Konusu ile İlgili Mevcut Durum", "Mevcut faaliyetler ve ihtiyaçların bugün nasıl karşılandığı"),
        ("2.13", "2.13 Projenin Amacı ve Gerekçesi", "Projeye neden ihtiyaç var; hazırlık ve teknik fizibilite çalışmaları"),
        ("2.14", "2.14 Projenin Konusu", "Faaliyetler; kapasite, ürün çeşitliliği, teknoloji düzeyi, ihracat potansiyeli ve "
                                         "insan kaynağına etkisi"),
        ("2.15", "2.15 Projenin Hedef ve Faaliyetleri", "Hedef kartları: her hedefin faaliyetleri, çıktıları ve giderlerinin "
                                                        "gerekçesi"),
        ("2.16", "2.16 Projenin Hedeflere, Pazara ve Rekabet Durumuna Etkisi", "Orta/uzun dönem hedeflere katkı, pazar payı "
                                                                               "ve genişliği, lojistik uygunluk"),
        ("2.17", "2.17 Riskler, Önlemler ve Varsayımlar", "Uygulama sırasında ve sonrasında riskler ve önlemler"),
        ("2.18", "2.18 Projede Kullanılacak İşletme Kaynakları", "Personel, makine ve öz kaynakla yapılacak giderler"),
        ("2.19", "2.19 Proje Yönetimi", "Proje yöneticisi, koordinasyon, gözden geçirme ve izleme görev dağılımı"),
        ("2.20", "2.20 Sürdürülebilirlik", "Kurumsal ve mali sürdürülebilirlik"),
    ],
    "tablolar": ["2.3 Proje konusu ürüne ilişkin bilgiler", "2.4 Dış ticaret verileri (son 3 yıl)",
                 "2.5 Yurt içi-yurt dışı pazar büyüklüğü (son 3 yıl)", "2.6 Ürüne-muadiline ilişkin ihracat ve ithalat",
                 "2.7 Rakip firmalar", "2.8 Müşteriler", "2.9 Üretim-satış planı", "2.10 Yatırımın geri dönüş süresi"],
}
FORMLAR: dict[int, dict] = {34: _TUBITAK, 44: _TUBITAK, 8: _KOSGEB_KG}


def form(tesvik_id: int | None) -> dict | None:
    return FORMLAR.get(tesvik_id) if tesvik_id is not None else None


def _self_test() -> int:
    k = [
        ("üç program", set(FORMLAR) == {34, 44, 8}),
        ("anahtarlar tekil", all(len({b[0] for b in f["bolumler"]}) == len(f["bolumler"]) for f in FORMLAR.values())),
        ("TÜBİTAK A-E bölümleri sırayla", [b[0][0] for b in _TUBITAK["bolumler"]] == list("ABBBBCCCDDE")),
        ("KOSGEB 2.11-2.20", [b[0] for b in _KOSGEB_KG["bolumler"]] == [f"2.{i}" for i in range(11, 21)]),
        ("kaynaklar resmi", all(f["kaynak"].startswith(("https://www.tubitak.gov.tr", "https://webdosya.kosgeb.gov.tr"))
                                for f in FORMLAR.values())),
    ]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in k)
    print(f"\nself-test: {gecen}/{len(k)} geçti")
    return 0 if gecen == len(k) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
