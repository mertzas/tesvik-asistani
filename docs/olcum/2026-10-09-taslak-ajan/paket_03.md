# Vaka 03: Kapasite Geliştirme Destek Programı — KOSGEB

## Senin işletmen (yalnız bunları biliyorsun)
Konya Hassas Metal Ltd. Şti., 28 çalışan, ciro 85 milyon TL. Tarım makinelerine CNC ile yedek parça işliyorsunuz. Proje: 2 adet 5 eksen CNC işleme merkezi ve 1 koordinat ölçüm cihazı (CMM) alarak kapasiteyi %35 artırmak ve ihracatın satışlardaki payını %10'dan %25'e çıkarmak (müşteriler Almanya ve Romanya'da). Makineler 9.500.000 TL, CAM yazılımı 400.000 TL, operatör eğitimi 150.000 TL. 2 yeni CNC operatörü alınacak. Süre 12 ay, Mart 2027. Yurt içi 3 rakibiniz var (Konya ve Bursa'da). Bilmediğin: ürününüzün dış ticaret istatistikleri ve pazar büyüklüğü rakamları; yatırımın geri dönüş süresini hesaplamadınız.

## Uygulamanın gösterdiği program bilgisi
Başvuru yeri: KOSGEB e-Hizmetler (edevlet.kosgeb.gov.tr)
Dönem: Dönemsel çağrı: 2026 yılı 2. başvuru dönemi 6 Haziran 2026'da başladı; güncel takvim KOSGEB duyurularından
Tutar/oran: ₺1.000.000 - ₺20.000.000 (kredi limiti)
Kaynak: https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9200/kapasite-gelistirme-destek-programi

Kontrol listesi:
- [sart] İmalat, telekomünikasyon, bilgisayar programlama vb. NACE kodunda faaliyet
- [sart] KOSGEB veri tabanında aktif kayıtlı KOBİ
- [sart] Hızlı büyüyen işletme (teknogirişim rozeti veya tedarikçi geliştirme protokolü ile şart aranmayabilir)
- [belge] Başvuru Kontrol Formu
- [belge] KOSGEB e-hizmetler üzerinden istenen ek belgeler (mevzuata göre değişir)
- [basvuru] Başvuruyu yap: KOSGEB e-Hizmetler (edevlet.kosgeb.gov.tr) — Dönemsel çağrı: 2026 yılı 2. başvuru dönemi 6 Haziran 2026'da başladı; güncel takvim KOSGEB duyurularından

Başvuru dönemleri:
- 2026 yılı 2. başvuru dönemi: Kapandı

## Sihirbaz soruları (GET /api/basvuru-listesi/8/taslak-sorulari yanıtı)
```json
{
 "turler": [
  "yatirim"
 ],
 "gerekce": [
  {
   "anahtar": "2.11",
   "etiket": "2.11 İşletmenin Tarihçesi, Mevcut Faaliyetleri, Ortakları ve Proje Deneyimleri",
   "ipucu": "Tarihçe, ürün/ürün grupları, proje deneyimleri, ortakların deneyimi; ortak olunan diğer firmalar"
  },
  {
   "anahtar": "2.12",
   "etiket": "2.12 Proje Konusu ile İlgili Mevcut Durum",
   "ipucu": "Mevcut faaliyetler ve ihtiyaçların bugün nasıl karşılandığı"
  },
  {
   "anahtar": "2.13",
   "etiket": "2.13 Projenin Amacı ve Gerekçesi",
   "ipucu": "Projeye neden ihtiyaç var; hazırlık ve teknik fizibilite çalışmaları"
  },
  {
   "anahtar": "2.14",
   "etiket": "2.14 Projenin Konusu",
   "ipucu": "Faaliyetler; kapasite, ürün çeşitliliği, teknoloji düzeyi, ihracat potansiyeli ve insan kaynağına etkisi"
  },
  {
   "anahtar": "2.15",
   "etiket": "2.15 Projenin Hedef ve Faaliyetleri",
   "ipucu": "Hedef kartları: her hedefin faaliyetleri, çıktıları ve giderlerinin gerekçesi"
  },
  {
   "anahtar": "2.16",
   "etiket": "2.16 Projenin Hedeflere, Pazara ve Rekabet Durumuna Etkisi",
   "ipucu": "Orta/uzun dönem hedeflere katkı, pazar payı ve genişliği, lojistik uygunluk"
  },
  {
   "anahtar": "2.17",
   "etiket": "2.17 Riskler, Önlemler ve Varsayımlar",
   "ipucu": "Uygulama sırasında ve sonrasında riskler ve önlemler"
  },
  {
   "anahtar": "2.18",
   "etiket": "2.18 Projede Kullanılacak İşletme Kaynakları",
   "ipucu": "Personel, makine ve öz kaynakla yapılacak giderler"
  },
  {
   "anahtar": "2.19",
   "etiket": "2.19 Proje Yönetimi",
   "ipucu": "Proje yöneticisi, koordinasyon, gözden geçirme ve izleme görev dağılımı"
  },
  {
   "anahtar": "2.20",
   "etiket": "2.20 Sürdürülebilirlik",
   "ipucu": "Kurumsal ve mali sürdürülebilirlik"
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
 "form": {
  "ad": "KOSGEB Kapasite Geliştirme Destek Programı Proje Başvuru Formu (II. Bölüm)",
  "kaynak": "https://webdosya.kosgeb.gov.tr/Content/Upload/Dosya/KAPAS%C4%B0TE%20GEL%C4%B0ST%C4%B0RME/2026/2026.08.21/02b-Kapasite_Gelis%CC%A7tirme_Destek_Program%C4%B1_Proje_Bas%CC%A7vuru_Formu_II.Bo%CC%88lu%CC%88m.pdf",
  "tablolar": [
   "2.3 Proje konusu ürüne ilişkin bilgiler",
   "2.4 Dış ticaret verileri (son 3 yıl)",
   "2.5 Yurt içi-yurt dışı pazar büyüklüğü (son 3 yıl)",
   "2.6 Ürüne-muadiline ilişkin ihracat ve ithalat",
   "2.7 Rakip firmalar",
   "2.8 Müşteriler",
   "2.9 Üretim-satış planı",
   "2.10 Yatırımın geri dönüş süresi"
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
