# Aşama G — önce / sonra (eşleştirme + arama)

## Hedef eşleşmesi alan kart sayısı (ilk 12)

| Persona | Önce | Sonra |
|---|---|---|
| 1 Konya ciftci | 1 | 1 |
| 2 Izmir tekstil | 10 | 10 |
| 3 Ankara girisim | 0 | 0 |
| 4 Van otel | 4 | 4 |
| 5 Trabzon eticaret | 12 | 12 |
| 6 Istanbul SaaS | 12 | 12 |
| 7 Bursa buyuk imalat | 11 | 11 |
| 8 Hatay mikro | 3 | 3 |
| 9 Ekmek 10.71 Konya | 8 | 5 |
| 10 Hatay NACEsiz hizmet | 12 | 12 |
| 11 Konya bugday sentetik | 1 | 1 |
| 12 Bursa metal sentetik | 10 | 10 |

## Elenmesi gerekenler (sıra; '-' = listede yok)

| Persona | Program | Önce | Sonra |
|---|---|---|---|
| 11 Konya bugday sentetik | 1501 | - | - |
| 11 Konya bugday sentetik | Girişimci Destek Programı | - | - |
| 11 Konya bugday sentetik | Meyve-Sebze | - | - |
| 11 Konya bugday sentetik | Organik | 5 | 5 |
| 11 Konya bugday sentetik | Sera | - | - |
| 1 Konya ciftci | 1501 | - | - |
| 1 Konya ciftci | Girişimci Destek Programı | 10 | 10 |
| 8 Hatay mikro | 1501 | - | - |
| 8 Hatay mikro | 1507 | - | - |
| 10 Hatay NACEsiz hizmet | 1501 | - | - |
| 10 Hatay NACEsiz hizmet | 1507 | - | - |
| 12 Bursa metal sentetik | Girişimci Destek Programı | - | - |
| 2 Izmir tekstil | Girişimci Destek Programı | - | - |
| 7 Bursa buyuk imalat | Girişimci Destek Programı | - | - |

## Üstte olması gerekenler (sıra / hedef)

| Persona | Program | Hedef ≤ | Önce | Sonra |
|---|---|---|---|---|
| 12 Bursa metal sentetik | Kapasite Geliştirme | 6 | 1 | 1 |
| 12 Bursa metal sentetik | Hedef Yatırımlar | 3 | 2 | 2 |
| 2 Izmir tekstil | Hedef Yatırımlar | 3 | 2 | 2 |
| 11 Konya bugday sentetik | Hububat | 2 | 1 | 1 |

## İlk 5 (önce → sonra)

- **1 Konya ciftci:** 76, 160, 94, 161, 79 → 76, 160, 94, 161, 79
- **2 Izmir tekstil:** 8, 180, 81, 178, 7 → 8, 180, 81, 178, 7
- **3 Ankara girisim:** 174, 49 → 174, 49
- **4 Van otel:** 180, 178, 90, 181, 172 → 180, 178, 90, 172, 1
- **5 Trabzon eticaret:** 192, 162, 196, 187, 193 → 192, 162, 196, 187, 193
- **6 Istanbul SaaS:** 8, 182, 152, 34, 9 → 8, 182, 152, 34, 9
- **7 Bursa buyuk imalat:** 180, 179, 177, 181, 178 → 180, 179, 177, 181, 178
- **8 Hatay mikro:** 126, 186, 185, 178, 172 → 126, 186, 185, 178, 172
- **9 Ekmek 10.71 Konya:** 8, 81, 178, 7, 3 → 8, 81, 178, 7, 3
- **10 Hatay NACEsiz hizmet:** 172, 2, 87, 122, 126 → 172, 87, 122, 126, 154
- **11 Konya bugday sentetik:** 160, 76, 94, 178, 77 → 160, 76, 94, 178, 77
- **12 Bursa metal sentetik:** 8, 180, 81, 178, 7 → 8, 180, 81, 178, 7

## Arama ilk 8 (sonra)

**12 Bursa metal sentetik** — 5 eksenli CNC tezgahı almak istiyoruz, yaklaşık 18 milyon TL, hangi destek ve krediler var?

