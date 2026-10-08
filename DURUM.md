# DURUM — Teşvik Asistanı denetim çalışması

Son güncelleme: 2026-10-08 (İKAS App Store hazırlığı + yol haritası). Oturuma bunu okuyarak başla.

## Yapılanlar
- **Denetim 1** (6 aşama, tamamlandı): eşleştirme (ince_skor, uygunluk engelleri), RAG (akışlı yanıt `/api/sor/akis`,
  panelde yanıt alanı, 9903 destek unsurları), güvenlik/KVKK (CORS, SECRET_KEY nöbeti, hız sınırı, parola politikası,
  hesap silme), UI (ayarlar, geçmiş, FREE önizleme, mobil), operasyon (Redis sayaç, zamanlayıcı kilidi, nginx/compose/CI).
  Test 659 → 750. CI yeşil (`.github/workflows/tests.yml`).
- **Denetim 2 / Aşama A** (tamamlandı): 110 kayıt Chrome ile canlı kurum sayfasıyla karşılaştırıldı
  (`docs/olcum/2026-10-07-denetim2/A_fark_tablosu.json`, 117 satır). Düzeltmeler uygulandı:
  `scripts/fix_veri_2026_10_07_denetim2.py` (57 kayıt) + `_tur2.py` (25 kayıt); SGK/İŞKUR 4447 istihdam teşvikleri
  (`scripts/seed_istihdam_tesvikleri_4447.py`, 2 kayıt). DB: `data/tesvikler.db` 186 kayıt (aktif 99 / kararsız 12 /
  kapalı 75). Yedekler: `docs/olcum/2026-10-07-denetim2/*.db.bak` (gitignore'da).
- **Denetim 2 / Aşama B** (tamamlandı): 3 persona (çiftçi, imalatçı KOBİ, şirketsiz girişimci) kayıt→profil→eşleşme→
  bütçe→3 soru→geçmiş→rıza→silme (`B_yolculuk.json`). Düzeltmeler: SGK işveren teşviki şirketsize gelmez; retrieve'de
  hedef-tabanlı sektör; tarım sorusunda alt kategori bonusu; autocomplete; index.html geçiş düğmeleri. Test 758.

## Kararlar ve gerekçeleri
- Gerçek Claude çağrısı yalnızca onayla; Aşama B rıza kapalı yapıldı (0 çağrı). Denetim 1 Aşama 3 ölçümü ≈1,1 USD.
- Kayıt 78 "Tarımsal Makineleştirme" → KKYP olarak yeniden yazıldı (bireysel traktör hibesi diye yanlış vaat ediyordu).
- Hayvancılık birim tutarları (Karar 8760) taranmış PDF'te; OCR olmadan teyit edilemedi → kayıt bunu açıkça söylüyor.
- Girişim modu: şirket yok | TRL ≤ 6 | şirket ≤ 3 yaş | soru dili. JWT 7 gün.
- Kökteki `tesvik.db` 0 baytlık artık dosya; gerçek DB `data/tesvikler.db`. (2026-10-08: göreli `DATABASE_URL` artık proje köküne göre çözülür, kalıntı yeniden oluşmaz; bkz. `tests/test_database_url.py`.)

- **Denetim 2 / Aşama C** (tamamlandı, kısıtla): rapor `docs/olcum/2026-10-07-denetim2/C_RAPOR.md`. Soru 1–3 gerçek
  claude-sonnet-5 (≈0,3 USD); API bakiyesi bitince 4–12'yi oturum modeli birebir prompt+bağlamla elle yanıtladı
  (`C_prompt_NN.md` → `C_ham_NN.md`, `C_olcum.py dump|skor N`). **Gerçek hata bulundu/düzeltildi:** `_tesvik_detay_metni`
  `tesvil_tutari` alanını bağlama yazmıyordu (A'da düzeltilen 80+ kaydın limit/vade/oranı modele görünmüyordu).
  Sonuç: uydurma 0, beklenen değer 41/41 (düzeltme öncesi 4–12'de 25/38). Test 761 geçti.
  Kesme işareti düzeltmesiyle Eurostars kaydı bağlama giriyor.

## Sıradaki adım
- **Aşama C üretim modeliyle tekrar**: bakiye yüklenince `C_olcum.py N` (N=4..12, ~0,9 USD). Kayıt temizliği UYGULANDI
  (tur3, 5 kayıt: 2, 7, 48, 163, 174; yedek *.db.bak, git dışı); açık: 163 güncel limit, 48 son başvuru tarihi.
- **Denetim 2 / Aşama D** (tamamlandı, kısıtlarla): rapor `docs/olcum/2026-10-07-denetim2/D_RAPOR.md`. 3 hata bulundu/düzeltildi (akış kopması uyarısız, askıda Claude 271 sn, kilitli DB'de /health yanlış 200). Test 766 geçti. Yapılamayanlar: gerçek modelle ilk parça süresi (kredi/onay yok), Linux'ta --workers 2 flock kanıtı (Docker/WSL yok). Dev sunucusu (:8000) yeniden başlatılmalı.
- **Denetim 2 / Aşama E** (kod tamam, 2 bilgi + 1 göç bekliyor): rapor `docs/olcum/2026-10-07-denetim2/E_RAPOR.md`. CSP eklendi (unsafe-inline kaldı), çilek paneli kalıcı XSS kapandı, İKAS webhook mağaza belirteciyle korundu (İKAS imza tanımlamıyor), parola sıfırlama + e-posta doğrulama eklendi. Test 791 geçti. BEKLEYEN: (1) KVKK DOLDURULACAK alanları kullanıcıdan, (2) SMTP sağlayıcısı kullanıcıdan (şifre .env'ye), (3) `alembic upgrade head` veri/dev DB'ye uygulanmadı (yeni kodla açılmadan önce şart).
- **Denetim 2 / Aşama F** (tamamlandı): `docs/olcum/2026-10-07-denetim2/F_RAPOR.md`. KARAR: ödeme alan genel yayın için HAYIR; engeller KVKK alanları, SMTP, Stripe test modu, Linux dağıtım denemesi, üretim modeliyle ölçüm, veri boşlukları. Göç `g4b6c8d0e456` dev DB'ye UYGULANDI (yedek `tesvikler_oncesi_gocE.db.bak`). Dev sunucusu :8000 eski kodla çalışıyor, yeni kod için yeniden başlatılmalı. 14 yerel commit push edilmedi.
- **Denetim 2 / Aşama G** (tamamlandı): sentetik profil denemesinden çıkan eşleştirme/arama/bütçe düzeltmeleri, rapor `docs/olcum/2026-10-07-denetim2/G_RAPOR.md`. Test 810. Tur4–6 veri düzeltmeleri UYGULANDI (8, 81, 7, 142, 3, 125, 9, 107 kapsam/ölçek; 5 YÖNDE eski şart metni; yedekler *.db.bak).
- **Denetim 2 / Aşama H** (tamamlandı): 49 kayıt (12 kararsız + 37 karşılaştırılmamış aktif) canlı sayfayla tarandı,
  rapor `docs/olcum/2026-10-07-denetim2/H_RAPOR.md`. Tur7 UYGULANDI (37 kayıt, varsayılan: yıllık tek pencereli
  kapanan KKYP/TSS/1711/SAYEM kapalı; yedek `tesvikler_oncesi_tur7.db.bak`). DB: aktif 100 / kapalı 84 / kararsız 2.
  Kazıyıcı tohumu (`app/scrapers/tarim_bakanligi.py`) 4 tarım kaydında DB ile eşitlendi; `tests/test_tarim_tohum_tutarlari.py`
  tohumu `app/tarim_destek_2026.py` sabitlerine bağlar. Test 835. 2027'de KKYP/TSS çağrısı açılınca 78/80 yeniden aktif edilmeli.
- **Güvenlik kod listesi 1–3** (2026-10-08, tamamlandı, 3 commit):
  1. JWT iptali: `users.oturum_surumu` (göç `h5c7e9f1a567`, dev DB'ye UYGULANDI, yedek `tesvikler_oncesi_gocH.db.bak`),
     belirteçte "sv"; parola sıfırlama ve `POST /api/auth/tum-oturumlari-kapat` eski belirteçleri geçersiz kılar.
     Panelde 401 → `/?oturum=bitti`; hesap silmede yanlış parola artık 403.
  2. Doğrulama zorunlu kayıt `KAYIT_EPOSTA_DOGRULAMA_ZORUNLU` (varsayılan KAPALI): açıkken kayıt yanıtı hesap var/yok
     aynı (202), doğrulanmamış hesap giremez, etkinleştirme bağlantı + parola ister (önceden ele geçirmeye karşı).
     Girişte kayıtsız adreste de bcrypt (zamanlama). AÇMADAN ÖNCE: SMTP gerçekten posta gönderebilmeli (aşağıya bak).
  3. CSP `script-src 'self'`: 5 sayfanın betiği `app/static/js/`, 28 olay özniteliği `data-tikla/degisim/gonder` +
     EYLEMLER listesi; çilek Tailwind'i `app/static/css/cilek.css` (yeniden derleme komutu `tools/tailwind/tailwind.config.js`).
     style-src 'unsafe-inline' bilerek kaldı. Testler `tests/test_csp.py`. Test 866.
- **Hemen yapılabilecekler listesi** (2026-10-08, tamamlandı, 9 commit): testler gerçek SMTP'ye bağlanamaz
  (conftest koruması); günlük cp1254 emoji hatası; kilitli DB → JSON 503 + Retry-After, beklenmeyen hata → JSON 500 +
  hata kimliği; girdi uzunluk sınırları (çilek, giriş/silme parolası; geçersiz ortam tipi 500 → 422); Türkçe 422
  (`app/dogrulama_mesajlari.py`, gönderilen değer yansıtılmaz) + statik dosyalarda `Cache-Control: no-cache`;
  lifespan (on_event kalktı) + isteğe bağlı Sentry (`SENTRY_DSN`, yerel değişken/gövde gönderilmez); kart ve 9903/
  veri tazeliği metinleri Türkçe karakterli; profil düğmeleri stilli + "Başlarken" rehberi; tur8 başlık göçü
  (160/161 "(Mazot-Gübre)" → temel destek; yedek `tesvikler_oncesi_tur8.db.bak`). Test 892+.
- **Aşama I — başvuru belgeleri** (2026-10-08, UYGULANDI): evrak hazırlama desteğinin ön koşulu. En sık eşleşen 34
  programın resmî sayfaları tarandı, rapor `docs/olcum/2026-10-07-denetim2/I_RAPOR.md`. Tur 9: 32 kayıt, yalnız boş
  alan (yedek `tesvikler_oncesi_tur9.db.bak`). Aktif kayıtlarda belge 17→49, başvuru yeri 27→49, şart 75→78.
- **Başvuru kontrol listesi** (2026-10-08, tamamlandı): `app/basvuru_listesi.py` (`--self-test` 6/6), tablo
  `basvuru_takipleri` (göç `i6d8f0a2b678`; dev DB'de sunucu create_all ile önce oluşturmuştu, şema aynı olduğu
  doğrulanıp `alembic stamp head`; yedek `tesvikler_oncesi_gocI.db.bak`). Maddeler kaydın şart/belge/başvuru yeri
  alanlarından; işaretler sunucuda; eşleşme kartında "Kontrol listesi", menüde "Başvurularım"; yazdır/PDF tarayıcıda.
  Hesap silmede silinir, KVKK metnine eklendi.
- **Başvuru ön taslağı** (2026-10-08, kod tamam, CANLI ÇAĞRI YAPILMADI): `app/basvuru_taslagi.py` (`--self-test` 6/6),
  `POST /api/basvuru-listesi/{id}/taslak`; koşullar ücretli çağrıdan önce: PRO+, açık rıza, profil, API anahtarı,
  kuruluş başına günde 5. Belgeler bölümü modelden değil kontrol listesinden; bilinmeyen yerler [DOLDURUN].
  Göç `j7e9a1b3c789` dev DB'ye uygulandı (yedek `tesvikler_oncesi_gocJ.db.bak`). Testler modeli yamar (ağ yok).
  Canlı ölçüm onaylandı (3 taslak, ≤0,15 USD) ve denendi: ilk çağrı "credit balance is too low" (400) ile düştü,
  ücret yok (`docs/olcum/2026-10-08-taslak/olcum.json`). BAKİYE YÜKLENİNCE: `python docs/olcum/2026-10-08-taslak/
  taslak_olcum.py --canli` (taslaklar aynı klasöre, otomatik denetim: başlık sırası, bağlamda olmayan sayı, [DOLDURUN]).
  API yerine oturum modeliyle ölçüldü (Aşama C yöntemi, birebir istem: `--dok` → `yanit_<n>.md` → `--elle`):
  3/3 başlık sırası doğru, bağlamda olmayan sayı 0, [DOLDURUN] 26-32, kelime 448-501. İstem okunurken bulunan ve
  düzeltilen: özet alanındaki site menüsü taslak bağlamına giriyordu (`_temiz_ozet`), şartlar cümle ortasında
  kesiliyordu (`_kisalt`). AÇIK VERİ İŞİ: 22 aktif kaydın özeti tamamen menü/başlık metni (KGF 12, KOSGEB 7,
  TÜBİTAK 3), 27'si kısmen; kartlarda ve danışman bağlamında görünüyor → özetler resmî sayfalardan yeniden yazılmalı.
  Sıradaki: tarih hatırlatması (SMTP sonrası).
- **İKAS App Store hazırlığı** (2026-10-08, kod tamam, mock modda doğrulandı): yol haritası `docs/IKAS_YOL_HARITASI.md`
  (paylaşılabilir sayfa: https://claude.ai/artifact/CKhXWEgLxi2CPFbCL6L7tk, özel). Kurulum `GET /api/oauth/authorize/ikas`
  (state + httpOnly çerez), callback `GET /api/oauth/callback/ikas` (me + getMerchant → hesap açar, e-posta başka hesaptaysa
  bağlamaz; merchantId ile yeniden kurulum aynı hesaba döner; saveWebhook), imzalı açılış `/ikas` → `POST /api/ikas/oturum`,
  imzalı webhook `POST /api/ikas/webhook` (sipariş: 10 dk erteleme + panelde tamamlama; `store/app/deleted`: belirteç
  silme), token yenileme, `DELETE /api/ikas/baglanti`, `/`, `/ikas`, `/dashboard` yalnız `IKAS_CERCEVE_KAYNAKLARI`
  (varsayılan `https://*.myikas.com`) tarafından çerçevelenir. Veri hataları düzeltildi: iptal `status` alanında
  (ödeme durumunda değil), `productName` şemada yok → `variant.name`, sayfalama + 365 gün süzgeci, döviz ayrı.
  E-ihracat göstergeleri (yurt dışı teslimat, ülke, döviz) → profile "ihracat" hedefi, taslak bağlamı, panel kartı.
  İmzalar SDK JS fonksiyonlarıyla çapraz doğrulandı. Göç `k8f0b2c4d890` dev DB'ye UYGULANDI (yedek
  `tesvikler_oncesi_gocK.db.bak`). `python -m app.ikas_integration --self-test` 11/11, `tests/test_ikas_uygulama.py` 31.
  BEKLEYEN (Mert/İKAS): Partner hesabı, Next.js zorunluluğu ve faturalama soruları, client id/secret, HTTPS sunucu,
  2 geliştirme mağazasında gerçek API testi (kontrol listesi yol haritasında).
- **İKAS Next.js kabuğu** (2026-10-08): `ikas-app/` (README orada). İKAS'ın resmi şablonu
  (`github.com/ikascom/ikas-app-examples/examples/starter-app`, `ikas` CLI 0.0.30) okunarak aynı yapı ve AppBridge
  akışıyla yazıldı; şablonun Prisma/iron-session belirteç deposu ALINMADI (belirteçler yalnız FastAPI'de).
  Next 16.4.0 (15.x'te PostCSS açıkları; `npm audit` 0). FastAPI'ye eklenenler: `POST /api/ikas/appbridge-oturum`
  (HS256, sub=merchantId, aud=authorizedAppId; alg=none reddi), callback `signature`=HMAC(code) denetimi,
  kurulum kimliği `getAuthorizedApp` (me yedek), yenileme `api` alanına, `IKAS_UYGULAMA_URL`.
  Doğrulama: self-test 15/15, `tests/test_ikas_uygulama.py` 36, kabuk `npm test` 9/9 + tsc + build; tarayıcıda kurulum →
  imzalı açılış → panel, iframe içinde AppBridge (`scripts/ikas_appbridge_deneme.py`, self-test 4/4), 375 px.
- **Veri izi + platform** (2026-10-08): yol haritası beş ize genişletildi (`docs/IKAS_YOL_HARITASI.md` §3A).
  - Çağrı modeli: tablo `tesvik_cagrilari` (göç `l9a1c3e5f901`; dev sunucusu create_all ile önce açmıştı → şema aynı,
    yedek `tesvikler_oncesi_gocL.db.bak`, `alembic stamp head`). `app/cagrilar.py` (`--self-test` 6/6), `GET /api/cagrilar`,
    kontrol listesi ve İKAS panelinde "son başvuru / kalan gün" (web paneli + Next kabuğu).
  - `init_db` artık Alembic'in yönettiği DB'de create_all ÇALIŞTIRMAZ; göç geride ise CRITICAL uyarı (`tests/test_init_db.py`).
  - Eşleştirme: `uygunluk_kriterleri.sirket_turleri` (kayıtta varsa şahıs/şirketsiz elenir; `tests/test_sirket_turu_engeli.py`).
  - **ONAY BEKLEYEN veri betikleri** (kopya DB'de prova edildi, idempotent):
    `scripts/fix_veri_2026_10_08_cagrilar_tur10.py` (8 çağrı: TÜBİTAK 1501/1507 2026-2 açık, KOSGEB İstihdamı Koruma
    2026-2 açık, diğerleri kapanmış; tarihler resmi sayfa/çağrı PDF takviminden) ve
    `scripts/fix_veri_2026_10_08_ihracat_5973_tur11.py` (5973 sayılı Karar m.3/4/6/11/12, 2026 üst limitleri limit
    tablosundan hücre hücre; belge listesi/başvuru süresi genelge okunamadığı için boş).
  - Açık: 5986 ve kayıt 163'ün şirket türü şartı doğrulanmadı; 5973 fuar (m.7) 2026 limiti; genelgeler (JS ile
    yükleniyor, curl/WebFetch okuyamadı).
  - Platform: `ikas-app` CI işi (test, tip, derleme, npm audit) + Dockerfile (standalone) + `docker-compose.ikas.yml`.
  - **Tur10 + Tur11 UYGULANDI** (2026-10-08, yedek `tesvikler_oncesi_tur10_11.db.bak`): 8 çağrı, 5 yeni 5973 kaydı;
    aktif 100 → 105, Ticaret Bakanlığı 3 → 8.
  - **Tur12 UYGULANDI 2026-10-08** (`scripts/fix_veri_2026_10_08_eihracat_tur12.py`, self-test 11/11, kopyada prova):
    5973 kayıtlarına genelgelerden başvuru yeri/süresi/belge listesi + ihracatçı birliği üyeliği şartı; 5986'dan 5 yeni
    kayıt (m.4 pazaryeri reklamı, m.5 e-ihracat tanıtımı [statü], m.6 fulfillment, m.8 çevrim içi mağaza [1 M USD],
    m.9 komisyon; 2026 limitleri resmi xlsx "ŞİRKETLER" sütunu); 162 resmi kaynakla düzeltme + şahıs için konsorsiyum
    yolu (Genelge m.33/7); **163 pasif** (dayanağı 2573 sayılı Karar 18.08.2022'de mülga — Bakanlık sayfası yazıyor).
    Uygulama sonrası aktif 109, Ticaret 12.
  - Word çıktısı: `app/basvuru_docx.py` (`--self-test` 9/9), `GET /api/basvuru-listesi/{id}/docx` (liste + çağrılar +
    taslak; başka kuruluşun işaretleri sızmaz), web paneli ve Next kabuğunda "Word (.docx) indir".
  - `requirements.prod.txt`: `sentry-sdk` eksikti (kod ImportError'ı yuttuğu için canlıda hata izleme sessizce kapalı
    kalırdı) + `python-docx` eklendi.
  - Açık: 5973 fuar (m.7) 2026 limiti; TEKMER çağrı tarihleri (PDF); 5986 şemsiye dışındaki m.3/m.7 (statü sahipleri).
- **Arayüz sadeleştirme** (2026-10-08): panel "Ana sayfa"yla açılır (`GET /api/ozet`, `app/ozet.py` `--self-test` 9/9):
  tek "sıradaki adım" (profil yok > temel alan eksik > 30 gün içinde kapanan çağrı ve listesi bitmemiş > ilk liste),
  profil tamamlanma yüzdesi, öne çıkan 3 destek, 60 gün içindeki son başvurular, devam eden listeler. Menü: Ana sayfa ·
  Uygun destekler · Başvurularım · Danışmana sor | Hesap. Profil formu 6 temel alan + "Ayrıntılar" katlanır bölümü;
  il alanı 81 ilden seçim (`GET /api/iller`); kayıttan sonra doğrudan uygun desteklere geçer. Eşleşme kartında çağrı
  çipi ("Başvuru açık · 23 gün kaldı"); kart özeti `kart_ozeti` ile menü satırlarından arındırılıp 320 karakterde
  kesilir (boşsa özet gösterilmez, başka alana geri düşülmez). Bölüm değişince sayfa üste kayar.
  `tests/test_ozet.py` 8 test; `tests/test_turkce_metinler.py` ast tabanlı (CI 3.11 kırmızısının kökü; billing metinleri düzeltildi).
  - **Tur13 UYGULANDI 2026-10-08** (`scripts/fix_veri_2026_10_08_ozet_tur13.py`, self-test 5/5, kopyada prova 15 → ikinci
    koşu 0): özeti tamamen site menüsü olan 22 aktif kaydın 15'ine kaynak sayfanın "Programın Amacı / Ürün Açıklaması /
    Genel Bilgi" metni (`docs/olcum/2026-10-08-ozet/tur13_ozetler.json`, çıkarıcı `ozet_cikar.py`). Kalan 7 KGF sayfası
    (93, 116, 125, 153, 154, 171, 173) içeriği JS ile yüklüyor; özetsiz gösterilir.
- **Hazırlık yol haritası + e-ihracat geri ödeme hesaplayıcı** (2026-10-08, commit edilmedi):
  - `app/eticaret_destek_hesaplayici.py` (self-test 12/12) 5986 Karar metnine göre yeniden yazıldı: kalem bazında madde,
    oran, hedef ülke +20 puan (m.4/m.6/m.5; m.8/m.9'da yok, m.16/3), satış tavanları (m.4 %20, m.6 %10), Türk ürünü
    payı (m.10/1), %75 tavanı (m.16/4), 2026 limitleri ve bölüm limiti (m.10/2). Eski sürüm komisyona %70 uyguluyor ve
    statüsüz şirkete m.3/m.7 kalemlerini hesaplıyordu. Çıktı ileriye dönük (ön onaydan önceki harcama desteklenmez):
    şimdi / hazırlıkla / teyitle + aylık bekleme maliyeti.
  - `app/hazirlik.py` (self-test 8/8): şirket türü karşı-olgusu (limited olsaydı açılan programlar) + eşleşen
    programların ön şartları (KOSGEB kaydı, birlik üyeliği, DYS, Madrid, ön onay, e-imza, KEP, ÇKS, teşvik belgesi).
    `GET/PUT /api/hazirlik`; durum `financial_profiles.hazirlik` (JSON, göç `m0b2d4f6a012`).
  - Arayüz: "Uygun destekler"de yol haritası + katlanır hesaplayıcı; ana sayfada "E-ihracat geri ödemesi" ve
    "Uygunluk için ilk adım" kartları. Test: `tests/test_hazirlik.py` 9, `tests/test_eticaret_destek.py` 30.
  - Göç `m0b2d4f6a012` gerçek DB'ye UYGULANDI (2026-10-08; aşağıdaki sıra).
  - 10 persona uçtan uca deneme: `docs/olcum/2026-10-08-persona/RAPOR.md` (beklenen 22/25; tarih gösteriminde TÜBİTAK
    ön kayıt son günü vurgulanmıyor; tarım ve mikro hizmette ilk sıralarda yanlış öneri; 9 maddelik düzeltme listesi).
  - **Persona düzeltmeleri** (aynı gün, commit edilmedi; RAPOR.md "Düzeltme sonrası"): firmanın son günü
    (`tesvik_cagrilari.on_kayit_son`, göç `n1c3e5a7b234`, yeni durum `on_kayit_kapandi`), takipteki başvurular "sıradaki
    adım"a girer, eşleştirmede KOSGEB-büyük işletme / şahıs ürünü / 9903 şirketsiz / asgari ihracat USD engelleri, hedef
    kitle etiketi +0,3, Organik beyansız −0,2, 9903 hedef uyumsuz −0,3, skor 0 gizli; hazırlıkta ÇKS önceliği ve ilgili
    program eşiği. `tests/test_persona_duzeltmeleri.py` 19. Ölçüm: beklenen 23/25, eski 12 personada gerileme yok.
  - **Gerçek DB'ye UYGULANDI (2026-10-08, Mert onayı):** yedek `docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur12_14_gocMN.db.bak`
    → göç m0b2d4f6a012 + n1c3e5a7b234 (head) → tur12 (6 güncelleme, 5 yeni, 163 pasif) → tur13 (15 özet) → tur14 (2 ön
    kayıt + 2 ihracat eşiği). İkinci koşular 0; aktif 109, Ticaret 12; kopyayla birebir. Commit b78a8d7, CI yeşil.
  - **Tur15 başvuru süresi UYGULANDI** (2026-10-08, yedek `tesvikler_oncesi_tur15.db.bak`): 34 kayda başvuru süresi
    (9903 ×5: Karar m.5/5 31/12/2030'a kadar müracaat, m.5/6 öncesi harcama kapsam dışı; KGF ×28: sayfalarda son tarih
    yok → "bankadan teyit", KOSGEB'e bağlı 5 paket önce KOSGEB onayı, 170 son kullandırım 31.12.2028; KOSGEB 9) + 6 çağrı
    (9903 kapanış 31.12.2030, KGF 142 = KOSGEB 2026-2). Alıntılar `docs/olcum/2026-10-08-basvuru-suresi/kanit.json`.
    `/api/cagrilar` pencere dışında kapanan açık çağrıyı "yaklaşan"a koymaz. Boş başvuru süresi 54 → 20 (kalan: akademik
    TÜBİTAK, KOSGEB 5/6); persona yol bilgisi 199/245 → 222/245.
  - **Tur16 UYGULANDI 2026-10-08** (yedek `tesvikler_oncesi_tur16.db.bak`; `scripts/fix_veri_2026_10_08_sart_yer_sure_tur16.py`, self-test 6/6, kopyada prova
    50 alan + 3 çağrı → ikinci koşu 0): tarım şartları/belgeleri (76: Hayvancılık Desteklemeleri Uygulama Tebliği 2024/23
    m.4, m.6; 77/79: Bitkisel Üretim Tebliği 2024/39 m.3, m.7/3-4, m.8, m.15, m.17), KGF kredi veren bankalar (13),
    KGF 116/149 şartları, KOSGEB 4-6 yer/süre, TÜBİTAK 18 kayıt süre/yer + 3 çağrı (1001 2026-2, 2224-C Lindau, 4006
    13. dönem). Alıntılar `docs/olcum/2026-10-08-tur16/kanit.json` (36 kaynak, hepsi metinde birebir denetlendi).
    Sonrası: boş başvuru süresi 0, persona yol bilgisi 242/245. Bulgular: 26 ve 50 (2223-D UK/Newton) yalnız 2016 dönemi
    → muhtemelen sona ermiş, pasif kararı bekliyor; 79 Sera açıklaması "kurulum hibesi" diyor, tutarı dekar bazlı.
  - **KGF sayfa izleme** (`app/kgf_izleme.py`, self-test 6/6): ürün bölümü özeti + tarih ifadeleri tabanla
    (`app/data/kgf_taban.json`, 31 sayfa) karşılaştırılır; zamanlayıcıda ayda bir (6'sı 03:00), bulgular WARNING.
    İnceleme sonrası `python -m app.kgf_izleme --taban-yaz`.
  - **Tur17 UYGULANDI** (2026-10-08, yedek `tesvikler_oncesi_tur17.db.bak`; `scripts/fix_veri_2026_10_08_kalanlar_tur17.py`,
    kanıt `docs/olcum/2026-10-08-tur17/kanit.json`): işletmeye önerilebilen TÜBİTAK 1515/1702/1719/1832 şart-belge-yer
    (elle seçilmiş tam cümle), 31 akademik kayda yalnız başvuru sistemi adresi (otomatik şart/belge çıkarımı gürültülüydü,
    yazılmadı), KOSGEB 6 belge/7 yer, 79 Sera özet-açıklaması tutarla uyumlu (eski "kurulum hibesi" metni nota),
    26 ve 50 pasif (yalnız 2016 dönemi), 4 TYBS çağrısı (27.10.2026). Aktif 107; boş: şart 12, belge 42, yer 6, süre 0.
- **Yapay zekâsız şablon taslak** (2026-10-08): `app/sablon_taslak.py` (self-test 9/9) aynı 5 bölüm + belgeler; profil,
  program amacı (yalnız tam cümle), çağrı/ön kayıt tarihi, ön onay uyarısı, tutar/formül, İKAS toplamları kaynağıyla,
  hedef + program türüne göre göstergeler; bilinmeyen her yer [DOLDURUN]. `POST /api/basvuru-listesi/{id}/taslak`
  varsayılanı `yontem=sablon` (plan/rıza/servis gerekmez, veri dışarı çıkmaz, `taslak_model=sablon-v1`);
  `yontem=yapay_zeka` eski Claude yolu (PRO + rıza + günlük sınır). Panelde "Taslak oluştur" şablon, "Yapay zekâyla yaz"
  isteğe bağlı; İKAS kabuğu varsayılanı şablon.
- SMTP: `.env`'de SMTP_* dolu ama gönderim "Connection unexpectedly closed" ile düşüyor (port 587); kimlik/sunucu
  doğrulanmalı. Doğrulama zorunlu kayıt bu düzelmeden açılmamalı.
- Açık: 76 hayvancılık birim tutarı (OCR), 163 e-ticaret üyelik limiti (5973 Genelge), 37 ve 73 kararsız (sayfa
  yetersiz), Sentry için DSN (AB bölgesi) ve KVKK metnine eklenmesi.

## Komutlar
- Test: `PYTHONIOENCODING=utf-8 python -m pytest -q` · Lint: `python -m flake8 app/ tests/ scripts/ --select=E9,F63,F7,F82,F401,F811`
- Sunucu: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` · Persona ölçümü: `docs/olcum/.../asama3_olcum.py`
- Test hesabı: test@example.com (şifre `scripts/seed_test_hesabi.py` TEST_SIFRE), AI rızası kapalı bırakılır.
