# Teşvik bulunduktan sonraki yardım: şablon, sihirbaz, taslak, Word — ajanlarla deneme (2026-10-09)

Betik: `taslak_ajan.py` (`hazirla` → `uret` → `ozet`, `--self-test` 7/7). Ücretli API çağrısı yok.
Dosyalar: `paket_NN.md` (kullanıcıya gösterilen), `cevap_NN.json` + `deneyim_NN.md` (kullanıcı ajanı), `taslak_bos_NN.md`
(hızlı taslak), `taslak_NN.md` (sihirbazlı), `degerlendirme_NN.json` (hakem), `denetim.json`, `ozet.md`.

## Yöntem
- 12 vaka × 12 farklı program: 3'ü resmi form şablonlu (1501, 1507, KOSGEB Kapasite Geliştirme), diğerleri 9903
  yatırım teşviki, BiGG, KOSGEB Girişimci, E-İhracat, Yapay Zekâ Kredisi, SGK 4447 prim teşviki, hububat dekar desteği,
  hizmet ihracatı (bilişim), KOBİ Dijital Dönüşüm.
- **Kullanıcı ajanı (Sonnet, 6 ajan):** yalnız kendisine verilen işletme bilgisiyle (bilinçli boşluklar dahil) sihirbazı
  doldurdu, deneyim notu yazdı.
- **Uygulama yolu:** cevaplar API'nin şeması (`TaslakCevaplari`) ile doğrulandı, taslak `sablon_taslak.uret`, Word
  `basvuru_docx.belge_olustur` ile üretildi (uygulamadaki fonksiyonların kendisi).
- **Hakem ajanı (Opus, 3 ajan):** taslağı programın resmî başvurusuna hazırlık açısından 6 ölçütte (1-5) puanladı, kusurları
  alıntıyla ve türüyle (şablon kodu / veri kaydı / kullanıcı cevabı / kapsam) listeledi.
- Sınır: hakem genel program bilgisini kullandı; mevzuat iddialarının bir kısmını kendisi "teyit gerekir" diye işaretledi.
  Rapordaki yüksek önem dereceli bulgular kod/veri üzerinden ayrıca doğrulandı (aşağıda ✔).

## Sonuç 1 — mekanik doğruluk: temiz
12/12: şema geçerli, kullanıcının her cevabı taslakta, bütçe toplamı ve destek hesabı doğru, uydurma sayı 0, resmi form
başlıkları sıralı (3/3), kural maddeleri uyarı olarak, Word üretildi ve proje adını içeriyor.

## Sonuç 2 — işe yararlık: zayıf
| | Sonuç |
|---|---|
| Kullanıcı: "bu sihirbazla başvuruya hazırlanabilir miydim" | **evet 0 · kısmen 8 · hayır 4** |
| Hakem: resmî forma aktarılabilir | **evet 0 · kısmen 7 · hayır 5** |
| Hakem ortalaması (1-5) | forma aktarılabilirlik **2,1** · programa uygunluk **2,3** · kullanıcı bilgisinin yansıması 3,8 · iç tutarlılık 2,7 · eksiklerin işaretlenmesi 2,8 · doğruluk/yanıltmama 2,6 |
| En iyi | 1501 ve 1507 (3,5), hizmet ihracatı (3,3), KOSGEB Kapasite (3,2): resmi form şablonu olanlar |
| En kötü | Yapay Zekâ Kredisi ve hububat (1,8), KOSGEB Girişimci ve SGK teşviki (2,2) |
| Kusur türleri (95) | şablon kodu 57 (19 yüksek) · kapsam 22 (13 yüksek) · veri kaydı 26 (8 yüksek) · kullanıcı cevabı 6 |

Kullanıcı bilgisini taşımada iyi (3,8); sorun yanlış soruları sormak ve programın gerçek başvuru biçimine uymamak.

## Ana bulgu: sihirbaz her programı "proje önerisi" sanıyor ✔
`program_turleri` 6 türden birini seçiyor (arge, yatırım, ihracat, istihdam, girişim, tarım) ve hepsi proje anlatısı +
bütçe + faaliyet takvimi istiyor. Oysa programların çoğu başka bir başvuru biçimi kullanıyor:

