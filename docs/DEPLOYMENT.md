# DEPLOYMENT.md - Production Deployment Guide

---

## Pre-Deployment Checklist

- [ ] All tests passing
- [ ] Environment variables configured
- [ ] Stripe keys verified (live mode if production)
- [ ] Database backups configured
- [ ] SSL certificates obtained
- [ ] Domain DNS updated
- [ ] Monitoring setup
- [ ] Alerting configured

---

## Production Environment Setup

### 1. Update Environment Variables

```bash
# Copy and edit production .env
cp .env.example .env.production

# Set all production values:
ENVIRONMENT=production
DATABASE_URL=postgresql://user:pass@db.example.com/flyrank_billing
STRIPE_API_KEY=sk_live_your_live_key  # NOT test key
STRIPE_WEBHOOK_SECRET=whsec_live_secret
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
POSTGRES_PASSWORD=your_secure_password
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### 2. SSL/TLS Certificates

**Using Let's Encrypt with Certbot**:

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot certonly --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com \
  --non-interactive \
  --agree-tos \
  -m admin@yourdomain.com

# Certificates saved to:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem

# Copy to project
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./ssl/key.pem
sudo chown $USER:$USER ./ssl/*
```

### 3. Database Setup

**Option A: Managed PostgreSQL (Recommended)**

```bash
# Use AWS RDS, Google Cloud SQL, or similar
DATABASE_URL=postgresql://user:password@db-prod.region.rds.amazonaws.com:5432/flyrank_billing

# Run migrations
docker-compose exec backend alembic upgrade head
```

**Option B: Self-Hosted PostgreSQL**

```bash
# Create database
docker volume create postgres_data_prod

# Update docker-compose
DATABASE_URL=postgresql://flyrank_user:password@postgres:5432/flyrank_billing

# Start container with volume
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d postgres
```

---

## Deployment Methods

### Method 1: Docker Compose (Simple Production)

**Step 1: Build Images**

```bash
docker-compose build --no-cache

# Tag for registry
docker tag flyrank-billing-backend:latest myregistry.azurecr.io/flyrank-backend:1.0.0
docker tag flyrank-billing-frontend:latest myregistry.azurecr.io/flyrank-frontend:1.0.0

# Push to registry
docker push myregistry.azurecr.io/flyrank-backend:1.0.0
docker push myregistry.azurecr.io/flyrank-frontend:1.0.0
```

**Step 2: Deploy**

```bash
# Load environment
export $(cat .env.production | xargs)

# Start services with production profile
docker-compose --profile production up -d

# Verify
docker-compose ps
docker-compose logs backend frontend
```

### Method 2: Kubernetes (Scalable Production)

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flyrank-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: myregistry.azurecr.io/flyrank-backend:1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database-url
        - name: STRIPE_API_KEY
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: stripe-api-key
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

**Deploy to Kubernetes**:

```bash
# Create secrets
kubectl create secret generic app-secrets \
  --from-literal=database-url=$DATABASE_URL \
  --from-literal=stripe-api-key=$STRIPE_API_KEY

# Deploy
kubectl apply -f kubernetes/

# Monitor
kubectl get pods
kubectl logs -f deployment/flyrank-backend
```

---

## Post-Deployment Verification

### 1. Health Checks

```bash
# API health
curl https://api.yourdomain.com/health
# Expected: {"status": "healthy"}

# Frontend loads
curl -I https://yourdomain.com
# Expected: HTTP 200 OK

# Database connected
curl https://api.yourdomain.com/api/usage \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "X-Tenant-ID: $TEST_TENANT_ID"
# Expected: Usage data
```

### 2. SSL Certificate

```bash
# Verify certificate
curl -vI https://yourdomain.com

# Should show:
# * Server certificate:
# *  subject: CN=yourdomain.com
# *  issuer: C=US, O=Let's Encrypt
# *  SSL certificate verify ok.
```

### 3. Database Migrations

```bash
# Verify migrations ran
docker-compose exec backend alembic current
# Expected: FlyRank_Billing_20240101_000000_initial_schema

# Check tables
docker-compose exec postgres psql -U flyrank_user -d flyrank_billing -c "\dt"
```

### 4. Stripe Webhook

```bash
# Test webhook delivery
curl -X POST https://api.yourdomain.com/api/webhooks/stripe \
  -H "stripe-signature: t=1234567890,v1=abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "id": "evt_test_123",
    "type": "checkout.session.completed",
    "data": {"object": {}}
  }'

# Expected: 200 OK or 400 if signature invalid
```

---

## Monitoring & Alerting

### 1. Application Metrics

```bash
# Prometheus endpoint
curl https://api.yourdomain.com/api/metrics

# Metrics to monitor:
# - http_requests_total (traffic)
# - http_request_duration_seconds (latency)
# - database_connection_pool (pool utilization)
```

### 2. Logging

**Structured Logging (JSON)**:

