# Denetim 2 / Aşama G — sentetik profil denemesinden çıkan eşleştirme düzeltmeleri (2026-10-07)

Tetikleyen: tarayıcıda iki sentetik profille deneme (Konya 220 dekar buğday/arpa, şahıs çiftçi; Bursa 18 çalışanlı metal işleme Ltd.).
Ölçüm aracı: `G_persona_esles.py` (Aşama 3'ün 10 personası + 2 sentetik profil, LLM yok, DB'ye yazmaz). Ham çıktılar: `G_once.json`, `G_sonra.json`, `G_fark.md`.

## Kod değişiklikleri
| # | Sorun | Kök neden | Düzeltme |
|---|---|---|---|
| 1 | Her kartta "hedeflerle eşleşme bulunamadı"; Kapasite Geliştirme 17. sırada | Hedef değeri ("yatirim") Türkçe başlıkta ("Yatırım") harfiyen aranıyordu | `matching._hedef_eslesmeleri`: ortak ihtiyaç sınıflandırıcısı + tarım alt kategorisi |
| 2 | Şahıs işletmesine/kooperatife TÜBİTAK 1501, 1507 | Sermaye şirketi engeli yalnızca "şirketim yok" için vardı | Şahıs ve kooperatif de engelleniyor (TTK md.124) |
| 2 | 12–15 yaşındaki işletmeye KOSGEB Girişimci | İşletme yaşı kontrolü yoktu | Şart metnindeki "0-3 yaş işletme" kalıbından kural; KOSGEB sayfasından 2026-10-07 teyit; kişi yaşı ("18-29 yaş erkekler") eşleşmez; kuruluş tarihi bilinmiyorsa elemez |
| 3 | Tahıl üreticisine Meyve-Sebze, Sera | Açık kategori seçiminde dar programlara yalnızca ceza veriliyordu | Hedefte yoksa listeden çıkar; hedefte varsa (hayvancılığa geçiş) cezalı kalır |
| 3 | Organik üretim yapmayana "Tahmini ₺57.970"; kredi kartında "Tahmini ₺10.500.000" | Kart tahmini toplamdan farklı kural kullanıyordu | Kategori uyuşmazlığında, kredi/kefaletlerde ve proje tavanlarında kart tahmini yok |
| 4 | "CNC tezgahı" sorusu yalnızca KGF kredileri getiriyordu; "3 kişi işe alacağım" hiçbir ihtiyaca sınıflanmıyordu | Soru sınıflandırıcısında makine adları ve "işe al-" yoktu | CNC/tezgah/robot/kalıp/pres/GES vb. ve istihdam kalıpları; traktör bilerek yok (tarım alt kategorisinden yürür) |
| 5 | Bütçe metinleri Türkçe karaktersiz; "Önerilen stok maliyeti" harcama hedefi gibi | — | 86 metin parçası `tokenize` ile güvenli dönüştürüldü (durum kodları/anahtarlar değişmedi); kart başlıkları "Sektör Ortalamasına Göre…" + kıyas notu |

Düzeltilen yanlış tespitim: bütçe modülü "her sektöre aynı %5,8" kullanmıyor; kâr oranı sektör başına TCMB verisinden geliyor (tarım ve imalat ikisi de %5,8, perakende %2,2, hizmet %3,4, Ar-Ge %7,7).

## Ölçüm (kod düzeltmeleri, veri düzeltmesi öncesi)
- Hedef eşleşmesi alan kart (ilk 12): Bursa metal 3 → 12, İzmir tekstil 3 → 12, Bursa büyük 1 → 12, ekmek üreticisi 1 → 8.
- Elenmesi gerekenler: 1501 (4 personada) ve Girişimci (Bursa metal, sentetik çiftçi) listeden çıktı; Meyve-Sebze ve Sera tahıl üreticisinden çıktı.
- Kapasite Geliştirme (Bursa metal): 17 → 8. **Veri düzeltmesiyle (kopya DB'de denendi) → 2.**
- Arama: CNC sorusunda ilk 4 = KGF Kapasite paketi, KGF Yatırım-İşletme, KOSGEB Kapasite Geliştirme, 9903 Hedef Yatırımlar; traktör sorusunda ilk 8'in tamamı tarım desteği; istihdam sorusunda SGK/İŞKUR + İstihdamı Koruma.
- Tarayıcıda (çiftçi): toplam tahmini destek ₺160.047–3.809.695 → ₺150.040–279.620.
- Test 791 → 810 (1 atlandı), flake8 hata sınıfları 0.

## Veri düzeltmesi — UYGULANDI (2026-10-07; yedek `tesvikler_oncesi_tur4.db.bak`, git dışı; ikinci çalıştırma 0 kayıt)
`scripts/fix_veri_2026_10_07_denetim2_tur4.py`: kayıt 8, 81 (Kapasite Geliştirme: NACE C, 61, 62, 63, 72) ve 7, 142 (İstihdamı Koruma: NACE C) "genel" sektörlü ve NACE kapsamsızdı; otele ve çiftçiye öneriliyor, imalatçıda sektör puanı alamıyordu. Gerçek DB'de sonuç: Bursa metal KOBİ'sinde Kapasite Geliştirme 2., KGF paketi 1., İstihdamı Koruma 6., KGF İstihdam 5.; otel, tahıl üreticisi ve Hatay restoranında dördü de listede yok.

## Ek: KOSGEB onayına bağlı KGF paketleri (eklendi)
6 KGF paketi (81, 107, 118, 125, 142, 170) KOSGEB programına kabul şartına bağlı; eşit skorda asıl programın önüne geçiyordu. Bunlara 1,0 tavanından sonra 0,05 sıralama cezası ve "önce KOSGEB programına başvurun" notu eklendi. Sonuç: Bursa metal KOBİ'sinde KOSGEB Kapasite Geliştirme 1., KGF paketi 3.; ekmek üreticisinde İstihdamı Koruma (7) KGF paketinin (142) önünde. Test 812.

## Açık kalanlar
- Organik Tarım, tahıl üreticisinde hâlâ listede (kasıtlı: "geniş" program, sertifikayla her üretici başvurabilir) ama artık tahmini tutarsız.
- Puanlar sık sık 1,0'da doyuyor; sıralama eşitlik bozucuya (ince skor) kalıyor.
- KOSGEB programlarının tarıma (NACE A) genel olarak kapalı olup olmadığı kaynaktan teyit edilmedi; Girişimci programı kuruluş tarihi bilinmeyen çiftçide hâlâ görünür.
