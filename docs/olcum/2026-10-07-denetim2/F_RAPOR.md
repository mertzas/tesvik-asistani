# Denetim 2 / Aşama F — kapanış (2026-10-07)

## Karar: yayına hazır mı?

**HAYIR, ödeme alan genel yayın için hazır değil.** Kapalı beta (ödemesiz, davetli kullanıcı) için aşağıdaki "Yayından önce" listesindeki ilk dört madde kapandığında hazır olur.

**Gerekçe (kanıtlı engeller):**

| # | Engel | Kanıt |
|---|---|---|
| 1 | **KVKK aydınlatma metni eksik** (yasal) | `kvkk.html`'de ticaret unvanı, adres, VERBİS durumu, başvuru kanalı, saklama süresi `DOLDURULACAK`; şirket kuruluşuna bağlı, uydurulmadı |
| 2 | **SMTP tanımlı değil** | Parola sıfırlama/e-posta doğrulama kodda ve testte çalışıyor ama posta gitmiyor (günlüğe uyarı düşüyor); gerçek bir hesapla uçtan uca denenmedi |
| 3 | **Stripe test modunda** | `sk_test_` anahtarları; canlı anahtar ve webhook imzası üretimde denenmedi |
| 4 | **Dağıtım yapılandırması canlıda hiç denenmedi** | Docker/WSL bu makinede yok: compose, nginx, backup servisi ve `--workers 2` zamanlayıcı kilidi (Windows'ta iki süreç de kilidi aldı) Linux'ta doğrulanmadı |
| 5 | **Üretim modeliyle danışman ölçümü eksik** | Aşama C'de 12 sorunun 9'unu üretim modeli değil oturum modeli yazdı; akışta ilk parça/toplam süre ve maliyet gerçek modelle ölçülmedi (Anthropic kredisi bitti) |
| 6 | **Veri tazeliği** | 99 aktif kaydın 26'sında başvuru şartı, 46'sında tutar, 73'ünde süre boş; 12 kayıt kararsız (KKYP, TSS, Hayvancılık dahil); 37 aktif kayıt Denetim 2'de canlı sayfayla karşılaştırılmadı; kazınmış metin bir dönem geride kalabiliyor (kayıt 7) |

## Sayılarla iki denetim

| Ölçüt | Başlangıç | Şimdi |
|---|---|---|
| Test | 659 | 791 geçti, 1 atlandı |
| flake8 hata sınıfları | 21 uyarı | 0 |
| Teşvik kaydı | 186 | 186: 99 aktif, 75 kapalı, 12 kararsız |
| Denetim 2'de canlı kaynakla karşılaştırılan kayıt | 0 | 110 (82 düzeltme + 5 temizlik + 2 yeni kayıt) |
| Danışman: uydurma rakam | — | 0 (12 yanıt; 9'u oturum modeliyle) |
| Gerçek model çağrısı | — | Denetim 1: 10 (~1,1 USD); Denetim 2: 3 (~0,3 USD) |
| Yerel commit (push edilmedi) | — | 14 |

## Denetim 2'de bulunan ve kapatılan gerçek hatalar
1. Danışman bağlamı `tesvil_tutari` alanını hiç yazmıyordu; Aşama A'da düzeltilen 80+ kaydın limit/vade/oranı modele görünmüyordu (C).
2. Eurostars gibi özel adlardaki kesme işareti ekleri aramada terimi bozuyordu (C ön kontrolü).
3. SGK/İŞKUR işveren teşviki şirketsiz girişimciye öneriliyordu; hedefi ihracat olan imalatçıya E-İhracat kayıtları gelmiyordu; "süt ineği" sorusunda Organik Tarım 1. geliyordu (B).
4. Akış ortasında Claude bağlantısı kopunca kesik yanıt tam yanıt gibi gösteriliyordu (D).
5. Askıda Claude bağlantısı 271 sn bekletiyordu; 180 sn'ye indi (D).
6. Kilitli SQLite'ta `/health` 35 sn sonra yanlışlıkla 200 dönüyordu; 7 sn'de 503 (D).
7. Çilek panelinde parsel adıyla kalıcı XSS (E).
8. İKAS webhook'u kimlik doğrulamasızdı; mağaza belirteciyle korundu (E).
9. Parola sıfırlama ve e-posta doğrulama hiç yoktu (E); `email.py`'de yenisini ezecek ölü bir yöntem vardı.
10. Yanlış/eski kayıt metinleri: yapay zekâ kredisinde eksik **Teknogirişim Rozeti** şartı, İstihdamı Koruma'da önceki dönem kuralları, Eurostars 2026/2, BiGG eski 150.000 TL, TÜBİTAK ve KGF taşınan 46 kayıt adresi.

## Açık liste

### Yayından önce (engel)
- [ ] KVKK alanlarının doldurulması (kullanıcı/şirket bilgisi)
- [ ] SMTP sağlayıcısı + `.env` + gerçek e-postayla uçtan uca deneme
- [ ] `alembic upgrade head` her ortamda (geliştirme DB'sine **uygulandı**, 2026-10-07; yedek `tesvikler_oncesi_gocE.db.bak`)
- [ ] Linux'ta docker compose + nginx + `--workers 2` kanıtı (zamanlayıcı tek işçide); backup servisinin geri yükleme denemesi
- [ ] Stripe canlı anahtarı ve webhook imzası (ödeme alınacaksa)
- [ ] Üretim modeliyle Aşama C 4–12 tekrarı (~0,9 USD) ve akış gecikmesi ölçümü (10 çağrı, ~1 USD)

### Veri
- [ ] 163 e-ticaret üyelik güncel TL limiti (5973 Genelge eki)
- [ ] 48 Eurostars son başvuru tarihi (çağrı duyurusu PDF'inde; indirme izni gerekir)
- [ ] 76 hayvancılık birim tutarları (Karar 8760 taranmış PDF, OCR gerekir)
- [ ] 12 kararsız kayıt (78 KKYP, 80 TSS, 76 Hayvancılık önce)
- [ ] 37 aktif kaydın canlı sayfayla karşılaştırılması; kazınmış metinlerin periyodik yenilenmesi
- [ ] KOSGEB Yapay Zekâ Kredisi NACE listesi (sayfada "Desteklenen Sektörler" bölümü okunamadı)

### Kod
- [ ] CSP'den `'unsafe-inline'` kaldırma (olay yöneticilerini nonce'lu dinleyicilere taşıma); çilek paneli Tailwind'i CDN yerine derlenmiş CSS
- [ ] JWT iptal (parola değişince eski oturumlar 7 gün açık)
- [ ] Kayıtta e-posta numaralandırma (`Bu email zaten kullanımda`)
- [ ] Kilitli DB'de düz metin 500 yerine JSON hata; uzun yazan scraper için PostgreSQL
- [ ] `ParselCreate.ad` ve benzeri alanlarda sunucu tarafı uzunluk sınırı
- [ ] Hata izleme (Sentry vb.), `on_event` kullanımdan kalkma uyarıları
- [ ] Windows geliştirmede zamanlayıcı kilidi için `msvcrt` yedeği (isteğe bağlı)

### Ürün kararı (kullanıcıya ait)
- [ ] Girişi e-posta doğrulamasına bağlama (şimdi yalnızca hatırlatma)
- [ ] Ödemesiz kapalı beta mı, ödemeli genel yayın mı?
- [ ] Kayıt sonrası onboarding, profil düğmeleri stili, bütçe modülünde tek sektör kâr oranı (%5,8), kuruluş tarihi boşken KOSGEB Girişimci filtresi
- [ ] İKAS: webhook'u uygulama içinden kaydetme (şimdi mağaza sahibi elle kaydediyor)
- [ ] `git push` ve CI'nin yeniden koşulması (son yeşil koşu bu 14 commit'ten öncesine ait)

## Kapsam dışı kalanlar (bilerek)
Gerçek e-posta gönderimi, gerçek Stripe/İKAS hesaplarıyla işlem, Docker/Linux dağıtım denemesi, ücretli Claude çağrıları (onay ve kredi yok), PDF indirme.
