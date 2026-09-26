# Teşvik Asistanı - API Referansı

Taban adres: `http://localhost:8000` (geliştirme)

Bu dosyadaki tüm yollar **tam yoldur**, taban adrese eklenir. Önceki hâli
taban adresi `.../api` olarak veriyor ama yolların bir kısmını `/auth/signup`,
bir kısmını `/api/sor` diye yazıyordu; ikisi birleştirildiğinde biri
`/api/auth/signup` (doğru), diğeri `/api/api/sor` (404) oluyordu.

Çalışan sunucuda otomatik ve her zaman güncel referans: **`/docs`**
(OpenAPI). Bu dosya, sık kullanılan akışların elle yazılmış özetidir.

## Kimlik doğrulama

`/api/auth/*`, `/api/veri-durumu` ve `/health` dışındaki tüm endpoint'ler
Bearer token ister:

```
Authorization: Bearer <access_token>
```

Token `/api/auth/login` veya `/api/auth/signup` yanıtındaki `access_token`
alanından gelir ve varsayılan olarak 30 gün geçerlidir.

Token yoksa veya biçimi bozuksa **401**, token geçerli ama yetki yetersizse
(örneğin FREE hesapla PRO endpoint'i) **403** döner.

## Hız sınırları

Pahalı endpoint'ler organizasyon bazlı kayan pencere ile sınırlıdır
(`app/rate_limit.py`). Sınır aşılırsa **429** döner. Örnek: `/api/sor`
dakikada 20, `/api/ikas/senkronize` dakikada 5.

## Endpoints

### Authentication

#### POST `/api/auth/signup`
Yeni hesap oluştur.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123",
  "full_name": "John Doe",
  "company_name": "Tech Corp"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe"
  }
}
```

#### POST `/api/auth/login`
Giriş yap.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response:** Same as signup.

---

### Search

#### POST `/api/sor`
Teşvik ara.

**Request:**
```json
{
  "question": "KOSGEB desteği Ar-Ge için"
}
```

**Response:**
```json
{
  "query_id": "uuid",
  "question": "KOSGEB desteği Ar-Ge için",
  "results": [
    {
      "id": 1,
      "kurum": "KOSGEB",
      "baslik": "Ar-Ge ve İnovasyon Destekleri",
      "ozet": "Özet metin...",
      "hedef_kitle": "KOBİ",
      "baslama_tarihi": "2024-01-01T00:00:00Z",
      "bitis_tarihi": "2024-12-31T23:59:59Z",
      "relevance_score": 0.95
    }
  ],
  "tokens_used": 6,
  "message": "5 sonuç bulundu"
}
```

---

### Organizations

#### GET `/api/organizations/me`
Mevcut organizasyonu getir.

**Response:**
```json
{
  "id": "uuid",
  "name": "Tech Corp",
  "email": "admin@techcorp.com",
  "plan": "pro",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-20T15:45:00Z"
}
```

#### POST `/api/organizations/upgrade`
Plan yükselt.

**Request:**
```json
{
  "plan": "business",
  "stripe_token": "tok_visa_4242"
}
```

**Response:**
```json
{
  "subscription_id": "sub_...",
  "client_secret": "pi_...",
  "status": "active"
}
```

#### POST `/api/organizations/downgrade`
Free plana geri dön.

**Response:**
```json
{
  "message": "Abonelik iptal edildi"
}
```

---

### Analytics

#### GET `/api/analytics/usage`
Kullanım istatistikleri.

**Response:**
```json
{
  "org_id": "uuid",
  "usage_stats": {
    "queries_this_month": 45,
    "queries_limit": 1000,
    "api_calls_this_month": 120,
    "users_active": 3,
    "storage_used_mb": 125.5
  },
  "created_at": "2024-01-20T15:45:00Z"
}
```

#### GET `/api/queries/history`
Sorgulama geçmişi.

**Query Parameters:**
- `limit` (default: 50)

**Response:**
```json
[
  {
    "id": "uuid",
    "question": "KOSGEB destekleri",
    "results": [...],
    "tokens_used": 6,
    "created_at": "2024-01-20T15:45:00Z"
  }
]
```

---

### Admin Endpoints

#### GET `/api/admin/organizations`
Tüm organizasyonları listele.

**Query Parameters:**
- `skip` (default: 0)
- `limit` (default: 50)

#### GET `/api/admin/organizations/{org_id}`
Organizasyon detaylarını getir.

#### POST `/api/admin/organizations/{org_id}/plan`
Plan güncelle.

**Request:**
```json
{
  "plan": "business"
}
```

#### DELETE `/api/admin/organizations/{org_id}`
Organizasyonu sil.

#### GET `/api/admin/analytics/overview`
Platform genel istatistikleri.

#### GET `/api/admin/analytics/revenue`
Gelir analitiği.

#### GET `/api/admin/analytics/churn`
Churn analitiği.

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Geçersiz istek"
}
```

### 401 Unauthorized
```json
{
  "detail": "Kimlik doğrulaması yapılmadı"
}
```

### 403 Forbidden
```json
{
  "detail": "Erişim reddedildi"
}
```

### 429 Too Many Requests
```json
{
  "detail": "Aylık sorgulama limitini aştınız"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Sunucu hatası"
}
```

---

## Plan kotaları (HTTP hız sınırından farklıdır)

İki ayrı sınır var, karıştırılmamalı:

- **Plan kotası** — aylık sorgu hakkı, `app/billing.py` içindeki
  `PLAN_FEATURES`'ta tanımlı. Aşılırsa iş kuralı hatası döner.
