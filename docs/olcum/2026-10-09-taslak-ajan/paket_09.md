# Vaka 09: Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İstihdamı Teşviki (4447 sayılı Kanun geçici 10. madde) — SGK / İŞKUR

## Senin işletmen (yalnız bunları biliyorsun)
Hatay'da 4 çalışanlı lokanta (şahıs işletmesi). Kasım 2026'da 3 kişi işe alacaksın: 22 ve 25 yaşında iki genç erkek ve 35 yaşında bir kadın; üçü de son 6 ayda kayıtlı çalışmamış, ikisi İŞKUR'a kayıtlı. Aylık brüt ücret asgari ücret. Bilmediğin: teşvikin hangi ayda başlayacağı ve sana kaç TL kazandıracağı.

## Uygulamanın gösterdiği program bilgisi
Başvuru yeri: SGK (e-Bildirge) — uygulayıcı kurum; bilgi: İŞKUR il müdürlükleri
Dönem: Sürekli; 31.12.2026 tarihine kadar yapılan işe alımlar için
Tutar/oran: İşveren SGK prim payı, kişi başı aylık 7.184,03–64.656,23 TL (2026; prime esas kazancın alt ve üst sınırı arası), 6–54 ay
Kaynak: https://www.iskur.gov.tr/isveren/tesvikler/kadin-genc-ve-mesleki-yeterlilik-belgesi-olanlarin-tesviki/

Kontrol listesi:
- [sart] İşe alınan kişinin son 6 aydır işsiz olması
- [sart] Kişinin, işe alındığı tarihten önceki son 6 ayın ortalama sigortalı çalışan sayısına İLAVE olarak istihdam edilmesi
- [sart] Özel sektör işvereni olmak; aylık prim ve hizmet belgelerinin yasal süresinde verilmesi ve primlerin ödenmesi (SGK genel şartları)
- [sart] Uygulama süresi: 31.12.2026 tarihine kadar işe alımlar
- [belge] SGK e-Bildirge üzerinden teşvik kodu ile bildirim
- [belge] İŞKUR kaydı (ek 6 ay için)
- [basvuru] Başvuruyu yap: SGK (e-Bildirge) — uygulayıcı kurum; bilgi: İŞKUR il müdürlükleri — Sürekli; 31.12.2026 tarihine kadar yapılan işe alımlar için

Başvuru dönemleri:
- (kayıtlı dönem yok)

## Sihirbaz soruları (GET /api/basvuru-listesi/185/taslak-sorulari yanıtı)
```json
{
 "turler": [
  "istihdam"
 ],
 "gerekce": [
  {
   "anahtar": "istihdam",
   "etiket": "Korunacak/oluşturulacak istihdam",
   "ipucu": "Pozisyonlar ve kişi sayısı"
  },
  {
   "anahtar": "durum",
   "etiket": "İstihdamı etkileyen durum",
   "ipucu": "Talep düşüşü, finansman ihtiyacı, büyüme"
  }
 ],
 "cikti": [
  {
   "anahtar": "ilave_istihdam",
   "etiket": "İstihdam etkisi",
   "ipucu": "İlave ya da korunan istihdam (kişi)"
  }
 ],
 "faaliyet_onerileri": [
  "İşe alım/istihdamın korunması planı",
  "SGK bildirgeleriyle izleme"
 ],
 "gider_kalemleri": [],
 "oran_secenekleri": [],
 "ust_limit": null,
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
