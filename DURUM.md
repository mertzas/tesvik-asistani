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
- SMTP: `.env`'de SMTP_* dolu ama gönderim "Connection unexpectedly closed" ile düşüyor (port 587); kimlik/sunucu
  doğrulanmalı. Doğrulama zorunlu kayıt bu düzelmeden açılmamalı.
- Açık: 76 hayvancılık birim tutarı (OCR), 163 e-ticaret üyelik limiti (5973 Genelge), 37 ve 73 kararsız (sayfa
  yetersiz), Sentry için DSN (AB bölgesi) ve KVKK metnine eklenmesi.

## Komutlar
- Test: `PYTHONIOENCODING=utf-8 python -m pytest -q` · Lint: `python -m flake8 app/ tests/ scripts/ --select=E9,F63,F7,F82,F401,F811`
- Sunucu: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` · Persona ölçümü: `docs/olcum/.../asama3_olcum.py`
- Test hesabı: test@example.com (şifre `scripts/seed_test_hesabi.py` TEST_SIFRE), AI rızası kapalı bırakılır.
