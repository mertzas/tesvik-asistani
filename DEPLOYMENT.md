# Teşvik Asistanı - Deployment Guide

Production'da dağıtmak için 3 seçenek:

## 1. AWS (Recommended - Scalable)

### Requirements
- AWS Account
- AWS CLI installed
- Docker installed

### Steps

```bash
# 1. ECR (Elastic Container Registry) repository oluştur
aws ecr create-repository --repository-name tesvik-asistani --region us-east-1

# 2. Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# 3. Build & push image
docker build -f Dockerfile.prod -t tesvik-asistani:latest .
docker tag tesvik-asistani:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/tesvik-asistani:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/tesvik-asistani:latest

# 4. RDS PostgreSQL oluştur
# AWS Console -> RDS -> Create Database -> PostgreSQL 15

# 5. ElastiCache Redis oluştur
# AWS Console -> ElastiCache -> Create Redis cluster

# 6. ECS Cluster oluştur ve Fargate task çalıştır
aws ecs create-cluster --cluster-name tesvik-prod

# 7. Environment variables
# AWS Secrets Manager'da sakla:
# - DATABASE_URL
# - SECRET_KEY
# - STRIPE_SECRET_KEY
```

### Cost Estimate
- ECS Fargate: $50-100/month
- RDS (t3.micro): $30/month
- ElastiCache (cache.t3.micro): $20/month
- **Total: ~$100-150/month**

---

## 2. DigitalOcean (Simple - Budget-friendly)

### Requirements
- DigitalOcean Account
- doctl CLI installed

### Steps

```bash
# 1. SSH key setup
doctl compute ssh-key list

# 2. Droplet oluştur (Ubuntu 22.04, $6/month)
doctl compute droplet create tesvik-prod \
  --region nyc3 \
  --image ubuntu-22-04-x64 \
  --size s-1vcpu-1gb \
  --ssh-keys YOUR_SSH_KEY_ID

# 3. SSH ile bağlan
ssh root@YOUR_DROPLET_IP

# 4. Docker & Docker Compose yükle
sudo apt-get update && sudo apt-get install -y docker.io docker-compose

# 5. Repo clone et
git clone YOUR_REPO_URL
cd tesvik-asistani

# 6. Environment variables ayarla
cp .env.example .env
# .env'de değerleri güncelle: DATABASE_URL, SECRET_KEY, STRIPE_SECRET_KEY

# 7. Docker Compose çalıştır
sudo docker-compose -f docker-compose.prod.yml up -d

# 8. SSL certificate (Let's Encrypt)
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot certonly --standalone -d your-domain.com

# 9. Nginx restart
sudo systemctl restart nginx

# 10. Health check
curl https://your-domain.com/health
```

### Cost Estimate
- Droplet ($6/month) + Managed DB ($15/month): **$21/month**

---

## 3. Heroku (Very Simple - No DevOps)

### Requirements
- Heroku Account
- Heroku CLI installed

### Steps

```bash
# 1. Login
heroku login

# 2. App oluştur
heroku create tesvik-asistani

# 3. Buildpack ayarla
heroku buildpacks:add heroku/python
heroku buildpacks:add heroku/docker-runtime

# 4. PostgreSQL add-on ekle
heroku addons:create heroku-postgresql:standard-0

# 5. Redis add-on ekle (optional)
heroku addons:create heroku-redis:premium-0

# 6. Environment variables ayarla
heroku config:set \
  SECRET_KEY="your-secret-key" \
  STRIPE_SECRET_KEY="sk_live_..." \
  ENVIRONMENT="production"

# 7. Deploy
git push heroku main

# 8. Migrate database
heroku run "alembic upgrade head"

# 9. Check
heroku logs --tail
heroku ps
```

### Cost Estimate
- Dyno (Basic): $50/month
- PostgreSQL (Standard): $50/month
- Redis (Premium): $30/month
- **Total: $130/month** (Most expensive but easiest)

---

## Post-Deployment Checklist

- [ ] Environment variables configured
- [ ] Database migrations ran successfully
- [ ] SSL certificate installed
- [ ] CORS configured for your domain
- [ ] Stripe webhooks configured
- [ ] Monitoring/logging enabled
- [ ] Backups automated
- [ ] CDN configured (optional)
- [ ] Error tracking (Sentry) setup
- [ ] Performance monitoring (Datadog) setup

---

## Monitoring & Maintenance

### Logs
```bash
# Docker
docker logs -f container_name

# Heroku
heroku logs --tail

# AWS CloudWatch
aws logs tail /ecs/tesvik-prod --follow
```

### Backups
```bash
# PostgreSQL backup
pg_dump DATABASE_URL > backup.sql

# Restore
psql DATABASE_URL < backup.sql
```

### Update & Redeploy
```bash
# Docker
docker build -f Dockerfile.prod -t tesvik:v2 .
docker push your-registry/tesvik:v2

# DigitalOcean
cd tesvik-asistani
git pull origin main
docker-compose -f docker-compose.prod.yml up -d

# Heroku
git push heroku main
```

---

## Security Best Practices

1. **Environment Variables**: Never commit secrets to git
   ```bash
   # Use .env.example (without values)
   # For secrets, use platform-specific secret management
   ```

2. **Database**: Always use encrypted connections
   ```python
   # In .env
   DATABASE_URL=postgresql+psycopg2://user:pass@host/db?sslmode=require
   ```

3. **Stripe**: Use environment-specific keys
   ```bash
   # Development: sk_test_...
   # Production: sk_live_...
   ```

4. **Rate Limiting**: Enabled in Nginx
   ```nginx
   limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
   ```

5. **SSL/TLS**: Use Let's Encrypt
   ```bash
   # Auto-renewal
   certbot renew --quiet --no-eff-email
   ```

---

## Scaling Guidelines

**Free Plan Users**: 1 server sufficient
- DigitalOcean $6/month droplet

**Pro Plan Users** (100-1000): 2-3 servers
- Load balancer
- 2-3 app instances
- RDS Multi-AZ

**Enterprise**: Full CDN + multi-region
- CloudFront + Route 53 (AWS)
- Multi-region databases
- Dedicated support

---

## Troubleshooting

### Database Connection Failed
```bash
# Check connection string
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### Stripe Webhook Not Working
```bash
# Check webhook logs
heroku addons:open papertrail  # For Heroku

# Retry failed webhooks in Stripe Dashboard
```

### High Memory Usage
```bash
# Check app memory
docker stats

# Increase resources or optimize code
```

---

**Ready to deploy? Choose your platform and follow the steps above!**
