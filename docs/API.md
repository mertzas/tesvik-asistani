# Teşvik Asistanı SaaS - API Documentation

Base URL: `http://localhost:8000/api` (development)

## Authentication

All endpoints (except `/auth/*`) require Bearer token authentication:

```
Authorization: Bearer <your_access_token>
```

## Endpoints

### Authentication

#### POST `/auth/signup`
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

#### POST `/auth/login`
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

## Rate Limiting

- **Free Plan:** 5 queries/month
- **Pro Plan:** 1000 queries/month
- **Business Plan:** Unlimited
- **Enterprise:** Unlimited + custom limits

---

## Webhook Events

Subscribe to webhooks via dashboard.

### `incentive.updated`
Yeni teşvik eklendiğinde.

```json
{
  "event": "incentive.updated",
  "timestamp": "2024-01-20T15:45:00Z",
  "data": {
    "id": 1,
    "kurum": "KOSGEB",
    "baslik": "Yeni teşvik programı",
    "baslama_tarihi": "2024-02-01T00:00:00Z"
  }
}
```

### `subscription.upgraded`
Plan yükseltildiğinde.

```json
{
  "event": "subscription.upgraded",
  "timestamp": "2024-01-20T15:45:00Z",
  "org_id": "uuid",
  "from_plan": "free",
  "to_plan": "pro"
}
```

---

## Testing with cURL

```bash
# Signup
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepass123",
    "full_name": "Test User",
    "company_name": "Test Corp"
  }'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepass123"
  }'

# Ask question
curl -X POST http://localhost:8000/api/sor \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "KOSGEB Ar-Ge"}'
```

---

## SDK Examples

### JavaScript/TypeScript

```typescript
const client = new TesvikClient({
  apiKey: "your_api_key",
  baseUrl: "https://api.tesvikasistani.com"
});

const results = await client.search("KOSGEB destekleri");
console.log(results);
```

### Python

```python
from tesvik_api import TesvikClient

client = TesvikClient(api_key="your_api_key")
results = client.search("KOSGEB destekleri")
print(results)
```

---

## Support

Email: support@tesvikasistani.com
Discord: https://discord.gg/tesvikasistani
