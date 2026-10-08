# 10 sentetik işletmeyle uçtan uca deneme — ham sonuç (2026-10-08)

Veritabanı: tur12 + tur13 + göç m0b2d4f6a012 uygulanmış KOPYA. Beklentiler çalıştırmadan önce yazıldı.

| Persona | Eşleşme | Beklenen (tuttu/toplam) | Yasak gelen | İlk 5'te yasak (ek) | Tarih hatası | Yol bilgisi (ilk 5) | Hazırlık ilk adım |
|---|---|---|---|---|---|---|---|
| P1 İKAS şahıs e-ticaret (Denizli) | 25 | 2/3 | 0 | 0 | 0 | 25/25 | ✓ sirket |
| P2 İKAS Ltd e-ihracatçı (İstanbul kozmetik) | 30 | 5/5 | 0 | 0 | 0 | 25/25 | ✓ dys_kaydi |
| P3 Konya buğday çiftçisi (şahıs) | 25 | 2/2 | 1 | 1 | 0 | 23/25 | ✓ cks |
| P4 Afyon büyükbaş hayvancı (şahıs) | 25 | 2/2 | 0 | 1 | 0 | 22/25 | ✓ cks |
| P5 Bursa metal imalat Ltd (45 kişi) | 30 | 4/4 | 0 | 0 | 0 | 25/25 | ✓ dys_kaydi |
| P6 Ankara şirketsiz yapay zekâ girişimcisi | 2 | 1/1 | 0 | 0 | 0 | 9/10 | ✓ sirket |
| P7 İzmir yazılım hizmet ihracatçısı Ltd | 30 | 2/2 | 0 | 0 | 0 | 25/25 | ✓ dys_kaydi |
| P8 Hatay kadın girişimci kuaför (şahıs) | 23 | 2/3 | 0 | 1 | 0 | 23/25 | ✓ kosgeb_kaydi |
| P9 Gaziantep gıda imalat A.Ş. (320 kişi) | 30 | 1/1 | 0 | 0 | 0 | 24/25 | ✓ dys_kaydi |
| P10 Karaman tarım kooperatifi | 30 | 2/2 | 0 | 0 | 0 | 21/25 | ✓ cks |

## P1 İKAS şahıs e-ticaret (Denizli)

**İlk 10:**