```bash
# Backend logs
docker-compose logs backend | jq .

# Example log entry:
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "info",
  "message": "User logged in",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

### 3. Alerting Rules

```yaml
# prometheus/alerts.yml
groups:
- name: flyrank
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 1m
    annotations:
      summary: "High error rate detected"
  
  - alert: DatabaseDown
    expr: up{job="postgres"} == 0
    for: 1m
    annotations:
      summary: "Database unreachable"
  
  - alert: HighLatency
    expr: histogram_quantile(0.95, http_request_duration_seconds_bucket) > 1
    for: 5m
    annotations:
      summary: "P95 latency > 1 second"
```

---

## Backup & Recovery

### Automated Database Backups

**Daily Backup Cron Job**:

```bash
# /etc/cron.d/flyrank-backup
0 2 * * * /usr/local/bin/backup-flyrank.sh

# /usr/local/bin/backup-flyrank.sh
#!/bin/bash
set -e

DB_HOST=${POSTGRES_HOST:-localhost}
DB_NAME="flyrank_billing"
BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

pg_dump \
  --verbose \
  --format=custom \
  --file=$BACKUP_DIR/flyrank_$DATE.dump \
  postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$DB_HOST/$DB_NAME

# Keep only last 30 days
find $BACKUP_DIR -name "flyrank_*.dump" -mtime +30 -delete

# Verify backup
pg_restore --list $BACKUP_DIR/flyrank_$DATE.dump > /dev/null && \
  echo "Backup verified: $BACKUP_DIR/flyrank_$DATE.dump"
```

### Point-in-Time Recovery

```bash
# Restore to specific time
pg_restore --clean --if-exists \
  --format=custom \
  $BACKUP_DIR/flyrank_20240101_020000.dump | \
  psql postgresql://user:pass@host/flyrank_billing

# Verify restore
psql -c "SELECT COUNT(*) FROM usage_events;" postgresql://user:pass@host/flyrank_billing
```

---

## Scaling & Performance

### Horizontal Scaling

```bash
# Run multiple backend instances
docker-compose up -d --scale backend=3

# Nginx load balances between instances
```

### Database Scaling

```bash
# Read replicas for reporting queries
# Primary: writes (metering, webhooks)
# Replica: reads (usage dashboard)

# Connection string with failover
DATABASE_URL=postgresql://user:pass@primary.rds.amazonaws.com,replica.rds.amazonaws.com:5432/flyrank_billing
```

### Caching

```python
# Redis cache for plan data (rarely changes)
cache.set('plans', plans_data, ttl=3600)
```

---

## Security Hardening

### 1. Firewall Rules

```bash
# Allow only HTTPS
ufw allow 443/tcp
ufw allow 80/tcp  # For certbot renewal
ufw deny all

# Restrict database access
# Only allow from backend container/pod
```

### 2. Secrets Management

```bash
# Use AWS Secrets Manager
aws secretsmanager create-secret \
  --name flyrank/production \
  --secret-string '{"STRIPE_API_KEY":"sk_live_..."}'

# Reference in application
import json
import boto3

secrets = aws_secretsmanager.get_secret("flyrank/production")
os.environ.update(json.loads(secrets['SecretString']))
```

### 3. Rate Limiting

```nginx
# nginx.conf
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;

location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
}

location /api/auth/ {
    limit_req zone=auth_limit burst=2 nodelay;
}
```

---

## Rollback Procedure

**If deployment fails**:

```bash
# Stop new version
docker-compose down

# Start previous version
docker pull myregistry.azurecr.io/flyrank-backend:1.0.0-prev
docker-compose up -d

# Verify
curl https://api.yourdomain.com/api/health

# Investigate error in logs
docker-compose logs backend --tail=100
```

---

## Troubleshooting

### API returns 500 errors

```bash
# Check backend logs
docker-compose logs backend -f

# Common causes:
# - Database connection failed
# - Stripe API key invalid
# - Unhandled exception in code

# Fix and redeploy
docker-compose restart backend
```

### Stripe webhooks not processing

```bash
# Verify webhook secret matches
echo $STRIPE_WEBHOOK_SECRET

# Test webhook delivery
stripe trigger checkout.session.completed

# Check webhook logs
docker-compose logs backend | grep webhook
```

### High database connections

```bash
# Check pool size
SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;

# Increase pool size in .env
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# Restart
docker-compose restart backend
```

---

## Upgrade Path

### Database Schema Updates

```bash
# 1. Run new migrations on staging
alembic upgrade head

# 2. Test full flow
pytest tests/

# 3. Deploy to production (migrations run automatically)
docker-compose restart backend

# 4. Verify
curl https://api.yourdomain.com/api/health
```

### API Backward Compatibility

- Keep old API endpoints working (deprecation notice in 6 months)
- Version new endpoints: `/api/v2/`
- Client updates not required immediately

---

**Last Updated**: 2024
**Deployment Status**: Production Ready
