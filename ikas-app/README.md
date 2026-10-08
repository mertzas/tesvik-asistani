# Teşvik Asistanı — İKAS uygulaması (Next.js kabuğu)

İKAS Admin App'leri İKAS'ın Next.js projesiyle geliştirilir (builders.ikas.com, `ikas app init`; şablon:
`github.com/ikascom/ikas-app-examples/examples/starter-app`). Bu klasör o yapıya uyan **ince bir kabuktur**:

- İKAS yönetim panelinde açılan arayüz (mağaza özeti, uygun destekler, kontrol listesi, başvuru ön taslağı)
- AppBridge oturumu: panel `REQUEST_TOKEN` ile JWT verir → `POST /api/ikas/appbridge-oturum`
- İmzalı açılış adresi (`?storeName&merchantId&authorizedAppId&timestamp&signature`) → `POST /api/ikas/oturum`

Şablondan bilerek **alınmayanlar**: Prisma/SQLite belirteç tablosu, iron-session, sunucu tarafı GraphQL istemcisi.
İKAS erişim belirteçleri tek yerde, FastAPI'nin şifreli `ikas_baglanti` tablosunda durur; OAuth, webhook, sipariş
senkronu, eşleştirme ve taslak FastAPI'dedir (`app/ikas_panel.py`). Kabuğun kendi sırrı yoktur.

```
İKAS paneli (iframe) ──► ikas.ALAN  ─┬─ /            Next.js (bu klasör)
                                     └─ /api/*       FastAPI (OAuth, webhook, veri)
```

## Akışlar

| Olay | Adres | Kim karşılar |
|---|---|---|
| İKAS'tan kurulum (Kurulum Adresi) | `/api/oauth/authorize/ikas?storeName=` | FastAPI |
| OAuth dönüşü (Redirect URI) | `/api/oauth/callback/ikas` | FastAPI → `https://{mağaza}.myikas.com/admin/authorized-app/{id}` |
| Panelde açılış (Uygulama adresi) | `/` | Next.js → AppBridge → `/api/ikas/appbridge-oturum` |
| Webhook (kurulumda otomatik kaydedilir) | `/api/ikas/webhook` | FastAPI |

Giriş kararı `src/lib/akis.ts`'tedir (birim testli): imzalı parametre > iframe (AppBridge, saklı oturum kullanılmaz) >
saklı oturum > geçerli `storeName` (kurulum) > mağaza adı formu.

## Ortam değişkenleri

| Değişken | Nerede | Not |
|---|---|---|
| `BACKEND_URL` | kabuk, **derleme anında** | Tanımlıysa `/api/*` ve `/kvkk` FastAPI'ye yeniden yazılır. Next yeniden yazımları derlemede `routes-manifest.json`'a gömülür; değiştirince yeniden derleyin. Canlıda nginx kullanılıyorsa boş bırakılır. |
| `IKAS_CERCEVE_KAYNAKLARI` | kabuk, derleme anında | Varsayılan `https://*.myikas.com` (CSP `frame-ancestors`). |
| `IKAS_UYGULAMA_URL` | FastAPI `.env` | Kabuğun genel adresi (`https://ikas.ALAN`). Redirect URI ve webhook adresi buradan üretilir. |
| `IKAS_CLIENT_ID`, `IKAS_CLIENT_SECRET`, `IKAS_MOCK_MODE=false` | FastAPI `.env` | İKAS partner panelinden. Sır yalnızca FastAPI'de. |

## Komutlar

```bash
npm install
npm test          # akış kararı + biçimlendirme birim testleri (node --test)
npm run typecheck
npm run build
```

## Yerel deneme (gerçek İKAS olmadan, mock mod)

1. FastAPI: `IKAS_UYGULAMA_URL=http://localhost:3001 SCHEDULER_ENABLED=false python -m uvicorn app.main:app --port 8001`
   (gerçek veritabanı yerine kopya kullanmak için `DATABASE_URL=sqlite:///.../kopya.db`).
2. Kabuk: `BACKEND_URL=http://127.0.0.1:8001 IKAS_CERCEVE_KAYNAKLARI="https://*.myikas.com http://localhost:3002" npm run build && npx next start -p 3001`
3. Kurulum: `http://localhost:3001/api/oauth/authorize/ikas?storeName=kabuk-magaza` gerçek İKAS onay ekranına gider
   (mock istemci kimliğiyle ilerlemez); state'i kullanarak callback'i çağırın:
   `http://localhost:3001/api/oauth/callback/ikas?code=x&state=STATE` → imzalı açılışla panel.
4. AppBridge (iframe): `python scripts/ikas_appbridge_deneme.py --magaza kabuk-magaza --cikti DIZIN` ve
   `python -m http.server 3002 --directory DIZIN` → `http://localhost:3002/` kabuğu iframe içinde açar, `REQUEST_TOKEN`'a
   İKAS biçiminde JWT ile yanıt verir.

2026-10-08'de bu adımların hepsi tarayıcıda denendi: kurulum, imzalı açılış, panel sekmeleri, kontrol listesi
işaretleme, FREE planda taslak reddi, iframe içinde AppBridge girişi, 375 px genişlikte taşma yok.

## Canlıya alma (öneri)

Kabuğu ayrı alt alan adında yayınlayın; nginx `/api/` isteklerini doğrudan FastAPI'ye verir (istemci IP'si hız
sınırları için korunur), gerisini Next.js'e:

```nginx
server {
    listen 443 ssl;
    server_name ikas.ALAN;
    location /api/ { proxy_pass http://web; proxy_set_header Host $host;
                     proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto $scheme; }
    location = /kvkk { proxy_pass http://web; proxy_set_header Host $host; }
    location / { proxy_pass http://ikas_app:3000; proxy_set_header Host $host; }
}
```

İKAS partner panelinde: Kurulum Adresi `https://ikas.ALAN/api/oauth/authorize/ikas`, Redirect URI
`https://ikas.ALAN/api/oauth/callback/ikas`, Uygulama adresi `https://ikas.ALAN/`.

## Sürümler

Next.js 16.4.0, React 19.3.0, Tailwind 4.3.3, `@ikas/app-helpers` 1.0.10. Şablon Next 15.3.0 kullanıyor; 15.x hattında
Next'in içerdiği PostCSS için açık uyarılar (GHSA-qx2v-qp2m-jg93 vb.) yalnız 16.4.0'da kapandığı için 16'ya geçildi
(`npm audit`: 0 açık). Kod Next 15/16 arasında farklı davranan bir API kullanmıyor.
