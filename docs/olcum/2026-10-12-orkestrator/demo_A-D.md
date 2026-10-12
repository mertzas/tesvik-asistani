

=============== SENARYO A: Yalnız Amazon/Etsy satışı yapan mikro şahıs işletmesi (sentetik girdi) ===============

#### BÖLÜM 1: AJAN TARTIŞMASI VE DÜZELTME RAPORU — Senaryo A
**1 Ayrıştırma**
- 2 harcama ayrıştırıldı; toplam KDV hariç 62.250,00 TL.
**2 Mevzuat eşleştirme**
- Kalem eşleştirmesi: #1 Dijital Pazaryeri Tanıtım (Reklam) Desteği → RET; #2 Yurt Dışı Pazaryeri Komisyon Gideri Desteği → RET.
**3 KOBİ ve KOSGEB**
- KOBİ ölçeği: mikro işletme.
- KOSGEB'in güncel kayıtlarında yurt dışı pazar/e-ihracat desteği yok; şablondaki 'KOSGEB Yurt Dışı Pazar Destek Programı' kayıtlı güncel programlar arasında değil.
**4 Hedef ülke**
- #1 ABD hedef ülke listesinde; Dijital Pazaryeri Tanıtım oranı %50 → %70 (+20 puan, kayıttan).
- #2 ABD hedef ülke listesinde, ama bu kalem için kayıtta hedef ülke oranı yazılı değil; ilave uygulanmadı.
**5 Mükerrerlik ve usulsüzlük**
- Mükerrerlik/usulsüzlük: 2 ret, 0 şartlı harcama.
**Hesap**
- Dijital Pazaryeri Tanıtım (Reklam) Desteği (ABD): esas 0,00 TL × %70 = 0,00 TL → RET.
- Yurt Dışı Pazaryeri Komisyon Gideri Desteği: esas 0,00 TL × %50 = 0,00 TL → RET.
**6 DYS eksikleri**
- İhracatçı birliği üyeliği
- Ticaret Bakanlığı DYS kaydı
- Yurt dışı marka tescili (Madrid Sistemi)
- Harcamadan önce ön onay
- DYS yetkilendirme (şirket yetkilisi adına DYS kullanıcı yetkisi)
- Güncel imza sirküleri
**8 Onarım rotaları**
- Dijital Pazaryeri Tanıtım (Reklam) Desteği — ABD: Limited/anonim şirkete geçin ya da E-İhracat Konsorsiyumu üyesi olun; harcamaları şirket kurulduktan ve ön onay alındıktan sonra şirket adına yapın.
- Yurt Dışı Pazaryeri Komisyon Gideri Desteği: Limited/anonim şirkete geçin ya da E-İhracat Konsorsiyumu üyesi olun; harcamaları şirket kurulduktan ve ön onay alındıktan sonra şirket adına yapın.
**7 Senaryo stres testi**
- Senaryo A (Yalnız Amazon/Etsy satışı yapan mikro şahıs işletmesi): 0 uygun, 0 şartlı, 2 ret; toplam talep 0,00 TL.
- Senaryo B (Kendi ikas sitesinden doğrudan yurt dışına (D2C) satan marka): 0 uygun, 0 şartlı, 2 ret; toplam talep 0,00 TL.
- Senaryo C (Pazaryerinde satan, hedef ülkede deposu olan karma işletme): 2 uygun, 0 şartlı, 1 ret; toplam talep 345.310,00 TL.
- Senaryo D (Harcaması tavanı aşan, kuru eksik ve süresi geçmiş kalemleri olan sınır durum): 0 uygun, 1 şartlı, 0 ret; toplam talep 3.698.274,00 TL.

#### BÖLÜM 2: RESMİ BAŞVURU GEREKÇE METNİ
Başvuru sahibi şirketin sunduğu harcamaların hiçbiri 5986 ve 5973 sayılı Kararlar kapsamında destek şartlarını sağlamamaktadır; başvuru yapılmamalı, düzeltme rotaları uygulanmalıdır.

