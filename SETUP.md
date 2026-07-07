# 🚀 Teşvik Asistanı SaaS - Setup Guide

## Prerequisites

- Python 3.11+
- PostgreSQL 13+
- Redis 7+
- Docker & Docker Compose (for containerized deployment)
- Node.js 16+ (for frontend development - optional)

## Development Setup

### 1. Clone the Repository

```bash
cd C:\Users\huawei\Desktop\tesvik-asistani
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Environment Variables

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/tesvik_saas

# Security
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_DAYS=30

# Stripe (optional for development)
STRIPE_SECRET_KEY=sk_test_your_test_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_test_key

# Email
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# App
APP_NAME=Teşvik Asistanı SaaS
APP_URL=http://localhost:8000
ENVIRONMENT=development
```

### 5. Setup PostgreSQL

```bash
# Windows with PostgreSQL installed
psql -U postgres -c "CREATE DATABASE tesvik_saas;"
psql -U postgres -c "CREATE USER tesvik_user WITH PASSWORD 'tesvik_password_123';"
psql -U postgres -c "ALTER ROLE tesvik_user SET client_encoding TO 'utf8';"
psql -U postgres -c "ALTER ROLE tesvik_user SET default_transaction_isolation TO 'read committed';"
psql -U postgres -c "ALTER ROLE tesvik_user SET default_transaction_deferrable TO on;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE tesvik_saas TO tesvik_user;"
```

### 6. Run Database Migrations

```bash
# First time setup
python -c "from app.models import init_db; init_db()"

# Or with Alembic (recommended)
alembic upgrade head
```

### 7. Scrape Initial Data

```bash
# Collect incentive data from all institutions
python -m app.scrapers.run_all

# Or individual institutions:
python -m app.scrapers.kosgeb
python -m app.scrapers.tubitak
python -m app.scrapers.kgf
python -m app.scrapers.hazine_tesvik
```

### 8. Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Visit:
- **Web App:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## Docker Deployment

### 1. Build and Run Containers

```bash
docker-compose up -d
```

### 2. Run Migrations

```bash
docker-compose exec web alembic upgrade head
```

### 3. Seed Initial Data

```bash
docker-compose exec web python -m app.scrapers.run_all
```

### 4. Create Admin User

```bash
docker-compose exec web python << 'EOF'
from app.models import SessionLocal, Organization, User
from app.auth import hash_password
from uuid import uuid4

db = SessionLocal()

org = Organization(name="Admin Org", email="admin@example.com")
db.add(org)
db.flush()

user = User(
    email="admin@example.com",
    hashed_password=hash_password("admin123"),
    full_name="Admin User",
    org_id=org.id,
    role="admin",
)
db.add(user)
db.commit()

print("Admin user created!")
print(f"Email: admin@example.com")
print(f"Password: admin123")
EOF
```

### 5. Access Application

- **Web:** http://localhost
- **API:** http://localhost/api
- **Docs:** http://localhost/api/docs

---

## Production Deployment

### AWS EC2

```bash
# 1. Launch EC2 instance (Ubuntu 22.04, t3.medium+)
# 2. SSH into instance
# 3. Install Docker and Docker Compose
# 4. Clone repository
# 5. Setup .env with production values
# 6. Generate SSL certificates (Let's Encrypt via Certbot)
# 7. Run: docker-compose -f docker-compose.prod.yml up -d
```

### Heroku

```bash
# 1. Install Heroku CLI
# 2. heroku login
# 3. heroku create tesvik-asistani
# 4. heroku addons:create heroku-postgresql:standard-0
# 5. heroku config:set STRIPE_SECRET_KEY=sk_live_...
# 6. git push heroku main
```

### DigitalOcean App Platform

```bash
# 1. Connect GitHub repository
# 2. Configure environment variables
# 3. Set database to DigitalOcean Managed PostgreSQL
# 4. Deploy
```

---

## Testing

### Run Tests

```bash
pytest tests/ -v
```

### Test Coverage

```bash
pytest tests/ --cov=app --cov-report=html
```

### Load Testing

```bash
# Install locust
pip install locust

# Run load test
locust -f tests/load_test.py --host=http://localhost:8000
```

---

## Database Migrations

### Create New Migration

```bash
alembic revision --autogenerate -m "Add new field to users table"
```

### Apply Migrations

```bash
alembic upgrade head
```

### Rollback

```bash
alembic downgrade -1
```

---

## API Testing

### Login and Get Token

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "admin123"
  }'
```

### Make Authorized Request

```bash
TOKEN="your_access_token"
curl -X GET http://localhost:8000/api/organizations/me \
  -H "Authorization: Bearer $TOKEN"
```

### Ask Question

```bash
curl -X POST http://localhost:8000/api/sor \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "KOSGEB Ar-Ge"}'
```

---

## Monitoring & Logging

### View Logs

```bash
# Docker logs
docker-compose logs -f web

# Application logs
tail -f logs/app.log
```

### Health Check

```bash
curl http://localhost:8000/health
```

---

## Troubleshooting

### Database Connection Error

```bash
# Check PostgreSQL is running
psql -U tesvik_user -d tesvik_saas -c "SELECT 1;"

# Check DATABASE_URL in .env
echo $DATABASE_URL
```

### Port Already in Use

```bash
# Change port in docker-compose.yml or .env
# Or kill process using port
lsof -i :8000
kill -9 <PID>
```

### Migrations Failed

```bash
# Reset database (development only!)
dropdb tesvik_saas
createdb tesvik_saas
alembic upgrade head
```

### Stripe Integration Issues

```bash
# Test Stripe API key
curl -H "Authorization: Bearer sk_test_..." https://api.stripe.com/v1/charges
```

---

## Performance Optimization

### Database Indexing

```python
# Already configured in models.py
# Add custom index if needed:
from sqlalchemy import Index

Index('idx_query_org_date', Query.org_id, Query.created_at)
```

### Caching with Redis

```python
from redis import Redis
redis = Redis(host='localhost', port=6379, db=0)

# Cache incentives for 1 hour
redis.setex('incentives:kosgeb', 3600, cached_data)
```

### Query Optimization

```python
# Use eager loading
db.query(Organization).options(
    selectinload(Organization.users),
    selectinload(Organization.queries)
)
```

---

## Security Checklist

- [ ] Change `SECRET_KEY` in production
- [ ] Use HTTPS (SSL/TLS) in production
- [ ] Enable database encryption
- [ ] Setup rate limiting (nginx configured)
- [ ] Enable CORS only for trusted domains
- [ ] Rotate API keys regularly
- [ ] Enable 2FA for admin accounts
- [ ] Setup monitoring and alerting
- [ ] Regular backups (daily)
- [ ] Run security audits

---

## Maintenance

### Regular Tasks

**Daily:**
- Monitor error logs
- Check database size

**Weekly:**
- Review user feedback
- Check performance metrics

**Monthly:**
- Backup database
- Review and update dependencies
- Analyze usage statistics

### Backup

```bash
# Backup PostgreSQL
pg_dump -U tesvik_user tesvik_saas > backup_$(date +%Y%m%d).sql

# Restore
psql -U tesvik_user tesvik_saas < backup_20240120.sql
```

---

## Support

- Email: dev@tesvikasistani.com
- Documentation: https://docs.tesvikasistani.com
- GitHub Issues: https://github.com/tesvikasistani/saas/issues
