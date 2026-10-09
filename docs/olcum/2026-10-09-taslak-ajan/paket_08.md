# Vaka 08: Yapay Zekâ Kredi Programı — KOSGEB

## Senin işletmen (yalnız bunları biliyorsun)
Sohbet Yazılım Ltd. Şti., İstanbul, 12 çalışan, ciro 20 milyon TL. Yapay zekâ destekli müşteri hizmetleri asistanı ürününüz 40 kurumsal müşteride çalışıyor (TRL 8). Krediyle: GPU sunucu 1.800.000 TL, yapay zekâ yazılım lisansları 400.000 TL, veri etiketleme hizmeti 300.000 TL. Teknogirişim Rozeti'niz var mı bilmiyorsun. Kesin teminat mektubu için bankayla görüşmediniz.

## Uygulamanın gösterdiği program bilgisi
Başvuru yeri: KOSGEB bilgi sistemi (www.kosgeb.gov.tr ve/veya e-Devlet) üzerinden Yapay Zeka Kredi Başvurusu
Dönem: Sayfada dönem/son tarih belirtilmiyor; başvuru KOSGEB bilgi sistemi üzerinden elektronik ortamda, koşullar sistemce otomatik kontrol edilir
Tutar/oran: Kredi 500.000 – 5.000.000 TL; faiz ve komisyon yok; vade 24 ay (ilk 12 ay ödemesiz); GO Dijital Cüzdan'a blokeli, bankadan Kesin Teminat Mektubu zorunlu (limit = teminat tutarı, en az 500.000 TL); geçerli Teknogirişim Rozeti şartı
Kaynak: https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9414/yapay-zek-kredi-programi

Kontrol listesi:
- [sart] Türk Ticaret Kanunu'nda tanımlı gerçek veya tüzel kişi statüsünde KOBİ olmak
- [sart] KOSGEB sisteminde kayıtlı, işletme beyanı güncel ve aktif olmak
- [sart] Başvuru tarihi itibarıyla geçerli Teknogirişim Rozeti sahibi olmak
- [sart] GO Dijital Cüzdan hesabına sahip olmak
- [sart] Bankadan GO Dijital Teknoloji Hizmetleri A.Ş.'ye hitaben Kesin Teminat Mektubu getirmek (limit = teminat tutarı, en az 500.000 TL)
- [belge] Yapay Zekâ Kredisi Başvuru Formu (KOSGEB sistemi / e-Devlet üzerinden elektronik)
- [belge] Yapay Zekâ Kredisi Taahhütnamesi
- [belge] Yapay Zekâ Kredisi Hizmet Giderleri Tablosu
- [belge] Bankadan Kesin Teminat Mektubu (kredinin GO Dijital Cüzdan hesabına blokeli aktarımı için zorunlu)
- [basvuru] Başvuruyu yap: KOSGEB bilgi sistemi (www.kosgeb.gov.tr ve/veya e-Devlet) üzerinden Yapay Zeka Kredi Başvurusu — Sayfada dönem/son tarih belirtilmiyor; başvuru KOSGEB bilgi sistemi üzerinden elektronik ortamda, koşullar sistemce otomatik kontrol edilir

Başvuru dönemleri:
- (kayıtlı dönem yok)

## Sihirbaz soruları (GET /api/basvuru-listesi/2/taslak-sorulari yanıtı)
```json
{
 "turler": [
  "arge"
 ],
 "gerekce": [
  {
   "anahtar": "yenilik",
   "etiket": "Teknolojik yenilik ve özgün değer",
   "ipucu": "Mevcut çözümlerden farkı"
  },
  {
   "anahtar": "yontem",
   "etiket": "Teknik riskler ve yöntem",
   "ipucu": "Belirsizlikler, deney/prototip planı"
  },
  {
   "anahtar": "ticarilesme",
   "etiket": "Ticarileşme",
   "ipucu": "Hedef müşteri, pazar, gelir modeli"
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
 "oran_secenekleri": [],
 "ust_limit": 5000000.0,
 "form": null
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
