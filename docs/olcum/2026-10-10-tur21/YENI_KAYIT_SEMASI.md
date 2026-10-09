# Yeni program kaydı şeması (tur21, 2026-10-10)

Her program için `kayit/<slug>.json` (slug: küçük harf, tire; ör. `tkdk-ipard3-101`, `ka-ankara-2026-mdp`). Veritabanına
yalnız **her rakamı, tarihi ve şartı resmî kaynaktan birebir alıntıyla** gelen kayıt girer. Alıntılar makinece
denetlenir: `kaynak_url` indirilir (HTML ya da PDF), alıntı metinde aranır; bulunamayan iddia kayıttan düşer.

```json
{
  "slug": "tkdk-ipard3-101",
  "kurum": "TKDK",
  "baslik": "IPARD III — Tarımsal İşletmelerin Fiziki Varlıklarına Yönelik Yatırımlar (Tedbir 101)",
  "ozet": "2-4 cümle; yalnız kaynakta yazanlar",
  "kaynak_url": "programa/çağrıya özel resmî sayfa ya da PDF (kurum ana sayfası değil)",
  "aktif_mi": true,
  "durum": {"metin": "neden açık/kapalı/belirsiz", "alinti": "kaynaktan birebir", "kaynak_url": "..."},
  "basvuru_bicimi": "proje",
  "bolge_kisitli": ["Afyonkarahisar", "..."],
  "sektorler": ["tarim"],
  "sirket_turleri": ["sahis", "limited", "anonim", "kooperatif"],
  "tesvil_tutari": "kısa metin; içindeki her rakam aşağıda alıntılı",
  "basvuru_yeri": "...",
  "basvuru_suresi": "...",
  "kontrol_listesi": [{"tur": "sart|belge|adim|kural|bilgi", "metin": "kullanıcıya gösterilecek kısa madde",
                       "alinti": "birebir", "kaynak_url": "..."}],
  "cagrilar": [{"ad": "...", "acilis": "YYYY-AA-GG", "kapanis": "YYYY-AA-GG", "on_kayit_son": null,
                "kaynak_url": "...", "alinti": "tarihlerin geçtiği birebir parça", "notlar": null}],
  "alintilar": [{"iddia": "hibe oranı %50-%70", "alinti": "birebir parça", "kaynak_url": "..."}]
}
```

Kurallar
- `basvuru_bicimi`: proje · kredi · faiz_destegi · kefalet · bildirim_prim · uretim_odeme · belge_etuys · gider_on_onay ·
  hisse_fon · gotuyu_hibe · diger.
- `sektorler` yalnız şu etiketlerden: genel, arge, ihracat, imalat, e-ticaret, tarim, hizmet.
- `sirket_turleri` yalnız: sahis, limited, anonim, kooperatif, yok (henüz işletme yok). Kaynak yazmıyorsa alanı koyma.
- `bolge_kisitli`: programın açık olduğu iller (il adları). Ülke geneliyse boş liste.
- `tesvil_tutari`, `ozet`, `kontrol_listesi` ve `cagrilar` içindeki her rakam/tarih/oran `alintilar` ya da kendi
  `alinti` alanında birebir geçmeli. Alıntı ≤ 300 karakter, kesintisiz; satır sonu yerine boşluk olabilir.
- Kaynak: yalnız kurumun kendi alan adı (tkdk.gov.tr, *.kalkinma ajansı alan adları, resmigazete.gov.tr,
  sanayi.gov.tr, yatirimadestek.gov.tr). Haber sitesi, danışmanlık firması, forum kaynak değildir.
- Çağrı tarihi bilinmiyorsa çağrı ekleme; tahmin yok. Kapanmış 2026 çağrıları da eklenebilir (durum doğru gösterilir).
- Emin olmadığın bilgiyi yazma; bulunamayan alanı boş bırak.