- 1. 162 Ticaret Baka | E-İhracat Destekleri (5986 Sayılı Karar) (1.00)
- 2. 159 KGF | İhracat Destek Paketi (0.70)
- 3. 9 KOSGEB | Küresel Rekabetçilik Destek Programı (0.70)
- 4. 168 KGF | ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ (0.70)
- 5. 107 KGF | KÜRESEL REKABETÇİLİK DESTEK PAKETİ (0.65)
- 6. 172 KGF | DİJİTAL KEFALET DESTEK PROGRAMI (0.30)
- 7. 1 KOSGEB | Girişimci Destek Programı (0.30)
- 8. 186 SGK / İŞKUR | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik ( (0.30)
- 9. 87 KGF | HALK BANKASI ŞAHIS İŞLETMELERİ DESTEK KREDİSİ PROJESİ (0.30)
- 10. 2 KOSGEB | Yapay Zekâ Kredi Programı (0.30)

**Beklenen:** 1 sıra 7 (≤6) ✗, 162 sıra 1 (≤10) ✓, 87 sıra 9 (≤12) ✓

**Yasak gelen:** yok

**Tarih:** tutarlı

**Başvuru yolu (ilk 5):**

| id | Program | yer | süre | şart | belge | resmi kaynak | çağrı |
|---|---|---|---|---|---|---|---|
| 162 | E-İhracat Destekleri (5986 Sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 159 | İhracat Destek Paketi | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 9 | Küresel Rekabetçilik Destek Programı | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 168 | ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 107 | KÜRESEL REKABETÇİLİK DESTEK PAKETİ | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |

**Hazırlık adımları:** sirket (10), kosgeb_kaydi (5), on_onay (1), dys_kaydi (1), birlik_uyeligi (1)

**E-ihracat:** şimdi 0 · hazırlıkla 122,100 · teyitle 0 · aylık bekleme 0 · adımlar ['sirket', 'birlik_uyeligi', 'madrid_marka'] · {'pazaryeri_reklam': ('hazirlik', 81600.0), 'pazaryeri_komisyon': ('hazirlik', 40500.0)}

## P2 İKAS Ltd e-ihracatçı (İstanbul kozmetik)

**İlk 10:**

- 1. 192 Ticaret Baka | Dijital Pazaryeri Tanıtım (Reklam) Desteği (5986 sayılı (1.00)
- 2. 162 Ticaret Baka | E-İhracat Destekleri (5986 Sayılı Karar) (1.00)
- 3. 187 Ticaret Baka | Pazara Giriş Belgesi Desteği (5973 sayılı Karar m.3) (1.00)
- 4. 193 Ticaret Baka | Sipariş Karşılama (Fulfillment) Hizmeti Desteği (5986 s (1.00)
- 5. 190 Ticaret Baka | Yurt Dışı Birim Kira Desteği — Mağaza, Depo, Ofis (5973 (1.00)
- 6. 188 Ticaret Baka | Yurt Dışı Marka Tescil Desteği (5973 sayılı Karar m.4) (1.00)
- 7. 189 Ticaret Baka | Yurt Dışı Pazar Araştırması Desteği (5973 sayılı Karar  (1.00)
- 8. 194 Ticaret Baka | Yurt Dışı Pazaryeri Komisyon Gideri Desteği (5986 sayıl (1.00)
- 9. 191 Ticaret Baka | Yurt Dışı Tanıtım ve Pazarlama Desteği (5973 sayılı Kar (1.00)
- 10. 159 KGF | İhracat Destek Paketi (0.70)

**Beklenen:** 192 sıra 1 (≤10) ✓, 193 sıra 4 (≤12) ✓, 194 sıra 8 (≤12) ✓, 188 sıra 6 (≤15) ✓, 9 sıra 11 (≤15) ✓

**Yasak gelen:** yok

**Tarih:** tutarlı

**Başvuru yolu (ilk 5):**

| id | Program | yer | süre | şart | belge | resmi kaynak | çağrı |
|---|---|---|---|---|---|---|---|
| 192 | Dijital Pazaryeri Tanıtım (Reklam) Desteği (5986 sayılı Karar m.4) | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 162 | E-İhracat Destekleri (5986 Sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 187 | Pazara Giriş Belgesi Desteği (5973 sayılı Karar m.3) | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 193 | Sipariş Karşılama (Fulfillment) Hizmeti Desteği (5986 sayılı Karar m.6 | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 190 | Yurt Dışı Birim Kira Desteği — Mağaza, Depo, Ofis (5973 sayılı Karar m | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |

**Hazırlık adımları:** dys_kaydi (9), birlik_uyeligi (8), on_onay (4), kosgeb_kaydi (4), madrid_marka (3), kep (1)

**E-ihracat:** şimdi 0 · hazırlıkla 0 · teyitle 1,140,000 · aylık bekleme 95,000 · adımlar [] · {'pazaryeri_reklam': ('teyit', 630000.0), 'siparis_karsilama': ('teyit', 210000.0), 'pazaryeri_komisyon': ('teyit', 300000.0), 'cevrim_ici_magaza': ('kapali', 0.0)}

## P3 Konya buğday çiftçisi (şahıs)

**İlk 10:**

- 1. 160 Tarım Bakanl | Hububat ve Baklagil Üretim Destekleri (Temel Destek + P (1.00)
- 2. 94 KGF | TARIM KEFALET DESTEK PROGRAMI (0.70)
- 3. 178 Sanayi ve Te | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) (0.65)
- 4. 77 Tarım Bakanl | Organik Tarım Destekleri (0.50)
- 5. 172 KGF | DİJİTAL KEFALET DESTEK PROGRAMI (0.30)
- 6. 2 KOSGEB | Yapay Zekâ Kredi Programı (0.30)
- 7. 186 SGK / İŞKUR | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik ( (0.30)
- 8. 87 KGF | HALK BANKASI ŞAHIS İŞLETMELERİ DESTEK KREDİSİ PROJESİ (0.30)
- 9. 5 KOSGEB | YÖNDE - Yönderlik ve Değerlendirme Destek Programı (0.30)
- 10. 185 SGK / İŞKUR | Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İst (0.30)

**Beklenen:** 160 sıra 1 (≤3) ✓, 94 sıra 2 (≤10) ✓

**Yasak gelen:** 77 sıra 4 (organik)

**Tarih:** tutarlı

**Başvuru yolu (ilk 5):**

| id | Program | yer | süre | şart | belge | resmi kaynak | çağrı |
|---|---|---|---|---|---|---|---|
| 160 | Hububat ve Baklagil Üretim Destekleri (Temel Destek + Planlı Üretim) | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 94 | TARIM KEFALET DESTEK PROGRAMI | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 178 | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | 9903 teşvik belgesi müracaat süresi: acik son gün 2030-12-31 (1545 gün) |
| 77 | Organik Tarım Destekleri | ✓ | ✓ | ✗ | ✗ | ✓ | doğrulanmış tarih yok |
| 172 | DİJİTAL KEFALET DESTEK PROGRAMI | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |

**Hazırlık adımları:** cks (2), kosgeb_kaydi (3), kep (2), yatirim_tesvik_belgesi (2)

## P4 Afyon büyükbaş hayvancı (şahıs)

**İlk 10:**

- 1. 76 Tarım Bakanl | Hayvancılık Destekleri (1.00)
- 2. 94 KGF | TARIM KEFALET DESTEK PROGRAMI (0.70)
- 3. 77 Tarım Bakanl | Organik Tarım Destekleri (0.50)
- 4. 180 Sanayi ve Te | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) (0.40)
- 5. 178 Sanayi ve Te | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) (0.35)
- 6. 172 KGF | DİJİTAL KEFALET DESTEK PROGRAMI (0.30)
- 7. 2 KOSGEB | Yapay Zekâ Kredi Programı (0.30)
- 8. 186 SGK / İŞKUR | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik ( (0.30)
- 9. 87 KGF | HALK BANKASI ŞAHIS İŞLETMELERİ DESTEK KREDİSİ PROJESİ (0.30)
- 10. 5 KOSGEB | YÖNDE - Yönderlik ve Değerlendirme Destek Programı (0.30)

**Beklenen:** 76 sıra 1 (≤3) ✓, 94 sıra 2 (≤10) ✓

**Yasak gelen:** yok

**Tarih:** tutarlı

**Başvuru yolu (ilk 5):**

| id | Program | yer | süre | şart | belge | resmi kaynak | çağrı |
|---|---|---|---|---|---|---|---|
| 76 | Hayvancılık Destekleri | ✓ | ✓ | ✗ | ✓ | ✓ | doğrulanmış tarih yok |
| 94 | TARIM KEFALET DESTEK PROGRAMI | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 77 | Organik Tarım Destekleri | ✓ | ✓ | ✗ | ✗ | ✓ | doğrulanmış tarih yok |
| 180 | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | 9903 teşvik belgesi müracaat süresi: acik son gün 2030-12-31 (1545 gün) |
| 178 | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | 9903 teşvik belgesi müracaat süresi: acik son gün 2030-12-31 (1545 gün) |

**Hazırlık adımları:** cks (1), kosgeb_kaydi (3), kep (2), yatirim_tesvik_belgesi (2)

## P5 Bursa metal imalat Ltd (45 kişi)

**İlk 10:**

- 1. 8 KOSGEB | Kapasite Geliştirme Destek Programı (1.00)
- 2. 180 Sanayi ve Te | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) (1.00)
- 3. 179 Sanayi ve Te | Stratejik Hamle Programı (9903 sayılı Karar) (1.00)
- 4. 81 KGF | KAPASİTE GELİŞTİRME DESTEK PAKETİ (0.95)
- 5. 178 Sanayi ve Te | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) (0.95)
- 6. 7 KOSGEB | İstihdamı Koruma Destek Programı (0.70)
- 7. 159 KGF | İhracat Destek Paketi (0.70)
- 8. 192 Ticaret Baka | Dijital Pazaryeri Tanıtım (Reklam) Desteği (5986 sayılı (0.70)
- 9. 3 KOSGEB | KOBİ Dijital Dönüşüm Destek Programı (0.70)
- 10. 168 KGF | ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ (0.70)

**Beklenen:** 8 sıra 1 (≤6) ✓, 180 sıra 2 (≤6) ✓, 81 sıra 4 (≤12) ✓, 7 sıra 6 (≤15) ✓

**Yasak gelen:** yok

**Tarih:** tutarlı

**Başvuru yolu (ilk 5):**

| id | Program | yer | süre | şart | belge | resmi kaynak | çağrı |
|---|---|---|---|---|---|---|---|
| 8 | Kapasite Geliştirme Destek Programı | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 180 | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | 9903 teşvik belgesi müracaat süresi: acik son gün 2030-12-31 (1545 gün) |
| 179 | Stratejik Hamle Programı (9903 sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | 9903 teşvik belgesi müracaat süresi: acik son gün 2030-12-31 (1545 gün) |
| 81 | KAPASİTE GELİŞTİRME DESTEK PAKETİ | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 178 | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | 9903 teşvik belgesi müracaat süresi: acik son gün 2030-12-31 (1545 gün) |

**Hazırlık adımları:** dys_kaydi (11), birlik_uyeligi (10), kosgeb_kaydi (7), on_onay (6), kep (6), yatirim_tesvik_belgesi (5), madrid_marka (3)

## P6 Ankara şirketsiz yapay zekâ girişimcisi

**İlk 10:**

- 1. 174 TUBITAK | 1512 - Girişimcilik Destek Programı (BiGG - Bireysel Ge (0.70)
- 2. 49 TUBITAK | 1812 - Yatırım Tabanlı Girişimcilik Destek Programı (Bi (0.70)

**Beklenen:** 174 sıra 1 (≤3) ✓

**Yasak gelen:** yok

**Tarih:** tutarlı

**Başvuru yolu (ilk 5):**

| id | Program | yer | süre | şart | belge | resmi kaynak | çağrı |
|---|---|---|---|---|---|---|---|
| 174 | 1512 - Girişimcilik Destek Programı (BiGG - Bireysel Genç Girişim) | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 49 | 1812 - Yatırım Tabanlı Girişimcilik Destek Programı (BiGG Yatırım) | ✓ | ✗ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |

**Hazırlık adımları:** sirket (19)

## P7 İzmir yazılım hizmet ihracatçısı Ltd

**İlk 10:**

- 1. 182 Ticaret Baka | Hizmet İhracatı Destekleri – Bilişim Sektörü (10962 say (1.00)
- 2. 8 KOSGEB | Kapasite Geliştirme Destek Programı (0.70)
- 3. 159 KGF | İhracat Destek Paketi (0.70)
- 4. 34 TUBITAK | 1501 - TÜBİTAK Sanayi Ar-Ge Projeleri Destekleme Progra (0.70)
- 5. 192 Ticaret Baka | Dijital Pazaryeri Tanıtım (Reklam) Desteği (5986 sayılı (0.70)
- 6. 152 KGF | TÜBİTAK Transfer Ödemeleri (0.70)
- 7. 9 KOSGEB | Küresel Rekabetçilik Destek Programı (0.70)
- 8. 75 TUBITAK | 1505 - Üniversite-Sanayi İşbirliği Destek Programı (0.70)
- 9. 162 Ticaret Baka | E-İhracat Destekleri (5986 Sayılı Karar) (0.70)
- 10. 168 KGF | ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ (0.70)

**Beklenen:** 182 sıra 1 (≤6) ✓, 44 sıra 12 (≤15) ✓

**Yasak gelen:** yok

**Tarih:** tutarlı

**Başvuru yolu (ilk 5):**

| id | Program | yer | süre | şart | belge | resmi kaynak | çağrı |
|---|---|---|---|---|---|---|---|
| 182 | Hizmet İhracatı Destekleri – Bilişim Sektörü (10962 sayılı Karar, Hizm | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 8 | Kapasite Geliştirme Destek Programı | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 159 | İhracat Destek Paketi | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 34 | 1501 - TÜBİTAK Sanayi Ar-Ge Projeleri Destekleme Programı | ✓ | ✓ | ✓ | ✓ | ✓ | 2026 yılı 2. çağrı: acik son gün 2026-10-22 (14 gün) |
| 192 | Dijital Pazaryeri Tanıtım (Reklam) Desteği (5986 sayılı Karar m.4) | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |

**Hazırlık adımları:** dys_kaydi (12), birlik_uyeligi (10), on_onay (6), kosgeb_kaydi (5), madrid_marka (3), kep (2), borc_durumu (1), yatirim_tesvik_belgesi (1)

## P8 Hatay kadın girişimci kuaför (şahıs)

**İlk 10:**

- 1. 126 KGF | İSTİHDAM TAAHHÜTLÜ KOBİ FİNANSMAN DESTEK PROGRAMI-II (B (0.60)
- 2. 186 SGK / İŞKUR | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik ( (0.60)
- 3. 169 KGF | ZİRAAT BANKASI KADIN VE GENÇ GİRİŞİMCİ DESTEK PAKETİ (0.60)
- 4. 185 SGK / İŞKUR | Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İst (0.60)
- 5. 178 Sanayi ve Te | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) (0.35)
- 6. 172 KGF | DİJİTAL KEFALET DESTEK PROGRAMI (0.30)
- 7. 1 KOSGEB | Girişimci Destek Programı (0.30)
- 8. 87 KGF | HALK BANKASI ŞAHIS İŞLETMELERİ DESTEK KREDİSİ PROJESİ (0.30)
- 9. 2 KOSGEB | Yapay Zekâ Kredi Programı (0.30)
- 10. 122 KGF | HALKBANK İLK ADIM KREDİSİ PROJESİ (0.30)

**Beklenen:** 1 sıra 7 (≤6) ✗, 169 sıra 3 (≤12) ✓, 185 sıra 4 (≤12) ✓

**Yasak gelen:** yok

**Tarih:** tutarlı

**Başvuru yolu (ilk 5):**

| id | Program | yer | süre | şart | belge | resmi kaynak | çağrı |
|---|---|---|---|---|---|---|---|
| 126 | İSTİHDAM TAAHHÜTLÜ KOBİ FİNANSMAN DESTEK PROGRAMI-II (BMZ II) | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 186 | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik (4447 sayılı Kan | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 169 | ZİRAAT BANKASI KADIN VE GENÇ GİRİŞİMCİ DESTEK PAKETİ | ✗ | ✓ | ✓ | ✗ | ✓ | doğrulanmış tarih yok |
| 185 | Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İstihdamı Teşviki  | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 178 | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | 9903 teşvik belgesi müracaat süresi: acik son gün 2030-12-31 (1545 gün) |

**Hazırlık adımları:** kosgeb_kaydi (4), kep (1), yatirim_tesvik_belgesi (1)

## P9 Gaziantep gıda imalat A.Ş. (320 kişi)

**İlk 10:**

- 1. 180 Sanayi ve Te | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) (1.00)
- 2. 179 Sanayi ve Te | Stratejik Hamle Programı (9903 sayılı Karar) (1.00)
- 3. 178 Sanayi ve Te | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) (0.95)
- 4. 7 KOSGEB | İstihdamı Koruma Destek Programı (0.70)
- 5. 159 KGF | İhracat Destek Paketi (0.70)
- 6. 192 Ticaret Baka | Dijital Pazaryeri Tanıtım (Reklam) Desteği (5986 sayılı (0.70)
- 7. 168 KGF | ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ (0.70)
- 8. 162 Ticaret Baka | E-İhracat Destekleri (5986 Sayılı Karar) (0.70)
- 9. 196 Ticaret Baka | E-İhracat Tanıtım Desteği — Perakende E-Ticaret Sitesi  (0.70)
- 10. 187 Ticaret Baka | Pazara Giriş Belgesi Desteği (5973 sayılı Karar m.3) (0.70)

**Beklenen:** 180 sıra 1 (≤5) ✓

**Yasak gelen:** yok

**Tarih:** tutarlı

**Başvuru yolu (ilk 5):**

| id | Program | yer | süre | şart | belge | resmi kaynak | çağrı |
|---|---|---|---|---|---|---|---|
| 180 | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | 9903 teşvik belgesi müracaat süresi: acik son gün 2030-12-31 (1545 gün) |
| 179 | Stratejik Hamle Programı (9903 sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | 9903 teşvik belgesi müracaat süresi: acik son gün 2030-12-31 (1545 gün) |
| 178 | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | 9903 teşvik belgesi müracaat süresi: acik son gün 2030-12-31 (1545 gün) |
| 7 | İstihdamı Koruma Destek Programı | ✗ | ✓ | ✓ | ✓ | ✓ | 2026-2 dönemi: acik son gün 2026-10-31 (23 gün) |
| 159 | İhracat Destek Paketi | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |

**Hazırlık adımları:** dys_kaydi (11), birlik_uyeligi (10), on_onay (6), kep (6), yatirim_tesvik_belgesi (5), madrid_marka (3), kosgeb_kaydi (1)

## P10 Karaman tarım kooperatifi

**İlk 10:**

- 1. 94 KGF | TARIM KEFALET DESTEK PROGRAMI (0.70)
- 2. 180 Sanayi ve Te | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) (0.65)
- 3. 178 Sanayi ve Te | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) (0.65)
- 4. 116 KGF | KGF Kooperatif Destek Paketi (0.60)
- 5. 76 Tarım Bakanl | Hayvancılık Destekleri (0.60)
- 6. 160 Tarım Bakanl | Hububat ve Baklagil Üretim Destekleri (Temel Destek + P (0.60)
- 7. 161 Tarım Bakanl | Meyve-Sebze Üretim Destekleri (Temel Destek) (0.60)
- 8. 79 Tarım Bakanl | Sera/Örtüaltı Tarım Destekleri (0.60)
- 9. 77 Tarım Bakanl | Organik Tarım Destekleri (0.50)
- 10. 172 KGF | DİJİTAL KEFALET DESTEK PROGRAMI (0.30)

**Beklenen:** 116 sıra 4 (≤10) ✓, 94 sıra 1 (≤10) ✓

**Yasak gelen:** yok

**Tarih:** tutarlı

**Başvuru yolu (ilk 5):**

| id | Program | yer | süre | şart | belge | resmi kaynak | çağrı |
|---|---|---|---|---|---|---|---|
| 94 | TARIM KEFALET DESTEK PROGRAMI | ✓ | ✓ | ✓ | ✓ | ✓ | doğrulanmış tarih yok |
| 180 | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | 9903 teşvik belgesi müracaat süresi: acik son gün 2030-12-31 (1545 gün) |
| 178 | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) | ✓ | ✓ | ✓ | ✓ | ✓ | 9903 teşvik belgesi müracaat süresi: acik son gün 2030-12-31 (1545 gün) |
| 116 | KGF Kooperatif Destek Paketi | ✗ | ✓ | ✗ | ✗ | ✓ | doğrulanmış tarih yok |
| 76 | Hayvancılık Destekleri | ✓ | ✓ | ✗ | ✓ | ✓ | doğrulanmış tarih yok |

**Hazırlık adımları:** cks (3), kep (4), yatirim_tesvik_belgesi (4), kosgeb_kaydi (3)