| Gerçek başvuru biçimi | Örnek (vaka) | Şu an ne oluyor | Gerekli olan |
|---|---|---|---|
| Kredi / faiz desteği | Yapay Zekâ Kredisi (8), KOBİ Dijital Dönüşüm (12) | "arge"/"yatirim" türü: yenilik, TRL, darboğaz soruluyor | kredi tutarı, vade, teminat, ön koşul kontrolü (rozet, cüzdan, olgunluk raporu) |
| Bildirimle prim teşviki | SGK 4447 (9) | "Proje: 3 kişilik ilave istihdam" metni | kişi bazlı uygunluk (yaş, cinsiyet, İŞKUR), ilavelik hesabı, kişi × ay × prim tutarı |
| Dekar/üretim başı ödeme | Hububat (10) | mibzer bütçesi + proforma isteniyor | ÇKS ve ekiliş beyanı adımları, dekar × birim hesabı (ör. 180 da × 403 TL) |
| Belge (E-TUYS) | 9903 Hedef Yatırım (4) | anlatı taslağı | yatırım cinsi, EK-3 eşleşmesi, bölge, asgari tutar, makine listesi |
| Gider bazlı ön onay | E-İhracat (7), hizmet ihracatı (11) | tek oranla toplam hesap | kalem ↔ karar maddesi eşleşmesi, kalem/ülke oranı, ön onay adımı takvimde |
| Hisse karşılığı fon | BiGG (5) | %3/%5 "destek oranı" olarak sunuluyor ✔ | hisse oranı ≠ destek oranı; uygunluk soruları (öğrenci/mezun, ortaklık) |
| Götürü kuruluş desteği | KOSGEB Girişimci (6) | %100/%80/%50 tek listede, bütçe 680 bin vs limit 30 bin açıklamasız ✔ | önce destek bileşeni seçimi (İş Kurma / İş Geliştirme / faiz) |

## Doğrulanan diğer kusurlar
- ✔ `oran_secenekleri` metindeki her yüzdeyi alıyor: BiGG'de hisse oranı, KOSGEB Girişimci'de üç farklı aracın oranı.
- ✔ Takvim kapanmış dönemi söylemiyor (KOSGEB Kapasite: "6 Haziran'da başladı", dönem kapalı; `_takvim` yalnız açık/yaklaşan).
- ✔ 1507 kaydında `basvuru_suresi` eskimiş ("genellikle Ocak-Şubat") ve çağrı kaydıyla (ön kayıt 9 Kasım 2026) aynı taslakta çelişiyor.
- ✔ Resmi form tabloları (KOSGEB 2.3-2.10, TÜBİTAK M011-M016) yalnız listeleniyor; kullanıcının verdiği rakip, müşteri, bütçe
  kalemleri ilgili tabloya yerleştirilmiyor.
- ✔ 1501'de destek oranını belirleyen bilgi (firmanın daha önce desteklenen proje sayısı) sorulmuyor; kullanıcı oran seçemedi,
  destek hesaplanmadı.
- SGK kaydında kişi başı aralık (7.184-64.656 TL) asgari ücretli çalışan için üst değeri de gösteriyor (hakem: yanıltıcı).
- Test verisi notu: vaka 1'de NACE 13.20 (dokuma) personaya benim yazdığım hata; örme 13.91 (teyit gerekir). Uygulama kusuru değil.

## Öneri (öncelik sırası)
1. **Başvuru biçimi alanı:** her programa `basvuru_bicimi` (proje / kredi / bildirim-prim / üretim-ödeme / belge-ETUYS /
   gider-ön onay / hisse-fon / götürü) ve sihirbazı buna göre kur. Proje biçimi dışındakiler için anlatı taslağı yerine
   "başvuru dosyası kontrol listesi + hesap" üret (kredi: tutar/vade/teminat; prim: kişi × ay; üretim: dekar × birim).
   En büyük etki; şablon kodu kusurlarının çoğu buradan.
2. **Oran seçenekleri:** hisse/faiz/geri ödemeli oranları ayıkla ya da oranı bileşenle birlikte sun ("İş Kurma %100 —
   götürü 10.000-30.000 TL").
3. **Takvim:** kapanmış dönemi "kapandı; sonraki dönem duyurusunu bekleyin" diye yaz; çağrı kaydı varsa `basvuru_suresi`
   metnini taslakta ikinci kez verme.
4. **Veri turu:** 1507 `basvuru_suresi`, SGK kişi başı tutar ifadesi; BiGG `tutari_hesaplama_formulu` hisse cümlesi.
5. **Resmi form tabloları:** kullanıcının bilgisi varsa tablo satırı olarak doldur (rakip, müşteri, bütçe → M011-M016 eşlemesi).
6. 1501: "daha önce desteklenen proje sayısı" sorusu → oran otomatik.
