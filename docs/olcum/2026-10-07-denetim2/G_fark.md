# Aşama G — önce / sonra (eşleştirme + arama)

## Hedef eşleşmesi alan kart sayısı (ilk 12)

| Persona | Önce | Sonra |
|---|---|---|
| 1 Konya ciftci | 2 | 2 |
| 2 Izmir tekstil | 3 | 9 |
| 3 Ankara girisim | 0 | 1 |
| 4 Van otel | 1 | 4 |
| 5 Trabzon eticaret | 2 | 6 |
| 6 Istanbul SaaS | 2 | 12 |
| 7 Bursa buyuk imalat | 1 | 11 |
| 8 Hatay mikro | 3 | 3 |
| 9 Ekmek 10.71 Konya | 1 | 8 |
| 10 Hatay NACEsiz hizmet | 10 | 10 |
| 11 Konya bugday sentetik | 2 | 2 |
| 12 Bursa metal sentetik | 3 | 9 |

## Elenmesi gerekenler (sıra; '-' = listede yok)

| Persona | Program | Önce | Sonra |
|---|---|---|---|
| 11 Konya bugday sentetik | 1501 | 13 | - |
| 11 Konya bugday sentetik | Girişimci Destek Programı | 11 | - |
| 11 Konya bugday sentetik | Meyve-Sebze | 8 | - |
| 11 Konya bugday sentetik | Organik | 5 | 5 |
| 11 Konya bugday sentetik | Sera | 9 | - |
| 1 Konya ciftci | 1501 | 14 | - |
| 1 Konya ciftci | Girişimci Destek Programı | 12 | 12 |
| 8 Hatay mikro | 1501 | 8 | - |
| 8 Hatay mikro | 1507 | 14 | - |
| 10 Hatay NACEsiz hizmet | 1501 | 18 | - |
| 10 Hatay NACEsiz hizmet | 1507 | - | - |
| 12 Bursa metal sentetik | Girişimci Destek Programı | 9 | - |
| 2 Izmir tekstil | Girişimci Destek Programı | 9 | 20 |
| 7 Bursa buyuk imalat | Girişimci Destek Programı | - | - |

## Üstte olması gerekenler (sıra / hedef)

| Persona | Program | Hedef ≤ | Önce | Sonra |
|---|---|---|---|---|
| 12 Bursa metal sentetik | Kapasite Geliştirme | 6 | 17 | 1 |
| 12 Bursa metal sentetik | Hedef Yatırımlar | 3 | 1 | 2 |
| 2 Izmir tekstil | Hedef Yatırımlar | 3 | 2 | 2 |
| 11 Konya bugday sentetik | Hububat | 2 | 1 | 1 |

## İlk 5 (önce → sonra)

- **1 Konya ciftci:** 160, 76, 78, 94, 161 → 160, 76, 78, 94, 161
- **2 Izmir tekstil:** 168, 180, 162, 178, 90 → 8, 180, 81, 178, 7
- **3 Ankara girisim:** 174, 49, 177, 178, 180 → 174, 49, 177, 178, 180
- **4 Van otel:** 180, 178, 90, 125, 1 → 180, 178, 90, 181, 172
- **5 Trabzon eticaret:** 162, 168, 163, 159, 125 → 162, 163, 159, 9, 168
- **6 Istanbul SaaS:** 182, 152, 2, 34, 168 → 8, 182, 152, 34, 9
- **7 Bursa buyuk imalat:** 180, 179, 177, 181, 178 → 180, 179, 177, 181, 178
- **8 Hatay mikro:** 178, 142, 7, 185, 125 → 178, 126, 186, 185, 172
- **9 Ekmek 10.71 Konya:** 178, 90, 125, 1, 186 → 8, 81, 178, 7, 3
- **10 Hatay NACEsiz hizmet:** 180, 178, 125, 7, 59 → 180, 178, 172, 2, 87
- **11 Konya bugday sentetik:** 160, 78, 76, 94, 77 → 160, 78, 76, 94, 77
- **12 Bursa metal sentetik:** 180, 168, 162, 178, 90 → 8, 180, 81, 178, 7