| Önce | Sonra |
|---|---|
| 81 KGF | KAPASİTE GELİŞTİRME DESTEK PAKETİ | 81 KGF | KAPASİTE GELİŞTİRME DESTEK PAKETİ |
| 8 KOSGEB | Kapasite Geliştirme Destek Programı | 8 KOSGEB | Kapasite Geliştirme Destek Programı |
| 90 KGF | YATIRIM-İŞLETME DESTEK PAKETİ | 90 KGF | YATIRIM-İŞLETME DESTEK PAKETİ |
| 180 Sanayi ve Teknoloji Bakanlığı | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) | 180 Sanayi ve Teknoloji Bakanlığı | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) |
| 125 KGF | 2024 Dijital Dönüşüm Destek Paketi | 125 KGF | 2024 Dijital Dönüşüm Destek Paketi |
| 142 KGF | İSTİHDAM KORUMA DESTEK PROGRAMI | 142 KGF | İSTİHDAM KORUMA DESTEK PROGRAMI |
| 3 KOSGEB | KOBİ Dijital Dönüşüm Destek Programı | 3 KOSGEB | KOBİ Dijital Dönüşüm Destek Programı |
| 170 KGF | GİRİŞİMCİ DESTEK PROGRAMI KREDİ FAİZ PROGRAMI | 170 KGF | GİRİŞİMCİ DESTEK PROGRAMI KREDİ FAİZ PROGRAMI |

**9 Ekmek 10.71 Konya** — Yeni ekmek üretim hattı için makine alacağım; yatırım teşvik belgesi alabilir miyim?

| Önce | Sonra |
|---|---|
| 81 KGF | KAPASİTE GELİŞTİRME DESTEK PAKETİ | 81 KGF | KAPASİTE GELİŞTİRME DESTEK PAKETİ |
| 8 KOSGEB | Kapasite Geliştirme Destek Programı | 8 KOSGEB | Kapasite Geliştirme Destek Programı |
| 90 KGF | YATIRIM-İŞLETME DESTEK PAKETİ | 90 KGF | YATIRIM-İŞLETME DESTEK PAKETİ |
| 178 Sanayi ve Teknoloji Bakanlığı | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) | 178 Sanayi ve Teknoloji Bakanlığı | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) |
| 185 SGK / İŞKUR | Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İst | 185 SGK / İŞKUR | Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İst |
| 186 SGK / İŞKUR | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik ( | 186 SGK / İŞKUR | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik ( |
| 25 TUBITAK | 1511 - TÜBİTAK Öncelikli Alanlar Araştırma Teknoloji Ge | 25 TUBITAK | 1511 - TÜBİTAK Öncelikli Alanlar Araştırma Teknoloji Ge |
| 180 Sanayi ve Teknoloji Bakanlığı | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) | 180 Sanayi ve Teknoloji Bakanlığı | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) |

**1 Konya ciftci** — Traktör ve mibzer almak istiyorum, hibe var mı?

| Önce | Sonra |
|---|---|
| 79 Tarım Bakanlığı | Sera/Örtüaltı Tarım Destekleri | 79 Tarım Bakanlığı | Sera/Örtüaltı Tarım Destekleri |
| 94 KGF | TARIM KEFALET DESTEK PROGRAMI | 94 KGF | TARIM KEFALET DESTEK PROGRAMI |
| 76 Tarım Bakanlığı | Hayvancılık Destekleri | 76 Tarım Bakanlığı | Hayvancılık Destekleri |
| 77 Tarım Bakanlığı | Organik Tarım Destekleri | 77 Tarım Bakanlığı | Organik Tarım Destekleri |
| 160 Tarım Bakanlığı | Hububat ve Baklagil Üretim Destekleri (Temel Destek + P | 160 Tarım Bakanlığı | Hububat ve Baklagil Üretim Destekleri (Temel Destek + P |
| 161 Tarım Bakanlığı | Meyve-Sebze Üretim Destekleri (Temel Destek) | 161 Tarım Bakanlığı | Meyve-Sebze Üretim Destekleri (Temel Destek) |
| 178 Sanayi ve Teknoloji Bakanlığı | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) | 178 Sanayi ve Teknoloji Bakanlığı | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) |
| 180 Sanayi ve Teknoloji Bakanlığı | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) | 180 Sanayi ve Teknoloji Bakanlığı | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) |

**2 Izmir tekstil** — Almanya'ya ihracata başlayacağız, hangi destekler var?

