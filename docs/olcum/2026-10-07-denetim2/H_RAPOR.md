# Denetim 2 / Aşama H — kayıt taraması (12 kararsız + 37 karşılaştırılmamış aktif kayıt)

Tarih: 2026-10-07 gece – 2026-10-08. Yöntem: her kaydın `kaynak_url` sayfası (gerekirse kurumun duyurusu) Chrome'da
salt okunur açıldı; başvuru takvimi ve tutar ifadeleri sayfadan JS ile çekildi. Kullanıcı hesabında işlem yapılmadı.
Liste: `H_tarama_listesi.json` (49 kayıt). Düzeltme: `scripts/fix_veri_2026_10_08_denetim2_tur7.py` (dry-run hazır,
**veritabanına henüz yazılmadı**).

## Karar kuralı (Denetim 2 emsali)

- Yılda **tek** başvuru penceresi olan ve 2026 penceresi kapanmış program → `aktif_mi=False`
  (emsal: 4006-C, 2517 SDF, 1701 kayıtları).
- Yılda **birden çok** dönemi olan program → aktif kalır, takvime "(kapandı)" yazılır (emsal: KOSGEB Girişimci).
- Sayfa doğrulamaya yetmiyorsa kayıt kararsız (`None`) kalır, yalnızca not düşülür.

Eşleştirmede `False` kayıt listeden ve toplamdan çıkar; `None` gösterilir ama aynı skordaki `True` kayıtların altına
sıralanır (`app/matching.py`).

## Bulgular

### Kararsız → aktif (3)
| id | Program | Kanıt (sayfa) |
|---|---|---|
| 57 | 1503 Proje Pazarları | "Başvurular sürekli açıktır ve yılın her günü TÜBİTAK'a yapılabilir" |
| 66 | 2224-D Yurt dışı eğitim etkinlikleri | "Program 365 gün başvuruya açıktır" |
| 76 | Hayvancılık Destekleri | HAYGEM duyurusu 268 (01.09.2026): 2026 büyükbaş talimatı; 1. dönem 01/09–01/12/2026 |

### Kararsız → kapalı (7)
| id | Program | Kanıt |
|---|---|---|
| 30 | 1833 SAYEM Yeşil Dönüşüm | 2026 çağrısı: ön başvuru 23 Şubat–23 Mart, 2. aşama 8 Nisan–4 Haziran 2026 |
| 31 | 4004 Doğa Eğitimi | sayfada "ÇAĞRISI SONUÇLANDI" |
| 33 | 4009 Köy Okulları | "Çağrısı Sonuçlandı", 237 proje desteklendi |
| 35 | 1612 BiGG uygulayıcı kuruluş | 2026–2028 dönemi uygulayıcı kuruluşları belirlenmiş |
| 38 | 2223-D NIH çalıştay | sayfadaki tek dönem 6 Nisan–8 Mayıs 2015 |
| 78 | KKYP | TRGM duyurusu 29.04.2026: başvurular 29 Nisan–12 Haziran 2026 23:59 |
| 80 | TSS sulama hibesi | aynı TRGM duyurusu (KKYP ve TSS birlikte) |

### Kararsız kalır (2)
| id | Program | Neden |
|---|---|---|
| 37 | 4003 Bilim Merkezi | sayfada yalnızca program tanımı var, takvim yok |
| 73 | 1000 Üniversite Ar-Ge | çağrı bazlı, sayfada açık çağrı veya tarih yok |