## Arama ilk 8 (sonra)

**12 Bursa metal sentetik** — 5 eksenli CNC tezgahı almak istiyoruz, yaklaşık 18 milyon TL, hangi destek ve krediler var?

| Önce | Sonra |
|---|---|
| 170 KGF | GİRİŞİMCİ DESTEK PROGRAMI KREDİ FAİZ PROGRAMI | 81 KGF | KAPASİTE GELİŞTİRME DESTEK PAKETİ |
| 87 KGF | HALK BANKASI ŞAHIS İŞLETMELERİ DESTEK KREDİSİ PROJESİ | 8 KOSGEB | Kapasite Geliştirme Destek Programı |
| 171 KGF | Ziraat Katılım Bankası Katılım Finans Destek Paketi | 90 KGF | YATIRIM-İŞLETME DESTEK PAKETİ |
| 168 KGF | ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ | 180 Sanayi ve Teknoloji Bakanlığı | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) |
| 154 KGF | KGF Genel Destek Programı | 125 KGF | 2024 Dijital Dönüşüm Destek Paketi |
| 91 KGF | TKYB KREDİ DESTEK PAKETİ | 142 KGF | İSTİHDAM KORUMA DESTEK PROGRAMI |
| 118 KGF | KOSGEB Geri Ödemeli Destekleri | 3 KOSGEB | KOBİ Dijital Dönüşüm Destek Programı |
| 125 KGF | 2024 Dijital Dönüşüm Destek Paketi | 170 KGF | GİRİŞİMCİ DESTEK PROGRAMI KREDİ FAİZ PROGRAMI |

**9 Ekmek 10.71 Konya** — Yeni ekmek üretim hattı için makine alacağım; yatırım teşvik belgesi alabilir miyim?

