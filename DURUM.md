# DURUM — Teşvik Asistanı denetim çalışması

Son güncelleme: 2026-10-07 (Denetim 2 / Aşama B sonu). Oturuma bunu okuyarak başla.

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

## Sıradaki adım
- **Aşama C**: danışman yanıt kalitesi — 10 doğrulanmış soru (persona başına gerçek Claude çağrısı, ~1 USD, çıktı
  `docs/olcum/2026-10-07-denetim2/C_*.md`), her sayısal iddia kaynak sayfayla işaretlenir. Onay bekliyor.
- Aşama D (performans/dayanıklılık), E (CSP, parola sıfırlama, İKAS imza, KVKK alanları, cilek/index XSS), F (kapanış).
- Açık: 76 hayvancılık tutarı (OCR), 163 e-ticaret üyelik limiti (5973 Genelge), 10 kararsız akademik kayıt,
  bütçe modülünde tek sektör kâr oranı (%5,8), profil düğmeleri stilsiz, kayıt sonrası onboarding yok.

## Komutlar
- Test: `PYTHONIOENCODING=utf-8 python -m pytest -q` · Lint: `python -m flake8 app/ tests/ scripts/ --select=E9,F63,F7,F82,F401,F811`
- Sunucu: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` · Persona ölçümü: `docs/olcum/.../asama3_olcum.py`
- Test hesabı: test@example.com (şifre `scripts/seed_test_hesabi.py` TEST_SIFRE), AI rızası kapalı bırakılır.
