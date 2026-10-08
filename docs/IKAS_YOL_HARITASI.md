# Teşvik Asistanı × İKAS App Store — Yol Haritası

Tarih: 2026-10-08 · Kaynaklar: builders.ikas.com geliştirici belgesi (erişim 2026-10-08), `@ikas/api-client` 2.0.2
derlenmiş kaynağı (imza, webhook, OAuth, GraphQL tipleri), proje kodu ve testleri.

## 1. Durum özeti

İKAS'ın uygulama yayını için istediği **teknik akışların tamamı kodda hazır ve mock modda uçtan uca test edildi**
(31 yeni test + tarayıcıda kurulum → İKAS panelinden açılış → panel akışı). Yayına kalan işler kod dışı: İKAS Partner
hesabı, gerçek `client_id/secret`, HTTPS alan adında canlı sunucu, iki geliştirme mağazasında gerçek API denemesi ve
İKAS incelemesi.

| İKAS yayın şartı (belge) | Durum | Nerede |
|---|---|---|
| OAuth, İKAS panelinden kurulum ("Kurulum Adresi", Senaryo A) | Hazır | `GET /api/oauth/authorize/ikas?storeName=` |
| OAuth, uygulamadan bağlanma (Senaryo B) | Hazır | `GET /api/ikas/baglan` (oturumlu) |
| Callback adresi belgedeki kalıpla birebir | Hazır | `GET /api/oauth/callback/ikas` (eski yol da çalışır) |
| Callback'te `me` (authorizedAppId) + mağaza bilgisi, İKAS'a geri dönüş | Hazır | `https://{mağaza}.myikas.com/admin/authorized-app/{id}` |
| İKAS panelinden imzalı açılış (HMAC, 120 sn) | Hazır | `/ikas` sayfası → `POST /api/ikas/oturum` |
| İKAS arayüzüyle bütünleşme (panel içinde açılma) | Hazır | `/`, `/ikas`, `/dashboard` yalnız `https://*.myikas.com` tarafından çerçevelenebilir |
| İmzalı webhook doğrulama | Hazır | `POST /api/ikas/webhook` (HMAC-SHA256(client_secret, data)) |
| Uygulama kaldırılınca veri temizliği (`store/app/deleted`) | Hazır | belirteçler + sipariş özeti silinir |
| Token yenileme | Hazır | süresi 5 dk içinde dolan belirteç kullanılmadan önce yenilenir |
| En az 2 geliştirme mağazasında kurulum/test | **Bekliyor** | Partner hesabı gerekiyor |
| Doğrulanmış Partner hesabı | **Bekliyor** | Mert |
| İKAS incelemesi | **Bekliyor** | İKAS |

İmza doğrulamaları SDK'nın kendi JS fonksiyonlarıyla çapraz denendi: Python `giris_imzasi_uret` →
`validateAuthSignature` = `true`; `webhook_imzasi_uret` → `validateIkasWebhookSignature` = `true`.

## 2. Bu turda yapılanlar (2026-10-08)

**Uç noktalar**
- Kurulum akışı hesabı kendisi açar: İKAS `getMerchant` e-postası, unvanı ve ili ile kuruluş + kullanıcı + profil.
  E-posta başka hesapta kayıtlıysa **o hesaba bağlanmaz** (sahiplik kanıtı yok), yer tutucu adresle ayrı hesap açılır.
  Aynı mağaza yeniden kurulursa (merchantId) yeni hesap açılmaz, eski hesaba dönülür.
- Login-CSRF koruması: kurulum state'i httpOnly çerezle tarayıcıya bağlı, 15 dk ömürlü, tek kullanımlık.
- Mağaza adı süzgeci (`[a-z0-9-]`): authorize/token isteği başka ana bilgisayara yönlendirilemez.
- Webhook: sipariş olayı 10 dk'dan sık gelirse tam senkron ertelenir, panel açılınca tamamlanır (İKAS'a anında 200).
- `DELETE /api/ikas/baglanti`: kullanıcı bağlantıyı keser, saklı belirteçler ve özet silinir.