### Aktif → kapalı (2)
| id | Program | Kanıt |
|---|---|---|
| 27 | 1711 Yapay Zekâ Ekosistem | 2026 çağrısı 15 Haziran–2 Ekim 2026 23:59 ([duyuru](https://www.tubitak.gov.tr/tr/destekler/destek/sanayi/ulusal-destek-programlari/cagri-1711-yapay-zeka-ekosistem-2026-yili-cagrisi-acildi)) |
| 58 | 2516 Kore MSIT/NRF | son çağrının son başvurusu 30 Eylül 2024 |

### Aktif kalır, başvuru takvimi yazılır (17)
- **Dönemsel, şu an açık:** 11 (2223-C), 20 (2223-B), 24 (2224-B), 45 (2224-A). Duyuru 05.10.2026: 2026 3. dönem açıldı,
  son başvuru 27 Ekim 2026 17:30. Sayfa gövdesinde "2. dönem" yazıyor; bu TÜBİTAK'ın yazım hatası, başlık 3. dönemi söylüyor.
- **Dönemsel, 2026 dönemleri kapandı:** 69 (2237-A): 26 Ocak–17 Şubat ve 20 Temmuz–11 Ağustos 2026.
- **Çağrı bazlı:** 29 (1071).
- **Sürekli açık:** 22, 41, 43, 60, 64, 65, 68, 71, 75, 175, 176.

### Tutar metni düzeltmeleri (6)
| id | Eski metin | Yeni metin özeti | Kaynak |
|---|---|---|---|
| 77 | "Dekar başına ₺500 - ₺2.000" | 62–465 TL/da (tutari_min/max zaten bu) | BUGEM 2026 birim fiyat tablosu |
| 79 | "m² başına ₺50 - ₺200" | 310 TL/da temel + 527 TL/da iyi tarım örtüaltı = en çok 837 | aynı |
| 160 | "mazot+gübre desteği, kararnameyle" | 620–806 TL/da (temel + planlı üretim) | aynı |
| 161 | "mazot+gübre desteği, kararnameyle" | 310 TL/da temel; fidan 620/1.550 TL/da ayrıca | aynı |
| 185 | (boş) | kişi başı aylık 7.184,03–64.656,23 TL işveren prim payı, 6–54 ay | İŞKUR sayfası |
| 186 | (boş) | kişi başı aylık 11.395,35 TL | İŞKUR sayfası |

2026'da mazot ve gübre desteği "temel destek" adıyla birleşti; 160 ve 161'in başlığındaki "(Mazot-Gübre)" ibaresi
kazıyıcıda (`app/scrapers/tarim_bakanligi.py`) eşleşme anahtarı olduğu için değiştirilmedi.

İŞKUR tutarlarının aylık olduğu aritmetikle doğrulandı. Sayfa "aylık" kelimesini kullanmıyor. 2026 brüt asgari ücret
33.030 TL varsayımıyla:

    7.184,03 / 33.030 = %21,75 (işveren payı)      64.656,23 / (9 × 33.030) = %21,75
    11.395,35 / 33.030 = %34,5 (uzun vade + GSS + kısa vade payı)

### Değişiklik gerektirmeyen (12)
18 (1613), 40 (1601), 49 (1812, 2026-2 çağrısı açık), 53 (2223-D ikili), 72 (2237-B), 162 (E-İhracat),
177–181 (9903 Kararı), 182 (10962 Kararı). 1601 sayfası önceki denemede 404 vermişti. 2026-10-08'de yeniden açıldı
ve TÜBİTAK program listesinde aynı adresle duruyor. Önceki hata geçiciydi.

## Etki ölçümü (veritabanı kopyasında, `H_etki.py`)

12 personadan yalnızca iki çiftçi personası etkileniyor. Arama ilk 8'de yalnızca Konya çiftçisi sorusu değişiyor.

| Persona | Listeden çıkan | Not |
|---|---|---|
| 1 Konya çiftçi | 78 KKYP, 80 TSS | Hayvancılık 2→1 (hedefte "hayvan" var, kayıt artık doğrulanmış) |
| 11 Konya buğday sentetik | 78 KKYP, 80 TSS | Hububat 1. sırada kalıyor |

`--kapali-donem-aktif` bayrağıyla KKYP ve TSS listede kalıyor; 1711 ve SAYEM hiçbir personada çıkmıyor.
Ayrıntı: `H_fark.md`.

## Karar (2026-10-08)

Mert varsayılanı seçti: KKYP, TSS, 1711 ve SAYEM kapalı. Tur 7 uygulandı (yedek `tesvikler_oncesi_tur7.db.bak`);
kazıyıcı tohumu da düzeltildi ve `tests/test_tarim_tohum_tutarlari.py` ile birim fiyat modülüne bağlandı.
2027 KKYP/TSS çağrısı açıldığında 78 ve 80 yeniden aktif edilmeli.

Karar öncesi değerlendirme: KKYP ve TSS çiftçinin "makine/sulama" hedefine en uygun iki hibe; 2026 penceresi Haziran'da kapandı, 2027 çağrısı
büyük olasılıkla Nisan–Haziran'da. İki seçenek:

1. **Varsayılan (emsale uygun):** kapalı. Kullanıcıya şu an başvurulamayan program gösterilmez.
2. **`--kapali-donem-aktif`:** aktif, takvimde "2026 dönemi kapandı; yıllık çağrı". Çiftçi gelecek yıla hazırlanabilir,
   ama kart "başvurulabilir" gibi görünür. Kartta dönem durumunu ayrıca gösteren bir alan yok.
