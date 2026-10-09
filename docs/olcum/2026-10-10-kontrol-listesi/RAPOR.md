# Kontrol listesi ve resmî kaynak denetimi (2026-10-10)

Talimat: `DENETIM_TALIMATI.md`. Girdi: `mevcut.json` (uygulamanın gösterdiği 77 programın kontrol listesi, 507 madde).
Kanıt: `../2026-10-09-uygunluk/kaynak/<id>.txt` "## CANLI SAYFA" bölümü (2026-10-09 indirilen resmî sayfa) ve aynı
klasördeki doğrulanmış kriterler. 7 Sonnet ajanı her maddeye hüküm + tür verdi; `denetim_ozet.py` (self-test 5/5) her
alıntıyı canlı sayfada aradı: **507/507 hüküm ve 177/177 eksik madde alıntısı doğrulandı.** Ayrıntı: `ozet.md`, `denetim/`.

## Sonuç
| Hüküm | Madde | Oran |
|---|---|---|
| doğru (canlı sayfa destekliyor) | 249 | %49 |
| desteksiz (canlı sayfada yok; çoğu Genelge/uygulama esasına ait olabilir) | 171 | %34 |
| belirsiz (birden çok koşul tek kutuda, "aranmayabilir" gibi koşullu) | 74 | %15 |
| yanlış | 11 | %2 |
| eskimiş | 2 | — |

**Kutuların karışması (tür):** 507 maddenin **139'u (%27) yanlış türde**: şart diye gösterilen 41 kural (işaretlenecek bir
şey değil), 35 bilgi (oran/limit/süre), 11 adım; belge diye gösterilen 18 adım, 13 bilgi, 5 şart; kural diye işaretlenmiş
12 gerçek şart. Bugün bunların hepsi aynı onay kutusuyla gösteriliyor.

**Eksik:** resmî metinde zorunlu olup listede olmayan **177 madde** (alıntılı), ör. Ziraat Kadın-Genç'te "kadın ya da
18-35 yaş girişimci", Halkbank İlk Adım'da 29 yaş sınırı, KGF İstihdam Koruma'da NACE C, Yeşil İhracat'ta net ihracatçı +
Greendeks, 9903'te diğer kamu desteği yasağı ve e-fatura.

## Yanlış ve eskimiş maddeler (13)
| Program | Mevcut | Doğrusu (kaynaktan) |
|---|---|---|
| KOSGEB Kapasite Geliştirme (8), KOBİ Dijital Dönüşüm (3) | "KOBİ olmak" | yalnız **küçük ve orta**; mikro işletme yararlanamaz |
| KOSGEB Girişimci (1) | İş Geliştirme: imalat/yazılım/Ar-Ge | NACE C, 61, 62, 63, 72 (telekomünikasyon ve bilişim altyapısı dahil) |
| KOSGEB Girişimci (1), Dijital Dönüşüm (3) | "Ödeme belgeleri", "satın alma faturaları" başvuru belgesi | başvuruda istenmez; onaydan sonra ödeme aşamasında |
| TÜBİTAK 1511, 1509, 1709, 1505 | "Ar-Ge Yardımı İstek Formu" başvuru belgesi | destek kazanıldıktan sonra dönemsel sunulan ödeme formu |
| TÜBİTAK 1507 | "aynı anda en fazla 5 proje" | firmanın **ilk 5 projesi** desteklenir |
| Stratejik Hamle (179) | asgari yatırım 12/6 milyon TL | m.8/2: yüksek teknoloji 100, diğer 200 milyon TL |
| TÜBİTAK 1707 (55), 1832 (59) | çağrı tarihleri | geçmiş dönemler listeleniyor; açık dönem farklı (eskimiş) |

## Resmî kaynak
- 71 program programa özel resmî sayfaya bağlı. **6 program genel sayfaya bağlı:** Organik (77), Sera (79), Hububat (160),
  Meyve-Sebze (161) → BUGEM ana sayfası (#parçalar sayfada yok); E-İhracat (162) → menü sayfası; BiGG (174) → portal ana
  sayfası. Kullanıcı bu programların resmî metnine ulaşamıyor.
- 9903 programları Karar PDF'ine bağlı (doğru) ama "#teknoloji-hamlesi" gibi parçalar PDF'te bir yere gitmiyor; madde
  numarası yazılmalı.
- Çağrı çelişkisi 4 programda: Teknoloji Merkezi (4; kuruluş desteği son başvuru 07.10.2026 geçti, kayıtta yok), Kapasite
  Geliştirme (8; dönem "kapandı", başvuru maddesi "başladı"), Hızlı Büyüyen (9), 1812 (49; kayıt "kapandı", sayfa
  "2026-2 açıldı"). 12 dönemsel programda çağrı kaydı yok.

## Kök neden
Liste kayıttaki üç serbest metin alanından türetiliyor (`basvuru_sartlari`, `gerekli_belgeler`, `basvuru_yeri` +
`basvuru_suresi`); madde türü alanın adından geliyor, içeriğinden değil. Kaynak alıntısı ve tarih tutulmuyor. Başvuru
maddesine `basvuru_suresi` serbest metni eklendiği için çağrı kaydıyla çelişebiliyor.
