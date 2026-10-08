# 10 sentetik işletmeyle uçtan uca deneme — değerlendirme (2026-10-08)

Betik: `persona_uctan_uca.py` (ücretsiz, LLM yok, DB'ye yazmaz). Ham çıktı: `ham_sonuc.md`, `sonuc.json`.
Veritabanı: tur12 + tur13 + göç `m0b2d4f6a012` uygulanmış **kopya** (gerçek DB'ye uygulanınca göreceğimiz durum).
Beklentiler (beklenen program + kabul edilebilir en kötü sıra, yasak programlar) çalıştırmadan önce yazıldı.

## Özet

| Ölçüt | Sonuç |
|---|---|
| Beklenen programlar eşiğinde | **22/25** (P1 GDP 7. sırada, eşik 6; P8 Ziraat kadın girişimci 20.; P10 KGF Kooperatif 18.) |
| İlk 5'te açıkça yanlış öneri | **6 persona'da 1'er** (aşağıda) |
| Çağrı durumu iç tutarlılığı (açık/yaklaşan/kapandı) | 0 hata |
| Tarihlerin resmi kaynakla canlı karşılaştırması | 3/3 tarih kaynakta birebir (KOSGEB İstihdamı Koruma 31.10.2026 HTML; TÜBİTAK 1501 26.10.2026 ve 1507 11.11.2026 çağrı PDF'i) |
| **Tarih gösterimi** | **Hatalı vurgu:** TÜBİTAK'ta firmanın son günü ön kayıt (1501: 22.10.2026, 1507: 09.11.2026); çip, "sıradaki adım" ve kalan gün çağrı kapanışını (26.10 / 11.11) gösteriyor. Ön kayıt tarihi yalnız kontrol listesindeki notta. |
| Başvuru yolu bilgisi (ilk 5 programda yer/süre/şart/belge/resmi kaynak) | **215/250 (%86)**; en sık boşluk başvuru süresi (9903, KGF ürünleri), sonra 76 Hayvancılık ve 77 Organik'te şart listesi |
| Hazırlık yol haritası | Şirket/limited kararı e-ticaret ve girişimcide doğru ve en üstte; **çiftçide yanlış**: "şirkete geçin, 11 program açılır" diyor, açılanların hepsi TÜBİTAK sanayi Ar-Ge. Çiftçi için ilk adım ÇKS olmalı, listede sonda. |
| E-ihracat hesabı | P1 (şahıs) şimdi 0, hazırlıkla 122.100 TL, adımlar şirket + birlik + Madrid; P2 (Ltd, 300 bin USD) 1.140.000 TL "teyitle" (Madrid bilinmiyor), çevrim içi mağaza 1 M USD şartından kapalı: kurallarla tutarlı |

## Persona bazında yargı: "başarılı olur muydu?"

| Persona | Doğru teşvik | Yanlış/gürültü | Tarih | Başvuru yolunda yardım | Yargı |
|---|---|---|---|---|---|
| P1 İKAS şahıs e-ticaret | 5986 şemsiye (konsorsiyum yolu) 1., KGF ihracat, GDP 7., Halkbank şahıs | — | çağrısız kayıtlar, "tarih yok" dürüst | şirket kararı ilk adım; e-ihracat hesabı hazırlıkla 122 bin TL | **Orta-iyi.** Kısa vadede GDP + KGF kredisi; e-ihracat için önce şirketleşme kararı. Asıl katkı engeli baştan söylemek. |
| P2 İKAS Ltd e-ihracatçı | 192/193/194/188/9 hepsi eşikte | 196 (statü, 500 bin USD altı) 3. sırada; eşleştirme USD ihracatı bilmiyor | 5986 sürekli (ön onaylı), doğru | ilk 5'te 25/25 alan dolu; hesap 1,14 M TL, aylık bekleme 95 bin TL | **Yüksek.** Madrid tescilini ve birlik üyeliğini teyit ederse doğrudan ön onaya gider. |
| P3 Konya buğday | 160 Hububat 1., 94 Tarım kefalet 2. | **77 Organik 3.** (beyan yok) | — | hazırlıkta **yanlış ilk adım** (şirket → TÜBİTAK); ÇKS sonda | **Düşük katma değer.** 160 zaten ÇKS ile neredeyse otomatik; ürün çiftçiye yeni bir şey söylemiyor, organik gürültü. |
| P4 Afyon hayvancı | 76 Hayvancılık 1., 94 2. | **77 Organik 3.**; 76'da şart listesi yok | — | aynı şirket adımı sorunu | **Düşük-orta.** Aynı sorunlar; hayvancılık destek kalemleri (buzağı, süt primi) kayıtta ayrıntısız. |
| P5 Bursa metal Ltd | 8, 180, 179, 81, 7 — tam beklenen | — | 7 İstihdamı Koruma 31.10 canlı doğrulandı | 9903'te başvuru süresi boş, diğerleri dolu | **Yüksek.** Gerçek bir danışmanın ilk listesiyle örtüşüyor. |
| P6 Ankara şirketsiz AI | 1512 BiGG 1., 1812 2. | **9903 kayıtları skor 0,00 ile listede** (şirketsiz yatırımcı olamaz) | — | "şirket kurarsanız 39 program açılır" doğru ve yararlı | **Orta-yüksek.** Doğru kapı (BiGG); sıfır skorlu kayıtlar güveni bozar. |
| P7 İzmir yazılım ihracatı | 182 Hizmet ihracatı (bilişim) 1., 8, 9, 1501, 1505 | — | **1501 "son başvuru 26 Ekim, 18 gün" — firmanın ön kayıt son günü 22 Ekim** | 24/25 | **Yüksek, tarih riski var.** Kullanıcı çipe güvenirse ön kaydı kaçırabilir. |
| P8 Hatay kadın kuaför | 185 SGK kadın istihdamı 4., GDP 6. | **9903 Yerel Kalkınma Hamlesi 1.** (2 kişilik kuaför için yatırım teşviki); 169 Ziraat kadın-genç girişimci 20. | — | 22/25 | **Düşük-orta.** İlk öneri yanıltıcı; kadın girişimci etiketi sıralamaya yansımıyor. |
| P9 Gaziantep gıda A.Ş. 320 kişi | 180 Hedef Yatırımlar 1., 179, 178, 7 | **9 KOSGEB Küresel Rekabetçilik 8.** (KOBİ programı; kayıtta ölçek kriteri yok); 192/196 e-ticaret statü gürültü | 7 doğru | 9903 başvuru süresi boş | **Orta-yüksek.** Ana öneri doğru; KOBİ programı büyük firmaya gitmemeli. |
| P10 Karaman tarım kooperatifi | 94 Tarım kefalet 1. | **77 Organik 2.**, 87 Halkbank şahıs kredisi 12., 116 KGF Kooperatif paketi 18. | — | 20/25 | **Düşük-orta.** Kooperatife özgü paket aşağıda, şahıs ürünü listede. |

**Genel yargı:** imalat, e-ihracat ve yazılım ihracatında (P2, P5, P7, P9) bir danışmanın ilk listesiyle büyük ölçüde örtüşüyor ve başvuru yolu bilgisi yeterli; e-ticaret şahıs ve girişimcide (P1, P6) engeli doğru söylüyor. Tarım (P3, P4, P10) ve mikro hizmette (P8) katma değer düşük, ilk sıralarda yanlış öneri var. Tarihler kaynakla doğru, ama TÜBİTAK'ta firmanın asıl son günü (ön kayıt) öne çıkarılmıyor.

## Düzeltme listesi (öncelik sırasıyla)

1. **Firmanın son günü** (tarih doğruluğu): çağrıya `basvuru_son` (ön kayıt / kuruluş başvurusu son tarihi) alanı; çip, "sıradaki adım", kalan gün ve hatırlatmalar bunu kullanır. Etkilenen: 1501, 1507 (tur10 notlarında tarih zaten var). Göç gerekir.
2. **Organik (77)** yalnız organik beyanında (tarim_kategori=organik ya da hedef organik); aynı kontrol Sera (79) için. 3 tarım personasında ilk 3'teki yanlış öneriyi kaldırır.
3. **Ölçek kriteri eksik KOSGEB/KGF kayıtları** (9 ve benzerleri): KOBİ tanımı (250 çalışan altı) kayda `max_olcek` olarak; büyük firmaya KOSGEB gitmesin. Tüm KOSGEB kayıtları taranmalı.
4. **Skor 0 kayıtlar listelenmesin**; 9903 yatırım teşvikleri şirketsiz (`yok`) profile kapalı.
5. **Hazırlık sıralaması:** şirket adımı yalnız profilin sektör/hedefiyle ilgili program açıyorsa öne çıksın (çiftçide açılanlar sanayi Ar-Ge); tarım profilinde ÇKS ilk adım.
6. **Hedef kitle etiketi ve şirket türüne özgü ürünler:** `kadin_girisimci`/`kooperatif` etiketli programlar (169, 116) öne; "şahıs işletmeleri" ürünü (87) kooperatif/A.Ş.'ye kapalı.
7. **9903 Yerel Kalkınma Hamlesi** mikro hizmet işletmesine ilk sırada çıkmasın: il bazlı yatırım konusu (EK) ve asgari yatırım tutarı kontrolü.
8. **E-ihracat statü şartları eşleştirmede:** hazırlık kaydındaki önceki yıl ihracatı (USD) 195 (1 M USD) ve 196 (500 bin USD statü) kayıtlarını elesin.
9. **Başvuru süresi boşlukları:** 9903 (E-TUYS) ve KGF ürünleri; resmi kaynaktan doldurulmalı (veri turu, onaylı).

Not: 1–8 eşleştirme değişikliği; proje kuralı gereği her biri `docs/olcum/2026-10-07-denetim2/G_persona_esles.py` önce/sonra ölçümü ve bu betiğin yeniden koşusuyla doğrulanmalı.

---

# Düzeltme sonrası (aynı gün, ikinci koşu)

Önce/sonra ham çıktılar: `ham_sonuc_once.md` → `ham_sonuc.md`; 12 personalık eski düzenek: `G12_once.json`,
`G12_sonra.json`, `G12_fark.md`. Kopya DB'ye ek olarak göç `n1c3e5a7b234` ve tur14 uygulandı.

| Düzeltme | Uygulama | Sonuç |
|---|---|---|
| 1. Firmanın son günü | `tesvik_cagrilari.on_kayit_son` (göç), `cagrilar.son_gun`, yeni durum `on_kayit_kapandi`; tur14 veri (1501: 22.10, 1507: 09.11, PDF'ten). Çip, "sıradaki adım", Word, Next kabuğu | P7: "son gün 2026-10-22 (14 gün)"; panelde "Ön kayıt son gün 22 Ekim 2026 (14 gün) · kapanış 26 Ekim 2026" |
| 1b. Takipteki başvuru (tarayıcıda bulundu) | `/api/ozet` yaklaşanlara kullanıcının kontrol listelerindeki çağrıları da ekler; 0/0 liste tamamlanmış sayılmaz | "Sıradaki adım" 23 günlük eşleşme yerine takipteki 1501'in 14 günlük ön kaydını gösteriyor |
| 2. Organik | beyansız profilde −0,2 ve "yalnız sertifikalı üretim" notu (2026-09-26 "geniş program" kararı korunarak çıkarılmadı) | P10'da ilk 5'ten çıktı; P3'te 3→4, P4'te 3. kaldı (skor 0,70→0,50) |
| 3. KOSGEB ve büyük işletme | `uygunluk_engeli`: kesin büyük ölçek + şartında "büyük işletme" yoksa kapalı | P9'dan Küresel Rekabetçilik çıktı; İstihdamı Koruma (büyüğe açık) kaldı |
| 4. Skor 0 / 9903 şirketsiz | 0 skorlu kayıt listelenmez; Sanayi ve Teknoloji Bakanlığı işletme gerektiren kurum | P6: yalnız BiGG 1512 ve 1812 |
| 5. Hazırlık | şirket adımı yalnız ≥0,5 skorlu açılan programla; tarımda ÇKS ilk | P3/P4/P10 ilk adım ÇKS; çiftçide "şirkete geçin" kalktı |
| 6. Hedef kitle / şahıs ürünü | zorunlu hedef kitle etiketi eşleşirse +0,3; "şahıs işletmeleri" ürünü şahıs olmayana kapalı | P8 Kadın-Genç Girişimci 20→3; P10 Kooperatif paketi 18→4, şahıs kredisi elendi |
| 7. 9903 hedefsiz | hedef beyan edilmiş ve yatırım/makine yoksa −0,3 (hedef hiç yoksa ceza yok) | P8 Yerel Kalkınma 1→5 |
| 8. E-ihracat USD | kayıtta `min_onceki_yil_ihracat_usd` (tur14: m.8 1 M, m.5 500 bin + statü muafiyeti); profilin hesaplayıcı beyanı | P2 (300 bin USD) için 196 ilk 5'ten çıktı |

## Sayılar

| Ölçüt | Önce | Sonra |
|---|---|---|
| Beklenen eşiğinde (ilk koşudan önce yazılan) | 22/25 | 23/25 (eksik: P1 ve P8'de GDP 7. sırada, eşik 6) |
| Yasak listesindeki program ilk 30'da | 5 | 1 (P3 Organik, 4. sıra, notlu) |
| İlk 5'te yasak — **sonradan eklenen** beklenti | 6 | 3 (P3/P4 Organik, P8 Yerel Kalkınma 5.) |
| Tarih iç tutarlılık hatası | 0 | 0 |
| Eski 12 persona: "üstte olmalı" eşikleri | 4/4 | 4/4 (gerileme yok) |
| Test paketi | 1028 | 1047 geçti, 1 atlandı |

**Beklentinin fazla katı olduğu yerler:** P3 ve P4'te "Organik ilk 5'te olmasın" beklentisi bu profillerde gerçekten
ilgili yalnız 3-4 program olduğu için sağlanamıyor; Organik onların arkasında ve "sertifikalı üretime geçerseniz" notuyla
duruyor. Kuralı daha da sertleştirmek ölçüme göre ayar olurdu; yapılmadı. P8'de Yerel Kalkınma 5. sırada, hedefe
uymadığı notuyla.

## Kalan işler
- 9. madde (başvuru süresi boşlukları: 9903 E-TUYS, KGF ürünleri) veri turu olarak açık; kaynaklı doldurulmalı.
- 9903 Yerel Kalkınma için il bazlı yatırım konusu (EK) ve asgari yatırım tutarı kontrolü (7. madde yalnız sıralamayla
  hafifletildi).
- GDP (KOSGEB Girişimci) mikro işletmede 6-7. sırada; KOSGEB 0-3 yaş işletme ve hedef "istihdam/büyüme" eşlemesi
  güçlendirilebilir.
