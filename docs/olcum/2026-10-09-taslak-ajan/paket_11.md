# Vaka 11: Hizmet İhracatı Destekleri – Bilişim Sektörü (10962 sayılı Karar, Hizmet Sektörleri Atılım Programı) — Ticaret Bakanlığı

## Senin işletmen (yalnız bunları biliyorsun)
Ege Yazılım Ltd. Şti., İzmir, 18 çalışan, ciro 35 milyon TL, gelirin %30'u ABD'deki SaaS abonelerinden. 2027'de ABD'de büyümek için: yurt dışı dijital reklam 600.000 TL, Web Summit fuarı katılımı 350.000 TL, ABD pazar araştırması raporu 150.000 TL. Bilmediğin: hizmet ihracatçısı olarak hangi kayıtların gerektiği.

## Uygulamanın gösterdiği program bilgisi
Başvuru yeri: Ticaret Bakanlığı Uluslararası Hizmet Ticareti Genel Müdürlüğü; incelemeci kuruluş: Hizmet İhracatçıları Birliği Genel Sekreterliği (DYS üzerinden)
Dönem: Sürekli (program bazlı; yararlanıcı başına en fazla 5 yıl)
Tutar/oran: -
Kaynak: https://ticaret.gov.tr/data/69a9d756269de18b843851b7/%C3%87er%C3%A7eve%20Karar.pdf

Kontrol listesi:
- [sart] Yararlanıcı: Türkiye'de yerleşik, 6102 sayılı TTK hükümlerine göre kurulmuş şirket (veya 1163 sayılı Kanun kapsamında kooperatif) olmak (Karar MADDE 3 – 'Yararlanıcı' tanımı); şahıs işletmesi ve şirketleşmemiş girişim yararlanıcı tanımına girmez
- [sart] Bilişim sektöründe faaliyet göstermek; desteğe konu ürün yararlanıcının kendi yazılımı, mobil uygulaması veya dijital oyunu olmak (MADDE 16, 17, 22)
- [sart] Giderlerin yurt dışı pazara giriş / yurt dışına yönelik faaliyetlere ilişkin olması (MADDE 16, 17, 22)
- [sart] Ürün bazlı desteklerde yılda en fazla 10 ürün; yararlanıcı başına destek süresi en fazla 5 yıl (MADDE 16/2, 17/2-3, 22/2-3, 23/2, 31/2)
- [sart] Destek, giderler yapılıp belgelendikten sonra ödenir (geri ödemesiz, harcama sonrası); usul ve esaslar Genelge'de (Genelge MADDE 1-4)
- [belge] Destek Yönetim Sistemi (DYS) üzerinden başvuru ve gider belgeleri (Genelge MADDE 3 dayanağı: 2019/7 sayılı Ticaret Bakanlığı DYS Genelgesi)
- [belge] Gider faturaları/dekontları ve ödeme belgeleri
- [basvuru] Başvuruyu yap: Ticaret Bakanlığı Uluslararası Hizmet Ticareti Genel Müdürlüğü; incelemeci kuruluş: Hizmet İhracatçıları Birliği Genel Sekreterliği (DYS üzerinden) — Sürekli (program bazlı; yararlanıcı başına en fazla 5 yıl)

Başvuru dönemleri:
- (kayıtlı dönem yok)

## Sihirbaz soruları (GET /api/basvuru-listesi/182/taslak-sorulari yanıtı)
```json
{
 "turler": [
  "ihracat"
 ],
 "gerekce": [
  {
   "anahtar": "pazar",
   "etiket": "Hedef pazarlar ve seçim gerekçesi",
   "ipucu": "Ülkeler, pazar araştırması dayanağı"
  },
  {
   "anahtar": "mevcut_ihracat",
   "etiket": "Mevcut ihracat durumu",
   "ipucu": "Son yıl ihracat, başlıca alıcılar/kanallar"
  },
  {
   "anahtar": "rekabet",
   "etiket": "Rekabet avantajı",
   "ipucu": "Ürün, fiyat, sertifika, marka"
  }
 ],
 "cikti": [
  {
   "anahtar": "ihracat",
   "etiket": "İhracat hedefi",
   "ipucu": "Son yıl → hedef tutar ve pazarlar"
  }
 ],
 "faaliyet_onerileri": [
  "Pazar araştırması ve hedef ülke seçimi",
  "Tanıtım/fuar/pazaryeri faaliyetleri",
  "Alıcı görüşmeleri ve sipariş",
  "İhracat sonuçlarının izlenmesi"
 ],
 "gider_kalemleri": [],
 "oran_secenekleri": [
  50.0
 ],
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
