# Vaka 10: Hububat ve Baklagil Üretim Destekleri (Temel Destek + Planlı Üretim) — Tarım Bakanlığı

## Senin işletmen (yalnız bunları biliyorsun)
Konya'da 180 dekar buğday eken bir çiftçisin (şahıs). ÇKS kaydın var. Bu sezon sertifikalı tohum kullanacaksın. Traktörün eski; yeni mibzer almak istiyorsun (180.000 TL). Bilmediğin: hububat desteğinin ne zaman ve nasıl ödendiği, mibzerin bu destekle ilgisi.

## Uygulamanın gösterdiği program bilgisi
Başvuru yeri: İL/İlçe Tarım ve Orman Müdürlüğü (ÇKS başvurusu)
Dönem: Yıllık ilan edilir (ÇKS başvuru dönemi için BUGEM duyurularını takip edin)
Tutar/oran: Dekar başına 620–806 TL (2026): temel destek + planlı üretim desteği, her biri ürün katsayısı × 310 TL (mercimek/nohut 1,0; buğday/arpa/mısır 1,3); sertifikalı tohum ayrıca. 2026'da mazot ve gübre desteği 'temel destek' adıyla birleştirildi
Kaynak: https://www.tarimorman.gov.tr/BUGEM#hububat-baklagil

Kontrol listesi:
- [sart] Çiftçi Kayıt Sistemi (ÇKS)'ye kayıtlı olmak
- [sart] Arazi/parsel bilgilerinin ÇKS'de güncel olması
- [sart] İlgili üretim sezonunda ekim yapılmış olması
- [belge] ÇKS Kaydı
- [belge] Arazi/Parsel Belgesi
- [belge] Ekiliş Beyanı
- [basvuru] Başvuruyu yap: İL/İlçe Tarım ve Orman Müdürlüğü (ÇKS başvurusu) — Yıllık ilan edilir (ÇKS başvuru dönemi için BUGEM duyurularını takip edin)

Başvuru dönemleri:
- (kayıtlı dönem yok)

## Sihirbaz soruları (GET /api/basvuru-listesi/160/taslak-sorulari yanıtı)
```json
{
 "turler": [
  "tarim"
 ],
 "gerekce": [
  {
   "anahtar": "uretim",
   "etiket": "Üretim durumu",
   "ipucu": "Ürün, alan (dekar) ya da hayvan sayısı, ÇKS/TÜRKVET kaydı"
  },
  {
   "anahtar": "amac",
   "etiket": "Desteğin kullanım amacı",
   "ipucu": "Verim, kalite, maliyet, sertifikasyon"
  }
 ],
 "cikti": [
  {
   "anahtar": "tarim_cikti",
   "etiket": "Üretim etkisi",
   "ipucu": "Verim, alan ya da hayvan sayısı değişimi"
  }
 ],
 "faaliyet_onerileri": [
  "Kayıtların (ÇKS/ÖKS/TÜRKVET) güncellenmesi",
  "Üretim/uygulama dönemi",
  "Başvuru ve belge teslimi"
 ],
 "gider_kalemleri": [],
 "oran_secenekleri": [],
 "ust_limit": 806.0,
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
