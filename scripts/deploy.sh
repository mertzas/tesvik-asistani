#!/bin/bash
# Tek sunucu uretim dagitimi (docker compose v2, docker-compose.prod.yml).
#
# Onceki hali (denetim 2026-10-07): gelistirme Dockerfile'ini build edip var olmayan bir
# registry'ye push ediyor, v1 `docker-compose` ile yalnizca `restart` yaptigi icin yeni
# imaj hic devreye girmiyordu. Simdi: testler -> build + up (gocler kapsayici acilisinda
# `alembic upgrade head` ile uygulanir) -> saglik kontrolu; basarisizsa durur.
#
# Kullanim: ./scripts/deploy.sh            (proje kokunde, .env dolu olmali)
#           SKIP_TESTS=1 ./scripts/deploy.sh

set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.prod.yml"

[ -f .env ] || { echo "❌ .env yok (cp .env.example .env ve doldurun)"; exit 1; }

echo "📥 Kod guncelleniyor..."
git pull --ff-only

if [ "${SKIP_TESTS:-0}" != "1" ]; then
    echo "🧪 Testler..."
    python -m pytest tests/ -q --tb=short
fi

echo "🐳 Imaj derleniyor ve servisler guncelleniyor..."
$COMPOSE up -d --build --remove-orphans

echo "🏥 Saglik kontrolu..."
for i in $(seq 1 12); do
    if $COMPOSE exec -T web python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=5).status==200 else 1)" 2>/dev/null; then
        echo "✅ Dagitim tamam."
        $COMPOSE ps
        exit 0
    fi
    sleep 5
done

echo "❌ Saglik kontrolu 60 sn icinde gecmedi; gunlukler:"
$COMPOSE logs --tail=50 web
exit 1