**Veri doğruluğu (canlıda yanlış sonuç verecek hatalar düzeltildi)**
- İptal/iade denetimi `orderPaymentStatus` alanına bakıyordu; `CANCELLED/REFUNDED` değerleri `Order.status`
  alanında. İptal siparişler ciroya giriyordu → düzeltildi; taslak ve upsell bekleyen siparişler de çıkarıldı.
- Sorgu `orderLineItems.productName` istiyordu; bu alan SDK şemasında yok (gerçek API'de sorgu hata verirdi) →
  `variant { name }`.
- Tek sayfa (100 sipariş) okunuyordu → sayfalama (200'lük, `hasNext`, en çok 50 sayfa) + sunucuda son 365 gün süzgeci.
- Döviz siparişleri TL ciroya ekleniyordu → TL ciro ayrı, döviz toplamları ayrı (kur çevrimi yok; İKAS
  `currencyRates` anlamı belgelenmemiş).
- Mock veri artık geçerli durum kodları, iptal/iade, döviz ve yurt dışı teslimat içeriyor.

**Evrak yardımı (İKAS satıcısına özgü)**
- Sipariş özetinden e-ihracat göstergeleri: yurt dışı teslimat sayısı, oranı, ülke kodları, döviz satışlar.
- Yurt dışı teslimat varsa profile "ihracat" hedefi eklenir → eşleşmede ilk sıraya **E-İhracat Destekleri (5986)**
  ve ihracat programları gelir (önizlemede doğrulandı).
- Başvuru ön taslağı, bağlı mağazanın toplamlarını (kişisel veri değil) bağlam olarak alır; model bunları "e-ticaret
  mağaza kayıtlarına göre" diye yazar ve ETGB/gümrük beyannamesiyle teyit edilmesini ister. KVKK metni güncellendi.
- Panelde "İKAS mağaza verisi" kartı: durum, son senkron, ciro, yurt dışı, döviz, notlar, yenile, bağlantıyı kes.

## 3. Yol haritası

Sorumlu: **M** = Mert, **İ** = İKAS, **K** = kod (oturumda yapılabilir).

### Faz 0 — İKAS ile ön görüşme ve kayıt (1. hafta)

| # | İş | Sorumlu | Çıktı |
|---|---|---|---|
| 0.1 | İKAS Partner hesabı açma ve doğrulama | M | Partner paneli erişimi |
| 0.2 | **Çözüldü (kod):** İKAS'ın Next.js şablonuna uyan kabuk yazıldı (`ikas-app/`, AppBridge girişi, İKAS paneli içinde çalışır). İKAS'a yalnızca teyit için sorulur: kabuk + ayrı API sunucusu mimarisi kabul ediliyor mu? | M → İ | Teyit |
| 0.3 | Uygulama kaydı: Kurulum Adresi `https://ALAN/api/oauth/authorize/ikas`, Redirect URI `https://ALAN/api/oauth/callback/ikas`, Uygulama adresi `https://ALAN/` (ALAN = kabuğun alt alan adı, ör. `ikas.tesvikasistani.com`) | M | `IKAS_CLIENT_ID`, `IKAS_CLIENT_SECRET` |
| 0.4 | Yetki kapsamı: yalnız `read_orders` yeterli; `read_products` kullanılmıyor → çıkarılması önerilir (en az yetki, inceleme kolaylığı) | M | `IKAS_SCOPE=read_orders` |
| 0.5 | **Sorulacak:** İKAS üzerinden satılan uygulamada faturalama İKAS planlarıyla mı zorunlu (TRY, yıllık, fiyat ≠ 0, `getMerchantLicence`) yoksa kendi Stripe aboneliğimiz kalabilir mi? Gelir paylaşımı (%15–20 teklifimiz) | M → İ | Ticari model kararı |

**Next.js kabuğu (2026-10-08, yapıldı):** İKAS'ın resmi başlangıç uygulaması (`ikas app init`, `github.com/ikascom/ikas-app-examples`) okunup aynı yapı ve AppBridge akışıyla `ikas-app/` yazıldı. Şablondan farkı: belirteçler ayrı bir Prisma veritabanında değil, yalnız FastAPI'nin şifreli tablosunda; kabuğun kendi sırrı yok. Ayrıntı ve canlıya alma: `ikas-app/README.md`.

### Faz 1 — Canlı altyapı (1–2. hafta)

| # | İş | Sorumlu | Not |
|---|---|---|---|
| 1.1 | Linux sunucu + HTTPS alan adı | M + K | İKAS webhook adresi **https** olmak zorunda, özel IP kabul edilmiyor |
| 1.2 | Veritabanı göçü `alembic upgrade head` (k8f0b2c4d890) | K | Yerel dev DB'ye uygulandı (yedek `tesvikler_oncesi_gocK.db.bak`); canlı DB'de yedek alınarak |
| 1.3 | `.env`: `IKAS_MOCK_MODE=false`, client id/secret, `APP_URL=https://ALAN`, `IKAS_TOKEN_KEY` (ayrı şifreleme anahtarı) | M | Sırlar sohbete yazılmaz |
| 1.4 | SMTP düzeltmesi (587'de "Connection unexpectedly closed") | M | Parola sıfırlama İKAS kullanıcısının panel dışı girişi için gerekli |
| 1.5 | Sentry DSN (AB bölgesi) | M | İlk gerçek kullanıcılardaki hataları görmek için |

### Faz 2 — İki geliştirme mağazasında gerçek API testi (2–3. hafta)

Mock ile doğrulanamayan, **gerçek API'de teyit edilecek** noktalar:

| Kontrol | Beklenen | Başarısızsa |
|---|---|---|
| Token yanıtı ve `expires_in` | 4 saat (SDK testleri) | yenileme payı ayarlanır |
| Yenileme isteği mağaza alanına mı `api` alanına mı | SDK mağaza alanını kullanıyor; belge örneği `api` | `_token_istegi` alan adı değiştirilir |
| `orderedAt` Timestamp biçimi | ms sayı | ISO ise ayrıştırıcı zaten kabul ediyor |
| `listOrder(orderedAt: {gte})` sunucu süzgeci | son 365 gün | istemci tarafı süzgeç zaten var |
| `me.id` = authorizedAppId; imzalı açılıştaki `authorizedAppId` ile aynı | eşit | eşleme merchantId'ye kaydırılır |
| Webhook gövdesi `data` metin, imza HMAC(data) | SDK testiyle aynı | gövde ayrıştırıcı güncellenir |
| `store/app/deleted` kayıtlı adrese geliyor mu | evet | kaldırma, panelde "bağlantı yok" ile yakalanır |
| İframe içinde `localStorage` (Safari/Chrome bölümlenmiş depolama) | çalışır | AppBridge belirteci + bellek içi oturum |
| Satış senaryoları: iptal, kısmi iade, döviz, yurt dışı sipariş | özet notlarında doğru | eşleme kuralı güncellenir |

Test planı: her mağazada Senaryo A (İKAS'tan kurulum), Senaryo B (uygulamadan bağlanma), panelden yeniden açılış,
sipariş oluşturma (webhook), kaldırma ve yeniden kurma. Sonuçlar `docs/olcum/` altına tarihli rapor.

### Faz 3 — Mağaza vitrini ve ticari hazırlık (3. hafta)

| # | İş | Sorumlu |
|---|---|---|
| 3.1 | App Store metni (TR): ne yapar, hangi veriyi okur (yalnız sipariş toplamları), ne yapmaz (başvuruyu kurum adına yapmaz) | K taslak, M onay |
| 3.2 | Ekran görüntüleri: İKAS mağaza kartı, eşleşen teşvikler, kontrol listesi, başvuru ön taslağı | K |
| 3.3 | Gizlilik politikası adresi `https://ALAN/kvkk`, destek e-postası, KVKK aydınlatma metninin hukukçu kontrolü | M |
| 3.4 | Plan eşlemesi: İKAS lisansı → PRO özellikleri (taslak, kontrol listesi); 0.5 kararına göre | K |
| 3.5 | Sunum düzeltmeleri: "210 teşvik kaydı" → **186 kayıt (100 açık, 84 kapalı, 2 belirsiz)**; yetki adları `orders:read` değil `read_orders` | M |

### Faz 4 — İnceleme ve yayın (4. hafta)

İKAS incelemesine gönderim, geri bildirim düzeltmeleri, Türkiye bölgesinde yayın. İlk 90 gün ölçütleri: kurulum
sayısı, kurulumdan panele dönüş oranı, eşleşme sonrası kontrol listesi açma ve taslak üretme oranı.

## 4. Ürün yol haritası (yayın sonrası)

1. **GTİP ile ihracat sınıflaması:** sipariş satırındaki `variant.hsCode` (SDK şemasında var) → ihracat ürün grubu,
   Turquality/sektörel programlarla eşleşme.
2. **5986 e-ihracat hesaplayıcısının otomatik doldurulması:** yurt dışı teslimat cirosu + reklam/pazaryeri gideri.
3. **Kayıt özetlerinin temizlenmesi:** 49 kaydın özetinde kurum sitesi menü metni var (22 tamamen, 27 kısmen); kartlarda
   ve danışman bağlamında görünüyor. Kaynak sayfalardan yeniden yazım, veri betiği (dry-run + yedek + onay).
4. **Başvuru dönemi bildirimleri:** eşleşen programın çağrısı açılınca e-posta (SMTP sonrası).
5. **Canlı taslak ölçümü:** Anthropic kredisi yüklenince `taslak_olcum.py --canli` (onaylı tavan 0,15 USD).

## 5. Riskler ve açık sorular

| Risk | Etki | Azaltma |
|---|---|---|
| İKAS kabuk + ayrı API mimarisini kabul etmezse | kabuk API rotalarına taşıma | kabuk zaten şablon yapısında; iş mantığı HTTP arkasında, taşıma sınırlı |
| İKAS faturalaması zorunluysa Stripe ile çift sistem | gelir modeli değişir | 0.5 kararı; kod tarafı plan eşlemesi küçük iş |
| Mağaza e-postası İKAS'ta doğrulanmamış olabilir | başka birinin adresiyle hesap açılabilir | mevcut hesaba asla bağlanmaz; yalnız mağazanın kendi verisi görünür |
| Büyük mağaza (>10.000 sipariş/yıl) | ciro eksik kalır | özet notunda "kısmi" uyarısı; gerekirse aylık toplu senkron |
| Mock mod canlıda açık kalırsa | sahte veriyle hesap açılabilir | https adreste mock açıksa açılışta CRITICAL günlük kaydı (eklendi); canlı kontrol listesinde `IKAS_MOCK_MODE=false` |
| Parolasız İKAS hesabının silinmesi | hesap silme parola istiyor | yer tutucu e-postalı hesaplar için İKAS oturumuyla silme akışı (Faz 2 sonrası) |

## 6. Teknik ek: yeni uç noktalar

| Yöntem | Yol | Kimlik | Amaç |
|---|---|---|---|
| GET | `/api/oauth/authorize/ikas?storeName=` | yok (çerez + state) | İKAS'tan kurulum başlangıcı |
| GET | `/api/oauth/callback/ikas` | state | token, mağaza bilgisi, hesap, webhook kaydı |
| GET | `/ikas` | imzalı adres | İKAS panelinden açılış sayfası |
| POST | `/api/ikas/oturum` | HMAC imza | imzalı açılıştan oturum belirteci |
| POST | `/api/ikas/appbridge-oturum` | İKAS AppBridge JWT (HS256) | Next.js kabuğunun İKAS paneli içinden girişi |
| POST | `/api/ikas/webhook` | HMAC imza | sipariş olayı, uygulama kaldırma |
| DELETE | `/api/ikas/baglanti` | JWT | bağlantıyı kesme |
| GET | `/api/ikas/durum`, `/api/ikas/panel` | JWT | özet, eşleşme (ertelenmiş senkronu tamamlar) |

Doğrulama: `python -m app.ikas_integration --self-test` (11/11), `pytest tests/test_ikas_uygulama.py` (31),
tam paket 945 geçti / 1 atlandı.