#### BÖLÜM 3: RESMİ ENJEKSİYON JSON ŞEMASI
```json
{
  "basvuru_meta": {
    "mevzuat_dayanagi": "5986 sayılı Cumhurbaşkanı Kararı (e-ihracat destekleri) ve 5973 sayılı Cumhurbaşkanı Kararı (marka tescili, pazar araştırması, birim kira, tanıtım)",
    "basvuru_turu": "Ödeme başvurusu (kalem bazında; ön onay gerektiren kalemlerde ön onay sonrası)",
    "kobi_olcegi": "mikro işletme"
  },
  "tesvik_kalemleri": [
    {
      "kalem_adi": "Dijital Pazaryeri Tanıtım (Reklam) Desteği — ABD",
      "harcama_tutari_orijinal": 1200.0,
      "harcama_para_birimi": "USD",
      "harcama_tutari_try": 0,
      "destek_orani_yuzde": 50,
      "hedef_ulke_ilave_puani": 20,
      "net_destek_orani": 70,
      "mevzuat_tavan_try": 36993646.0,
      "talep_edilen_hakedis_try": 0.0,
      "onay_durumu": "RET",
      "not": "#1: Kalem açıklamadan çıkarıldı: pazaryeri_reklam. #1: Şahıs işletmesi doğrudan yararlanamaz (kayıt şartı: \"Şirket ya da kooperatif olmak (şahıs işletmesi yalnız E-İhracat Konsorsiyumu aracılığıyla, sınırlı süre)\")."
    },
    {
      "kalem_adi": "Yurt Dışı Pazaryeri Komisyon Gideri Desteği",
      "harcama_tutari_orijinal": 300.0,
      "harcama_para_birimi": "USD",
      "harcama_tutari_try": 0,
      "destek_orani_yuzde": 50,
      "hedef_ulke_ilave_puani": 0,
      "net_destek_orani": 50,
      "mevzuat_tavan_try": 3698274.0,
      "talep_edilen_hakedis_try": 0.0,
      "onay_durumu": "RET",
      "not": "#2: Kalem açıklamadan çıkarıldı: pazaryeri_komisyon. #2: Şahıs işletmesi doğrudan yararlanamaz (kayıt şartı: \"Şirket ya da kooperatif olmak (şahıs işletmesi yalnız E-İhracat Konsorsiyumu aracılığıyla, sınırlı süre)\")."
    }
  ],
  "toplam_talep_try": 0.0,
  "eksik_ve_tamamlanacak_evraklar": [
    "İhracatçı birliği üyeliği",
    "Ticaret Bakanlığı DYS kaydı",
    "Yurt dışı marka tescili (Madrid Sistemi)",
    "Harcamadan önce ön onay",
    "DYS yetkilendirme (şirket yetkilisi adına DYS kullanıcı yetkisi)",
    "Güncel imza sirküleri"
  ]
}
```


=============== SENARYO B: Kendi ikas sitesinden doğrudan yurt dışına (D2C) satan marka (sentetik girdi) ===============

