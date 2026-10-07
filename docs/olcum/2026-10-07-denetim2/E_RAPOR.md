# Denetim 2 / Aşama E — güvenlik ve hesap akışları (2026-10-07)

Doğrulama ortamı: üretim DB'sinin geçici kopyası, uvicorn :8001, Chrome (salt okunur gezinti + test hesabı). Gerçek e-posta gönderilmedi, SMTP tanımlı değil.

## 1. CSP (içerik güvenlik politikası) — eklendi
- `app/main.py` middleware: yalnızca HTML yanıtlara; `/docs` ve `/redoc` muaf (Swagger CDN'den script yükler).
- Politika: `default-src 'self'`, `script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com`, `style-src 'self' 'unsafe-inline'`, `img-src/font-src 'self' data:`, `connect-src 'self'`, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, `frame-ancestors 'none'`.
- **Bilinen kalan risk:** `'unsafe-inline'` kaldı çünkü paneller `onclick` gibi satır içi olay yöneticileri kullanıyor (index 7, dashboard 7, çilek 8). Enjekte edilmiş satır içi script'i bu politika engellemez; asıl koruma çıktı kaçışı (aşağıda). Kaldırmak için olay yöneticilerinin nonce'lu `addEventListener`'a taşınması gerekir.
- Tarayıcı doğrulaması: giriş sayfası, dashboard (profil bölümü), çilek paneli, KVKK sayfası yüklendi; konsolda CSP hatası yok, `securitypolicyviolation` olayı 0. Çilek paneli Tailwind'i CDN'den yükleyip çalışıyor (konsolda "üretimde kullanmayın" uyarısı var).

## 2. XSS denetimi
| Sayfa | Bulgu | Sonuç |
|---|---|---|
| `cilek_dashboard.html` | API metinleri (parsel adı, mesajlar, tank tipi vb.) kaçışsız `innerHTML`'e giriyordu: **kalıcı XSS** (kullanıcının girdiği parsel adı) | `api()` yanıtındaki tüm metinler tek noktada HTML-kaçışlanıyor |
| `index.html` | `innerHTML` yalnızca sabit metin ("Giriş Yap", yükleme göstergesi) | Açık yok |
| `dashboard.html` | Denetim 1'de kaçışlandı | Değişiklik gerekmedi |

Kanıt (tarayıcı): parsel adı `<img src=x onerror="window.__xss=1">Parsel-A` ile oluşturuldu; panelde 44 karakterlik **düz metin** olarak görünüyor, sayfada `img` etiketi 0, `window.__xss` tanımsız. Not: sunucu tarafı giriş uzunluğu sınırı yok (`ParselCreate.ad`), çıktı kaçışına güveniliyor.

## 3. İKAS webhook
- **Bulgu:** `POST /api/ikas/webhook/order-created` kimlik doğrulamasızdı; herkes herhangi bir mağaza için senkronizasyon (dış API çağrısı + DB yazımı) tetikleyebiliyordu.
- **İKAS belgesi (ikas.dev, Webhooks ve WebhookInput sayfaları, 2026-10-07):** yalnızca `endpoint`, `scopes`, `salesChannelIds` tanımlı. **İmza/secret mekanizması ve gövde şeması belgelenmemiş.** İmza doğrulaması uydurulmadı.
- **Yapılan:** mağazaya özgü HMAC-SHA256(`SECRET_KEY`, mağaza) belirteci adrese eklendi (`/api/ikas/webhook/order-created/{belirtec}`); sabit zamanlı karşılaştırma, bağlı olmayan mağaza ve yanlış belirteç 401, eski belirteçsiz adres kaldırıldı. `GET /api/ikas/durum` kullanıcıya kendi `webhook_url`'sini verir. 7 test.
- **Açık:** uygulama webhook'u İKAS'ta kaydetmiyor; mağaza sahibinin bu adresi elle (`store/order/created`) kaydetmesi gerekir. `SECRET_KEY` değişirse belirteçler geçersiz olur.

## 4. Parola sıfırlama ve e-posta doğrulama — eklendi
- Uç noktalar: `POST /api/auth/sifre-unuttum`, `POST /api/auth/sifre-sifirla`, `POST /api/auth/eposta-dogrula`, `GET /api/auth/me`, `POST /api/auth/dogrulama-gonder`; sayfalar `/sifre-sifirla`, `/eposta-dogrula`; girişte "Şifremi unuttum" bağlantısı; dashboard'da doğrulanmamış e-posta uyarısı.
- Tasarım: tek kullanımlık, amaca bağlı belirteç (sıfırlama 1 saat, doğrulama 48 saat); DB'de yalnızca SHA-256 özeti; yeni istek öncekini iptal eder; hesap var/yok **aynı yanıt** (numaralandırma yok); IP başına 5/dk ve e-posta başına 3/saat sınırı; pasif hesaba posta gitmez; sıfırlamada parola politikası aynen geçerli; bağlantı `#` (fragment) kısmında taşınır ve sayfa okuyunca adresten siler; SMTP arka planda gönderilir, SMTP yoksa istek yine başarılı, günlüğe uyarı düşer.
- Göç: `g4b6c8d0e456` (tablo + `users.email_dogrulama_zamani`), kopya DB'de yukarı/aşağı/yukarı denendi. **Üretim/geliştirme DB'sine uygulanmadı.**
- Doğrulama: 16 birim/entegrasyon testi + tarayıcıda uçtan uca (belirteç → yeni parola formu → "Parolanız güncellendi"; yeni parola giriş 200, eski parola 401, aynı belirteç ikinci kez 400; fragment adresten silindi).
- Bulunan yan hata: `app/email.py`'de aynı adlı, kullanılmayan eski bir `send_password_reset_email` (farklı imza, "24 saat") yenisini ezecekti; kaldırıldı.
- **Giriş e-posta doğrulamasına bağlı değil** (yalnızca hatırlatma). Bağlamak ürün kararı.
- Bilinen sınırlar: parola değişince eski JWT'ler 7 gün geçerli kalır; kayıt "Bu email zaten kullanımda" diyerek e-posta numaralandırmaya izin veriyor (giriş ve sıfırlama vermiyor).

## 5. KVKK aydınlatma metni — **bilgi bekleniyor**
`app/static/kvkk.html` içinde `DOLDURULACAK` işaretli alanlar: ticaret unvanı, adres, VERBİS kayıt durumu, başvuru/iletişim kanalı (KEP veya e-posta), saklama süresi (satır 228), başvuru adresi (satır 250). Bu bilgiler şirket kuruluşuna bağlı, uydurulmadı. Metin bu alanlar dolana kadar yayına hazır değil.

## Test ve komutlar
Test sayısı 775 → 791 (1 atlandı), flake8 hata sınıfları 0. SMTP sağlayıcısı ve KVKK bilgileri gelince: `.env`'ye SMTP değerleri, `alembic upgrade head`, `/kvkk` alanları.
