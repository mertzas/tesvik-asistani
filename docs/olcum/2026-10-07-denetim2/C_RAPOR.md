# Denetim 2 / Aşama C — danışman yanıt kalitesi (2026-10-07)

## Yöntem ve sınırlar (önce bunlar)
- 12 soru, 9 persona. Beklenen rakamlar Aşama A'da canlı kaynaktan doğrulanmış değerlerdir (`A_fark_tablosu.json`).
- **Yanıtların kaynağı iki türlü:**
  - Soru 1–3: gerçek `claude-sonnet-5` çağrısı (3 çağrı, ≈0,3 USD). Eski bağlamla (aşağıdaki hata düzeltilmeden önce) üretildi.
  - Soru 4–12: Anthropic API kredisi bittiği için (400 "credit balance is too low") yanıtları bu oturumdaki model, uygulamanın **birebir sistem promptu ve bağlamıyla** (`C_prompt_NN.md`) elle yazdı. Bu, üretim modelinin davranışını değil, **bağlamın yeterliliğini ve prompt kurallarına uyumu** ölçer. Üretim modeliyle tekrar koşu için bakiye gerekir.
- **Kaynak sayfayla satır satır Chrome karşılaştırması bu aşamada tekrarlanmadı.** Rakamlar, Aşama A'da kaynakla doğrulanmış DB kayıtlarından ve bağlam metninden geliyor; "bağlam dışı sayı" denetimi otomatik (regex) + elle.

## Bulunan gerçek hata (düzeltildi)
`app/rag.py` `_tesvik_detay_metni` kaydın `tesvil_tutari` alanını bağlama **hiç yazmıyordu**. Aşama A'da düzeltilen 80'den fazla kaydın limit/vade/oran metni DB'de doğruydu ama model onu görmediği için "vade, ödemesiz dönem bilgisi elimde yok" diyordu.
- Etki (düzeltme öncesi bağlamla): soru 5 (600.000 TL), 9 (500.000 TL, 24 ay, 12 ay), 10 (150 Milyon TL), 12 (3.000.000/2.400.000 TL) beklenen değerler yanıtta yoktu.
- Düzeltme sonrası: dört soruda da beklenen değerler bağlamda ve yanıtta. Test: `test_tesvil_tutari_alani_baglama_yazilir`, `test_tutar_alanlari_oncelik_sirasi`. Test sayısı 759 → 761 geçti (1 atlandı), flake8 hata sınıfları 0.

## Sonuç tablosu (düzeltme sonrası bağlam)

| # | Persona | Kayıt | Beklenen | Bağlam dışı sayı (otomatik) | Elle sınıf |
|---|---|---|---|---|---|
| 1 | çiftçi | 78 KKYP | 5/5 | %30 | türetilmiş (100 − %70) |
| 2 | çiftçi | 80 TSS | 4/4 | 70 ay | regex artefaktı ("%50/60/70 ayrımı") |
| 3 | tekstil | 44 1507 | 3/3 | yok | — |
| 4 | tekstil | 48 Eurostars | 3/3 | 60 milyon | profil ciro değeri |
| 5 | girişim | 174 BiGG | 3/3 | yok | — |
| 6 | girişim | 1 KOSGEB Girişimci | 2/2 | yok | kayıt bağlamda yok; "elimde yok" + işletme gerekir |
| 7 | otel | 180 9903 | 4/4 | 30 milyon | profil ciro değeri |
| 8 | e-ticaret | 163 5973 | 3/3 | 4 milyon | profil ciro değeri |
| 9 | saas | 2 Yapay Zekâ Kredisi | 4/4 | 20 milyon, 500.000TL | profil ciro; 500.000 bağlamda ("500.000 – 5.000.000") |
| 10 | büyük | 7 İstihdamı Koruma | 4/4 | yok | — |
| 11 | restoran | 185 4447 | 4/4 | yok | — |
| 12 | hatay_nacesiz | 86 TOBB Nefes | 2/2 | 1/2,2/5 milyon | bağlamda (büyük harf biçimi: "2,2 Milyon") |

