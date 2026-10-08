# 100 sentetik ajanla uçtan uca deneme — analiz (2026-10-09)

Betikler: `simulasyon.py` (100 ajan, 18 denetim), `gurultu.py` (ilk 10'da ilgisiz öneri ölçümü). Ham çıktılar:
`sonuc_once.json` / `sonuc.json`, `ozet.md`, `G12_once.json` / `G12_sonra.json` / `G12_fark.md`, `persona10_*.txt`.

## Yöntem ve sınırlar
- **Ajan = kurallı simüle kullanıcı**, LLM değil (API bakiyesi yok; sonuç tekrarlanabilir olsun diye sabit tohum).
  20 arketip × 5 varyasyon: il 81 ilden rastgele, ölçek/ciro/NACE/şirket türü/kuruluş yılı/hedef/etiket arketip
  aralığında.
- Her ajan kullanıcı yolculuğunu API'nin çağırdığı fonksiyonlarla yürür: eşleşme → kontrol listesi ve çağrı tarihleri →
  hazırlık yol haritası → (e-ticaret/ihracat) e-ihracat hesabı → cevapsız taslak → sihirbaz cevaplı taslak.
- **Denetlenmeyenler:** danışmana soru-cevap (Claude, ücretli), İKAS OAuth/ödeme akışları, gerçek kullanıcı arayüzü
  davranışı, il bazlı kalkınma ajansı programları (veride yok). Beklentiler arketip düzeyinde, program bazında değil.

## 1. Değişmez kurallar ve danışman beklentisi: 18 denetimin hepsi %100
Büyük işletmeye KOSGEB yok, şahıs ürünü yalnız şahısa, şirketsize 9903 yok, şirket türü listelerine uyuluyor, tarım
dışına Tarım Bakanlığı yok, akademik çağrı yok, skor > 0 ve gerekçe var, çağrı durumu tarihle tutarlı, ilk 5'te
başvuru yeri/süresi/madde dolu, tarımda ilk hazırlık adımı ÇKS, e-ihracat ≤ %75 ve şahısta "şimdi" 0, cevapsız
taslakta boş tablo ve uydurma rakam yok, sihirbaz bütçe hesabı doğru; her arketipte beklenen program eşikte.

**Ama bu %100 yanıltıcıydı:** denetimlerin çoğu son günlerde eklenen kuralların aynısını sınıyor ve beklenen kümeler
geniş. Asıl kalite sorusu "ilk 10'un ne kadarı bu işletmeye gerçekten ilgili" idi; o ölçülmüyordu.

## 2. İlgi (gürültü) ölçümü — eşleştirmeden bağımsız danışman kuralları

| | Önce | Sonra (ilgi cezası) |
|---|---|---|
| İlk 10'larda ilgisiz öneri | **177/960 (%18,4)** | **41/960 (%4,3)** |
| Hiç ilgisiz önerisi olmayan ajan | 37/100 | 79/100 |
| Tarım arketipleri (buğday/sebze/organik/sera) | %40 | %0-20 |
| Turizm/hizmet yatırım | %34 | %0 |

Gürültünün kaynağı (önce): SGK istihdam teşvikleri hedefinde istihdam olmayanlara (77), Yapay Zekâ Kredisi Ar-Ge
sinyali olmayanlara — çiftçi, kuaför, otel (52), KOSGEB YÖNDE çiftçiye (24), Stratejik Hamle/Öncelikli/Teknoloji
Hamlesi mikro-küçük firmaya (17), TÜBİTAK sanayi Ar-Ge'si otele (7). Hepsi yalnız "genel" sektör etiketiyle 0,30 alıyordu.

**Düzeltme** (`app/matching._ilgi_engeli`, ceza 0,30): yalnız genel etiketle gelen zayıf eşleşme 0'a iner ve gizlenir;
güçlü sinyali olan (ör. istihdam hedefi beyan etmiş işletmeye SGK teşviki, yazılım NACE'li firmaya Yapay Zekâ
Kredisi) kalır ya da yalnız geri alınır. Eşleşmeden atma değil, ilgi sıralaması.

**Kalan 41:** 38'i hedef girmemiş profillerde SGK teşviki — "yokluk ihlal değildir" ilkesi gereği bilinçli olarak
cezalandırılmıyor (bağımsız ölçüt burada uygulamadan katı); 3'ü kesin küçük ölçekli firmada yatırım hedefi güçlü
olduğu için geri sırada kalan 9903 programı.

**Gerileme yok:** 10 persona denemesinin tüm değerleri aynı; eski 12 personada "üstte olmalı" eşikleri aynı, değişen
iki ilk-5 doğru yönde (Hatay hizmetten Yapay Zekâ Kredisi, Van otelinden Öncelikli Yatırımlar düştü).

## 3. Neleri yapabildi
- 20 arketipin hepsinde danışmanın bekleyeceği ana programı ilk sıralarda buldu (Hububat, Hayvancılık, Kapasite
  Geliştirme, Hedef Yatırımlar, 5986 reklam, Hizmet İhracatı-Bilişim, BiGG, KGF Kooperatif, KGF Savunma, Ziraat kadın-genç).
- Kapsam dışı kuralları hatasız uyguladı (yasak program 0/100).
- Başvuru yolu: ilk 5 önerinin hepsinde başvuru yeri, süresi ve kontrol maddeleri var; çağrı tarihleri tutarlı;
  TÜBİTAK'ta firmanın asıl son günü (ön kayıt) öne çıkıyor.
- Hazırlık: şirketleşme kararı ve tarımda ÇKS doğru sırada.
- Taslak: 100 ajanın 100'ünde uydurma rakam yok; sihirbazda bütçe toplamı ve destek (oran × toplam, üst limitle) doğru.

## 4. Neleri yapamadı (kapsam ve derinlik)
1. **Kapsam boşlukları — veride hiç yok:** kalkınma ajansları mali destek programları (il bazlı, KOBİ'lerin en sık
   başvurduğu hibelerden), TKDK/IPARD kırsal kalkınma hibeleri (çiftçi ve kooperatif için ana yatırım hibesi), Turquality,
   İŞKUR İşbaşı Eğitim Programı, Kültür ve Turizm Bakanlığı turizm teşvikleri. Turizm, çiftçi-yatırım ve deprem bölgesi
   arketiplerinin "en iyi" önerisi bu yüzden genel KGF/9903 kalıyor.
2. **Deprem bölgesi özel hükümleri** (9903'te afet bölgesi için 31.12.2026'ya kadar 6. bölge destekleri) ayrı bir
   eşleşme sinyali olarak modellenmedi; deprem bölgesindeki işletme diğer illerdekiyle aynı listeyi görüyor.
3. **Yatırım tutarı bilinmiyor:** 9903 programlarının asgari yatırım şartı profilde yatırım tutarı olmadığı için
   denetlenemiyor; ölçek yalnızca dolaylı sinyal. Profile "planlanan yatırım tutarı" alanı gerekli.
4. **Hedefsiz profil:** hedef girilmezse ilgi sıralaması zayıflıyor (kalan gürültünün %93'ü). Profil formunda hedefin
   zorunlu ya da öne çıkarılmış olması kaliteyi doğrudan artırır.
5. **Program bazında form:** sihirbaz soruları 6 program türüne göre; resmi form alanlarıyla birebir değil (1501/1507
   AGY100 ve KOSGEB Kapasite Geliştirme formları indirildi, şablonlaştırma sürüyor).
6. **Ölçüt sınırı:** ilgi ölçümü 5 kuraldan oluşan bağımsız bir danışman ölçütü; her gürültü türünü yakalamaz
   (ör. KGF paketlerinin büyük firmalara uygunluğu, organik desteğin sertifikasız üreticiye "geçiş seçeneği" olarak
   gösterilmesi değerlendirmeye alınmadı).

## Öncelikli öneriler
1. Kalkınma ajansları (26 ajans, il bazlı çağrılar) ve TKDK/IPARD veri turları — en büyük kapsam açığı.
2. Profile "planlanan yatırım tutarı" ve hedefin öne çıkarılması (9903 ve ilgi sıralaması için).
3. Deprem bölgesi hükümleri için il listesi + 9903 afet maddesi sinyali.
4. Program bazında form şablonlarının tamamlanması (1501/1507, KOSGEB Kapasite Geliştirme).
