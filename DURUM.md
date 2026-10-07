# DURUM — Teşvik Asistanı denetim çalışması

Son güncelleme: 2026-10-07 (Denetim 2 / Aşama F sonu). Oturuma bunu okuyarak başla.

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
- Kökteki `tesvik.db` 0 baytlık artık dosya; gerçek DB `data/tesvikler.db`.

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
- **Denetim 2 / Aşama G** (tamamlandı): sentetik profil denemesinden çıkan eşleştirme/arama/bütçe düzeltmeleri, rapor `docs/olcum/2026-10-07-denetim2/G_RAPOR.md`. Test 810. Tur4 ve Tur5 veri düzeltmeleri UYGULANDI (8, 81, 7, 142, 3, 125, 9, 107 kapsam/ölçek; yedekler *.db.bak).
- Açık: 76 hayvancılık tutarı (OCR), 163 e-ticaret üyelik limiti (5973 Genelge), 10 kararsız akademik kayıt,
  profil düğmeleri stilsiz, kayıt sonrası onboarding yok.

## Komutlar
- Test: `PYTHONIOENCODING=utf-8 python -m pytest -q` · Lint: `python -m flake8 app/ tests/ scripts/ --select=E9,F63,F7,F82,F401,F811`
- Sunucu: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` · Persona ölçümü: `docs/olcum/.../asama3_olcum.py`
- Test hesabı: test@example.com (şifre `scripts/seed_test_hesabi.py` TEST_SIFRE), AI rızası kapalı bırakılır.
