# Şablon taslak (yapay zekâsız) ile yapay zekâ taslağı — karşılaştırma (2026-10-08)

Betik: `karsilastir.py` (ücretsiz, ağ yok). Şablon çıktıları `sablon_<n>.md`, ölçümler `sonuc.json`.

## Yöntem ve sınırlar
- **Vakalar:** önceki taslak ölçümünün 3 vakası (`docs/olcum/2026-10-08-taslak`): Bursa metal + KOSGEB Kapasite
  Geliştirme, İzmir tekstil + KOSGEB Küresel Rekabetçilik, Ankara girişim + TÜBİTAK 1812.
- **Yapay zekâ tarafı:** üretim istemiyle (`app.basvuru_taslagi.SISTEM` + birebir kullanıcı istemi) yazılmış
  `taslak_elle_<n>.md`. Canlı API çağrısı o gün "credit balance is too low" ile düştüğü için taslakları **oturum
  modeli** yazdı; üretimdeki `claude-sonnet-5` değil. Bu nedenle sonuç model kalitesinin kesin ölçüsü değildir.
- **Şablon tarafı:** bugünkü veritabanıyla `app.sablon_taslak.uret` (tur12-17 sonrası kayıtlar).
- **Ölçüt düzeltmesi:** ilk sürüm program olgularını şablonun kendi kalıbıyla ("Başvuru dönemi") ve bugünkü kayıtla
  arıyordu; yapay zekâ "başvuru dönemsel çağrı ile alınmaktadır" yazdığı için 1/3 alıyordu. Ölçüt her yolun **kendi**
  bağlamına ve ifade biçiminden bağımsız kalıba çevrildi; aşağıdaki tablo düzeltilmiş ölçüttür.

## Sonuç

| Vaka | Yol | Başlık sırası | [DOLDURUN] | Kelime | Uydurma rakam adayı | Profil olgusu | Program olgusu |
|---|---|---|---|---|---|---|---|
| 1 Kapasite Geliştirme | şablon | ✓ | 37 | 406 | — | 4/4 | 3/3 |
| 1 Kapasite Geliştirme | yapay zekâ | ✓ | 26 | 499 | — | 4/4 | 3/3 |
| 2 Küresel Rekabetçilik | şablon | ✓ | 38 | 462 | — | 4/4 | 3/3 |
| 2 Küresel Rekabetçilik | yapay zekâ | ✓ | 29 | 501 | — | 4/4 | 3/3 |
| 3 TÜBİTAK 1812 | şablon | ✓ | 35 | 360 | — | 3/4 | 2/3 |
| 3 TÜBİTAK 1812 | yapay zekâ | ✓ | 32 | 448 | — | 2/4 | 2/3 |

(Vaka 3'te profil cirosu 0 olduğu için "ciro" iki yolda da uygulanamaz; şablon çalışan sayısını, yapay zekâ yazmadı.)

- **Doğruluk:** iki yolda da bağlamda olmayan rakam yok; profil ve program olguları eşit ya da şablonda bir fazla.
- **Fark:** yapay zekâ metni %10-25 daha uzun, akıcı düzyazı ve %10-30 daha az [DOLDURUN]. Kullanıcının dolduracağı
  alan şablonda daha fazla.
- **Yapay zekânın asıl katkısı uzunluk değil, programa özgü yönlendirici sorulardı** ("darboğaz ve kapasite kullanım
  oranı", "karşılanamayan talep", makine tedariki → kurulum → ölçüm). Bu, şablona program türüne göre kural tabanlı
  rehber olarak eklendi (yatırım/kapasite, ihracat, Ar-Ge, istihdam, girişim, tarım). Ölçüm sırasında bulunan iki
  hata düzeltildi: sektör etiketi "arge" yüzünden Kapasite Geliştirme'ye Ar-Ge soruları geliyordu (tür artık önce
  başlıktan); "Yatırım Tabanlı Girişimcilik"e makine/kapasite soruları geliyordu (girişimde yatırım türü düşürülür).

## Karar
Şablon varsayılan kalır: aynı doğrulukta, ücretsiz, rıza gerektirmez, veri dışarı çıkmaz. Yapay zekâ "metni
yapay zekâyla yaz" seçeneği olarak değerini akıcı gerekçe metninde korur. Üretim modeliyle kesin karşılaştırma için
API bakiyesi yüklenince `docs/olcum/2026-10-08-taslak/taslak_olcum.py --canli` (3 çağrı, önceki tahmin ≤ ~0,15 USD)
çalıştırılıp bu betik yeniden koşturulabilir.
