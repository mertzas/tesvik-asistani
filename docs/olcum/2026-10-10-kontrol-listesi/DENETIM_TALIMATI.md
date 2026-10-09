# Kontrol listesi denetimi — talimat (2026-10-10)

Girdi (salt okunur):
- `mevcut.json`: uygulamanın her program için kullanıcıya gösterdiği kontrol listesi (`maddeler`: anahtar, tur = sart/belge/basvuru,
  kural = "işaretlenmez, uyarıdır"), `kaynak_url`, `basvuru_yeri`, `basvuru_suresi`, `cagrilar` (başvuru dönemleri).
- `../2026-10-09-uygunluk/kaynak/<id>.txt`: programın resmî sayfası (2026-10-09 indirildi) + kayıtlı alanlar. Başlıklar:
  "## KAYITLI ALANLAR", "## KAYITLI DETAY", "## CANLI SAYFA". **Hakikat yalnız "## CANLI SAYFA" bölümüdür**; kayıtlı alanlar
  denetlenen şeyin kendisidir, kanıt sayılmaz.
- `../2026-10-09-uygunluk/kriter/<id>.json`: canlı metinden çıkarılmış, alıntısı doğrulanmış başvuru şartları.

Her program için `denetim/<id>.json` yaz (geçerli JSON):

```json
{
  "tesvik_id": 8,
  "maddeler": [
    {"anahtar": "s1", "hukum": "dogru", "dogru_tur": "sart", "alinti": "canlı sayfadan birebir parça", "not": "",
     "onerilen_metin": null}
  ],
  "eksik_maddeler": [
    {"tur": "sart", "metin": "kullanıcıya gösterilecek kısa madde", "alinti": "canlı sayfadan birebir parça"}
  ],
  "kaynak_url": {"hukum": "programa_ozel" , "not": ""},
  "cagri_tutarliligi": {"hukum": "tutarli", "not": ""}
}
```

## madde.hukum (her madde için tam bir tane)
- `dogru`: canlı sayfa maddeyi destekliyor. `alinti` zorunlu.
- `yanlis`: canlı sayfa maddeyle çelişiyor (oran, tarih, kapsam, kurum, belge adı farklı). `alinti` (çelişen yer) ve
  `onerilen_metin` zorunlu.
- `eskimis`: madde bir dönem için doğruydu ama canlı sayfa güncel başka bir şey söylüyor (tarih, dönem, limit). `alinti` +
  `onerilen_metin` zorunlu.
- `desteksiz`: canlı sayfada bulunamıyor (çelişmiyor ama kanıt yok). `alinti` boş.
- `belirsiz`: madde birden çok şeyi karıştırıyor, koşullu ("aranmayabilir", "gerekebilir") ya da kullanıcı neyi işaretleyeceğini
  anlayamaz. `onerilen_metin` zorunlu (tek, net, işaretlenebilir ifade; koşulluysa koşulu ayrı yaz).

## madde.dogru_tur (maddenin olması gereken türü)
- `sart`: başvuranın taşıması gereken nitelik (kim başvurabilir). Kullanıcı "sağlıyor muyum?" diye cevaplar.
- `belge`: hazırlanıp sunulacak belge/form. Kullanıcı "hazırladım" diye işaretler.
- `adim`: yapılacak işlem (kayıt olmak, sisteme girmek, ön onay almak, başvurmak). Kullanıcı "yaptım" diye işaretler.
- `kural`: işaretlenecek bir şey değil; bilinmesi gereken yasak/sınır (ör. "başvurudan önce yapılan harcama desteklenmez").
- `bilgi`: oran, limit, süre gibi açıklama; kontrol listesinde yeri yok.

## eksik_maddeler
`kriter/<id>.json` içinde `zorunlu: true` olup kontrol listesinde karşılığı olmayan şartlar ile canlı sayfadaki zorunlu
belge/adımlar. Kriter dosyasındaki "diger" şartlar da dahil. Abartma: en önemli en fazla 6 eksik.

## kaynak_url.hukum
`programa_ozel` (programın kendi sayfası/Karar metni) · `genel_sayfa` (kurumun liste/ana sayfası; program tek başına
bulunamıyor) · `yanlis_program` (başka programın sayfası) · `erisilemedi`.

## cagri_tutarliligi.hukum
`tutarli` · `celisik` (ör. dönem "kapandı" derken başvuru maddesi "başladı/açık" diyor; basvuru_suresi ile cagrilar farklı) ·
`cagri_yok` (dönemsel program ama çağrı kaydı yok) · `uygulanmaz` (sürekli açık program).

## Kurallar
- `alinti` canlı sayfadan birebir, kesintisiz (≤300 karakter); makine "## CANLI SAYFA" bölümünde arar.
- Genel bilgi, tahmin yok. Emin değilsen `desteksiz`.
- Web araması yapma, kod çalıştırma.