#### BÖLÜM 1: AJAN TARTIŞMASI VE DÜZELTME RAPORU — Senaryo B
**1 Ayrıştırma**
- 2 harcama ayrıştırıldı; toplam KDV hariç 141.400,00 TL.
**2 Mevzuat eşleştirme**
- Kalem eşleştirmesi: #1 E-İhracat Tanıtım Desteği (Perakende E-Ticaret Sitesi statüsü) → RET; #2 Kapsam dışı → RET.
**3 KOBİ ve KOSGEB**
- KOBİ ölçeği: mikro işletme.
- KOSGEB'in güncel kayıtlarında yurt dışı pazar/e-ihracat desteği yok; şablondaki 'KOSGEB Yurt Dışı Pazar Destek Programı' kayıtlı güncel programlar arasında değil.
**4 Hedef ülke**
- #1 Almanya hedef ülke listesinde; E-İhracat Tanıtım Desteği — Perakende E-Ticaret Sitesi Statüsü oranı %50 → %70 (+20 puan, kayıttan).
**5 Mükerrerlik ve usulsüzlük**
- Mükerrerlik/usulsüzlük: 2 ret, 0 şartlı harcama.
**Hesap**
- E-İhracat Tanıtım Desteği (Perakende E-Ticaret Sitesi statüsü) (Almanya): esas 0,00 TL × %70 = 0,00 TL → RET.
**6 DYS eksikleri**
- İhracatçı birliği üyeliği
- Harcamadan önce ön onay
- DYS yetkilendirme (şirket yetkilisi adına DYS kullanıcı yetkisi)
- Güncel imza sirküleri
**8 Onarım rotaları**
- E-İhracat Tanıtım Desteği (Perakende E-Ticaret Sitesi statüsü) — Almanya: Statü almadan yalnız statüsüz kalemlerden (pazaryeri reklamı, sipariş karşılama, pazaryeri komisyonu) yararlanabilirsiniz; site reklamını pazaryeri içi reklama kaydırın ya da statü başvurusu yapın.
- Kapsam Dışı / İncelenmeli: Uluslararası kargo navlun: Bu gider için kayıtlı destek kalemi yok; başvuru paketinden çıkarın.
**7 Senaryo stres testi**
- Senaryo A (Yalnız Amazon/Etsy satışı yapan mikro şahıs işletmesi): 0 uygun, 0 şartlı, 2 ret; toplam talep 0,00 TL.
- Senaryo B (Kendi ikas sitesinden doğrudan yurt dışına (D2C) satan marka): 0 uygun, 0 şartlı, 2 ret; toplam talep 0,00 TL.
- Senaryo C (Pazaryerinde satan, hedef ülkede deposu olan karma işletme): 2 uygun, 0 şartlı, 1 ret; toplam talep 345.310,00 TL.
- Senaryo D (Harcaması tavanı aşan, kuru eksik ve süresi geçmiş kalemleri olan sınır durum): 0 uygun, 1 şartlı, 0 ret; toplam talep 3.698.274,00 TL.

#### BÖLÜM 2: RESMİ BAŞVURU GEREKÇE METNİ
Başvuru sahibi şirketin sunduğu harcamaların hiçbiri 5986 ve 5973 sayılı Kararlar kapsamında destek şartlarını sağlamamaktadır; başvuru yapılmamalı, düzeltme rotaları uygulanmalıdır.

#### BÖLÜM 3: RESMİ ENJEKSİYON JSON ŞEMASI
```json
{
  "basvuru_meta": {
    "mevzuat_dayanagi": "5986 sayılı Cumhurbaşkanı Kararı (e-ihracat destekleri) ve 5973 sayılı Cumhurbaşkanı Kararı (marka tescili, pazar araştırması, birim kira, tanıtım)",
    "basvuru_turu": "Ödeme başvurusu (kalem bazında; ön onay gerektiren kalemlerde ön onay sonrası)",
    "kobi_olcegi": "mikro işletme"
  },
  "tesvik_kalemleri": [
    {
      "kalem_adi": "E-İhracat Tanıtım Desteği (Perakende E-Ticaret Sitesi statüsü) — Almanya",
      "harcama_tutari_orijinal": 2000.0,
      "harcama_para_birimi": "EUR",
      "harcama_tutari_try": 0,
      "destek_orani_yuzde": 50,
      "hedef_ulke_ilave_puani": 20,
      "net_destek_orani": 70,
      "mevzuat_tavan_try": 123315792.0,
      "talep_edilen_hakedis_try": 0.0,
      "onay_durumu": "RET",
      "not": "#1: Kalem açıklamadan çıkarıldı: site_tanitim. #1: Kendi sitenin yurt dışı tanıtımı statü ister (kayıt: \"Destek yalnız statü sahiplerine açıktır\"). Statüsüz şirketin yararlanabildiği kalemler: dijital pazaryeri reklamı, sipariş karşılama, pazaryeri komisyonu, (önceki yıl 1 milyon USD üzeri ihracatla) çevrim içi mağaza."
    },
    {
      "kalem_adi": "Kapsam Dışı / İncelenmeli: Uluslararası kargo navlun",
      "harcama_tutari_orijinal": 45000.0,
      "harcama_para_birimi": "TRY",
      "harcama_tutari_try": 45000.0,
      "destek_orani_yuzde": 0,
      "hedef_ulke_ilave_puani": 0,
      "net_destek_orani": 0,
      "mevzuat_tavan_try": 0.0,
      "talep_edilen_hakedis_try": 0.0,
      "onay_durumu": "RET",
      "not": "Kapsam Dışı / İncelenmeli: bu gider kayıtlı e-ihracat ya da 5973 kalemleriyle eşleşmedi (ör. kargo/navlun için kayıtlı bir destek kalemi yok)."
    }
  ],
  "toplam_talep_try": 0.0,
  "eksik_ve_tamamlanacak_evraklar": [
    "İhracatçı birliği üyeliği",
    "Harcamadan önce ön onay",
    "DYS yetkilendirme (şirket yetkilisi adına DYS kullanıcı yetkisi)",
    "Güncel imza sirküleri"
  ]
}
```


