# Soru anlama (Groq) — kararlar, 2026-10-12

Ölçüm: `soru_anlama_olc.py` (self-test 11/11), sonuçlar `rapor.md` / `rapor.json`. 75 özgün soru (eski 30 + persona 45,
sentetik) ve Groq'un ürettiği, kalıp kelimelerinden kaçınan 148 farklı söyleniş (E06 için Groq JSON doğrulama hatası
verdi, söylenişi yok). Toplam 568 Groq çağrısı, 0,0994 USD (`harcama.json`; tavan 0,15 USD).

## 1. İstem iki kez denendi
İlk istemin 43 soruluk pilotu (`pilot_istem1_gpt-oss-120b.jsonl`): genel liste sorularına ("hangi destekler var")
39 fazla niyet etiketi (çoğu `tanim`), tarım sorularına (traktör, damla sulama, sera, bahçe) `yatirim`. İkinci istem
(üretimdeki, `app/soru_anlama.SISTEM`) aynı 43 soruda fazla niyeti 39 → 20'ye indirdi; tarım `yatirim`ı sürdü.

## 2. Niyet etiketleri kullanılmıyor (`NIYET_KULLAN = False`)
İkinci istemde de "destek var mı / neler" sorularına `tanim`/`uygunluk` ekleniyor; niyet yanıtın yapısını değiştirdiği
için zararlı. Kalıplar niyette yeterli (özgün sorularda F1 0,972). Etiket istenmeye ve ölçülmeye devam ediyor.

## 3. Tarımda Groq'un `yatirim` etiketi atılıyor (`app/ihtiyac._TARIM_YATIRIMI`)
Kalıplar tarım makinesi/sera/sulama/bahçe yenilemeyi bilerek yatırım saymaz (tarım alt kategorisi). Groq istemdeki
yasağa uymadığı için aynı kural koda kondu ("seramik" ayrı tutulur, self-test).

## 4. Program ya da kurum adı geçen soru Groq'a gönderilmiyor (`app/rag.soru_anlama_gerekli_mi`)
İlk uçtan uca koşuda Groq etiketleri 75 özgün sorunun 6'sında yanıtı değiştirdi; ikisi açık gerileme:
"TKDK IPARD hibesi nedir" yanıtı `arge` etiketiyle IPARD'dan TÜBİTAK 1507'ye kaydı; "KOSGEB'den matbaa için destek"
yanıtı sorulmayan "makine/tesis yatırımı"nı yazdı. Dört birleştirme kuralı aynı veride karşılaştırıldı (120b,
ihtiyaç; K / D / F1):

| kural | özgün sorular | farklı söylenişler |
|---|---|---|
| yalnız kalıp | 0,941 / 0,969 / 0,955 | 0,934 / 0,510 / 0,660 |
| birleşim (her soruda) | 0,888 / 0,969 / 0,927 | 0,894 / 0,737 / 0,808 |
| **ad / kurum geçmiyorsa** (seçilen) | 0,922 / 0,969 / 0,945 | 0,907 / 0,706 / 0,794 |
| kalıp boşsa | 0,905 / 0,969 / 0,936 | 0,905 / 0,686 / 0,780 |
| kalıp boş ve ad yoksa | 0,931 / 0,969 / 0,950 | 0,921 / 0,660 / 0,769 |

Seçilen kural farklı söylenişlerdeki duyarlılık kazancının çoğunu (0,51 → 0,71) korur, gerilemelerin hepsini kaldırır
ve ad geçen sorularda hiçbir veri dışarı gitmez (223 sorunun 81'i). Maliyeti istek başına ~0,15 sn (kayıt adları
taranır), yalnız rızası olan kuruluşta.

## 5. Uçtan uca (seçilen kuralla, `uctan_uca/`)
Eski 30 senaryo: dayanak sorunu 0, beklenen isabet 41/41, yasak dil 0. Persona 45: dayanak 0, yasak dil 0.
Groq'suz tabana göre yalnız 2 yanıt değişti: E13 "Kafe açmak istiyorum" (`yatirim` → ilk kart Halkbank İlk Adım
yerine KOSGEB e-Akademi; kabul edilebilir) ve P01 Rekortiv ("Sorudan anlaşılan ihtiyaç"a "kredi/finansman" eklendi;
küçük fazlalık). Kayıt örtüşmesi (söyleniş ilk 5 ∩ özgün ilk 5): 0,456 → 0,520; iyileşen 24, kötüleşen 3 / 148.

## 6. Model
Varsayılan `openai/gpt-oss-120b` (söylenişlerde F1 0,794; gecikme p50 0,64 sn, p95 1,44 sn, 223 çağrıdan 1'i 2,5 sn
zaman aşımını aşar). `openai/gpt-oss-20b` (`SORU_ANLAMA_MODEL`): söylenişlerde F1 0,761, özgünlerde kalıpla aynı
(0,955), p50 0,51 sn, yarı fiyat. Çağrı başına ~915 giriş + ~120 çıkış token: 120b ≈ 0,00021 USD, 20b ≈ 0,0001 USD.

## Açık
- Hukuk: Groq'un veri işleme ekinde Türkiye/KVKK standart sözleşmesi yok; KVKK m.9 güvencesi kvkk.html'de
  DOLDURULACAK. Groq konsolunda Zero Data Retention açılmalı; canlı kullanım için ücretli katman.
- Altın etiket kalıba yakın (kalıp etiketi + 10 düzeltme); bağımsız bir etiketleyiciyle ikinci ölçüm yapılmadı.
