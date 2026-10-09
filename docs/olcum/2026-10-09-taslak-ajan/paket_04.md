# Vaka 04: Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) — Sanayi ve Teknoloji Bakanlığı

## Senin işletmen (yalnız bunları biliyorsun)
Van Gölü Turizm A.Ş., 25 çalışan, ciro 30 milyon TL, Van'da 40 odalı otel işletiyorsunuz. Proje: 30 odalı ek bina ile 70 odaya çıkmak. Yatırım tutarı 85.000.000 TL: inşaat 55.000.000, makine-teçhizat 18.000.000, mobilya-donanım 12.000.000 TL. 15 yeni istihdam. Mart 2027 - Haziran 2028. Arsa şirketin mülkü. Bilmediğin: teşvik belgesi başvurusunun teknik ayrıntıları, finansmanın ne kadarının kredi olacağı.

## Uygulamanın gösterdiği program bilgisi
Başvuru yeri: Sanayi ve Teknoloji Bakanlığı Teşvik Uygulama ve Yabancı Sermaye Genel Müdürlüğü (E-TUYS)
Dönem: Dönem yok: teşvik belgesi müracaatı E-TUYS üzerinden yapılır ve 31/12/2030 tarihine kadar yapılan müracaatlar değerlendirilir (9903 sayılı Karar m.5/5, m.5/12). Müracaat tarihinden önce yapılan yatırım harcamaları belge kapsamına alınmaz (m.5/6): harcamaya başlamadan önce başvurun.
Tutar/oran: -
Kaynak: https://www.yatirimadestek.gov.tr/pdf/assets/upload/dosyalar/karar-yatirim_tesvik_uygulamalari.pdf#hedef-yatirimlar

Kontrol listesi:
- [sart] Yatırım konusunun Karar'ın EK-3 listesinde ('Desteklerden faydalanabilecek sektörler ve şartlar') yer alması ve oradaki şartları sağlaması; eşleştirme NACE Rev.2.1 kodu üzerinden yapılır (MADDE 5/1).
- [sart] EK-3'te yer alan yatırım konuları, belirtilen şartları sağlamaları hâlinde desteklenir (MADDE 10/1).
- [sart] Asgari sabit yatırım tutarı (ayrıca belirtilmemişse): 1. ve 2. bölgelerde 12 milyon TL, diğer bölgelerde 6 milyon TL (MADDE 5/2).
- [sart] Finansal kiralama yöntemiyle yapılacak yatırımlarda, kiralamaya konu makine ve teçhizatın toplam tutarının her bir finansal kiralama şirketi için asgari 3 milyon TL olması (MADDE 5/3).
- [sart] Projenin, makroekonomik programlar ve arz-talep dengesi dikkate alınarak yapılacak sektörel, malî ve teknik değerlendirme sonucunda uygun görülmesi ve teşvik belgesi düzenlenmesi (MADDE 5/4).
- [sart] Müracaatın 31/12/2030 tarihine kadar yapılmış olması (MADDE 5/5).
- [sart, kural] DİKKAT: teşvik belgesi müracaat tarihinden ÖNCE gerçekleştirilmiş yatırım harcamaları belge kapsamına ALINMAZ (MADDE 5/6) - harcamaya başlamadan önce başvurun.
- [sart] KOBİ olmayan yatırımcılar ve Yerel Kalkınma Hamlesi yatırımcıları, sabit yatırım tutarının en az %2'si tutarında ekosistem geliştirme planı gerçekleştirmekle yükümlüdür (vergi indirimi öngörülen yatırımlarda) (MADDE 5/9).
- [sart] Başvuru ve tüm işlemler E-TUYS üzerinden elektronik ortamda yapılır (MADDE 5/12).
- [belge] E-TUYS yetkilendirmesi için Dilekçe, Taahhütname ve Kullanıcı Yetkilendirme Formu (Bakanlığın KEP adresine Kayıtlı Elektronik Posta ile gönderilir)
- [belge] Yetkilendirme sonrası yatırım teşvik belgesi başvurusu E-TUYS üzerinden yapılır; istenen bilgi ve belgeler E-TUYS kılavuzlarında tanımlıdır
- [basvuru] Başvuruyu yap: Sanayi ve Teknoloji Bakanlığı Teşvik Uygulama ve Yabancı Sermaye Genel Müdürlüğü (E-TUYS) — Dönem yok: teşvik belgesi müracaatı E-TUYS üzerinden yapılır ve 31/12/2030 tarihine kadar yapılan müracaatlar değerlendirilir (9903 sayılı Karar m.5/5, m.5/12). Müracaat tarihinden önce yapılan yatırım harcamaları belge kapsamına alınmaz (m.5/6): harcamaya başlamadan önce başvurun.

Başvuru dönemleri:
- 9903 teşvik belgesi müracaat süresi: Başvuruya açık

## Sihirbaz soruları (GET /api/basvuru-listesi/180/taslak-sorulari yanıtı)
```json
{
 "turler": [
  "yatirim"
 ],
 "gerekce": [
  {
   "anahtar": "darbogaz",
   "etiket": "Mevcut kapasite ve darboğazlar",
   "ipucu": "Hangi süreç ya da makinede darboğaz var, kapasite kullanım oranı"
  },
  {
   "anahtar": "talep",
   "etiket": "Karşılanamayan talep",
   "ipucu": "Reddedilen/ertelenen siparişler, talep artışı"
  },
  {
   "anahtar": "cozum",
   "etiket": "Yatırımın çözeceği sorun",
   "ipucu": "Verimlilik, kalite, maliyet etkisi"
  }
 ],
 "cikti": [
  {
   "anahtar": "kapasite",
   "etiket": "Kapasite artışı",
   "ipucu": "Mevcut → hedef (birim/yıl)"
  }
 ],
 "faaliyet_onerileri": [
  "Teklif ve proformaların toplanması",
  "Makine/ekipman tedariki",
  "Kurulum ve devreye alma",
  "Kapasite/verimlilik artışının ölçülmesi"
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
