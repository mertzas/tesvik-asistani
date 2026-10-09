# Vaka 12: KOBİ Dijital Dönüşüm Destek Programı — KOSGEB

## Senin işletmen (yalnız bunları biliyorsun)
Kayseri Ahşap Mobilya Ltd. Şti., 22 çalışan, ciro 40 milyon TL. Siparişleri Excel'de takip ediyorsunuz, üretimde gecikmeler var. Proje: ERP + üretim takip (MES) yazılımı ve atölyeye 6 tablet/barkod okuyucu. Yazılım 700.000 TL, donanım 300.000 TL. Hedef: teslim süresini 21 günden 14 güne indirmek. Bilmediğin: dijital dönüşüm danışmanı raporu gerekip gerekmediği.

## Uygulamanın gösterdiği program bilgisi
Başvuru yeri: KOSGEB KOBİ Bilgi Sistemi (online)
Dönem: Sürekli açık başvuru (24 aylık program süresi içinde kullanım gerekir)
Tutar/oran: ₺1.000.000 - ₺20.000.000 kredi (faiz desteği geri ödemesiz)
Kaynak: https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9144/kobi-dijital-donusum-destek-programi

Kontrol listesi:
- [sart] C-İmalat sektöründe faaliyet (NACE kodu)
- [sart] KOSGEB veri tabanında aktif kayıtlı KOBİ
- [sart] Onaylı dijital dönüşüm/olgunluk değerlendirme raporu (TÜSSİDE-DDX veya SIRI formatı)
- [sart] Son mali yıl öz kaynakları pozitif, son 3 yıldan en az biri kârlı
- [belge] Dijital dönüşüm/olgunluk değerlendirme raporu
- [belge] Başvuru Formu
- [belge] Mali tablolar ve işletme beyanı
- [belge] Satın alma faturaları/makbuzlar
- [basvuru] Başvuruyu yap: KOSGEB KOBİ Bilgi Sistemi (online) — Sürekli açık başvuru (24 aylık program süresi içinde kullanım gerekir)

Başvuru dönemleri:
- (kayıtlı dönem yok)

## Sihirbaz soruları (GET /api/basvuru-listesi/3/taslak-sorulari yanıtı)
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
 "ust_limit": 20000000.0,
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
