# Uygunluk kriteri şeması (v1, 2026-10-09)

Her program için `kriter/<id>.json`. Amaç: "bu profil bu programa başvurabilir mi" sorusunu makinenin belirlenimci
olarak cevaplayabilmesi. Yalnız kaynak metinde (`kaynak/<id>.txt`) yazanı kodla; yorum, genel bilgi, tahmin yok.

```json
{
  "tesvik_id": 8,
  "basvuru_bicimi": "proje",
  "bilesenler": ["İş Kurma Desteği", "İş Geliştirme Desteği"],
  "kriterler": [
    {"alan": "olcek", "kural": {"in": ["mikro", "kucuk", "orta"]}, "zorunlu": true, "bilesen": null,
     "metin": "KOBİ olmak", "alinti": "KOBİ statüsündeki işletmeler"}
  ],
  "belirsizlikler": ["metinde ... belirtilmemiş"]
}
```

## basvuru_bicimi (tek değer)
`proje` (proje önerisi/iş planı değerlendirilir) · `kredi` (kredi/finansman kullandırımı) · `faiz_destegi` (kredi faizine
destek) · `kefalet` (KGF kefaleti, banka kredisi) · `bildirim_prim` (SGK bildirimiyle prim teşviki) · `uretim_odeme`
(dekar/hayvan/ürün başı ödeme) · `belge_etuys` (yatırım teşvik belgesi) · `gider_on_onay` (gider kalemi bazlı ön onay ve
geri ödeme) · `hisse_fon` (hisse karşılığı yatırım) · `gotuyu_hibe` (sabit tutarlı hibe) · `diger`.

## kriter.alan ve kural biçimi (yalnız bunlar)
| alan | kural | anlamı |
|---|---|---|
| `sirket_turu` | `{"in": [...]}` | `sahis`, `limited`, `anonim`, `kooperatif`, `yok` (henüz işletme yok), `diger_tuzel` |
| `olcek` | `{"in": [...]}` | KOBİ sınıfı: `mikro`, `kucuk`, `orta`, `buyuk` |
| `calisan_sayisi` | `{"min": n}` / `{"max": n}` | |
| `yillik_ciro_tl` | `{"min": n}` / `{"max": n}` | net satış hasılatı |
| `isletme_yasi_yil` | `{"min": n}` / `{"max": n}` | kuruluştan başvuruya geçen yıl |
| `nace` | `{"in_prefix": [...]}` / `{"not_in_prefix": [...]}` | NACE kod önekleri ("62", "13.9", "Kısım C" için "C") |
| `faaliyet` | `{"in": [...]}` | NACE listesi yoksa kaba alan: `imalat`, `yazilim_bilisim`, `tarim`, `hayvancilik`, `turizm`, `ticaret`, `hizmet`, `insaat`, `enerji`, `saglik`, `egitim`, `lojistik`, `savunma` |
| `il` | `{"in": [...]}` / `{"not_in": [...]}` | il adları |
| `bolge_9903` | `{"in": [1..6]}` | |
| `hedef_grup` | `{"in": [...]}` | başvuranın (gerçek kişi/kurucu/çoğunluk ortak) niteliği: `kadin`, `genc`, `engelli`, `gazi_sehit_yakini`, `ogrenci`, `yeni_mezun`, `ciftci`, `kooperatif_ortagi`, `ihracatci` |
| `kurucu_yasi` | `{"min": n}` / `{"max": n}` | |
| `belge` | `{"gerekli": "..."}` | `uygulamali_girisimcilik_sertifikasi`, `teknogirisim_rozeti`, `ihracatci_birligi_uyeligi`, `cks_kaydi`, `kosgeb_kaydi`, `dys_kaydi`, `iskur_kaydi`, `mesleki_yeterlilik_belgesi`, `organik_sertifika`, `marka_tescili`, `ar_ge_merkezi_veya_teknopark`, `teminat_mektubu`, `dijital_olgunluk_raporu`, `e_imza`, `tobb_uyeligi`, `banka_kredisi` |
| `vergi_sgk_borcu_yok` | `{"esit": true}` | vadesi geçmiş vergi/SGK borcu olmamak |
| `onceki_destek_yok` | `{"esit": true}` | metinde yazan önceki destek yasağı (`metin`e hangisi olduğunu yaz) |
| `baska_sirkette_ortak_degil` | `{"esit": true}` | |
| `yatirim_tutari_tl` | `{"min": n}` / `{"max": n}` | |
| `onceki_yil_ihracat_usd` | `{"min": n}` | |
| `ilave_istihdam` | `{"esit": true}` | işe alınan kişi ilave olmalı |
| `calisan_niteligi` | `{"in": [...]}` | istihdam teşviklerinde işe alınan kişi: `kadin`, `genc_18_29`, `mesleki_belgeli`, `engelli`, `issiz_iskur` |
| `arazi_dekar` | `{"min": n}` | |
| `urun` | `{"in": [...]}` | tarımsal ürün/hayvan türü |
| `trl` | `{"min": n}` / `{"max": n}` | teknoloji hazırlık seviyesi |
| `diger` | `{"aciklama": "..."}` | yukarıdakilere sığmayan şart; makine değerlendirmez, "elle" sayılır |

- `zorunlu: true` = sağlanmazsa başvurulamaz/yararlanılamaz. `false` = ek destek, puan ya da oran artışı koşulu.
- `bilesen`: şart programın yalnız bir alt desteğine aitse o bileşenin adı (bilesenler listesinden), değilse null.
- `alinti`: kaynak metinden **birebir**, kesintisiz parça (en fazla 300 karakter). Makine kaynakta arar; bulunmayan kriter geçersiz.
- Birden fazla seçenekten biri yeterliyse tek kriter `in` listesiyle yazılır; hepsi gerekiyorsa ayrı kriterler.
- Kaynakta şart yoksa kriter ekleme. Programın kimlere açık olduğu kaynakta hiç yazmıyorsa `belirsizlikler`e yaz.