=============== SENARYO C: Pazaryerinde satan, hedef ülkede deposu olan karma işletme (sentetik girdi) ===============

#### BÖLÜM 1: AJAN TARTIŞMASI VE DÜZELTME RAPORU — Senaryo C
**1 Ayrıştırma**
- 4 harcama ayrıştırıldı; toplam KDV hariç 939.900,00 TL.
**2 Mevzuat eşleştirme**
- Kalem eşleştirmesi: #1 Dijital Pazaryeri Tanıtım (Reklam) Desteği → UYGUN; #2 Sipariş Karşılama (Fulfillment) Hizmeti Desteği → UYGUN; #3 Yurt Dışı Birim Kira Desteği → RET; #4 Dijital Pazaryeri Tanıtım (Reklam) Desteği → UYGUN.
**3 KOBİ ve KOSGEB**
- KOBİ ölçeği: küçük işletme.
- KOSGEB'in güncel kayıtlarında yurt dışı pazar/e-ihracat desteği yok; şablondaki 'KOSGEB Yurt Dışı Pazar Destek Programı' kayıtlı güncel programlar arasında değil.
**4 Hedef ülke**
- #1 Almanya hedef ülke listesinde; Dijital Pazaryeri Tanıtım oranı %50 → %70 (+20 puan, kayıttan).
- #2 Almanya hedef ülke listesinde; Sipariş Karşılama oranı %50 → %70 (+20 puan, kayıttan).
- #3 Almanya hedef ülke listesinde, ama bu kalem için kayıtta hedef ülke oranı yazılı değil; ilave uygulanmadı.
- #4 Almanya hedef ülke listesinde; Dijital Pazaryeri Tanıtım oranı %50 → %70 (+20 puan, kayıttan).
**5 Mükerrerlik ve usulsüzlük**
- Mükerrerlik/usulsüzlük: 2 ret, 0 şartlı harcama.
**Hesap**
- Dijital Pazaryeri Tanıtım (Reklam) Desteği (Almanya): esas 180.000,00 TL × %70 = 126.000,00 TL → UYGUN.
- Sipariş Karşılama (Fulfillment) Hizmeti Desteği (Almanya): esas 313.300,00 TL × %70 = 219.310,00 TL → UYGUN.
- Yurt Dışı Birim Kira Desteği: esas 0,00 TL × %50 = 0,00 TL → RET.
**6 DYS eksikleri**
- Eksik yok.
**8 Onarım rotaları**
- Dijital Pazaryeri Tanıtım (Reklam) Desteği — Almanya: Mükerrer satırı dökümden çıkarın.
- Dijital Pazaryeri Tanıtım (Reklam) Desteği — Almanya: Reklam bütçesini reklamdan dönen satışın %20'si içinde planlayın (SRMO ≤ %20, RDK ≥ 5).
**7 Senaryo stres testi**
- Senaryo A (Yalnız Amazon/Etsy satışı yapan mikro şahıs işletmesi): 0 uygun, 0 şartlı, 2 ret; toplam talep 0,00 TL.
- Senaryo B (Kendi ikas sitesinden doğrudan yurt dışına (D2C) satan marka): 0 uygun, 0 şartlı, 2 ret; toplam talep 0,00 TL.
- Senaryo C (Pazaryerinde satan, hedef ülkede deposu olan karma işletme): 2 uygun, 0 şartlı, 1 ret; toplam talep 345.310,00 TL.
- Senaryo D (Harcaması tavanı aşan, kuru eksik ve süresi geçmiş kalemleri olan sınır durum): 0 uygun, 1 şartlı, 0 ret; toplam talep 3.698.274,00 TL.

