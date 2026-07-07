# System Architecture - Teşvik Asistanı SaaS v2.0

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend Layer                           │
│  (Login/Dashboard HTML + JS + CSS)                          │
│  - http://localhost:8000                                    │
│  - http://localhost:8000/dashboard                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   Reverse Proxy (Nginx)                      │
│  - SSL/TLS Termination                                      │
│  - Rate Limiting                                            │
│  - Static File Serving                                      │
│  - Load Balancing (future)                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│               Application Layer (FastAPI)                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ API Endpoints                                        │   │
│  │ - /api/auth/* (JWT authentication)                  │   │
│  │ - /api/sor (Search incentives)                      │   │
│  │ - /api/organizations/* (Multi-tenant mgmt)          │   │
│  │ - /api/analytics/* (Usage tracking)                 │   │
│  │ - /api/admin/* (Admin panel)                        │   │
│  │ - /api/billing/* (Stripe webhooks)                  │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Business Logic                                       │   │
│  │ - Authentication & Authorization                    │   │
│  │ - Rate Limiting (per org/plan)                      │   │
│  │ - RAG Search (keyword + embedding-ready)            │   │
│  │ - Billing Management (Stripe integration)           │   │
│  │ - Analytics Aggregation                             │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
    ┌───────┐   ┌────────┐   ┌────────┐
    │   DB  │   │ Cache  │   │  Queue │
    │  PG   │   │ Redis  │   │ Celery │
    └───────┘   └────────┘   └────────┘
```

---

## Multi-Tenant Architecture

### Database Isolation

```
PostgreSQL
├── organizations table
│   ├── id (UUID, PK)
│   ├── name, email, plan
│   └── stripe_*, webhook_url
│
├── users table
│   ├── id (UUID, PK)
│   ├── org_id (FK) ← Row-Level Security filter
│   └── role (admin/member/viewer)
│
├── queries table
│   ├── id (UUID, PK)
│   ├── org_id (FK) ← Tenant isolation
│   └── results (JSON)
│
└── tesvikler table (shared read-only)
    ├── id (INT, PK)
    ├── kurum, baslik, ozet, detay
    └── (no org_id - shared across tenants)
```

### Request Context

```python
# Every request carries org_id through token
@app.post("/api/sor")
def ask(
    current_user: User = Depends(get_current_user),  # Has org_id
    current_org: Organization = Depends(get_current_org),  # Org context
    db: Session = Depends(get_db),
):
    # Queries automatically filtered by org_id
    query = Query(org_id=current_org.id, ...)
    db.add(query)
```

---

## Authentication Flow

```
1. User Signup/Login
   ┌──────────────────────────────────────────────┐
   │ POST /api/auth/signup                        │
   │ {email, password, full_name, company_name}   │
   └──────────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────┐
   │ Create Organization + User                   │
   │ - Hash password (bcrypt)                     │
   │ - Store in PostgreSQL                        │
   └──────────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────┐
   │ Generate JWT Token                           │
   │ Payload: {sub: user_id, org_id: org_id}      │
   │ Secret: SECRET_KEY (from .env)               │
   │ Expiry: 30 days                              │
   └──────────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────┐
   │ Return: {access_token, token_type, user}     │
   │ Client stores in localStorage                │
   └──────────────────────────────────────────────┘

2. Authenticated Request
   ┌──────────────────────────────────────────────┐
   │ POST /api/sor                                │
   │ Header: Authorization: Bearer <token>        │
   └──────────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────┐
   │ Middleware: get_current_user()               │
   │ - Decode JWT                                 │
   │ - Verify signature                           │
   │ - Extract user_id, org_id                    │
   │ - Fetch User from DB                         │
   │ - Check is_active                            │
   └──────────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────┐
   │ Rate Limit Check                             │
   │ - Get org.plan                               │
   │ - Count queries in last 30 days              │
   │ - Compare with plan.limit                    │
   └──────────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────┐
   │ Process Request (org_id scoped)              │
   │ - Search incentives                          │
   │ - Log query to db                            │
   │ - Return results                             │
   └──────────────────────────────────────────────┘
```

---

## Search & RAG Pipeline

```
User Question: "KOSGEB Ar-Ge destegi"
                     │
                     ▼
        ┌────────────────────────────┐
        │ 1. Tokenize & Normalize    │
        │ Split: ["KOSGEB", "Ar-Ge"] │
        │ Lowercase & remove accents │
        └────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────────┐
        │ 2. Keyword Search (Current)            │
        │ Query: WHERE detay ILIKE '%ar-ge%'     │
        │        AND (kurum='KOSGEB' OR ...)     │
        │ Result: Top 10 matches                 │
        └────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────────┐
        │ 3. Format Results                      │
        │ - Extract kurum, baslik, ozet         │
        │ - Add metadata (tarihler, hedef_kitle)│
        │ - Calculate relevance_score            │
        └────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────────┐
        │ 4. Return Response                     │
        │ {results: [...], tokens_used: N}       │
        │ - Store in queries table               │
        │ - Update org usage stats               │
        │ - Trigger webhooks if configured       │
        └────────────────────────────────────────┘

Future: Embedding-based search with pgvector
  - Generate embeddings for all tesvikler
  - User question → embedding
  - Cosine similarity search
  - Hybrid: keyword + semantic
```

---

## Billing & Subscription Flow

```
User upgrades to Pro Plan
         │
         ▼
┌─────────────────────────────────────────┐
│ 1. Create Stripe Customer               │
│ customer = stripe.Customer.create(      │
│   email=org.email,                      │
│   name=org.name,                        │
│   metadata={org_id}                     │
│ )                                       │
│ org.stripe_customer_id = customer.id    │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 2. Create Subscription                  │
│ subscription = stripe.Subscription.create(
│   customer=customer_id,                 │
│   items=[{price: 'price_...'}],         │
│   payment_behavior='default_incomplete' │
│ )                                       │
│ org.stripe_subscription_id = sub.id     │
│ org.plan = 'pro'                        │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 3. Handle Stripe Events                 │
│ - payment_intent.succeeded              │
│ - customer.subscription.updated         │
│ - customer.subscription.deleted         │
│ - invoice.payment_succeeded             │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 4. Update Organization                  │
│ - Upgrade/downgrade plan                │
│ - Update stripe references              │
│ - Log billing event                     │
└─────────────────────────────────────────┘
```

---

## Data Collection Pipeline

```
Cron Job (Windows Task Scheduler)
Every Monday 03:00 AM
         │
         ▼
┌──────────────────────────────────────┐
│ run_all.py                           │
│ - Calls all scraper modules          │
│ - Sequential: KOSGEB → TÜBİTAK →    │
│            KGF → Hazine              │
└──────────────────────────────────────┘
         │
    ┌────┴────┬────────┬─────────┐
    ▼         ▼        ▼         ▼
  KOSGEB   TÜBİTAK   KGF    Hazine
    │         │        │         │
    └────┬────┴────┬───┴─────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ HTML Scraping (BeautifulSoup)        │
│ - Parse CSS selectors                │
│ - Extract title, summary, link       │
│ - Handle pagination                  │
└──────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ Deduplication (seen_keys)            │
│ - Check kaynak_url                   │
│ - Check normalized baslik            │
│ - Skip duplicates                    │
└──────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ Store in PostgreSQL                  │
│ INSERT INTO tesvikler (...)          │
│ ON CONFLICT (kaynak_url)             │
│ DO UPDATE ...                        │
└──────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ Trigger Webhooks                     │
│ POST to webhook_url (if configured)  │
│ Event: incentive.updated             │
│ Payload: {id, kurum, baslik, ...}    │
└──────────────────────────────────────┘
```

---

## Admin Dashboard

```
Admin User (role='admin')
     │
     ▼
┌──────────────────────────────────────────┐
│ Dashboard Endpoints                      │
│                                          │
│ /api/admin/organizations                │
│ ├─ List all orgs (paginated)            │
│ └─ Get org details                      │
│                                          │
│ /api/admin/users                        │
│ ├─ List all users                       │
│ └─ Update user role/status              │
│                                          │
│ /api/admin/analytics/*                  │
│ ├─ platform overview                    │
│ ├─ revenue breakdown                    │
│ └─ churn analytics                      │
│                                          │
│ /api/admin/billing/*                    │
│ ├─ Manual plan changes                  │
│ └─ Refunds/adjustments                  │
└──────────────────────────────────────────┘
```

---

## Deployment Architecture

### Local Development
```
Developer Laptop
├── Python venv
├── SQLite (or PostgreSQL)
├── FastAPI dev server (uvicorn)
└── Static files (served directly)
```

### Docker Development
```
Docker Host
├── web container (FastAPI)
├── postgres container
├── redis container (optional)
└── nginx container (reverse proxy)
```

### Production (AWS EC2 / DigitalOcean)
```
┌─────────────────────────────────────┐
│         Internet                    │
│    (HTTPS via Let's Encrypt)        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Nginx (Reverse Proxy)              │
│  - SSL Termination                  │
│  - Rate Limiting                    │
│  - Static Files Caching             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  FastAPI Docker Containers          │
│  (Multiple replicas with LB)        │
└──────────────┬──────────────────────┘
        ┌──────┼──────┐
        ▼      ▼      ▼
    [app] [app] [app]
        │      │      │
        └──────┼──────┘
               │
               ▼
        ┌──────────────┐
        │ PostgreSQL   │
        │ (RDS/Cloud)  │
        └──────────────┘
```

---

## Monitoring & Analytics

```
Application Events
    │
    ├─ User signup
    ├─ Query execution
    ├─ Plan upgrade
    ├─ API error
    └─ Webhook delivery
         │
         ▼
    PostgreSQL (queries table)
         │
         ▼
    Analytics Dashboard
    ├─ Daily Active Users
    ├─ Monthly Recurring Revenue
    ├─ Churn Rate
    ├─ Query Volume
    └─ Plan Distribution
         │
         ▼
    Admin Panel (/api/admin/analytics/*)
```

---

## Security Considerations

1. **Authentication**
   - JWT tokens (HS256)
   - Token expiry: 30 days
   - Secure password hashing (bcrypt)

2. **Authorization**
   - Role-based access control (RBAC)
   - Organization-scoped queries
   - Row-level security (RLS) ready

3. **Data Protection**
   - All connections HTTPS
   - PostgreSQL encryption at rest
   - No PII in logs

4. **Rate Limiting**
   - Nginx: 10 req/s general, 100 req/s API
   - Application: Plan-based query limits
   - Stripe webhook verification

5. **OWASP Top 10**
   - SQL Injection: Parameterized queries (SQLAlchemy)
   - XSS: HTML escaping in templates
   - CSRF: Included in FastAPI by default
   - Authentication: JWT + password hashing
   - Sensitive Data: Environment variables (.env)

---

## Performance Optimization

1. **Database**
   - Indexes on frequently queried columns
   - Connection pooling
   - Query caching with Redis

2. **API**
   - Gzip compression (Nginx)
   - Response caching
   - Lazy loading with selectinload

3. **Frontend**
   - Minified CSS/JS
   - Static file caching headers
   - Debounced search input

---

## Scalability Path

```
Phase 1: Single Container
├─ Docker container on t3.medium
├─ PostgreSQL RDS
└─ CloudFront CDN

Phase 2: Horizontal Scaling
├─ Multiple FastAPI containers (ECS)
├─ RDS with read replicas
├─ ElastiCache for Redis
└─ Application Load Balancer

Phase 3: Global Distribution
├─ Multi-region deployment
├─ DynamoDB for sessions (optional)
├─ Route 53 for DNS failover
└─ CloudFlare for edge caching
```

---

## Roadmap for Improvements

- [ ] Implement pgvector for semantic search
- [ ] Add Elasticsearch for full-text search
- [ ] Setup Celery for background jobs
- [ ] Implement caching layer (Redis)
- [ ] Add GraphQL API option
- [ ] Setup CI/CD pipeline (GitHub Actions)
- [ ] Add comprehensive test suite
- [ ] Implement API rate limiting per key
- [ ] Add webhook delivery retries
- [ ] Setup monitoring (Sentry, DataDog)
