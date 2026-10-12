# DURUM — Teşvik Asistanı denetim çalışması

Son güncelleme: 2026-10-12 (tur34-36 + persona denemesi: 317 → 365 kayıt, etkin 244; 20 persona/45 senaryo hakem 2,40 → 2. tur ~2,9). Oturuma bunu okuyarak başla.

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
  - Karşılaştırma (`docs/olcum/2026-10-08-taslak-karsilastirma/RAPOR.md`, 3 vaka, ücretsiz): uydurma rakam iki yolda 0,
    olgu kapsaması eşit; yapay zekâ daha uzun, daha az [DOLDURUN]. Fark programa özgü yönlendirici sorulardı → şablona
    tür bazlı rehber (yatırım, ihracat, Ar-Ge, istihdam, girişim, tarım; tür önce başlıktan). API bakiyesi yok: üretim
    modeliyle kesin ölçüm için `taslak_olcum.py --canli` (≤ ~0,15 USD) bakiye yüklenince.
- **Taslak sihirbazı (sablon-v2)** (2026-10-08, kullanıcı: "bu böyle olmaz" — cevapsız şablon [DOLDURUN] tablosuydu):
  `GET /api/basvuru-listesi/{id}/taslak-sorulari` (program türüne göre gerekçe/çıktı soruları, önerilen adımlar, formüldeki
  gider türleri, kayıttaki oran seçenekleri, üst limit, kayıtlı cevaplar); `POST …/taslak` gövdede cevaplar
  (`basvuru_takipleri.taslak_cevaplar`, göç `o2d4f6b8c345`, UYGULANDI) → cümle + tablo, bütçe toplamı ve talep edilebilecek
  destek = toplam × seçilen oran (kayıttaki üst limitle sınırlı). Cevapsız taslakta boş tablo yok; göstergeler programın
  türünden; kurallar ("…desteklenmez", "en fazla 2 proje") işaretlenmez, ilerlemeye sayılmaz, uyarı bloğunda.
  Tarayıcıda 1501 ile uçtan uca: 3.000.000 TL × %75 = 2.250.000 TL, cevaplar yeniden açılışta geri geliyor.
- **Tur18 UYGULANDI** (yedek `tesvikler_oncesi_tur18_gocO.db.bak`; kopyada prova yapılmadı, tek kayıt): 1501 formülü tutarla
  çelişiyordu ("üst limit yok" ↔ "en fazla 20 M TL"); program sayfası + 2026-2 çağrı metniyle düzeltildi, eskimiş "genellikle
  Ocak-Şubat" süresi gerçek takvimle değişti, "en fazla 2 proje önerisi" şartı eklendi. Aynı çelişki türü için tüm aktif
  kayıtlar tarandı: başka yok.
- **100 sentetik ajan** (2026-10-09, `docs/olcum/2026-10-09-100-ajan/RAPOR.md`): 20 arketip × 5, kurallı ajan (LLM yok);
  18 değişmez/beklenti denetimi %100 ama yanıltıcıydı → bağımsız ilgi ölçümü: ilk 10'da ilgisiz öneri %18,4 → %4,3
  (`matching._ilgi_engeli`: Yapay Zekâ Kredisi, SGK teşviki, YÖNDE-tarım, TÜBİTAK-ilgisiz sektör, büyük 9903-küçük
  ölçek; ceza 0,30, dışlama değil). Persona/G12 gerilemesi yok. Yapamadıkları: kalkınma ajansları, TKDK/IPARD,
  Turquality, İşbaşı veride yok; deprem bölgesi sinyali ve yatırım tutarı alanı yok.
- **Resmi form şablonları + İKAS sihirbazı** (2026-10-09): `app/form_sablonlari.py` (self-test 5) — 1501/1507 (id 34, 44)
  sihirbaz soruları AGY100 A.3-E.1 bölümleri, KOSGEB Kapasite Geliştirme (id 8) II. Bölüm 2.11-2.20; taslak aynı
  başlıklarla yazılır, formun tablo bölümleri (M011-M016/M030, 2.3-2.10) "doldurulacak tablolar" olarak listelenir.
  Başlıklar indirilen resmi metinlerle denetlendi (`docs/olcum/2026-10-09-formlar/kanit.json`, eksik yok). Web
  sihirbazında form adı + kaynak bağlantısı. İKAS kabuğu: `ikas-app/src/components/sihirbaz.tsx` + `src/lib/sihirbaz.ts`
  (saf hesap/temizleme, 4 node testi); "Hızlı taslak" / "Sihirbazla doldur". Tarayıcıda: web'de kaydedilen 1501 cevapları
  İKAS'ta geri geldi, 3.500.000 × %60 = 2.100.000 TL, taslakta "### B.2 …" başlığı; 375 px'te taşma yok. Test 1066 + 1 atlanan.
- **Danışman sistem promptu yeniden yapılandırıldı** (2026-10-09, `app/rag.py` `SISTEM_PROMPTU`): XML bölümleri
  (rol, girdi yapısı, doğruluk kuralları, triyaj, analiz protokolü, çıktı formatı, sorumluluk reddi). TRİYAJ MODU:
  faaliyet/şirket türü/il alanlarından ikisi bilinmiyorsa program listelemez, en fazla 5 soru sorar. Program kartı
  (durum, uygunluk, şartlar, oran/limit, riskler, resmî kaynak), "[Genel ilke – teyit edin]" etiketi, garanti yasağı,
  il → bölge çıkarımı yasağı, bağlam metni veri sayılır (talimat değil), sabit sorumluluk reddi. Model yanıt başında
  `<analiz>` yazar; kullanıcıya gitmez: `analiz_ayikla` (tam yanıt) + `_AnalizSuzgeci` (akış, etiket parçalar arası
  bölünse de; her kesim noktasında tam ayıklamayla aynı sonuç testli). Yalnız analiz üretip kesilen yanıt liste formatına
  düşer. Bağlam `BUGÜN: YYYY-AA-GG` ile başlar. Girişim eki triyaj + analiz + sorumluluk reddini kapsar. Eski test
  ifadeleri korundu. Test 1079. **Gerçek modelle ölçülmedi** (API bakiyesi yok): prompt ~2 bin token uzadı;
  `C_olcum.py` ile uydurma/beklenen değer/triyaj tetiklenmesi ölçülmeden canlıya alınmamalı.
- **Yeni prompt ajanlarla denendi** (2026-10-09, `docs/olcum/2026-10-09-prompt-ajan/RAPOR.md`): 20 senaryo, birebir
  prompt + bağlam, danışman rolünü Sonnet alt ajanlar oynadı (API yok). Analiz bloğu 20/20 kapalı, sızıntı 0, ret metni
  20/20, mod 20/20, beklenen 34/34, uydurma sayı 0, enjeksiyon/garanti/manipülasyon/veride-yok/kalan gün/bölge doğru.
  Bulgu: yanıtlar ~2 kat uzun (ort. 9,8 bin kar); profil cirosu bağlama `4000000.0` gidiyor. 100-ajan yeniden: 18/18 %100
  (D14 ölçümü form şablonu numaralarını rakam sayıyordu, düzeltildi).
- **Taslak/sihirbaz katmanı ajanlarla denendi** (2026-10-09, `docs/olcum/2026-10-09-taslak-ajan/RAPOR.md`): 12 program,
  Sonnet kullanıcı + Opus hakem ajanları. Mekanik doğruluk 12/12 (şema, cevaplar, bütçe hesabı, uydurma 0, form başlıkları,
  Word). İşe yararlık zayıf: kullanıcı evet 0/kısmen 8/hayır 4; hakem forma aktarılabilirlik 2,1/5. Ana neden: sihirbaz her
  programı proje önerisi sanıyor (kredi, prim teşviki, dekar desteği, E-TUYS, ön onaylı gider, hisse fonu farklı biçim).
  Öneri: programlara `basvuru_bicimi` alanı + biçime göre sihirbaz; oran seçeneklerinde hisse/faiz ayıklama; kapanmış
  dönem takvimde. Onay bekliyor.