- **Uydurma: 0** (12 yanıtın hiçbirinde bağlamda ve profilde karşılığı olmayan sayı yok).
- **Beklenen değer kapsamı:** düzeltme sonrası 41/41 (öncesi: 1–3 için 12/12, 4–12 için 25/38).
- **"Bilgi elimde yok" davranışı:** soru 4–12'de açık "elimde yok / bağlamda yok" ifadesi 1–7 kez (toplam 27); soru 1–3'te 0 (gerçek model "teyit edin" dedi). Yanıt başına "teyit edin" 2–10.
- **Girişim modu (5, 6):** 4 BÖLÜM şablonu, HUKS ön skoru aynen (40/75, 100'e oranla 53), şirketsiz → 1512/1812, 1507/1501 elendi, 9903 DÜŞÜK OLASILIK, "garanti yok" notu. Soru 6'da KOSGEB Girişimci kaydı bağlamda yok (uygunluk engeliyle elenmiş), yanıt bunu dürüstçe söyledi ve işletme şartını **genel bilgi** diye etiketledi.

## Kaynak/veri tutarsızlıkları (yanıtlarda görünenler)
1. **Kayıt 163:** metin alanı "15.102 TL 2026-07-12'de teyit edildi" derken tutar alanı "15.102 TL ifadesi 2022 yılına aitti" diyor. Yanıt güncel limiti veremedi. **Karar gerek:** tek ifadeye indirilmeli (5973 Genelge'den doğrulama, açık madde).
2. **Kayıt 174:** metin alanında eski "150.000 TL / teyit edilemedi" uyarısı duruyor, tutar alanı 1.350.000 TL diyor. Hisse oranı da kayıtlar arasında farklı (1512 kaydı %3, 1812 metni en fazla %5).
3. **Kayıt 7:** serbest metin "başvuru son tarihi 30 Nisan 2026 / Haziran sonuna kadar tek seferde" (2026-1) ile 2026-2 tarihleri aynı kayıtta. Yanıt bunu işaretledi; metin alanı temizlenmeli.
4. **Kayıt 48:** sayfa metni "2026/1", alanlar "2026/2" diyor; son başvuru tarihi kayıtta yok.
5. **Kayıt 2:** NACE listesi ve başvuru dönemi kayıtta yok (sayfa kazıması menü metnine inmiş).
6. **Kayıt 7:** Destek Unsurları metni "13-…" diye kesik; performans desteği NACE listesi bağlamda yok.

## Kayıt temizliği (uygulandı, 2026-10-07)
Yukarıdaki tutarsızlıklar `scripts/fix_veri_2026_10_07_denetim2_tur3.py --uygula` ile 5 kayıtta (2, 7, 48, 163, 174) giderildi. Yedek: `tesvikler_oncesi_tur3.db.bak` (git dışı). İkinci çalıştırma 0 kayıt işledi (idempotent). Kaynaklar Chrome ile salt okunur okundu.
- **163:** eski 15.102 TL "2022 değeri, güncel sayılmaz" diye işaretlendi. Güncel TL limiti kaynakta bulunamadı, **hâlâ açık** (5973 Genelge eki).
- **174:** eski 150.000 TL metni kaldırıldı; 1.350.000 TL (2026) + 600.000 TL GCİP.
- **48:** canlı sayfa 2026/2; bütçe sınırları ve başvuru şartları eklendi. Son başvuru tarihi çağrı duyurusu PDF'inde, **hâlâ açık** (indirilmedi).
- **2:** canlı SSS içeriği. **Yeni bulgu: geçerli Teknogirişim Rozeti şart**, kayıtta hiç yoktu. Faiz ve komisyon yok, teminat limiti teminat mektubu tutarına eşit.
- **7:** kayıt 2026-1 dönemine aitti (2025 Kasım-Aralık referansı). 2026-2 canlı metni: referans 2026 Ocak-Haziran, prim gün sayısı Temmuz-Aralık'ta korunmalı, faiz en çok %37, komisyon en çok %1, destek yalnızca vergi ve SGK borcuna.
- Yeni bağlamla soru 4, 9, 10, 11 yanıtları yeniden yazıldı (9'da rozet şartı, 10'da 2026-2 kuralları). Skor: uydurma 0, beklenen 41/41.

## Hâlâ açık
- 163 güncel e-ticaret üyelik limiti; 48 son başvuru tarihi; 76 hayvancılık birim tutarı (taranmış PDF).
- Kazınmış metinlerin bayatlama riski: kayıt 7 tam bir dönem geride kalmıştı. Diğer aktif KOSGEB ve KGF kayıtlarını canlı sayfayla yeniden karşılaştırmak önerilir.
- Üretim modeliyle 4–12 tekrarı için Anthropic bakiyesi gerekir (~0,9 USD): `C_olcum.py N`.
