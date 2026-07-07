# 🎯 Teşvik Asistanı SaaS v2.0

Devlet teşviklerini bulmanın en kolay yolu. KOSGEB, TÜBİTAK, KGF ve daha birçok kurumun sağladığı teşvikleri saniyeler içinde keşfedin.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

## ✨ Features

- **🔍 Akıllı Arama:** Anahtar kelime tabanlı, embedding-ready altyapı
- **🏛️ 4+ Kamu Kurumu:** KOSGEB, TÜBİTAK, KGF, Hazine Yatırım Teşvik Sistemi
- **🔐 Multi-Tenant:** Organizasyon bazlı veri izolasyonu
- **💳 Stripe Entegrasyonu:** Freemium → Pro → Business → Enterprise
- **📊 Admin Dashboard:** Organizasyon ve kullanıcı yönetimi
- **📈 Analytics:** Kullanım istatistikleri ve gelir takibi
- **🔌 API First:** RESTful API + OpenAPI/Swagger
- **🐳 Docker Ready:** Docker + Docker Compose + Nginx
- **🔄 Auto-Updates:** Otomatik veri güncelleme (Windows Task Scheduler)
- **⚡ Rate Limiting:** Plan bazlı sorgu sınırları

## 🚀 Quick Start (Development)

### 1. Prerequisites
```bash
python --version  # 3.11+ required
postgres --version  # 13+ required
```

### 2. Clone & Setup
```bash
cd /c/Users/huawei/Desktop/tesvik-asistani
python -m venv venv
source venv/Scripts/activate  # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env with your values
```

### 5. Setup Database
```bash
# Create PostgreSQL database
createdb -U postgres tesvik_saas

# Run migrations
alembic upgrade head
```

### 6. Scrape Incentive Data
```bash
python -m app.scrapers.run_all
```

### 7. Run Server
```bash
uvicorn app.main:app --reload --port 8000
```

Visit:
- **Web:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Dashboard:** http://localhost:8000/dashboard (after login)

---

## 🐳 Docker Deployment

### Start All Services
```bash
docker-compose up -d
```

### Create Admin User
```bash
docker-compose exec web python << 'EOF'
from app.models import SessionLocal, Organization, User
from app.auth import hash_password

db = SessionLocal()
org = Organization(name="Admin Org", email="admin@example.com")
db.add(org)
db.flush()

user = User(
    email="admin@example.com",
    hashed_password=hash_password("admin123"),
    full_name="Admin",
    org_id=org.id,
    role="admin"
)
db.add(user)
db.commit()
print("✅ Admin created: admin@example.com / admin123")
EOF
```

### View Logs
```bash
docker-compose logs -f web
```

---

## 📚 Documentation

- **[Setup Guide](SETUP.md)** - Detailed installation & deployment instructions
- **[API Documentation](docs/API.md)** - Complete API reference
- **[Architecture](docs/ARCHITECTURE.md)** - System design & data flow
- **[Contributing](CONTRIBUTING.md)** - Development guidelines

---

## 📁 Project Structure

```
tesvik-asistani/
├── app/
│   ├── main.py              # FastAPI application
│   ├── models.py            # SQLAlchemy models (multi-tenant)
│   ├── schemas.py           # Pydantic models
│   ├── auth.py              # JWT authentication
│   ├── billing.py           # Stripe integration
│   ├── admin.py             # Admin endpoints
│   ├── rag.py               # Search/RAG logic
│   ├── scrapers/            # Data collection
│   │   ├── kosgeb.py
│   │   ├── tubitak.py
│   │   ├── kgf.py
│   │   ├── hazine_tesvik.py
│   │   └── run_all.py
│   └── static/              # Frontend (HTML/JS)
│       ├── index.html       # Login & signup
│       └── dashboard.html   # Main dashboard
├── migrations/              # Alembic database migrations
├── docs/                    # Documentation
├── tests/                   # Test suite
├── docker-compose.yml       # Docker services
├── Dockerfile              # App container
├── nginx.conf              # Reverse proxy config
├── requirements.txt        # Python dependencies
└── SETUP.md               # Setup instructions
```

---

## 🔑 Key Endpoints

### Authentication
- `POST /api/auth/signup` - Create new account
- `POST /api/auth/login` - Login

### Search
- `POST /api/sor` - Ask incentive question

