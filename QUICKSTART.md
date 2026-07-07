# 🚀 Teşvik Asistanı - 5 Dakikalık Quick Start

## Seçenek 1: Docker ile (Önerilen)

### Gereklilikler
- Docker & Docker Compose
- Git

### Başlayın
```bash
# 1. Klonlayın
git clone https://github.com/tesvikasistani/saas.git
cd tesvik-asistani

# 2. Başlatın
docker-compose up -d

# 3. Admin kullanıcı oluşturun
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
    full_name="Admin User",
    org_id=org.id,
    role="admin"
)
db.add(user)
db.commit()
print("✅ Giriş yap: admin@example.com / admin123")
EOF

# 4. Açın: http://localhost
```

---

## Seçenek 2: Local Development

### Gereklilikler
- Python 3.11+
- PostgreSQL 15+

### Başlayın
```bash
# 1. Setup
git clone https://github.com/tesvikasistani/saas.git
cd tesvik-asistani
python -m venv venv
source venv/Scripts/activate  # Windows

# 2. Kütüphaneler
pip install -r requirements.txt

# 3. Database
createdb -U postgres tesvik_saas
python -c "from app.models import init_db; init_db()"

# 4. Veri
python -m app.scrapers.run_all

# 5. Çalıştırın
uvicorn app.main:app --reload
```

Açın: **http://localhost:8000**

---

## 📧 Admin Giriş Bilgileri

| Alan | Değer |
|------|-------|
| Email | admin@example.com |
| Şifre | admin123 |

---

## 🎯 İlk Adımlar

### 1. Dashboard'a Gir
```
http://localhost:8000/dashboard
Email: admin@example.com
Şifre: admin123
```

### 2. Teşvik Ara
```
Arama kutusu: "KOSGEB Ar-Ge"
Ara butonuna tıkla
Sonuçları gör
```

### 3. Fiyatlandırma
```
Ana menü → Planlama
Upgrade yapmak için Pro/Business seç
```

### 4. Admin Paneline Erişim
```
URL: http://localhost:8000/api/admin/analytics/overview
Header: Authorization: Bearer <token>
```

---

## 🧪 API Test Etme

### cURL ile Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "admin123"
  }'
```

### cURL ile Soru Sor
```bash
TOKEN="<access_token_from_login>"
curl -X POST http://localhost:8000/api/sor \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "KOSGEB destekleri"}'
```

---

## 📚 Belgeler

- **Full Setup:** [SETUP.md](SETUP.md)
- **API Reference:** [API.md](docs/API.md)
- **Architecture:** [ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 🛠️ Troubleshooting

### Port zaten kullanımda
```bash
# Başka porta başlat
docker-compose up -d -e PORT=8001
# veya
uvicorn app.main:app --port 8001
```

### PostgreSQL bağlantı hatası
```bash
# Docker'da çalıştığından emin ol
docker ps | grep postgres

# Veya manual PostgreSQL'yi kur
# Ubuntu: sudo apt install postgresql postgresql-contrib
# Windows: https://www.postgresql.org/download/windows/
```

### Database migration hatası
```bash
docker-compose exec web alembic downgrade -1
docker-compose exec web alembic upgrade head
```

---

## 💡 Sonraki Adımlar

### Week 1: Test
- [ ] Admin hesabını test et
- [ ] Birkaç sorgu yap
- [ ] API'yi test et
- [ ] Logging'i kontrol et

### Week 2: Özelleştir
- [ ] .env dosyasını güncelle
- [ ] Database URL'sini değiştir
- [ ] Stripe test keys ekle
- [ ] Email konfigürasyonu yap

### Week 3: Deploy
- [ ] Production database oluştur
- [ ] Domain adı al
- [ ] SSL sertifikası oluştur
- [ ] AWS/DigitalOcean'a deploy et

---

## 📞 Destek

Sorunuz varsa:
- 📖 [Belgeler](README.md)
- 🐛 [GitHub Issues](https://github.com/tesvikasistani/saas/issues)
- 📧 support@tesvikasistani.com

---

**Happy coding! 🎉**
