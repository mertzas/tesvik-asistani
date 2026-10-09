# Vaka 07: E-İhracat Destekleri (5986 Sayılı Karar) — Ticaret Bakanlığı

## Senin işletmen (yalnız bunları biliyorsun)
Karadeniz Fındık Gıda Ltd. Şti., Trabzon, 3 çalışan, ciro 4 milyon TL. Fındık ezmesi ve kavrulmuş fındığı Amazon Almanya ve Etsy'de satıyorsunuz; geçen yıl yurt dışı satış 900.000 TL. 2027 planı: pazaryeri reklamı 240.000 TL, pazaryeri komisyonları 120.000 TL, Almanya'da sipariş karşılama (fulfillment) deposu 60.000 TL. Hedef 2027 yurt dışı satış 2.500.000 TL. İhracatçı birliği üyesisiniz. Bilmediğin: E-İhracat Destekleri'nde başvurunun hangi sırayla yapılacağı.

## Uygulamanın gösterdiği program bilgisi
Başvuru yeri: Önce ön onay, sonra ödeme başvurusu; ikisi de üyesi olunan İhracatçı Birliği Genel Sekreterliğine (incelemeci kuruluş) DYS üzerinden. İlk başvuruda EK-Şirket Başvuru Formu verilir.
Dönem: Destek süresi ön onay tarihini izleyen ayın ilk günü başlar; ödeme başvurusu ödeme belgesi tarihinden itibaren en geç 6 ay içinde, çeyrek dönemler itibarıyla
Tutar/oran: %50 (dijital pazaryeri reklamı, e-ihracat tanıtımı ve sipariş karşılamada hedef ülkelerde %70); 2026 toplam yıllık üst limit şirketler için 73.990.019 TL
Kaynak: https://ticaret.gov.tr/destekler/e-ihracat-destekleri

Kontrol listesi:
- [sart] Bir ihracatçı birliğine üye olmak (başvuru üyesi olunan İhracatçı Birliği Genel Sekreterliğine yapılır)
- [sart] Ticaret Bakanlığı Destek Yönetim Sistemi (DYS) kaydı; MERSİS kaydı güncel ve NACE kodu doğru
- [sart] Şirket ya da kooperatif olmak (şahıs işletmesi yalnız E-İhracat Konsorsiyumu aracılığıyla, sınırlı süre)
- [sart] Ürün Türk ürünü olmalı (üretimin tamamı ya da bir bölümü Türkiye'de); pazaryeri listelemesinde KTÜN, üretim yeri (Türkiye) ve tescilli marka bilgisi girilmeli (el işi/kişiselleştirilmiş ürünlerde KTÜN ve marka aranmayabilir)
- [sart] Her destek kalemi için önce ön onay alınmalı
- [belge] EK-Şirket Başvuru Formu (ilk başvuruda; marka tescil belgesi, tedarik ediliyorsa tedarik belgesi, üreticiyse kapasite raporu)
- [belge] Kaleme özel ön onay ve ödeme başvuru formları (Genelge Ekleri)
- [basvuru] Başvuruyu yap: Önce ön onay, sonra ödeme başvurusu; ikisi de üyesi olunan İhracatçı Birliği Genel Sekreterliğine (incelemeci kuruluş) DYS üzerinden. İlk başvuruda EK-Şirket Başvuru Formu verilir. — Destek süresi ön onay tarihini izleyen ayın ilk günü başlar; ödeme başvurusu ödeme belgesi tarihinden itibaren en geç 6 ay içinde, çeyrek dönemler itibarıyla

Başvuru dönemleri:
- (kayıtlı dönem yok)

## Sihirbaz soruları (GET /api/basvuru-listesi/162/taslak-sorulari yanıtı)
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
  70.0,
  50.0
 ],
 "ust_limit": 73990019.0,
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