#### BÖLÜM 2: RESMİ BAŞVURU GEREKÇE METNİ
Şirket-A1706D (küçük işletme ölçekli işletme), yurt dışı pazarlardaki e-ihracat faaliyetleri kapsamında gerçekleştirdiği giderler için 5986 sayılı Cumhurbaşkanı Kararı ve uygulama Genelgesi ile, ilgili olduğu ölçüde 5973 sayılı Cumhurbaşkanı Kararı hükümleri çerçevesinde destek talep etmektedir. Talep edilen kalemler: Dijital Pazaryeri Tanıtım (Reklam) Desteği — Almanya, Sipariş Karşılama (Fulfillment) Hizmeti Desteği — Almanya (ilgili maddeler: m.4, m.6). Destek oranları Karar'da öngörülen temel oran üzerinden, hedef ülke listesinde yer alan ülkelere yönelik giderlerde Karar'daki artırımlı oran uygulanarak, 2026 yılı üst limitleri aşılmayacak şekilde hesaplanmıştır.

Toplam talep tutarı 345.310,00 TL'dir. Giderler şirket adına düzenlenmiş fatura ve banka dekontu/kredi kartı ekstresi ile tevsik edilmekte olup aynı giderler için başka bir mevzuat veya program kapsamında destek talep edilmediği beyan edilir. Şartlı olarak işaretlenen kalemlere ilişkin eksik belgeler başvuru ekinde tamamlanacaktır.

#### BÖLÜM 3: RESMİ ENJEKSİYON JSON ŞEMASI
```json
{
  "basvuru_meta": {
    "mevzuat_dayanagi": "5986 sayılı Cumhurbaşkanı Kararı (e-ihracat destekleri) ve 5973 sayılı Cumhurbaşkanı Kararı (marka tescili, pazar araştırması, birim kira, tanıtım)",
    "basvuru_turu": "Ödeme başvurusu (kalem bazında; ön onay gerektiren kalemlerde ön onay sonrası)",
    "kobi_olcegi": "küçük işletme"
  },
  "tesvik_kalemleri": [
    {
      "kalem_adi": "Dijital Pazaryeri Tanıtım (Reklam) Desteği — Almanya",
      "harcama_tutari_orijinal": 10000.0,
      "harcama_para_birimi": "EUR",
      "harcama_tutari_try": 180000.0,
      "destek_orani_yuzde": 50,
      "hedef_ulke_ilave_puani": 20,
      "net_destek_orani": 70,
      "mevzuat_tavan_try": 36993646.0,
      "talep_edilen_hakedis_try": 126000.0,
      "onay_durumu": "UYGUN",
      "not": "SRMO sınırı: esas gider reklamdan dönen satışın %20'si ile sınırlandı (241.000,00 → 180.000,00 TL). #1: Kalem açıklamadan çıkarıldı: pazaryeri_reklam. #4: Kalem açıklamadan çıkarıldı: pazaryeri_reklam. #4: Mükerrer kayıt: #1 ile aynı tutar, tarih ve açıklama."
    },
    {
      "kalem_adi": "Sipariş Karşılama (Fulfillment) Hizmeti Desteği — Almanya",
      "harcama_tutari_orijinal": 6500.0,
      "harcama_para_birimi": "EUR",
      "harcama_tutari_try": 313300.0,
      "destek_orani_yuzde": 50,
      "hedef_ulke_ilave_puani": 20,
      "net_destek_orani": 70,
      "mevzuat_tavan_try": 36993646.0,
      "talep_edilen_hakedis_try": 219310.0,
      "onay_durumu": "UYGUN",
      "not": "#2: Kalem açıklamadan çıkarıldı: siparis_karsilama."
    },
    {
      "kalem_adi": "Yurt Dışı Birim Kira Desteği",
      "harcama_tutari_orijinal": 3000.0,
      "harcama_para_birimi": "EUR",
      "harcama_tutari_try": 0,
      "destek_orani_yuzde": 50,
      "hedef_ulke_ilave_puani": 0,
      "net_destek_orani": 50,
      "mevzuat_tavan_try": 9862972.0,
      "talep_edilen_hakedis_try": 0.0,
      "onay_durumu": "RET",
      "not": "#3: Kalem açıklamadan çıkarıldı: yurt_disi_depo. #3: E-ticaret deposu kirası 5986 statüsü (perakende site, pazaryeri ya da konsorsiyum) ister (kayıt 190, 5973 m.11/5-A)."
    }
  ],
  "toplam_talep_try": 345310.0,
  "eksik_ve_tamamlanacak_evraklar": []
}
```


