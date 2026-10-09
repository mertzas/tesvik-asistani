# Vaka 05: 1512 - Girişimcilik Destek Programı (BiGG - Bireysel Genç Girişim) — TUBITAK

## Senin işletmen (yalnız bunları biliyorsun)
Ankara'da 26 yaşında bir yazılım mühendisisin; şirket kurmadın, bir arkadaşınla (ortak kurucu) birlikte çalışıyorsun. Fikir: işitme engelliler için Türk İşaret Dili'ni kameradan metne çeviren mobil uygulama. Laboratuvar ortamında 300 işaretle %80 tanıma yapan bir prototipin var (TRL 4). 12 ayda 1.000 işarete çıkıp 50 kullanıcılı pilot yapmak istiyorsun. Harcama planı: yazılım geliştirme hizmeti 300.000 TL, test cihazları 120.000 TL, pazar doğrulama ve kullanıcı testleri 80.000 TL. Bilmediğin: şirketi ne zaman kuracağın, ticari model (abonelik mi kurum satışı mı).

## Uygulamanın gösterdiği program bilgisi
Başvuru yeri: Uygulayıcı kuruluşlar (üniversite TTO'ları, teknokentler) üzerinden; TÜBİTAK çağrı duyurusuna göre
Dönem: Çağrı dönemli - güncel takvim TÜBİTAK'tan teyit edilmeli
Tutar/oran: BiGG Fonu hisse karşılığı yatırım: 1.350.000 TL (2026); +600.000 TL GCİP ek yatırım imkânı (2025'ten itibaren)
Kaynak: https://bigg.tubitak.gov.tr/

Kontrol listesi:
- [sart] Başvuru tarihi itibarıyla HERHANGİ BİR İŞLETMENİN ortaklık yapısında yer almamak (şirket kurulduysa başvurulamaz)
- [sart] Üniversitelerin ön lisans/lisans/yüksek lisans/doktora programlarından öğrenci veya mezun olmak
- [sart] Daha önce Teknogirişim Sermayesi Desteği veya TÜBİTAK 1512 2. Aşama sermaye desteği almamış olmak
- [sart] Teknoloji/yenilik odaklı bir iş fikrine sahip olmak
- [belge] İş fikri başvuru formu (1. Aşama)
- [belge] İş planı (2. Aşama)
- [belge] Öğrenci belgesi veya diploma
- [basvuru] Başvuruyu yap: Uygulayıcı kuruluşlar (üniversite TTO'ları, teknokentler) üzerinden; TÜBİTAK çağrı duyurusuna göre — Çağrı dönemli - güncel takvim TÜBİTAK'tan teyit edilmeli

Başvuru dönemleri:
- (kayıtlı dönem yok)

## Sihirbaz soruları (GET /api/basvuru-listesi/174/taslak-sorulari yanıtı)
```json
{
 "turler": [
  "girisim"
 ],
 "gerekce": [
  {
   "anahtar": "fikir",
   "etiket": "İş fikri ve çözülen sorun",
   "ipucu": "Hedef müşteri ve ihtiyacı"
  },
  {
   "anahtar": "ekip",
   "etiket": "Ekip ve yetkinlik",
   "ipucu": "Kurucular, deneyim"
  },
  {
   "anahtar": "model",
   "etiket": "İş modeli",
   "ipucu": "Gelir kaynakları, ilk müşteriler"
  }
 ],
 "cikti": [
  {
   "anahtar": "girisim_cikti",
   "etiket": "Girişim hedefleri",
   "ipucu": "Müşteri, gelir ve yatırım hedefi"
  }
 ],
 "faaliyet_onerileri": [
  "Şirket kuruluşu / kayıtlar",
  "Ürün/hizmetin ilk sürümü",
  "İlk müşteriler ve satış",
  "Büyüme planı"
 ],
 "gider_kalemleri": [],
 "oran_secenekleri": [
  5.0,
  3.0
 ],
 "ust_limit": 1350000.0,
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