### Organizations
- `GET /api/organizations/me` - Current org info
- `POST /api/organizations/upgrade` - Upgrade plan
- `POST /api/organizations/downgrade` - Downgrade plan

### Analytics
- `GET /api/analytics/usage` - Usage statistics
- `GET /api/queries/history` - Query history

### Admin
- `GET /api/admin/organizations` - List orgs
- `GET /api/admin/analytics/overview` - Platform stats
- `GET /api/admin/analytics/revenue` - Revenue breakdown

See [API.md](docs/API.md) for complete reference.

---

## 💰 Pricing

| Plan | Price | Queries/mo | API | Support |
|------|-------|-----------|-----|---------|
| **Free** | ₺0 | 5 | ✗ | Email |
| **Pro** | ₺299 | 1000 | ✓ | Priority |
| **Business** | ₺999 | ∞ | ✓ + Webhooks | Dedicated |
| **Enterprise** | Custom | ∞ | ✓ + White-label | 24/7 |

---

## 🔄 Architecture

### Multi-Tenant Design
```
Organization 1 → Users + Queries (isolated)
Organization 2 → Users + Queries (isolated)
Organization 3 → Users + Queries (isolated)
```

### Tech Stack
- **Backend:** FastAPI + SQLAlchemy + Pydantic
- **Database:** PostgreSQL 15 + Alembic migrations
- **Auth:** JWT (python-jose)
- **Payments:** Stripe API
- **Frontend:** Vanilla JS + HTML/CSS
- **Deployment:** Docker + Nginx + Let's Encrypt
- **Infrastructure:** AWS/DigitalOcean/Heroku ready

---

## 📊 Database Schema

```sql
-- Organizations (Multi-tenant isolation)
organizations:
  id (UUID, PK)
  name, email, plan (free/pro/business/enterprise)
  stripe_customer_id, stripe_subscription_id
  webhook_url, created_at, updated_at

-- Users
users:
  id (UUID, PK)
  email, hashed_password, full_name
  org_id (FK) → organizations
  role (admin/member/viewer), is_active, last_login

-- Queries (Analytics)
queries:
  id (UUID, PK)
  org_id (FK) → organizations
  question, results (JSON), tokens_used, created_at

-- Incentives (Teşvikler)
tesvikler:
  id (INT, PK)
  kurum, baslik, ozet, detay
  hedef_kitle, kaynak_url, guncelleme_tarihi
  kategori, baslama_tarihi, bitis_tarihi
  tesvil_tutari, basin_orzu, uygunluk_kriterleri
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Test coverage
pytest tests/ --cov=app

# Load testing
locust -f tests/load_test.py --host=http://localhost:8000
```

---

## 🚀 Deployment Guides

### AWS EC2
1. Launch Ubuntu 22.04 instance (t3.medium+)
2. Install Docker: `curl -fsSL https://get.docker.com | sh`
3. Clone repo, setup .env
4. `docker-compose -f docker-compose.prod.yml up -d`
5. Setup SSL with Certbot

### Heroku
```bash
heroku create tesvik-asistani
heroku addons:create heroku-postgresql:standard-0
git push heroku main
```

### DigitalOcean App Platform
Connect GitHub repo → Auto-deploy

---

## 📈 Roadmap

- [ ] **Phase 1 (Feb 2024):** MVP launch, Freemium tier
- [ ] **Phase 2 (Mar 2024):** Web dashboard, Stripe billing
- [ ] **Phase 3 (Apr 2024):** Admin panel, Enterprise features
- [ ] **Phase 4 (May+):** Mobile app, AI enhancements, Marketplace

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/awesome-feature`
3. Commit changes: `git commit -m "Add awesome feature"`
4. Push to branch: `git push origin feature/awesome-feature`
5. Open Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 📧 Support & Contact

- **Email:** support@tesvikasistani.com
- **GitHub Issues:** [Report bugs](https://github.com/tesvikasistani/saas/issues)
- **Documentation:** [https://docs.tesvikasistani.com](https://docs.tesvikasistani.com)

---

## 🙏 Acknowledgments

- KOSGEB, TÜBİTAK, KGF için veri kaynakları
- FastAPI & SQLAlchemy ekipleri
- Açık kaynak kütüphaneler

---

**Made with ❤️ in Turkey | Built for KOBİs & Startups**