- **Gerçek uygunluk ölçümü** (2026-10-09, `docs/olcum/2026-10-09-uygunluk/RAPOR.md`): 77 programın resmî sayfası
  indirildi, 8 Sonnet ajanı 759 kriter çıkardı (alıntıların hepsi kaynakta doğrulandı), 12 gerçek profil. İlk 10 önerinin
  %16'sı resmî şarta göre uygun değil (E-İhracat şahsa 1. sırada, BMZ II il/NACE dışına, KOBİ-only paketler büyük
  firmaya, organik sertifikasıza, ≤29 yaş kredisi 50 yaşa); şirketsiz sertifikalı girişimciye boş liste
  (`uygunluk_engeli` KOSGEB/KGF'yi toptan kapatıyor). Neden: ölçek/şirket türü 30'ar programda zorunlu, kural 10-12'sinde.
  Veri çelişkisi: KOSGEB 5 ve 9, KGF 142 ve 149. 2. aşama planı raporda, onay bekliyor.
- **Kontrol listesi + resmî kaynak denetimi** (2026-10-10, `docs/olcum/2026-10-10-kontrol-listesi/RAPOR.md`): 507 madde,
  alıntıların hepsi doğrulandı. Doğru %49, desteksiz %34, belirsiz %15, yanlış 11 + eskimiş 2; %27'si yanlış türde
  (şart/belge/adım/kural/bilgi karışık); 177 zorunlu madde eksik; 6 program genel sayfaya bağlı; 4 çağrı çelişkisi.
  Kullanıcı geri bildirimi: taslak neye hazırlanıyor belirsiz, kutular karışık. Düzeltme planı onay bekliyor.
- **Kontrol listesi, taslak, kaynak, paket modu, TKDK/ajans turu** (2026-10-10; gerçek DB'ye UYGULANDI ve push edildi;
  sıra: `alembic upgrade head` → tur19 → tur20 → tur21 `--uygula`, her biri yedekli):
  - Göç `p3e5a7c9d456`: tesvikler.kontrol_listesi, basvuru_bicimi; basvuru_takipleri.uygunluk_cevaplari.
  - Kontrol listesi dört bölüm/dört etkileşim (şart Evet/Hayır/Emin değilim; belge, adım kutu; kural/bilgi kutusuz),
    her madde resmî alıntı ya da 'kurumdan teyit edin'; web + İKAS + Word. Taslak 'Ne için / Nereye / Ne değildir',
    proje dışı biçimlerde (kefalet, prim, üretim ödemesi, E-TUYS) taslak gizli. Dönem yalnız çağrı kaydından.
  - tur19: denetimden 77 programın kontrol listesi (yanlış/eskimiş/belirsiz düzeltildi, 177 eksik eklendi, tekrar ayıklandı).
  - tur20: 6 genel kaynak → resmî (8859 RG, E-ihracat Genelgesi 13.04.2026); 2026 tarım tutarları 11781 sayılı
    Kararla 310 → 367 TL (hububat mısır katsayısı 1,3 → 1,0 düzeltildi); 7 çağrı (1832 ön kayıt 08.10 kapanış 12.10;
    BİGG+ 2026-1 05.10-20.11; 1707 üç dönem; TEKMER); 1512 sayfası kapalı notu; ölçek/NACE/il kısıtı (9+2+1 program).
    Uygunluk ölçümü kopyada: ilk 10'da uygun değil %16 → %11, sistemce önlenebilir 7 → 2.
  - Paket modu: prompt bölümü + 'BİRLİKTE KULLANIM KURALLARI' bağlam bloğu (alıntılı) + yatırım sorusunda 12 aday.
  - tur21: 49 yeni program (TKDK IPARD III 101/103/302 + 18 kalkınma ajansı), her alıntı betikçe indirilip doğrulandı
    (49/49); 31'i aktif; il kısıtlı. İSTKA, İZKA, BEBKA, Trakya, GMKA, İpekyolu: 2026 işletme programı yok.
    100-ajan kopyada 18/18 %100, gürültü %4,1. Test 1086.
  - tur22 (UYGULANDI): 1512 BiGG pasif — TÜBİTAK 1612 sayfası BiGG 1. aşamasını 2026-2028'de 1812 çerçevesine
    bağlıyor (`docs/olcum/2026-10-10-tur22/tubitak_1612_en.txt`); şirketsiz girişimciye artık 1812 (49) önce geliyor.
    201 BAKKA Fizibilite, 231/232/235 OKA: rehberlerin 'Kimler başvurabilir' bölümünden alıntılı şart maddeleri.
- **Profil uygunluk alanları + tur23** (2026-10-10, UYGULANDI): profil formunda isteğe bağlı kurucu/%50 hissedar yaşı,
  başka şirkette ya da şahıs işletmesinde ortaklık, sertifikalar (organik / iyi tarım / hiçbiri). Göç `q4f6b8d0e567`
  (yedek `tesvikler_oncesi_gocQ.db.bak`). Eşleştirme `app/matching._kisisel_engel`: kayıtta yapılandırılmış şart VE
  profilde bilgi varsa eler; biri yoksa elemez. Bu alanlar dış dil modeline gönderilmez, KVKK tablosu güncel.
  tur23 (yedek `tesvikler_oncesi_tur23.db.bak`): 122 yaş ≤ 29, 112 yaş ≤ 35 (KGF sayfaları), 49 ortaklık yasağı
  (TÜBİTAK 1812 sayfası; borsa/kitle fonlaması payları hariç), 77 organik ürün sertifikası (8859 sayılı Karar m.2/7-c;
  PDF taranmış, kanıt sayfa görüntüsü + çevriyazı + SHA-256: `docs/olcum/2026-10-10-tur23/`), 153 TURYIB zorunlu
  hedef kitle genç. tur23 maddeleri `ekleyen: tur23` işaretli; tur19 yeniden koşulsa da korunur (tüm turlar 0 değişiklik).
  Test 1109 geçti / 1 atlandı.
- **B2B API planı** (`docs/API_URUN_PLANI.md`, kod yok, onay bekliyor): durumsuz `/v1` uçları (eşleşme, uygunluk,
  hazırlık, çağrılar, program, e-ihracat, şablon taslak), API anahtarı + kapsam + kota + ölçüm, hedef müşteri sırası,
  kill criteria, 6 adımlı uygulama planı.
- **Anthropic API kaldırıldı; yerel danışman + sağlayıcı katmanı** (2026-10-11): kullanıcı talimatı "son uçta bile
  Anthropic API kullanma". `app/yerel_danisman.py` varsayılan yanıt servisi: dil modeli yok, yanıtın her somut bilgisi
  veritabanı kaydından (kararlar: engel yok / Şartlı (9903 Karar şartı) / belirlenemedi / uygun değil / kapalı; çağrı
  takvimi ve kalan gün; kapsam sorusu; süre kırılımı; dekar × birim tutar; KGF paketinin bağlı KOSGEB çağrısı; yol
  ayrımı; mükerrer kayıt filtresi). `app/llm_saglayici.py` isteğe bağlı dış servis (`LLM_SAGLAYICI=yerel|gemini|
  openai_uyumlu`, OpenAI uyumlu uç; Gemini için `LLM_API_KEY`); dış yanıt `app/dayanak.py` denetiminden (URL/e-posta/
  tutar/oran/tarih/gün/telefon bağlamda olmalı; çarpım istisnası yalnız N kaynakta ve birim fiyat aynı birimle bağlamdaysa)
  geçmezse kullanıcı yerel yanıtı görür; SSE beklerken ": bekleniyor". Rıza sağlayıcıya özel (`ai_riza_saglayici`, göç
  `r5a7c9e1f678`, yedek `gocR`; eski rızalar "anthropic:Anthropic PBC" diye işaretli ve geçersiz). Yurt içi sunucuda
  rıza gerekmez ama vazgeçilebilir. Veri turları (hepsi yedekli, idempotent, UYGULANDI): tur24 organik atıf, tur25 KGF
  ölçek, tur26 başvuru sahibi türü, tur27 kayıt 78 detayındaki eski traktör metni, tur28 kayıt 112 sektör (imalat+arge,
  doğrulanmış alıntıdan), tur29 kayıt 138 Gençiz yaş sınırı 29 (doğrulanmış alıntıdan), tur30 kontrol listesindeki
  31 birinci tekil beyan metni nötr şart diline (24 kayıt; alıntılar aynı; tur19 SONRAKI_TURLAR kancasına ekli), tur31
  kayıt içi çelişkiler (163 mülga + halef m.8, m.4 üyeliği kapsamaz; 79 açıklamada eski 310/527 → 367/623,90; 142
  "Kefalet üst limiti 45 M TL", KOSGEB kredisinin %90'ı). Eşleştirme: kurucu yaşı 18-29
  ise "genç girişimci" etiketi türetilir (`app/match_adapter.profil_etiketleri`).
  Değerlendirme (`docs/olcum/2026-10-11-yerel-danisman/`): 30 senaryo, her turda 5 bağımsız Sonnet hakem (abonelik,
  API yok), ölçüt yalnız kaynak dosyası; `karsilastir.py`. Genel puan (1-5) tur1 2,62 → 3,04 → 3,06 → 3,24 → 3,38 →
  3,31 → 3,38 → 3,48 → 3,37 → tur10 3,46 (doğruluk 3,20 → 4,00; soruya odak 2,50 → 3,73); kritik bulgu 39 → 19 → 15
  → 11 → 7 → 12 → 4 → 5 → 3 → 0 (tur6 artışı v8'deki kalıp regresyonundan, tur7'de giderildi). Tur10 sonrası iki küçük
  düzeltme (eşik ifadesi çelişki sayılmaz, eski sürüm → güncel sürüm yönlendirmesi) yeniden puanlanmadı. Otomatik ölçüm: dayanak sorunu 0, beklenen değer 41/41. İki Opus kod
  incelemesi (12 + 12 bulgu: dayanak çarpım istisnası uydurma N ile aşılabiliyordu, 9903 EK-3 şartı yarım, çift
  listeleme, bağlı program takvimi, sektör filtresi tarım/hizmet NACE'sini tanımıyordu, 30-35 yaş genç programları,
  ters netleştirme sorusu, regex yanlış pozitifleri) düzeltildi ve testlendi ("hariç" dışlaması ve "isen" hitabı bilerek
  bırakıldı). Bulunan gizli hata: bash heredoc `\b`'yi 0x08'e çevirmişti; `_KOSULLU_BELGE` bu yüzden hiç eşleşmiyordu
  (koşullu belgeler sızıyordu); şimdi test tüm app/ ve scripts/ dosyalarında 0x08 arar. Uygunluk ölçümü ilk 10'da uygun
  değil %9 → %1 (`ozet_2026_10_11_tur29.md`).
  Kapanan hakem bulguları (2026-10-11 ikinci blok): birinci tekil beyanlar (tur30); alt destek/aşama çağrısı programın
  tamamını kapatmıyor (`alt_destek_cagrisi`); sorudaki yabancı ortak beyanı (`soru_beyanlari`); 9903 ailesinde bölgeye
  göre katkı/makine/faiz karşılaştırması, kart en avantajlıya; kapasite eşikli Karar şartı soruya döner; 4447 süre
  sorusunda kişi bilgisi sorulur; Turquality'de kaybedilecek 5973 maddeleri adıyla; soru ↔ profil çalışan çelişkisi;
  kapsam dışı kalemde "takip edin" yok; mülga programda halef, eski sürümde güncel sürüm; KGF tutarı "kredi ve kefalet
  limitleri"; yatırım ihtiyacı yokken 9903 gürültüsü yok; düşük olasılık ve "çağrı planlanıyor" etiketleri; hububatta
  yalnız temel destek tutarı ayrıca (477,10 × dekar); başarısız yapay zekâ taslağı günlük hakkı düşürmez
  (`rate_limit` `iade`). Dayanak: kuruş basamaklı sayı kaynakta birimsiz geçse de kabul (uydurma kuruşlu değer yine
  yakalanır).
  Kapanan tur10 orta bulguları (2026-10-11 üçüncü blok): dar soruda (tek tutar/tarih/süre) kısa şablon; tek anlamlı
  bütçe tavanı × tek oran = azami hibe (açık çarpım, dayanak `_YUZDE_CARPIM` ile denetlenir; çoklu oran/ilave/kaldırılmış
  oranda hesap yok); ciro eşikli şart profille karşılaştırılır (aşıyorsa uygun değil); iletişim il müdürlüğüne göre
  (diğer/alternatif/elenen programların kurumları da); "uygun değil"/kapalı odakta "Size açık görünen alternatifler"
  bloğu; işletmesi olmayan için "bu durum geçici" + kayıttaki şartlar; arazi biliniyorsa dekar aralığı toplam aralığa
  çevrilir. Tur11 (aynı 5 hakem): genel 3,55 (doğruluk 4,2; odak 3,7), kritik 2 → ikisi de kapandı: profilsiz kuruluş
  sorusunda kurulu işletme/rozet/teminat isteyen program adı soruyla eşleşse de öne çıkmaz (YZ Kredisi → BiGG);
  birlikte kullanım sorusunda yanıtta anılan tüm 9903 programlarının hükmü + "KOSGEB/TÜBİTAK istisnası yalnız Teknoloji
  Hamlesi'nde" notu. Ayrıca: Turquality dışlaması fıkralı madde (m.10/3); güncel sürüm eşleşmesi yıldan önceki ada
  bakar (TOBB 2020 PAKETİ → 2026 PROGRAMI); sorudaki tutar kayıtta geçiyorsa kısa cevapta bağlamı ("15.102 TL 2022
  yılı değeridir"). Tur11 sonrası düzeltmeler yeniden puanlanmadı.
- **Üçüncü taraf yapay zekâ tamamen kaldırıldı; yalnız kendi sunucumuzda model** (2026-10-11, dördüncü blok):
  kullanıcı talimatı "google open ai studio da kullanma, ikas veri güvenliğine önem veriyor". `app/llm_saglayici.py`
  yalnız `yerel` (varsayılan, dil modeli yok) ve `ozel_sunucu` (Ollama/vLLM/llama.cpp, Chat Completions, httpx; SDK
  yok) kabul eder; gemini/openai_uyumlu/anthropic reddedilir. `ozel_sunucu`: iç ağ açık izin listesi (10/8,
  172.16/12, 192.168/16, 127/8, ::1, fc00::/7; 6to4/Teredo/NAT64/CGNAT/meta veri/sayısal/Unicode ad reddi), her
  çağrıda DNS denetimi ve http'de IP sabitleme (rebinding), trust_env=False, yönlendirme yok, hata gövdesi günlüğe
  yazılmaz, sunucu istemi kestiyse (prompt_tokens < beklenenin %60'ı) yanıt atılır. Model kuruluş bazında varsayılan
  KAPALI (opt-in, `KULLANIM_KAYDI`), tercih sağlayıcı/adres değişince korunur; eski Gemini/Anthropic rızaları
  geçersiz ve rıza ucunda temizlenir. `openai` bağımlılığı kaldırıldı (requirements, prod: httpx). KVKK metni,
  panel, ikas-app tipleri/metinleri güncellendi. Opus güvenlik incelemesi: kritik 0, orta 6 → hepsi kapandı
  (vazgeçme kaybı, adres bağımlı vazgeçme, is_private aralıkları, DNS TOCTOU, KVKK iddiası, opt-in). Kurulum:
  `docs/OZEL_MODEL_SUNUCUSU.md`. Canlı ölçüm (yerel Ollama gemma4 8B, GPU yok; `docs/olcum/2026-10-11-ozel-model/
  SONUC.md`): yanıt 3,5-4,5 dk; Ollama varsayılan bağlamı istemi 2.051 token'a kesti, model kayıtları görmeden
  "bireysel traktör desteklenir" dedi ve sayı içermediği için dayanak denetiminden geçti → kesik istem koruması
  eklendi; KARAR: varsayılan yerel danışman kalır, ozel_sunucu yalnız GPU + 32k bağlam + hakem ölçümüyle açılır.
  Yerel danışman kalite turları 12-13 (aynı 5 hakem): genel 3,50 → 3,54 (doğruluk 4,07 → 4,13), kritik 3 → 4, hepsi
  kapandı. Kapananlar (tur11-13): yarım cümle kesmesi (sınırda cümle sonu yoksa bir sonrakine kadar uzatma; "…" ~70 →
  4); tekrar eden KGF takvim paragrafı; yürürlükten kalkmış (3305) kayıtlar yalnız adıyla sorulunca; iç veri notları
  kullanıcı diline; kadın yönetici şartı (TURWIB) kilit şart + kadın personada aday; "KOBİ değilseniz" kuralı KOBİ'ye
  gösterilmez; profilde karşılanan şirket statüsü/tarım sektörü sorulmaz; tarım personasında NACE sorulmaz; kapalı/
  uygun değil odakta 3-4. bölümler "engel / çağrı açılınca aranacaklar / belgeler / kanal"; hibe sorusunda açık hibe
  yoksa ilk satırda; kimler başvurabilir(di); şartsız kayıt "engel yok" (teyit notu düz satır); birlikte kullanım
  sorusunda kayıttaki hükümler karar cümlesi olarak; soruda geçen destek unsuru (KDV, yer tahsisi) başka 9903
  kaydında aranır; profilsiz kuruluş sorusunda girişim programları önce (KOSGEB Girişimci Destek), YZ Kredisi "kurulu
  işletme ister" notuyla Diğer'de; hedefli açık çağrıda (1812 Aşama 3) "engel yok" yerine belirlenemedi; USD ihracat
  eşiği ciroyla (1 USD > 10 TL alt sınırı; hesaplanmış sayı yazılmaz) "düşük olasılık"; tarih sorusunda çağrı notu ve
  tarihi yoksa "açık/kapalı belirlenemedi"; "ödemesiz dönem" tarih sorusu sayılmaz; "â/î/û" katlama; "yapay zekâ
  girişimi" gibi konu ifadesi program adı sayılmaz; kaynaksız "[Genel ilke]" satırları yanıttan çıktı. Ölçüm aracı:
  devredilen önceki program kaydı kaynak dosyasına eklenir. Otomatik ölçüm: dayanak 0, isabet 41/41.
  Gözlem: hakem puanı 4 turdur 3,5 civarında; her tur kritikler kapanıyor, hakemler yeni orta bulgular buluyor
  (hakem değişkenliği + kural tabanlı şablonun sınırı). Tur13 sonrası düzeltmeler yeniden puanlanmadı.
  Açık (tur13 orta): kısa cevabın her alt soruya ayrı satır vermesi; "Diğer ilgili" seçiminin konu/ölçek uyumu (TKYB,
  ihracat programları gürültü); kefalet/kredi limit etiketleri; çok rollü programlarda (1707) persona rolü; kayıtların
  kendi içindeki çelişkileri (1507 "aynı anda 5"/"ilk 5"); barındırma sağlayıcısı ve Sentry'nin KVKK "Diğer
  aktarımlar" listesinde olmaması. `.env`'de kullanılmayan ANTHROPIC_API_KEY duruyor (silmek kullanıcıya ait).
- **Kapsam matrisi ve tur32 veri genişletmesi** (2026-10-11): `docs/olcum/2026-10-11-kapsam/kapsam_olc.py`
  (`--self-test` 8/8): 7 sektör persona × 12 il × ihtiyaç = 468 hücre. Kayıt düzeyi = ürünün kendi değerlendirmesinde
  (degerlendir + 9903 ön değerlendirmesi) kapalı/uygun değil olmayan ve ihtiyaca hizmet eden kayıt sayısı; ürün
  düzeyi = gerçek yanıtta bu kayıtlardan biri kart (ya da 9903 bloğu) olarak gösteriliyor mu. İlk ölçüm hatalarını
  düzeltirken bulunan ürün hatası: profil hedefi ihracat olan kullanıcı "personel alırsak" diye sorunca SGK teşvikleri
  yalnız "Diğer"de kalıyor, kart bir kredi ürünüydü (50 hücre) → sorudaki ihtiyaç profil hedefinin önünde. Tur32
  (`scripts/fix_veri_2026_10_11_kapsam_tur32.py`, tur21 doğrulama hattının sarmalayıcısı; yeni resmî alan adları:
  kosgeb, ticaret, eximbank, kgf, ktb, iskur, sgk): 4 Sonnet araştırma ajanı 44 aday yazdı; betik her kaynağı indirip
  her alıntıyı aradı; 13 ret → 8'i önbellekteki birebir metinle onarıldı, 5 düşük değerli (kapalı/belirsiz) eklenmedi
  (`kayit/eklenmedi/`). UYGULANDI 39 kayıt (yedek `tesvikler_oncesi_tur32.db.bak`): 245 → 284 kayıt, etkin 137 → 166,
  kurum 29 → 37 (Türk Eximbank, Kültür ve Turizm Bakanlığı, İSTKA, İZKA, BEBKA, Trakya, GMKA, İKA). Kapsam önce →
  sonra: kayıt VAR 305 → 385, İNCE 140 → 60, BOŞ 23 → 23; ürün 389 → 410/468; gerileyen hücre 0. Kalan BOŞ hücreler:
  şirketi olmayan girişimci için finansman (12) ve Ar-Ge (11) — gerçek: krediler ve TÜBİTAK sanayi programları şirket
  ister. Bölgesel bulgu: eklenen 2026 ajans programlarının çoğu teknik destek ve kamu/STK/kooperatife açık; KOBİ
  persona için 12 ilin 10'unda açık ajans programı yok (veri değil, ajansların 2026 takvimi). Diğer düzeltmeler: başta
  yıl olan başlık ("2026 Yılı Turizm Ücret Desteği") adıyla tanınır (yalnız üç kelimelik kuralda; iki kelimelik kural
  ham başlıkla, KKYP çakışması); harfleri aralıklı PDF alıntısı kartta gösterilmez; kapalı KOSGEB Yurt Dışı Pazar
  "ayrıca bakın" önerisinden çıktı (adıyla sorulunca "kaydımız yok" sürer). Ölçüm: dayanak 0, isabet 41/41; test 1272.
  Önizlemede denendi (turizm ücret desteği, İşbaşı Eğitim, İSTKA, Eximbank). DİKKAT: `data/` git'te yok; üretim
  veritabanına tur32 betiği sunucuda `--dogrula` + `--uygula` ile ayrıca uygulanmalı.
- **GPU ölçüm paketi** (2026-10-12): kiralık GPU sunucusu için `scripts/gpu_olcum_paketi.py` (`--self-test` 5/5;
  kişisel tabloları boşaltılmış `data/tesvikler_kamu.db`, git dışı), `docs/olcum/2026-10-11-ozel-model/gpu_kurulum.sh`
  (GPU kontrolü → Ollama 127.0.0.1 + 32k bağlam → modeller → temiz klon + self-test → model başına 30 senaryo →
  `/root/gpu_olcum_sonuc.tgz`) ve `GPU_TALIMATI.md`. Burada denendi: temiz klonda 284 teşvik / 0 kuruluş, self-test'ler,
  ölçüm döngüsü yerel Ollama ile (kesik istem koruması devrede). Denenmedi: Linux kurulum adımları (GPU/Linux yok).
  SIRADAKİ: kullanıcı sunucuyu kiralar → betik → sonuç paketi buraya → hakem turu → `ozel_sunucu` kararı.
- **Tur33** (2026-10-12, `scripts/fix_veri_2026_10_12_tur33.py`, tur32 ayarlarını devralır; kanıt
  `docs/olcum/2026-10-12-tur33/`): 3 Sonnet araştırma ajanı 33 kayıt — 5973 m.8, 9, 13, 15-21, 23, 25-27 (14);
  10962 m.6-10, 12, 14, 15, 17, 22 (10); Eximbank Reeskont, İhracata Yönelik Yatırım, Marka, TİM Wings; SGK 81/i yurt
  dışı, 4447 ek 4, 2828 ek 1, 3294 ek 5, 6331 m.7. Doğrulama 32/33 → UR-GE'nin iki tutarı Karar metninden alıntılandı
  → 33/33. UYGULANDI (yedek `tesvikler_oncesi_tur33.db.bak`): 284 → 317 kayıt, etkin 199. İlk ölçüm "BOŞ 0" gösterdi
  ama yanlış: şirketsiz girişimciye Eximbank CIRR, TİM Wings ve tasarım şirketi destekleri çıkıyordu → Ticaret Bakanlığı,
  Türk Eximbank ve Kültür ve Turizm Bakanlığı `_ISLETME_GEREKTIREN_KURUMLAR`'a eklendi (5973/5986/10962 "şirket" tanımı);
  10962 m.17 ve m.22 (yalnız bilişim, alıntılı) sektörü ["arge","ihracat"] yapıldı, DB tur33 yedeğinden geri alınıp
  yeniden uygulandı; kapsam aracında başlığında " — " olan kart ayrıştırma hatası düzeldi. Kapsam tur32 → tur33:
  kayıt VAR 385 → 396, İNCE 60 → 49, BOŞ 23 → 23 (gerçek: şirketsiz finansman/Ar-Ge), ürün 410 → 421/468, gerileyen 0.
  Ölçüm dayanak 0, isabet 41/41; test 1273. Önizlemede: yurt içi fuar (303.563 / 1.000.000 TL), TİM Wings.
  Kalan araştırılmış ama eklenmeyen: 10962 m.16, 18-21, 23, 24, 26-32; Eximbank IBRD Yeşil İhracat, AYB.
- **Tur34** (2026-10-12, `scripts/fix_veri_2026_10_12_tur34.py`; resmî alan adları gib, mevzuat, tarsim, tmo,
  ziraatbank, halkbank, tarimkredi, tubitak, hmb ile genişledi; `--metin URL` ve `--dogrula-tek SLUG` eklendi): 4 Sonnet
  araştırma ajanı 48 kayıt, 48/48 doğrulandı, UYGULANDI (yedek `tesvikler_oncesi_tur34.db.bak`): 10962 kalan 21 madde
  (m.16, 18-21, 23-33, 35, 38-41), Eximbank 8 (IBRD Yeşil İhracat, AYB, finansal kiralama, faizsiz finansman/SÖİF, 3
  sigorta), vergi/girişimci 10 (GVK 20/B, genç girişimci istisnası, Halkbank esnaf Hazine kredisi, 4691 x2, 5746 x3,
  KOSGEB girişimcilik eğitimi, Bağ-Kur genç girişimci desteği — 7566 sayılı Kanunla 1/1/2026'dan kaldırıldı, pasif),
  tarım 9 (Fındık Temel Desteği; Fındık ABGD sona erdi — son ödeme 2024, pasif; TARSİM 2026 prim desteği %50/%70;
  Ziraat/TKK Hazine faiz destekli kredi; iyi tarım; fidan; lisanslı depo kira; organomineral gübre; Küçük Aile İşletmesi
  sona erdi). İki GİB ve beş 8859 kaydı aynı belgeye bağlıydı → `#madde` parçası (kaynak_url tekilliği). 317 → 365.
- **2026 tarım birim değeri**: `app/tarim_destek_2026.py` 310 TL/da kullanıyordu; 11781 sayılı CB Kararı (RG
  08.09.2026) 2026 için 367 TL (2027: 442 TL). Katsayılar BUGEM 2026 tablosundan doğru (10394 sayılı Karar, RG
  14.09.2025 tabloları değiştirdi: mısır 2. kategori, tohum 0,56, organomineral 0,32). Fındık 3. kategori → 550,50
  TL/da; fındıkta destek yalnız izinli ilçelerdeki parsellere (8859 m.6/4, 11781 m.4). Kanıt
  `docs/olcum/2026-10-12-tur34/TARIM_2026_KANIT.md` (RG sayfaları görüntü olarak okundu). Tarım kazıyıcısının tohumu
  artık doğrulanmış DB'den üretilir (`app/data/tarim_bakanligi_tohum.json`, `python -m app.scrapers.tarim_bakanligi
  --tohum-uret`); eski elle yazılmış tohumdaki kaynaksız "Tarımsal Makineleştirme" (bireysel traktör vaadi) ve "Sulama
  Yatırımı" kayıtları ayın 5'inde eski adlarıyla yeniden eklenecekti (başlık değişmişti).
- **Tur35** (`scripts/fix_veri_2026_10_12_persona_tur35.py`, self-test 10/10, yedek `tesvikler_oncesi_tur35.db.bak`):
  Ticaret Bakanlığı 5973/5986/10962 kayıtlarına şirket türü kısıtı (limited/anonim/kooperatif) + aynı Kararın alıntılı
  "Şirket olmak" maddesi; 10962 m.38-41 TİM/birliklere → `araci_kurulus`; KOSGEB girişim sermayesi fonu → aracı; TİM
  Wings kadın hedef kitlesi; TURWIB kadın önceliği; GVK 20/B şirketsiz kişiye açık; tarım alt sınırları 367 ile; 160
  hububat 2026 tabloları; 161'den fındık (`urun_haric`), 364 ve 365'e ürün listesi (8859 Tablo 10 ve 6).
- **Tur36** (`scripts/fix_veri_2026_10_12_limit2026_tur36.py`, self-test 7/7, 19/19 doğrulandı, yedek
  `tesvikler_oncesi_tur36.db.bak`): 5973 kayıtları Karar taban tutarlarını gösteriyordu (yurt dışı fuar 150/250/750 bin
  TL) → Bakanlığın 2026 üst limit tabloları (4 PDF; `docs/olcum/2026-10-12-tur34/limit_2026_5973.json`): ör. fuar
  738.563 / 1.231.848 / 3.698.274 TL, küresel tedarik zinciri 73.990.020 TL. Eski tutarlı kontrol maddeleri "Karar
  tabanı" notuyla işaretlendi.
- **Persona denemesi** (`docs/olcum/2026-10-12-persona/persona_olc.py`, self-test 5/5; Rekortiv (şirketsiz, 20/B), 9 da
  fındık (Ordu), 1,5 da çilek (Aydın), matbaa, sürücü kursu, 5 KOBİ, 10 İKAS mağazası; 45 senaryo; `--out` ile ara
  deneme): 5 Sonnet hakem. Tur 1 (`tur1/`, `degerlendirme_*.json`) ortalama 2,40 (kritik 35). Düzeltmeler:
  ihtiyaç türleri sigorta/tanıtım/tescil/lojistik/tarım ödemesi; eşleştirmede ihracat ilgi cezası (görünen skor
  düşmez, sıra), yaş/hedef kitle cezası, tavansız sıralama (`siralama`), özgül hedef ağırlığı, çalışan/mağaza eşiği,
  10962 Atılım sektör (NACE) ve alt sektör kapsamı, kültür/turizm belge kapsamı, başka ürün/ürün listesi, durum
  programları (refinansman, istihdamı koruma), `ilgi_cezalari=False` (hazırlık karşı-olgusu); yanıtta tarım doğrudan
  ödeme hesabı, "şirket kurarsam" varsayımı (+BiGG ortaklık uyarısı) ve şirketsiz boş sonuçta varsayımsal arama,
  kredi etiketi, kurum sorusunda ihtiyaç notu, sıralama anahtarı (ihtiyaç → kilit → çok ihtiyaç → kredi/vergi →
  ölçek → dar kitle → eşleşme ilgisi), "Belirlenemedi" → "Şarta bağlı", tekrar azaltma, EN_COK_KART 3; 9903 EK-3
  "hariç" alt kolları (85.53 → uygun değil); girişim HUKS şirketsiz gelir. Tur 2 (`degerlendirme2_*.json`): A 2,97 ·
  B 2,75 · C 2,95 · D 2,78 · E 3,08 (tur 1: 2,14 · 2,50 · 2,46 · 2,14 · 2,82). Testler: `tests/test_persona_2026_10_12.py`
  (37). Regresyon: eski 30 senaryo dayanak 0, isabet 41/41; kapsam kayıt 420/25/23, ürün 434/468 (tur33: 421; tarım ×
  Ar-Ge 11 hücrenin eski "isabeti" sahteydi: çiftçiye gemi-yat tasarım desteği). Test 1306 → 1312.
  Ders: Bash heredoc `\\` dizisini tek `\` yapıyor (`\b` backspace oldu) → yamalar Write ile betik dosyasına.
  Tur 3 (`tur3/`, `degerlendirme3_*.json`): A 3,14 · B 2,92 · C 2,72 · D 2,64 · E 3,00. Düzeltmeler: dışlama şartı
  ("... olmamak", "yapamaz", "bünyesindeyseniz") kilit sayılmaz; sona eren programa "takip edin" denmez; ön onay
  darboğazı yalnız kural cümlesinde; dar kitle kilitten önce; soru bir ihtiyacı soruyorsa "hedeflerinizde yok" notu
  gizlenir; BiGG uyarısı Mükemmeliyet Mührü aşamasını alıntılar; sermaye şirketi kuralı sayısal eşikli şartı (Ar-Ge
  merkezi) karşılamaz; şahıs/şirketsizde soruya yönelik şirket-kapalı şemsiye program değerlendirmeye girer;
  çalışan eşiği ve "0-1 yaş işletme" profilden ("şirket kurarsam" varsayımında kuruluş = bugün) sağlanır; soru
  ihtiyacına uyan programa "örtüşmüyor" yazılmaz; kurulu işletmenin girişim dışı kurum sorusunda girişim programı
  ve parasal olmayan eğitim (e-Akademi; başlık "girişimcilik eğitimi" → girişim ihtiyacı) geride; yurt içi
  reklam sorusunda "yalnız yurt dışına yönelik" uyarısı. Veri (tur35 genişletmesi): e-Akademi (330) tüm şirket
  türlerine açık. [YANLIŞ, tur37'de geri alındı: YÖNDE (5) kaydın eski `detay` metnine göre "%80, 280.000 TL, imalat
  küçük/orta" diye daraltılmıştı; canlı sayfa %100 / 700.000 TL / sektör-ölçek şartsız. Bu daraltmanın kapsamda
  yarattığı 434 → 410 düşüşü de gerçek değildi.] Eski 30 senaryo dayanak 0,
  isabet 41/41. Test 1312 → 1314.
  Tur 4 (`tur4/`, `degerlendirme4_*.json`): A 3,14 · B 2,89 · C 2,83 · D 2,83 · E 3,00 (ortalama 2,94; tur 3: 2,88).
  Düzeltmeler: 9903 EK-3 verisinde sütun kayması (30 kalem; `scripts/fix_ek3_9903_2026_10_12.py`, her metin resmî
  metinle birebir doğrulanır, self-test 7/7): 55.1 "50 oda ve üzeri", 18 matbaa "100 milyon TL ve üzeri tevsi ve
  modernizasyon", 82.2 "yalnız 6. bölge", 24.10.08/35.11/35.12/52.22.06 komşu kodun metni; sorudaki yatırım tutarı
  (`soru_yatirim_tutari`) EK-3 kalem eşiği ve MADDE 5/2 asgari sabit yatırımla kıyaslanır (`tutar_siniri`), "teşvik
  belgesi" sorusunda kısa cevapta Hedef Yatırımlar hükmü; tutar yoksa 9903 kartında ve kısa cevapta asgari yatırım,
  Bilgi Eksikliği'nde yatırım tutarı sorusu; asgari yatırımı yıllık cirodan büyük 9903 programı geride.
  "Yenilemek/tadilat" yatırım ihtiyacı (belge/bahçe yenileme değil); 2634 turizm kaydı yatırım ihtiyacı. İstihdam:
  işe alınacak kişiye bağlı şart (`KISI_ONEKI`; kadın/genç, işsizlik ödeneği, engelli, sosyal yardım) kilit sayılmaz,
  kart adayıdır; sıra geniş işe alım teşviki → genel prim desteği → dar kişi grubu → istihdam dışı; retrieval'da dar
  grup cezası. USD ihracat/gelir eşiği şart metninden de okunur (`usd_esigi`; m.17, m.33); TOBB üyeliği limited/anonimde
  sağlanır (5174 m.9); e-ihracatın beyannameyle tevsiki kilit şart; Instagram/Google reklam sorusunda pazaryeri içi
  reklam geride; düşük olasılıklı program öne çıkmaz; kapalı programın alternatifi kapalı programın ve sorunun
  ihtiyacını karşılamalı; KOSGEB veri tabanı kaydı ücretsiz eğitimde ön koşul değil; yol haritası ön koşulu ilk
  kartın, diğerleri program adıyla. Test 1314 → 1321; eski 30 senaryo dayanak 0, isabet 41/41; kapsam değişmedi.
  Tur 4 sonrası ikinci paket: kurum sorusunda kısa cevapta kurumun bütün programları "engel yok / şarta bağlı /
  size kapalı (gerekçe)" diye gruplanır (kapalılar alt listede yinelenmez) ve aramadan elenen ama soruya yönelik kurum
  programları da değerlendirilir; sorudaki gider kalemi (yazılım/donanım, kargo, kira, fuar, makine, komisyon) programın
  desteklediği giderle eşleşir (`gider_kalemi_eslesmesi`; ERP sorusunda KOBİ Dijital Dönüşüm öne); "belirtilmemiştir"
  cümleleri ve çift nokta tekrarlanmaz; iki sektör gerekçesi tekleşir. Eşleşme listesinde çağrısı kapanmış program,
  ölçeği (asgari yatırım, kredi tavanı) cirodan büyük program ve USD eşiğine ulaşılamayan program sıralamada geride
  (`esles`, uygunluk değil ilgi). Test 1321 → 1324.
  Tur 5 (`tur5/`, `degerlendirme5_*.json`): A 3,14 · B 3,14 · C 2,94 · D 2,86 · E 2,97 (ortalama 3,01; tur 4: 2,94).
  Düzeltmeler: YÖNDE geri alındı (`scripts/fix_veri_2026_10_12_yonde_tur37.py`, self-test 6/6, yedek tur37; canlı
  sayfa 2026-10-12 08:12 `docs/olcum/2026-10-12-tur34/kaynak/9ef78a8d785053a6.txt`; `detay` canlı metinle değişti;
  tur35 betiğinden YÖNDE kalemleri çıkarıldı). Ders: kaydın `detay` alanı eski sayfa sürümü olabilir; daraltıcı veri
  değişikliğinden önce canlı sayfa yeniden çekilir. Çalışan eşiği kuralı Ar-Ge/tasarım personeli ve tam zaman eşdeğer
  şartlarını kapsamaz (65 çalışanlı firmada Ar-Ge merkezi 50 personel şartı "sağlandı" sayılıyordu), bu şartlar kilit;
  TRL ≤ 6 girişim sinyali yalnız mikro/küçük işletmede (orta/büyük A.Ş.'ye HUKS bloğu gösterilmez). TARSİM'de ürün
  oranı kaydın listelerinden (`sigorta_orani_satiri`: %70 listesi, kış donu listesi, açık alan meyve teyidi); 5986
  hedef ülke listesi sorudaki ülke/bölgeyle (Körfez) eşleşir (`hedef_ulke_satiri`); "pazaryerlerinde" gibi ekli
  biçimler pazaryeri sorusu; pazaryeri sorusunda pazaryeri dışı program ad eşleşmesinden önce geride; yalnız girişim
  ihtiyaçlı kurum sorusu ("şirket kurarsam KOSGEB ve TÜBİTAK") genel kurum sorusu sayılır. Kapsam 396/49/23 →
  432/13/23, ürün 410 → 434. Test 1324 → 1329.
  Tur 5 sonrası ikinci paket: "belirtilmemiştir" tekrar süzgeci cümle sınırında başlar, kalın işareti ve parantezi
  yutmaz (tur 5'te "**Başvuru dönemi:" açık kalıyor, "(MADDE 5 … belirtilmemişse)" kesiliyordu); eşleşme panelinin
  sıralama notları ("hedeflerle eşleşme bulunamadı", "sektörden bağımsız", ölçek, kapalı dönem, USD eşiği) yanıt
  kartına taşınmaz (`_PANEL_NOTU`); uygun olmayan lider programın tutarı kısa cevapta yalnız tutar sorulursa; TOBB'a
  bağlı oda/borsa üyeliği varyantı; EK-3'te "X kodları desteklenmez" cümlesi profil kodu X değilse şart sayılmaz
  (halı 13.93 uygun; eski test 13.20'yi şartlı bekliyordu, 18.12'ye taşındı). Açık: 13.10.12'de "500 milyon TL üzeri
  modernizasyon hariç" istisnası kesin "uygun değil" sayılıyor (persona yok). Test 1329 → 1333.
  Tur 6 (`tur6/`, `degerlendirme6_*.json`): A 3,20 · B 3,31 · C 2,81 · D 2,84 · E 3,14 (ortalama 3,06; tur 5: 3,01;
  doğruluk ortalaması 3,67). Düzeltmeler: "kredi ya da hibe" sorusunda hibe tarafı hükmü (`hibe_satiri`; geri ödemesiz
  program varsa adı, yoksa "kayıtlı hibe yok"); temel destekteki fidan ek kalemi ürün fidan listesinde yoksa kartta
  işaretlenir (`fidan_kalemi_notu`); "X üreticisiyseniz" maddesi başka ürünün üreticisine gösterilmez; toplam
  sorusunda şarta bağlı ekler kayıttaki katsayılarla (gübre 0,32, iyi tarım 0,4–0,7; türetilmiş TL yazılmaz, dayanak
  denetimi); şemsiye e-ihracat kaydında statüsüz şirketin kalemleri kaydın cümlesiyle (`statusuz_kalem_satiri`);
  yalnız ihtiyaç türü etiketli (Ar-Ge, ihracat, e-ticaret) kapsam sektör engeli değil (Küresel Rekabetçilik); kalıcı
  engel (sektör) ölçekten önce yazılır; "yurt dışı ortaklı ... başvurusu yapılmış olmalı" kilit; başlıktaki imalata
  özel oran imalat dışı işletmede kapsam notu. Kapsam 432/13/23 → 444/1/23, ürün 434. Test 1333 → 1337.
  Tur 7 (`tur7/`, `degerlendirme7_*.json`): A 3,20 · B 3,39 · C 2,83 · D 2,86 · E 3,14 (ortalama 3,08; tur 6: 3,06).
  Gerileme yakalandı ve düzeltildi: ihtiyaç-türü etiket istisnası (Ar-Ge/ihracat/e-ticaret) yalnız mal üreten
  (imalat) işletmede geçerli; otelde 5973 m.12 yeniden "uygun değil" (tur 6'daki kapsam 444 artışı bu sahte
  açılmaydı, 432'ye döndü). Hibe satırı sorudaki gider kalemini karşılamayan hibeyi "farklı bir gideri karşılar"
  diye verir; gider eşleşmesi olumsuz cümleleri ("alımı değil", "kapsam dışı") saymaz (cümle bölmeli süzgeç: tek
  regex karesel geri izlemeyle yanıtı 16 sn'ye çıkarıyordu); uygulanmayan fidan tutarı Destek satırından da çıkar;
  "Fındık için:" biçimli ürün maddesi başka üreticiye gösterilmez. Test 1337 → 1340.
  Açık (sonraki iş): eşleşme paneli sıralaması (halı/zeytinyağı panelinde 5973 tanıtım-fuar ailesi ilk 20'de yok,
  Eximbank kredileri baskın; teknopark ve "önce başka programa kabul" kayıtları ilk 10'da); şahıs işletmesine esnaf
  kredisi (9436) ve genç girişimci istisnasının yanıta girmemesi (aday havuzu); İhracat Destek Finansmanı/Reeskont
  gibi "uygun faiz" ürünlerinin seçilmemesi; Hazine faizli tarım kredisinde "basınçlı sulama +10 puan" satırı;
  kurum sorusunda ilk satır hükmü; yanıt uzunluğu (12-17 KB); kaynak dışı: TKDK/IPARD, KKYDP, 3308 çırak katkısı.
- **Kalan eksikler turu** (2026-10-12, tur 7 sonrası): panel sıralaması — etiketleri yalnız ihtiyaç türü olan program
  (5973 fuar/tanıtım/marka) hedef eşleşmesinde sektör eşleşmesi kadar güçlü (0,6); finansman hedefi olmayan profilde
  kredi/kefalet ürünlerine yalnız sıralama cezası (`sira_cezasi`, görünen skor değişmez); gemi/yat tasarım desteği yalnız
  NACE 30.1/33.15 (5973 m.16 kural maddesi); teknopark istisnaları Ar-Ge sinyali olmayan profilde geride. Panelin ilk
  10'undan sorudaki ihtiyaca uyan en çok iki program aramaya eklenir (`rag.panel_adaylari_ekle`; dayanak bağlamına da
  girer). "X kategorisi:" alt kategori şartı kilit değil (esnaf kredisi); hedef kitle önceliği büyük ölçekli pakete
  verilmez; "uygun faiz" sorusu TCMB/faizsiz ürünleri öne alır; sulama sorusunda kredi tablosundaki "Basınçlı sulama"
  satırı alıntılanır (`konu_satiri`); kurum sorusunda ilk satır "Kısa hüküm"; EK-3 istisnalı dışlama (13.10.12: yalnız
  500 milyon TL üzeri modernizasyon) şartlı; üçüncü kart yalnız engelsiz ve ihtiyaca uygunsa, teyit kutusu 6 → 4,
  kapalı listesi en çok 6 satır (ortalama yanıt 12.358 → 11.479 karakter); hibe satırı açık hibe yoksa kapalı hibeyi
  adıyla anar. Doğrulama hattı (tur21) düzeltmesi: HTTP başlığında charset yoksa sayfanın meta charset'i (Resmî Gazete
  windows-1254 "ı" → "ý" bozulup bütün alıntılar düşüyordu); sıfırsız tarih biçimleri ("29/4/2026").
  Tur38 (`scripts/fix_veri_2026_10_12_tur38.py`): KKYDP (Tebliğ 2026/9-2026/10, 2026 dönemi 29/4-30/6 kapalı; 23 madde
  doğrulandı, görüntü PDF'indeki EK-2 oranları doğrulanamadığı için alınmadı); IPARD III M1 (28.07-07.09.2026) ve M3
  (12.06-20.07.2026) çağrıları zaten kayıtlıydı (tur38 yalnız adla karşılaştırıp ikinci kez ekledi; yinelenen
  satırlar silindi, eşleşme artık kapanış tarihiyle), M7'de 2026 çağrısı yok. 3308 sayılı Kanun Geçici 12. madde
  "Mesleki Eğitim Devlet Katkısı" (çırak/stajyer ücretinin 2/3'ü 20 kişiden az, 1/3'ü 20+ işletmede; 8 madde, 17 alıntı
  doğrulandı; sürüp sürmediği teyit edilemediği için `aktif_mi` boş). Yedek `tesvikler_oncesi_tur38.db.bak`.
  Hibe satırı konuya bakar: "Hibe değil, faiz indirimi" yazan kredi hibe sayılmaz (`hibe_mi`); sorunun konu sözcükleri
  (`soru_konulari`, genel teşvik sözcükleri hariç) açık hibede yoksa ve konuya uyan hibe kapalıysa yanıt önce kapalı
  olanı adıyla anar (damla sulama: TSS kapalı; Sera hibesi "farklı bir gideri karşılar"); bunun için arama da
  konuya uyan kapalı hibeyi adaylara ekler (`rag.panel_adaylari_ekle`). `_kredi_mi` artık "proje_bazli_tavan"
  niteliğini kredi saymaz (toplama girmez ama hibedir; KKYP/TSS/ajans hibeleri hibe satırından düşüyordu).
  Tur40 (`scripts/fix_veri_2026_10_12_tur40.py`, self-test 6/6): tur38'in KKYDP kaydı mevcut 78 (KKYP, Tebliğ 2026/9)
  ve 80'in (TSS, 2026/10) kopyasıydı; arama asıl kaydı geride bırakınca eski-30 isabeti 41 → 37'ye düştü. Kopyanın 24
  doğrulanmış maddesi (19 → 78, sulamaya ait 5 → 80) ve iki çağrısı taşındı, 78/80'in başvuru süresi uzatmayla
  güncellendi (29 Nisan – 30 Haziran 2026; ilk ilan 12 Haziran), kopya silindi, tur38 kayıt dosyası `birlesen/` altına
  alındı (tur38 yeniden çalışınca geri gelmesin). Yedek `tesvikler_oncesi_tur40.db.bak`. Ders: yeni kayıttan önce
  aynı Resmî Gazete URL'sine bağlı kayıt aranmalı.
- **Groq kayıt önerici** (`scripts/groq_kayit_onerici.py`, self-test 7/7): yalnız kamu mevzuat metnini (mevzuat.gov.tr
  PDF'i) Groq `openai/gpt-oss-120b`'ye verir ve kayıt taslağı ister; kullanıcı/kurum/ikas verisi gönderilmez,
  uygulamanın çalışma anındaki LLM yolu (`app/llm_saglayici.py`) değişmez. Model alıntıları birebir vermek zorunda;
  taslaklar `docs/olcum/2026-10-12-tur39/oneri/` ve `kayit/` altına, harcama `harcama.json` defterine yazılır (tavan
  1 USD). Taslak DB'ye doğrudan girmez: `scripts/fix_veri_2026_10_12_tur39.py --dogrula` (tur21 doğrulayıcısı) her
  alıntıyı resmî metinde arar, ancak geçenler `--uygula` ile eklenir. Aynı kanuna (mevzuat.gov.tr 1.5.<no>) bağlı
  kayıt varsa görev çalıştırılmaz (`cakisan_kayitlar`; 5746 görevi bu yüzden kaldırıldı: 281/333/334/335 zaten
  var). Kalan görev `gorevler.json`: 3065 KDV m.11 ihracat istisnası. Çalıştırmak için `.env` içine `GROQ_API_KEY`
  gerekir (tahmini en çok 0,008 USD).
- **Deterministik başvuru orkestratörü** (`app/basvuru_orkestrator.py`, self-test 10/10, `tests/test_basvuru_orkestrator.py`
  6): şirket profili + harcama dökümünden 10 adımda (ayrıştırma, mevzuat eşleştirme, KOBİ/KOSGEB, hedef ülke, mükerrerlik,
  DYS, A-D stres testi, onarım, gerekçe, JSON) üç bölümlü çıktı. Oran, tavan (2026), şart ve hedef ülke listesi kayıtlardan;
  kayıtta olmayan kalem "Kapsam Dışı / İncelenmeli"; dış dil modeli yok. Şablondaki düzeltilen varsayımlar: e-ihracat
  kalemleri 5986 (5973 değil); hedef ülke ilavesi kayıtta yalnız 5986 m.4/m.5/m.6 için %70; KOSGEB "Yurt Dışı Pazar
  Destek Programı" güncel kayıtlarda yok; KDV esası ve ilişkili taraf kuralı kayıtta yok (İncelenmeli). Demo:
  `docs/olcum/2026-10-12-orkestrator/demo_A-D.md`.
- SMTP: `.env`'de SMTP_* dolu ama gönderim "Connection unexpectedly closed" ile düşüyor (port 587); kimlik/sunucu
  doğrulanmalı. Doğrulama zorunlu kayıt bu düzelmeden açılmamalı.
- Açık: 76 hayvancılık birim tutarı (OCR), 163 e-ticaret üyelik limiti (5973 Genelge), 37 ve 73 kararsız (sayfa
  yetersiz), Sentry için DSN (AB bölgesi) ve KVKK metnine eklenmesi.

## Komutlar
- Test: `PYTHONIOENCODING=utf-8 python -m pytest -q` · Lint: `python -m flake8 app/ tests/ scripts/ --select=E9,F63,F7,F82,F401,F811`
- Sunucu: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` · Persona ölçümü: `docs/olcum/.../asama3_olcum.py`
- Test hesabı: test@example.com (şifre `scripts/seed_test_hesabi.py` TEST_SIFRE), AI rızası kapalı bırakılır.
