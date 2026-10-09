# Gerçek uygunluk ölçümü: öneriler resmî şartlara göre başvurulabilir mi? (2026-10-09)

Betikler: `kaynak_indir.py` (resmî sayfalar → `kaynak/<id>.txt`), `KRITER_SEMASI.md`, `kriter_dogrula.py` (şema + birebir
alıntı denetimi), `uygunluk_olc.py` (12 gerçek profil × 77 program). Çıktı: `kriter/<id>.json`, `sonuc.json`, `ozet.md`.
Ücretli API çağrısı yok.

## Yöntem
1. İşletmeye yönelik 77 aktif programın resmî sayfası indirildi (76/77; KGF refinansman ikinci denemede). KOSGEB
   sayfaları ilk indirmede bozuk kodlandı (sunucu UTF-8 bildiriyor, ayrıştırıcı yanlış tahmin etti); düzeltilip yeniden
   indirildi, KOSGEB kriterleri temiz metinle yeniden çıkarıldı.
2. 8 Sonnet ajanı her programın şartlarını sabit şemaya (KRITER_SEMASI.md) çıkardı: alan + kural + zorunlu mu + birebir
   alıntı. **759 kriterin 759'u geçerli** (alıntılar kaynak metinde birebir bulundu).
3. 12 gerçek profil: sistemin bildiği alanlar + sistemin bilmediği gerçekler (kurucu yaşı, hedef grup, ortaklık, borç,
   belgeler, yatırım tutarı, ihracat). Sistemin önerisi (`esles`, ilk 10) her programın zorunlu şartlarıyla belirlenimci
   olarak karşılaştırıldı. Program alt desteklerden oluşuyorsa en uygun alt destek esas alındı.
4. Değerlendirici hataları ayıklandı (Türkçe harf katlama, hayvancılık ⊂ tarım, bir profil eksiği) ve "uygun değil"
   sonuçlarının hepsi kriter metniyle elle doğrulandı.

## Sonuç

| İlk 10 önerinin (94) gerçek durumu | Sayı |
|---|---|
| Uygun (bütün zorunlu şartlar makinece sağlanıyor) | 1 |
| Bilinen engel yok; yalnız makine okunur olmayan şart(lar) elle teyit edilmeli | 67 |
| Karar için gereken bilgi profilde de yok (yatırım tutarı, NACE, işletme yaşı) | 11 |
| **Uygun değil (zorunlu bir şart sağlanmıyor)** | **15 (%16)** |

Sistem kendi bildiği alanlarla bu 15'in yalnız **7'sini** yakalayabilirdi; diğer 8'i profilde olmayan bilgiye
(kurucu yaşı, ortaklık) bağlı.

### Doğrulanmış yanlış öneriler
| Program | Kime önerildi (sıra) | Sağlanmayan şart (kaynaktan) | Sistemde bilgi var mı |
|---|---|---|---|
| E-İhracat Destekleri (5986) | Denizli şahıs e-ticaret (**1.**) | şirket ya da kooperatif olmak (şahıs yalnız konsorsiyumla, sınırlı süre) | var (şirket türü) |
| İstihdam Taahhütlü KOBİ Finansmanı (BMZ II) | Denizli (9.), Van (3.), Afyon (10.), Hatay lokanta (**1.**) | 20 ilden biri; NACE imalat/62/72 | var (il, NACE) |
| Yatırım-İşletme Destek Paketi | Van oteli (5.) | imalatçı KOBİ | var |
| KGF İstihdam Koruma, Ziraat Yeşil İhracat | Bursa 400 kişilik A.Ş. (6., 10.) | KOBİ olmak | var (çalışan, ciro) |
| Organik Tarım Destekleri | sertifikasız buğday çiftçisi (5.), besici (3.) | organik ürün sertifikası | yok |
| Halkbank İlk Adım Kredisi | 31, 45, 50, 52 yaşındaki işletme sahiplerine (8.-10.) | sahibi/ortağı en çok 29 yaş | yok |
| 1512 BiGG | başka şirkette ortak olan kişiye (**1.**) | hiçbir şirkette ortak olmamak | yok |

### Doğrulanmış kaçırma
- **Şirketi olmayan, Uygulamalı Girişimcilik sertifikalı kadın girişimciye hiç öneri yok** (liste boş).
  `matching.uygunluk_engeli` şirketi olmayana bütün KOSGEB ve KGF programlarını "kayıtlı işletme gerektirir" diye kapatıyor.
  Oysa KOSGEB Girişimci Destek Programı İş Kurma Desteği 0-1 yaşındaki işletme içindir: doğru yol "işletmeyi kur, 1 yıl
  içinde başvur". Program "kuruluştan sonra" notuyla gösterilmeliydi (aynısı KGF girişimci kredileri için).

