# 2026 bitkisel üretim destekleri — kanıt (2026-10-12)

Persona denemesi (9 dekar fındık) iki tutarsızlığı ortaya çıkardı: panel hesaplayıcısı (`app/tarim_destek_2026.py`)
2026 için 310 TL/da kullanıyordu, veritabanı 367 TL/da; hububat kaydı (160) ise 2024 tarihli Karar tablolarından
yazılmıştı (mısır 1,0; sertifikalı tohum 0,5), Bakanlığın 2026 tablosuyla çelişiyordu. Kaynaklar sayfa sayfa okundu
(Resmî Gazete PDF'leri taranmış; görüntü olarak okundu).

## Kaynaklar

1. **8859 sayılı CB Kararı** (RG 29.08.2024), 2025-2027 bitkisel üretim desteklemeleri —
   `docs/olcum/2026-10-10-tur20/rg_20240829_8859.pdf`, s. 2-7.
   - m.2/5-a Tablo 1: 3. kategori "Ayçiçeği (yağlık), Fındık, Kolza (kanola), Fasulye (kuru), Soya, Çay" — 1,5.
   - m.2/10 Tablo 10: lisanslı depoda fındık için kira desteği (Ticaret Bakanlığı tarifesinin %75'i).
   - m.6/4 (ilk hâli): 3267 sayılı BKK ile "kayıtlı olan alanlar" dışında fındık üretilen parsellere temel ve üretimi
     geliştirme desteği ödenmez.
   - m.6/5: Tarımsal Üretimin Planlanması Hakkında Yönetmeliğe aykırı yeni meyve bahçesine temel ve üretimi geliştirme
     desteği ödenmez.
2. **11781 sayılı CB Kararı** (RG 08.09.2026, sayı 33364) — `docs/olcum/2026-10-10-tur20/rg_20260908_11781.pdf`, s. 2-3.
   - m.1/a: 8859 m.2/4-a'daki "310 TL olarak" → "367 TL olarak, 2027 üretim yılı için destek katsayı değeri dekara
     442 TL olarak"; m.6/a ile **1/1/2026'dan geçerli**.
   - m.1/c: Tablo 4 ve Tablo 5 "2027 Üretim Yılı" katsayılarıyla değiştirildi (yürürlük 1/1/2027).
   - m.4: 8859 m.6/4'teki "kayıtlı olan alanlar" → "**fındık üretimine izin verilen ilçeler**"; m.6/b ile 1/1/2025'ten
     geçerli.
3. **BUGEM, 2026 Üretim Yılı Bitkisel Üretim Destekleme Birim Fiyatları** —
   https://www.tarimorman.gov.tr/BUGEM/Belgeler/Tar%C4%B1m%20Havzalar%C4%B1/2026%20Y%C4%B1l%C4%B1%20Destekleme%20Birim%20Fiyatlar%C4%B1.pdf
   (metin: `docs/olcum/2026-10-12-tur34/kaynak/1d11f092f9b0efcc.txt`). 2026 katsayıları: temel 2. kategori "Arpa,
   Buğday, Mısır (dane), İkinci grup yem bitkileri" 1,3; çavdar, tritikale, yulaf birinci grup yem bitkileri (1,0);
   sertifikalı tohum "Arpa, Buğday, Çavdar, Çeltik, Fasulye (kuru), Tritikale, Yulaf" 0,56; organomineral 0,32.
   Tablodaki toplamlar 310 TL ile hesaplıdır (11781'den önce yayımlandı).

4. **10394 sayılı CB Kararı** (RG 14.09.2025, sayı 33017; 1/1/2026'dan geçerli) — 8859'un m.2, 3, 5, 6, Geçici m.1 ve
   havza listesini değiştirdi: Tablo 1'de mısır (dane) 2. kategoriye, "diğer ürünler" 1. kategoriye; yulaf, çavdar,
   tritikale birinci grup yem bitkisi; Tablo 4'te arpa/buğday vb. tohum 0,5 → 0,56; katı organik gübre 0,21 → 0,32.
   Değişiklikler işlenmiş metin: https://www.mevzuat.gov.tr/MevzuatMetin/20.5.8859.pdf (tarım araştırma ajanı,
   2026-10-12). BUGEM 2026 tablosunun katsayıları bu hâle uygundur; tablodaki tek eskimiş değer 310 TL'dir.

## Sonuç (2026)

- Destek tutarı = BUGEM 2026 katsayısı × **367 TL/da**.
- Fındık: 1,5 × 367 = **550,50 TL/da** (9 da → 4.954,50 TL); planlı üretim desteği yok; yalnız fındık üretimine izin
  verilen ilçelerdeki parsellere.
- Hububat (kayıt 160): mercimek, nohut (ve birinci grup yem bitkisi olarak yulaf, çavdar, tritikale) 1,0 → 734,00
  TL/da (temel + planlı); arpa, buğday, mısır (dane) 1,3 → 954,20 TL/da; sertifikalı tohum arpa/buğday 0,56 → 205,52
  TL/da. Tur20 bu kaydı 8859'un 2024 tablolarıyla (mısır 1,0; tohum 0,5) yazmıştı.
- Kayıt alt sınırları (tutari_min): organik 73,40; sera 367; hububat 734; meyve-sebze 367 (önceden 310 TL'den kalma
  62/310/620/310 idi).

Uygulama: `scripts/fix_veri_2026_10_12_persona_tur35.py` (yedek `docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur35.db.bak`).
