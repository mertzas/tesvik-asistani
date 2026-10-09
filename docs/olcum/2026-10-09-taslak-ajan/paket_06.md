# Vaka 06: Girişimci Destek Programı — KOSGEB

## Senin işletmen (yalnız bunları biliyorsun)
Eskişehir'de 34 yaşında bir kadınsın; Uygulamalı Girişimcilik Eğitimi sertifikan var, henüz işletme kurmadın. Butik pastane açacaksın (NACE 10.71). Kuruluş planı: şahıs işletmesi olarak Ocak 2027'de kuruluş, 2 çalışan. Giderler: fırın ve soğutma makineleri 350.000 TL, dükkân dekorasyonu 150.000 TL, ilk 6 ay kira 180.000 TL. İlk yıl satış hedefi 2.400.000 TL. Bilmediğin: hangi giderlerin desteklendiği, iş planının nasıl yazılacağı.

## Uygulamanın gösterdiği program bilgisi
Başvuru yeri: KOSGEB e-Hizmetler (e-Devlet şifresi ile online)
Dönem: Dönemsel çağrı: İş Geliştirme 2026/2 dönemi 20 Nisan – 8 Mayıs 2026 (kapandı); yılda iki dönem, güncel takvim KOSGEB duyurularından
Tutar/oran: İş Kurma: gerçek kişi 10.000 TL / sermaye şirketi 20.000 TL (%100 geri ödemesiz; genç/kadın/engelli/gazi/şehit yakını +10.000 TL); İş Geliştirme: 1.500.000 TL'ye kadar (%80 geri ödemeli, +150.000 TL ilave); kredi faiz/kâr payı desteği: 1.000.000 TL kredi, faizin %50'si geri ödemesiz
Kaynak: https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/1231/girisimci-destek-programi

Kontrol listesi:
- [sart] İş Kurma Desteği: KOSGEB destekli sektörde faaliyet gösteren 0-1 yaş işletme
- [sart] İş Geliştirme Desteği: İmalat/yazılım/Ar-Ge sektöründe 0-3 yaş işletme
- [sart] KOSGEB veri tabanına kayıtlı ve aktif olmalı
- [sart] Şirket türü tutarı belirler: Gerçek kişi (şahıs) işletmesi 10.000 TL, sermaye şirketi (Ltd./A.Ş.) 20.000 TL İş Kurma Desteği alır
- [sart] Girişimcinin başvurduğu işletmedeki ortaklık payı en az %50 olmalıdır
- [sart] Desteklenen sektörler arasında imalat, telekomünikasyon, bilgisayar programlama, bilişim altyapısı ve bilimsel Ar-Ge yer alır
- [belge] e-Devlet üzerinden başvuru formu
- [belge] Proje Bilgi Dokümanı
- [belge] Ödeme Belgeleri
- [belge] İşletme Değerlendirme Raporu (gerekirse)
- [basvuru] Başvuruyu yap: KOSGEB e-Hizmetler (e-Devlet şifresi ile online) — Dönemsel çağrı: İş Geliştirme 2026/2 dönemi 20 Nisan – 8 Mayıs 2026 (kapandı); yılda iki dönem, güncel takvim KOSGEB duyurularından

Başvuru dönemleri:
- İş Geliştirme Çağrısı 2026 yılı 2. dönem: Kapandı

## Sihirbaz soruları (GET /api/basvuru-listesi/1/taslak-sorulari yanıtı)
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
  100.0,
  80.0,
  50.0
 ],
 "ust_limit": 30000.0,
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
