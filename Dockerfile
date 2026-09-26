# Gelistirme/yerel Docker imaji. Uretim icin Dockerfile.prod kullanin.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# DIKKAT: requirements.txt DEGIL requirements-postgres.txt kuruluyor.
# requirements.txt icinde psycopg2-binary bilerek yorumlanmis durumda (Windows'ta
# derlenmesi C derleyicisi gerektirdigi icin yerel gelistirmede SQLite kullaniliyor).
# Bu imaj PostgreSQL'e baglandigi icin sadece requirements.txt kurulursa kapsayici
# acilista "ModuleNotFoundError: No module named 'psycopg2'" ile coker.
COPY requirements.txt requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements-postgres.txt

COPY . .

# Goçler CALISMA ANINDA uygulanir - derleme aninda veritabani henuz yok.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