| Önce | Sonra |
|---|---|
| 162 Ticaret Bakanlığı | E-İhracat Destekleri (5986 Sayılı Karar) | 162 Ticaret Bakanlığı | E-İhracat Destekleri (5986 Sayılı Karar) |
| 159 KGF | İhracat Destek Paketi | 159 KGF | İhracat Destek Paketi |
| 168 KGF | ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ | 168 KGF | ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ |
| 9 KOSGEB | Küresel Rekabetçilik Destek Programı | 9 KOSGEB | Küresel Rekabetçilik Destek Programı |
| 196 Ticaret Bakanlığı | E-İhracat Tanıtım Desteği — Perakende E-Ticaret Sitesi  | 196 Ticaret Bakanlığı | E-İhracat Tanıtım Desteği — Perakende E-Ticaret Sitesi  |
| 107 KGF | KÜRESEL REKABETÇİLİK DESTEK PAKETİ | 107 KGF | KÜRESEL REKABETÇİLİK DESTEK PAKETİ |
| 187 Ticaret Bakanlığı | Pazara Giriş Belgesi Desteği (5973 sayılı Karar m.3) | 187 Ticaret Bakanlığı | Pazara Giriş Belgesi Desteği (5973 sayılı Karar m.3) |
| 188 Ticaret Bakanlığı | Yurt Dışı Marka Tescil Desteği (5973 sayılı Karar m.4) | 188 Ticaret Bakanlığı | Yurt Dışı Marka Tescil Desteği (5973 sayılı Karar m.4) |

**8 Hatay mikro** — 3 kişi daha işe alacağım, SGK desteği var mı?

| Önce | Sonra |
|---|---|
| 186 SGK / İŞKUR | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik ( | 186 SGK / İŞKUR | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik ( |
| 185 SGK / İŞKUR | Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İst | 185 SGK / İŞKUR | Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İst |
| 126 KGF | İSTİHDAM TAAHHÜTLÜ KOBİ FİNANSMAN DESTEK PROGRAMI-II (B | 126 KGF | İSTİHDAM TAAHHÜTLÜ KOBİ FİNANSMAN DESTEK PROGRAMI-II (B |
| 178 Sanayi ve Teknoloji Bakanlığı | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) | 178 Sanayi ve Teknoloji Bakanlığı | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) |
| 153 KGF | TURYIB Programı Destek Paketi | 153 KGF | TURYIB Programı Destek Paketi |
| 137 KGF | KGF Özkaynak Kefalet Programı | 137 KGF | KGF Özkaynak Kefalet Programı |
| 154 KGF | KGF Genel Destek Programı | 154 KGF | KGF Genel Destek Programı |
| 171 KGF | Ziraat Katılım Bankası Katılım Finans Destek Paketi | 171 KGF | Ziraat Katılım Bankası Katılım Finans Destek Paketi |

**10 Hatay NACEsiz hizmet** — İşletme sermayesi için uygun faizli kredi veya kefalet desteği arıyorum.

| Önce | Sonra |
|---|---|
| 87 KGF | HALK BANKASI ŞAHIS İŞLETMELERİ DESTEK KREDİSİ PROJESİ | 87 KGF | HALK BANKASI ŞAHIS İŞLETMELERİ DESTEK KREDİSİ PROJESİ |
| 90 KGF | YATIRIM-İŞLETME DESTEK PAKETİ | 90 KGF | YATIRIM-İŞLETME DESTEK PAKETİ |
| 170 KGF | GİRİŞİMCİ DESTEK PROGRAMI KREDİ FAİZ PROGRAMI | 170 KGF | GİRİŞİMCİ DESTEK PROGRAMI KREDİ FAİZ PROGRAMI |
| 91 KGF | TKYB KREDİ DESTEK PAKETİ | 91 KGF | TKYB KREDİ DESTEK PAKETİ |
| 122 KGF | HALKBANK İLK ADIM KREDİSİ PROJESİ | 122 KGF | HALKBANK İLK ADIM KREDİSİ PROJESİ |
| 168 KGF | ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ | 168 KGF | ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ |
| 172 KGF | DİJİTAL KEFALET DESTEK PROGRAMI | 172 KGF | DİJİTAL KEFALET DESTEK PROGRAMI |
| 86 KGF | TOBB NEFES KREDİSİ 2026 DESTEK PROGRAMI | 86 KGF | TOBB NEFES KREDİSİ 2026 DESTEK PROGRAMI |