=============== SENARYO D: Harcaması tavanı aşan, kuru eksik ve süresi geçmiş kalemleri olan sınır durum (sentetik girdi) ===============

#### BÖLÜM 1: AJAN TARTIŞMASI VE DÜZELTME RAPORU — Senaryo D
**1 Ayrıştırma**
- 3 harcama ayrıştırıldı; toplam KDV hariç 8.350.000,00 TL.
**2 Mevzuat eşleştirme**
- Kalem eşleştirmesi: #1 Yurt Dışı Pazaryeri Komisyon Gideri Desteği → UYGUN; #2 Yurt Dışı Pazaryeri Komisyon Gideri Desteği → SARTLI; #3 Yurt Dışı Pazaryeri Komisyon Gideri Desteği → RET.
**3 KOBİ ve KOSGEB**
- KOBİ ölçeği: orta büyüklükte işletme.
- KOSGEB'in güncel kayıtlarında yurt dışı pazar/e-ihracat desteği yok; şablondaki 'KOSGEB Yurt Dışı Pazar Destek Programı' kayıtlı güncel programlar arasında değil.
**4 Hedef ülke**
- #1 ABD hedef ülke listesinde, ama bu kalem için kayıtta hedef ülke oranı yazılı değil; ilave uygulanmadı.
- #2 Almanya hedef ülke listesinde, ama bu kalem için kayıtta hedef ülke oranı yazılı değil; ilave uygulanmadı.
- #3 ABD hedef ülke listesinde, ama bu kalem için kayıtta hedef ülke oranı yazılı değil; ilave uygulanmadı.
**5 Mükerrerlik ve usulsüzlük**
- Mükerrerlik/usulsüzlük: 1 ret, 1 şartlı harcama.
**Hesap**
- Yurt Dışı Pazaryeri Komisyon Gideri Desteği: esas 8.300.000,00 TL × %50 = 3.698.274,00 TL → SARTLI.
**6 DYS eksikleri**
- DYS yetkilendirme (şirket yetkilisi adına DYS kullanıcı yetkisi)
- Güncel imza sirküleri
**8 Onarım rotaları**
- Yurt Dışı Pazaryeri Komisyon Gideri Desteği: Süresi geçen ödeme belgesi kurtarılamaz; sonraki ödemeler için çeyrek dönem takvimine göre 6 ay içinde başvurun.
- Yurt Dışı Pazaryeri Komisyon Gideri Desteği: Gideri yalnız bir programa sunun: diğer başvuruyu geri çekin ya da bu kalemden vazgeçin.
- Yurt Dışı Pazaryeri Komisyon Gideri Desteği: Ödeme tarihindeki TCMB döviz satış kurunu girin; TL karşılığı yeniden hesaplanır.
- Yurt Dışı Pazaryeri Komisyon Gideri Desteği: Tavanı aşan tutar desteklenmez; harcamayı sonraki yıla ya da başka uygun kaleme yayın.
**7 Senaryo stres testi**
- Senaryo A (Yalnız Amazon/Etsy satışı yapan mikro şahıs işletmesi): 0 uygun, 0 şartlı, 2 ret; toplam talep 0,00 TL.
- Senaryo B (Kendi ikas sitesinden doğrudan yurt dışına (D2C) satan marka): 0 uygun, 0 şartlı, 2 ret; toplam talep 0,00 TL.
- Senaryo C (Pazaryerinde satan, hedef ülkede deposu olan karma işletme): 2 uygun, 0 şartlı, 1 ret; toplam talep 345.310,00 TL.
- Senaryo D (Harcaması tavanı aşan, kuru eksik ve süresi geçmiş kalemleri olan sınır durum): 0 uygun, 1 şartlı, 0 ret; toplam talep 3.698.274,00 TL.