| Önce | Sonra |
|---|---|
| 90 KGF | YATIRIM-İŞLETME DESTEK PAKETİ | 81 KGF | KAPASİTE GELİŞTİRME DESTEK PAKETİ |
| 178 Sanayi ve Teknoloji Bakanlığı | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) | 8 KOSGEB | Kapasite Geliştirme Destek Programı |
| 81 KGF | KAPASİTE GELİŞTİRME DESTEK PAKETİ | 90 KGF | YATIRIM-İŞLETME DESTEK PAKETİ |
| 8 KOSGEB | Kapasite Geliştirme Destek Programı | 178 Sanayi ve Teknoloji Bakanlığı | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) |
| 185 SGK / İŞKUR | Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İst | 185 SGK / İŞKUR | Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İst |
| 186 SGK / İŞKUR | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik ( | 186 SGK / İŞKUR | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik ( |
| 25 TUBITAK | 1511 - TÜBİTAK Öncelikli Alanlar Araştırma Teknoloji Ge | 25 TUBITAK | 1511 - TÜBİTAK Öncelikli Alanlar Araştırma Teknoloji Ge |
| 107 KGF | KÜRESEL REKABETÇİLİK DESTEK PAKETİ | 180 Sanayi ve Teknoloji Bakanlığı | Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar) |

**1 Konya ciftci** — Traktör ve mibzer almak istiyorum, hibe var mı?

| Önce | Sonra |
|---|---|
| 78 Tarım Bakanlığı | Kırsal Kalkınma Yatırım Programı (KKYP) – Tarımsal İşle | 78 Tarım Bakanlığı | Kırsal Kalkınma Yatırım Programı (KKYP) – Tarımsal İşle |
| 79 Tarım Bakanlığı | Sera/Örtüaltı Tarım Destekleri | 79 Tarım Bakanlığı | Sera/Örtüaltı Tarım Destekleri |
| 94 KGF | TARIM KEFALET DESTEK PROGRAMI | 94 KGF | TARIM KEFALET DESTEK PROGRAMI |
| 80 Tarım Bakanlığı | Tasarruflu Tarımsal Sulama Sistemleri (TSS) Hibe Desteğ | 80 Tarım Bakanlığı | Tasarruflu Tarımsal Sulama Sistemleri (TSS) Hibe Desteğ |
| 27 TUBITAK | 1711 - Yapay Zekâ Ekosistem Çağrısı | 77 Tarım Bakanlığı | Organik Tarım Destekleri |
| 77 Tarım Bakanlığı | Organik Tarım Destekleri | 160 Tarım Bakanlığı | Hububat ve Baklagil Üretim Destekleri (Mazot-Gübre) |
| 44 TUBITAK | 1507 - TÜBİTAK KOBİ Ar-Ge Başlangıç Destek Programı | 161 Tarım Bakanlığı | Meyve-Sebze Üretim Destekleri (Mazot-Gübre) |
| 160 Tarım Bakanlığı | Hububat ve Baklagil Üretim Destekleri (Mazot-Gübre) | 76 Tarım Bakanlığı | Hayvancılık Destekleri |

**2 Izmir tekstil** — Almanya'ya ihracata başlayacağız, hangi destekler var?

| Önce | Sonra |
|---|---|
| 162 Ticaret Bakanlığı | E-İhracat Destekleri (5986 Sayılı Karar) | 162 Ticaret Bakanlığı | E-İhracat Destekleri (5986 Sayılı Karar) |
| 159 KGF | İhracat Destek Paketi | 159 KGF | İhracat Destek Paketi |
| 168 KGF | ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ | 168 KGF | ZİRAAT BANKASI YEŞİL İHRACAT KREDİSİ DESTEK PAKETİ |
| 163 Ticaret Bakanlığı | Pazara Girişte Dijital Faaliyetlerin Desteklenmesi | 9 KOSGEB | Küresel Rekabetçilik Destek Programı |
| 118 KGF | KOSGEB Geri Ödemeli Destekleri | 163 Ticaret Bakanlığı | Pazara Girişte Dijital Faaliyetlerin Desteklenmesi |
| 171 KGF | Ziraat Katılım Bankası Katılım Finans Destek Paketi | 107 KGF | KÜRESEL REKABETÇİLİK DESTEK PAKETİ |
| 153 KGF | TURYIB Programı Destek Paketi | 125 KGF | 2024 Dijital Dönüşüm Destek Paketi |
| 154 KGF | KGF Genel Destek Programı | 3 KOSGEB | KOBİ Dijital Dönüşüm Destek Programı |

**8 Hatay mikro** — 3 kişi daha işe alacağım, SGK desteği var mı?

| Önce | Sonra |
|---|---|
| 186 SGK / İŞKUR | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik ( | 186 SGK / İŞKUR | İşsizlik Ödeneği Alanların İstihdamına Yönelik Teşvik ( |
| 55 TUBITAK | 1707 - Siparişe Dayalı Ar-Ge Projeleri için KOBİ Destek | 185 SGK / İŞKUR | Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İst |
| 178 Sanayi ve Teknoloji Bakanlığı | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) | 126 KGF | İSTİHDAM TAAHHÜTLÜ KOBİ FİNANSMAN DESTEK PROGRAMI-II (B |
| 185 SGK / İŞKUR | Kadın, Genç ve Mesleki Yeterlilik Belgesi Olanların İst | 178 Sanayi ve Teknoloji Bakanlığı | Yerel Kalkınma Hamlesi Programı (9903 sayılı Karar) |
| 125 KGF | 2024 Dijital Dönüşüm Destek Paketi | 153 KGF | TURYIB Programı Destek Paketi |
| 153 KGF | TURYIB Programı Destek Paketi | 137 KGF | KGF Özkaynak Kefalet Programı |
| 137 KGF | KGF Özkaynak Kefalet Programı | 154 KGF | KGF Genel Destek Programı |
| 154 KGF | KGF Genel Destek Programı | 171 KGF | Ziraat Katılım Bankası Katılım Finans Destek Paketi |

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