- **HTTP hız sınırı** — dakikalık istek sınırı, `app/rate_limit.py`. Aşılırsa
  **429** döner. Kötüye kullanımı ve dış API kotalarının tükenmesini engeller.

| Plan | Aylık sorgu | API erişimi | Takım |
|---|---|---|---|
| FREE | 5 | yok | 1 |
| PRO | 1000 | var | 3 |
| BUSINESS | sınırsız | var | 10 |
| ENTERPRISE | sınırsız | var | sınırsız |

---

## Belgelenmemiş kalan endpoint'ler

Aşağıdakiler bu dosyada ayrıntılı örnek olmadan listelenmiştir; istek/yanıt
gövdeleri için `/docs` (OpenAPI) kullanın. Üstteki bölümler API'nin yalnızca
bir kısmını kapsıyordu.

### Profil ve eşleştirme

| Endpoint | Açıklama |
|---|---|
| `GET /api/profil` | Finansal profili getirir. Profil yoksa **404**. |
| `PUT /api/profil` | Profili oluşturur/güncelleyip döner. |
| `GET /api/eslesme` | Profile göre puanlanmış teşvik listesi ve toplam tahmini destek. Kredi/kefalet ürünleri toplama dahil edilmez. |
| `GET /api/butce-onerisi` | Stok/reklam bütçesi aralıkları ve notlar. **PRO gerekir** (FREE'de 403). Profil yoksa 404. |
| `POST /api/eticaret/destek-hesapla` | E-ticaret gider kalemlerinden destek tahmini. |

### Veri durumu

| Endpoint | Açıklama |
|---|---|
| `GET /api/veri-durumu` | Her veri kaynağının son güncelleme tarihi, yaşı, kayıt sayısı ve durumu (`taze`/`eskiyor`/`bayat`/`veri_yok`). **Kimlik doğrulaması gerekmez** — kullanıcı üye olmadan önce veriye güvenip güvenemeyeceğini görebilmeli. Kişisel veri dönmez. |
| `GET /health` | `status`, `version` ve `veri_durumu`. İzleme sistemi için. |

### İKAS entegrasyonu

Şu an **mock modda** (gerçek `client_id`/`secret` üretilmedi), bkz. README.

| Endpoint | Açıklama |
|---|---|
| `GET /api/ikas/baglan?storeName=...` | OAuth yetkilendirme adresine yönlendirir. |
| `GET /api/ikas/callback-oauth` | OAuth dönüş adresi; kodu token'a çevirir. |
| `GET /api/ikas/durum` | Bağlantı durumu. |
| `POST /api/ikas/senkronize` | Siparişleri çeker ve profile yansıtır. En pahalı endpoint, dakikada 5 istek. |
| `GET /api/ikas/panel` | Mağaza içi gömülü panel verisi. |
| `POST /api/ikas/webhook/order-created` | İKAS'tan gelen sipariş bildirimi. |

### Çilek paneli

Ayrı bir dikey; parsel, sensör, sulama, ilaçlama, hasat, soğuk zincir ve
gübre rehberi endpoint'leri `/api/cilek/*` altındadır. Tam liste `/docs`'ta.

### Yönetim

`GET /api/admin/users`, `POST /api/admin/users/{user_id}/role`,
`POST /api/admin/users/{user_id}/deactivate` — üstteki Admin bölümünde
eksik kalmıştı.

---

## Webhook'lar

**Yalnızca gelen (inbound) webhook desteklenir:**

| Endpoint | Kaynak |
|---|---|
| `POST /api/webhooks/stripe` | Stripe abonelik olayları (imza doğrulaması `STRIPE_WEBHOOK_SECRET` ile) |
| `POST /api/ikas/webhook/order-created` | İKAS sipariş oluşturma bildirimi |

**Giden webhook yok.** Bu dosyanın önceki hâli "Subscribe to webhooks via
dashboard" diyerek `incentive.updated` ve `subscription.upgraded` olaylarını
belgeliyordu; böyle bir özellik uygulanmadı. `Organization.webhook_url`
sütunu veritabanında duruyor ama kodda **hiçbir yerde okunmuyor** — ileride
bu özellik yazılırsa kullanılacak boş bir alan.

---

## cURL ile deneme

```bash
# Kayıt
curl -X POST http://localhost:8000/api/auth/signup   -H "Content-Type: application/json"   -d '{"email":"test@example.com","password":"GucluSifre123",
       "full_name":"Test Kullanici","company_name":"Test Ltd"}'

# Giriş (token'ı alın)
curl -X POST http://localhost:8000/api/auth/login   -H "Content-Type: application/json"   -d '{"email":"test@example.com","password":"GucluSifre123"}'

# Soru sor
curl -X POST http://localhost:8000/api/sor   -H "Authorization: Bearer <TOKEN>"   -H "Content-Type: application/json"   -d '{"question":"Konyada 50 dekar bugday ekiyorum, hangi destekler var?"}'

# Eşleştirme
curl http://localhost:8000/api/eslesme -H "Authorization: Bearer <TOKEN>"

# Veri tazeliği (token gerekmez)
curl http://localhost:8000/api/veri-durumu
```

---

## Resmî istemci kütüphanesi yok

Bu dosyanın önceki hâli `TesvikClient` adlı bir JavaScript ve Python SDK'sı
ile bir Discord sunucusu ve destek adresi gösteriyordu; **hiçbiri mevcut
değil**. API standart REST/JSON olduğu için `requests`, `httpx` veya `fetch`
ile doğrudan çağrılabilir. OpenAPI şeması `/openapi.json` adresinde olduğu
için istemci kodu üretmek isterseniz `openapi-generator` kullanabilirsiniz.