#### BÖLÜM 2: RESMİ BAŞVURU GEREKÇE METNİ
Şirket-137A46 (orta büyüklükte işletme ölçekli işletme), yurt dışı pazarlardaki e-ihracat faaliyetleri kapsamında gerçekleştirdiği giderler için 5986 sayılı Cumhurbaşkanı Kararı ve uygulama Genelgesi ile, ilgili olduğu ölçüde 5973 sayılı Cumhurbaşkanı Kararı hükümleri çerçevesinde destek talep etmektedir. Talep edilen kalemler: Yurt Dışı Pazaryeri Komisyon Gideri Desteği (ilgili maddeler: m.9). Destek oranları Karar'da öngörülen temel oran üzerinden, hedef ülke listesinde yer alan ülkelere yönelik giderlerde Karar'daki artırımlı oran uygulanarak, 2026 yılı üst limitleri aşılmayacak şekilde hesaplanmıştır.

Toplam talep tutarı 3.698.274,00 TL'dir. Giderler şirket adına düzenlenmiş fatura ve banka dekontu/kredi kartı ekstresi ile tevsik edilmekte olup aynı giderler için başka bir mevzuat veya program kapsamında destek talep edilmediği beyan edilir. Şartlı olarak işaretlenen kalemlere ilişkin eksik belgeler başvuru ekinde tamamlanacaktır.

#### BÖLÜM 3: RESMİ ENJEKSİYON JSON ŞEMASI
```json
{
  "basvuru_meta": {
    "mevzuat_dayanagi": "5986 sayılı Cumhurbaşkanı Kararı (e-ihracat destekleri) ve 5973 sayılı Cumhurbaşkanı Kararı (marka tescili, pazar araştırması, birim kira, tanıtım)",
    "basvuru_turu": "Ödeme başvurusu (kalem bazında; ön onay gerektiren kalemlerde ön onay sonrası)",
    "kobi_olcegi": "orta büyüklükte işletme"
  },
  "tesvik_kalemleri": [
    {
      "kalem_adi": "Yurt Dışı Pazaryeri Komisyon Gideri Desteği",
      "harcama_tutari_orijinal": 8350000.0,
      "harcama_para_birimi": "TRY",
      "harcama_tutari_try": 8300000.0,
      "destek_orani_yuzde": 50,
      "hedef_ulke_ilave_puani": 0,
      "net_destek_orani": 50,
      "mevzuat_tavan_try": 3698274.0,
      "talep_edilen_hakedis_try": 3698274.0,
      "onay_durumu": "SARTLI",
      "not": "Çok para birimli kalem: orijinal tutar alanı TL karşılığıdır (satır ayrıntısı notta). Tavan aşıldı: hak ediş 2026 yıllık üst limitte (3.698.274,00 TL) sabitlendi. #1: Kalem açıklamadan çıkarıldı: pazaryeri_komisyon. #2: Kalem açıklamadan çıkarıldı: pazaryeri_komisyon. #2: EUR tutar için ödeme tarihindeki TCMB döviz satış kuru girilmedi; TL karşılığı hesaplanamadı. #3: Kalem açıklamadan çıkarıldı: pazaryeri_komisyon. #3: Ödeme belgesi tarihinden itibaren 6 aylık başvuru süresi geçmiş (10.02.2026). #3: Aynı gider KOSGEB kapsamında desteklenmiş/başvurulmuş: kayıt şartı \"Aynı gider için bu Karar dışında başka bir mevzuat/program kapsamında destek almamış olmalısınız\"."
    }
  ],
  "toplam_talep_try": 3698274.0,
  "eksik_ve_tamamlanacak_evraklar": [
    "DYS yetkilendirme (şirket yetkilisi adına DYS kullanıcı yetkisi)",
    "Güncel imza sirküleri"
  ]
}
```
