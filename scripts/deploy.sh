#!/bin/bash

# Production Deployment Script
# Usage: ./deploy.sh [staging|production]

set -e

ENV="${1:-staging}"
REPO="tesvikasistani/tesvik-saas"

if [ "$ENV" != "staging" ] && [ "$ENV" != "production" ]; then
    echo "Usage: ./deploy.sh [staging|production]"
    exit 1
fi

echo "🚀 Starting deployment to $ENV..."

# Pull latest changes
echo "📥 Pulling latest code..."
git pull origin main

# Run tests
echo "🧪 Running tests..."
pytest tests/ -v --tb=short || exit 1

# Build Docker image
echo "🐳 Building Docker image..."
docker build -t "$REPO:latest" -t "$REPO:$(date +%Y%m%d_%H%M%S)" .

# Push to registry
echo "📤 Pushing image to registry..."
docker push "$REPO:latest"

# Run migrations
echo "🔄 Running database migrations..."
docker-compose exec -T web alembic upgrade head

# Restart services
echo "🔁 Restarting services..."
docker-compose restart web nginx

# Health check
echo "🏥 Health checks..."
sleep 5
curl -f http://localhost/health || exit 1

echo "✅ Deployment completed successfully!"
echo "🌐 Application: https://$(hostname)"