## Neden: eşleştirme "ilgi" ölçüyor, "uygunluk" değil
Resmî metinlerdeki zorunlu şartların dayandığı bilgiler (77 program):

| Şart | Kaç programda zorunlu | Sistemde |
|---|---|---|
| ölçek (KOBİ) | 30 | profilde var, ama yapılandırılmış kural yalnız 12 programda → 18 programda denetlenmiyor |
| şirket türü | 30 | profilde var, kural yalnız 10 programda |
| NACE / faaliyet / il / bölge | 10 / 8 / 2 / 5 | profilde var, kural çoğunda yok |
| banka kredisi kullanımı | 33 | yok (KGF'nin doğası; kullanıcıya "banka kredisiyle" diye söylenmeli) |
| önceki destek / program çakışması | 20 | yok |
| KOSGEB kaydı, ihracatçı birliği, DYS, ÇKS, marka | 10 / 10 / 7 / 4 / 4 | yok |
| hedef grup (kadın, genç...), kurucu yaşı, ortaklık | 7 / 4 / 2 | yok |
| ilave istihdam, yatırım tutarı, önceki yıl ihracatı | 7 / 5 / 2 | yok |
| makine okunur olmayan şart ("diğer": onay yazısı, öncelikli ürün listesi, jüri puanı...) | **76** | — |

Başvuru biçimi: kefalet 31, proje 13, ön onaylı gider 8, üretim ödemesi 5, E-TUYS belgesi 5, faiz desteği 4, hisse
fonu 2, prim bildirimi 2, kredi 1, diğer 6. (Taslak raporundaki "her program proje sanılıyor" bulgusunu nicelleştirir:
proje biçimi 77'nin 13'ü.)

## Veri kayıtlarında bulunan çelişkiler (kaynak metinlerden)
- KOSGEB 5: kayıt "%80, 280.000 TL, Kısım C küçük/orta"; canlı sayfa "%100, 700.000 TL", ölçek/NACE kısıtı yok.
- KOSGEB 9: kayıt alt limit 20 M TL ve "limited/anonim"; canlı sayfa 30 M TL ve "gerçek veya tüzel kişi".
- KGF 142: kredi üst limiti kayıtta 50 M TL, kefalet tablosunda 45 M TL. KGF 149: KOBİ kefalet limiti 10 M / 24 M TL.
- TÜBİTAK 1511, 1509, 1832 sayfa içinde oran/limit iki farklı değer (sayfanın kendi çelişkisi).
- 1501 "en fazla 2 proje" çelişki değil: sayfa "çağrıda aksi belirtilmedikçe sınır yok" diyor, 2026-2 çağrısı sınır koymuş.

## Sınırlar
- Kriterleri Sonnet çıkardı; alıntılar makinece doğrulandı ama şartın *yorumu* (zorunlu mu, hangi alan) ajanındır.
  Yanlış pozitif tablosundaki her satır elle kontrol edildi; tüm 759 kriter elle gözden geçirilmedi.
- 12 profil; Eskişehir profili sistemin öneri vermemesi nedeniyle ilk-10 ölçümüne katılmadı (94 = 9×10 + 2 + 1 + 1).
- "Diğer" şartlar (76 programda en az bir tane) makinece karara bağlanamıyor; bunlar kullanıcıya teyit maddesi olmalı.

## Öneri — 2. aşama (onay bekliyor)
1. **Kural tabanı:** doğrulanmış 759 kriteri (alıntı + kaynak + tarih) veritabanına al; `app/uygunluk.py` (bu ölçümdeki
   belirlenimci değerlendirici, `--self-test`).
2. **Eşleştirmede kesin eleme:** zorunlu şartı sağlanmayan program önerilmez ya da "uygun değil — sebep" bölümüne iner;
   her öneride şart kartı: ✓ sağlıyor / ✗ sağlamıyor / ? bilgi gerekli (soru) / ☐ teyit et (alıntıyla).
3. **Profil alanları (yalnız gerektiğinde sorulur):** kurucu yaşı ve hedef grup, başka şirkette ortaklık, aldığı destekler,
   planlanan yatırım tutarı, önceki yıl ihracatı, kayıtlar (KOSGEB, DYS, ÇKS, ihracatçı birliği, e-imza), ilave istihdam planı.
4. **Şirketsiz girişimci:** KOSGEB/KGF toptan kapatma yerine "işletmeyi kurduktan sonra" koşullu gösterim.
5. **Veri turu:** yukarıdaki 5 çelişki (önce dry-run, yedek, onay).
6. **Güncellik:** kaynak sayfa değişince kriteri yeniden çıkarma işareti (KGF izleme gibi).
Doğrulama: bu ölçüm yeniden koşulur; hedef: sistemin bildiği alanlarla yakalanabilen yanlış öneri 0, şirketsiz girişimciye
boş liste 0; persona ve 100-ajan testleri gerilemesiz.
