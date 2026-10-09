# Vaka 02: 1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç Destek Programı — TUBITAK

## Senin işletmen (yalnız bunları biliyorsun)
Bulut Muhasebe Yazılım Ltd. Şti., İstanbul, 12 çalışan, ciro 20 milyon TL. KOBİ'lere bulut muhasebe yazılımı satıyorsunuz (1.400 abone). İlk TÜBİTAK başvurunuz. Proje: gelen e-faturaları gider hesaplarına otomatik sınıflandıran makine öğrenmesi modülü. Bugün müşteriler bunu elle yapıyor; sizin kural tabanlı denemeniz %70 doğru. Hedef %95 doğruluk ve fatura başına 2 saniyenin altında işlem. 12 ay, Şubat 2027 başlangıç. Bütçe: personel (2 yazılımcı + 1 veri bilimci, kısmi) 1.400.000 TL, bulut/GPU ve yazılım lisansı 250.000 TL, üniversiteden danışmanlık 200.000 TL. Ticarileşme: mevcut abonelere ek modül olarak aylık ücretle. Bilmediğin: hangi ML yöntemi seçileceği henüz netleşmedi.

## Uygulamanın gösterdiği program bilgisi
Başvuru yeri: Elektronik olarak PRODİS sistemi (https://eteydeb.tubitak.gov.tr)
Dönem: Yılda iki çağrı dönemi: genellikle Ocak-Şubat ve Temmuz-Ağustos (güncel duyuru tubitak.gov.tr'den teyit edilmeli)
Tutar/oran: Proje bütçesi en fazla 3.500.000 TL; ilk 5 projede %75 hibe (en az ikisi ortaklı başvuru kaydıyla); 2026 yılı 2. çağrı dokümanı
Kaynak: https://www.tubitak.gov.tr/tr/destekler/sanayi/ulusal-destek-programlari/1507-tubitak-kobi-ar-ge-baslangic-destek-programi

Kontrol listesi:
- [sart] Türkiye'de yerleşik, sermaye şirketi statüsünde bir KOBİ olmak
- [sart, kural] Aynı anda en fazla 5 projeye destek alınabilir, bunların en az 2'si ortaklı proje olmalı
- [belge] PRODİS sistemi üzerinden proje öneri formu
- [belge] Şirket kuruluş/faaliyet belgeleri
- [basvuru] Başvuruyu yap: Elektronik olarak PRODİS sistemi (https://eteydeb.tubitak.gov.tr) — Yılda iki çağrı dönemi: genellikle Ocak-Şubat ve Temmuz-Ağustos (güncel duyuru tubitak.gov.tr'den teyit edilmeli)

Başvuru dönemleri:
- 2026 yılı 2. çağrı: Başvuruya açık

## Sihirbaz soruları (GET /api/basvuru-listesi/44/taslak-sorulari yanıtı)
```json
{
 "turler": [
  "arge"
 ],
 "gerekce": [
  {
   "anahtar": "A3",
   "etiket": "A.3 Proje Kısa Tanıtımı",
   "ipucu": "Projenin konusu, amacı ve beklenen çıktısı (kısa)"
  },
  {
   "anahtar": "B1",
   "etiket": "B.1 Projenin Çağrı Konusuyla İlişkisi ve Hedefleri",
   "ipucu": "Proje çağrı konusuna nasıl karşılık geliyor; hedefler"
  },
  {
   "anahtar": "B2",
   "etiket": "B.2 Projenin Teknoloji Düzeyi",
   "ipucu": "Tekniğin/teknolojinin bilinen güncel durumu (ulusal ve uluslararası) ve projenin özgün katkısı"
  },
  {
   "anahtar": "B3",
   "etiket": "B.3 Projenin Somut / Ölçülebilir Hedeflerle Tanıtımı ve Çözüm Yaklaşımları (Ar-Ge Sistematiği)",
   "ipucu": "Proje çıktısının ölçülebilir başarı ölçütleri ve hedef değerleri; çözüm yaklaşımı ve yöntem"
  },
  {
   "anahtar": "B4",
   "etiket": "B.4 Projenin Yenilikçi Yönleri",
   "ipucu": "Benzer ürün/sistemlerle karşılaştırma; yenilik düzeyi (firma, ülke ya da dünya için yeni)"
  },
  {
   "anahtar": "C1",
   "etiket": "C.1 İş Planı",
   "ipucu": "İş paketleri, süreleri ve her paketin maliyet unsurları"
  },
  {
   "anahtar": "C2",
   "etiket": "C.2 Proje Yönetimi ve Organizasyonu",
   "ipucu": "Proje ekibi, görev dağılımı, yönetim ve izleme"
  },
  {
   "anahtar": "C3",
   "etiket": "C.3 Kuruluş Altyapısı",
   "ipucu": "Ar-Ge yapılanması, ekipman, deneyim"
  },
  {
   "anahtar": "D1",
   "etiket": "D.1 Ekonomik Öngörüler",
   "ipucu": "Ticari başarı potansiyeli, hedef pazar ve müşteriler, ithal ürün ikamesi, ekonomik getiri tahmini"
  },
  {
   "anahtar": "D2",
   "etiket": "D.2 Ulusal Kazanımlar",
   "ipucu": "Bilgi birikimine katkı, patent/lisans beklentisi, üniversite-sanayi işbirliği, yeni istihdam"
  },
  {
   "anahtar": "E1",
   "etiket": "E.1 Risk ve Finansman Yönetimi",
   "ipucu": "Teknik/ticari riskler, önlemler ve projenin finansmanı"
  }
 ],
 "cikti": [
  {
   "anahtar": "arge_cikti",
   "etiket": "Ar-Ge çıktıları",
   "ipucu": "Prototip, patent/faydalı model başvurusu, teknoloji hazırlık seviyesi"
  }
 ],
 "faaliyet_onerileri": [
  "Literatür/patent taraması ve gereksinimler",
  "Tasarım ve prototip geliştirme",
  "Test ve doğrulama",
  "Ticarileşme hazırlığı (fikri mülkiyet, pilot müşteri)"
 ],
 "gider_kalemleri": [],
 "oran_secenekleri": [
  75.0
 ],
 "ust_limit": 3500000.0,
 "form": {
  "ad": "TÜBİTAK Proje Öneri Bilgileri Formu (AGY100/AGY101, PRODİS)",
  "kaynak": "https://www.tubitak.gov.tr/sites/default/files/2024-09/1501_1507_proje_oneri_bilgileri_formu_hazirlama_kilavuzu_agy100-101.pdf",
  "tablolar": [
   "Proje bütçesi: M011 Personel, M012 Seyahat, M013 Alet/Teçhizat/Yazılım/Yayın, M014 Ar-Ge ve test kuruluşlarına yaptırılan işler, M015 Hizmet alımı, M016 Malzeme",
   "M030 Dönemsel giderler tablosu"
  ]
 }
}
```

## Cevap biçimi
```json
{
 "proje_adi": "metin (≤200)",
 "proje_ozeti": "metin (≤2000)",
 "gerekce": {
  "<soru anahtarı>": "metin (≤2000)"
 },
 "faaliyetler": [
  {
   "ad": "metin",
   "baslangic": "YYYY-AA veya null",
   "bitis": "YYYY-AA veya null"
  }
 ],
 "butce": [
  {
   "kalem": "metin",
   "tutar": "sayı (TL)"
  }
 ],
 "destek_orani": "oran_secenekleri'nden biri veya null",
 "ciktilar": {
  "<soru anahtarı veya 'olcum'>": "metin"
 }
}
```
