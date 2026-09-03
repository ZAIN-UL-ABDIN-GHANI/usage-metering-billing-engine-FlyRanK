# Deployment Guide

Production deployment guide for FlyRank Billing Engine.

---

## Pre-Deployment Checklist

### Configuration
- [ ] Update `SECRET_KEY` to strong 32+ character random string
- [ ] Set `DEBUG=false`
- [ ] Set `ENVIRONMENT=production`
- [ ] Set `LOG_LEVEL=warning`
- [ ] Update `CORS_ORIGINS` to production domains only
- [ ] Configure database URL for production PostgreSQL
- [ ] Add Stripe live keys (when ready for production payments)

### Security
- [ ] Generate new database password
- [ ] Configure HTTPS/TLS certificates (Let's Encrypt)
- [ ] Set up firewall rules (only allow 80, 443)
- [ ] Enable security headers in Nginx
- [ ] Configure rate limiting
- [ ] Set up logging and monitoring
- [ ] Enable audit logging

### Database
- [ ] Create production PostgreSQL instance
- [ ] Configure database backups (daily)
- [ ] Set up replication (optional)
- [ ] Run migrations on production
- [ ] Verify database performance indexes
- [ ] Set up monitoring

### Monitoring & Alerting
- [ ] Set up application monitoring (DataDog, New Relic, etc.)
- [ ] Configure error tracking (Sentry)
- [ ] Set up alerting (PagerDuty, OpsGenie)
- [ ] Configure logging (ELK, CloudWatch, etc.)
- [ ] Health check monitoring

### Testing
- [ ] Run full test suite
- [ ] Verify all endpoints in staging
- [ ] Load test (1000+ concurrent users)
- [ ] Test failover scenarios
- [ ] Verify webhook retries

---

## Docker Compose Production

### Build Production Images

```bash
docker build -f Dockerfile.backend -t registry.example.com/flyrank-backend:latest .
docker build -f frontend/Dockerfile -t registry.example.com/flyrank-frontend:latest frontend/

# Push to registry
docker push registry.example.com/flyrank-backend:latest
docker push registry.example.com/flyrank-frontend:latest
```

### Docker Compose Production File

Create `docker-compose.prod.yml`:

```yaml
version: '3.9'

services:
  postgres:
    image: postgres:16-alpine
    container_name: flyrank_postgres_prod
    environment:
      POSTGRES_DB: flyrank_billing
      POSTGRES_USER: flyrank_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_prod_data:/var/lib/postgresql/data
      - ./backups:/backups
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U flyrank_user"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - flyrank_network
    restart: always
    command:
      - "postgres"
      - "-c"
      - "shared_buffers=256MB"
      - "-c"
      - "effective_cache_size=1GB"
      - "-c"
      - "work_mem=64MB"

  backend:
    image: registry.example.com/flyrank-backend:latest
    container_name: flyrank_backend_prod
    environment:
      DATABASE_URL: postgresql://flyrank_user:${POSTGRES_PASSWORD}@postgres:5432/flyrank_billing
      STRIPE_API_KEY: ${STRIPE_API_KEY}
      STRIPE_WEBHOOK_SECRET: ${STRIPE_WEBHOOK_SECRET}
      SECRET_KEY: ${SECRET_KEY}
      ENVIRONMENT: production
      LOG_LEVEL: warning
      DEBUG: "false"
      WORKERS: ${WORKERS:-4}
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - flyrank_network
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    image: registry.example.com/flyrank-frontend:latest
    container_name: flyrank_frontend_prod
    environment:
      VITE_API_URL: https://api.example.com/api
      VITE_STRIPE_PUBLIC_KEY: ${VITE_STRIPE_PUBLIC_KEY}
      NODE_ENV: production
    depends_on:
      - backend
    networks:
      - flyrank_network
    restart: always

  nginx:
    image: nginx:alpine
    container_name: flyrank_nginx_prod
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl/cert.pem:/etc/nginx/ssl/cert.pem:ro
      - ./ssl/key.pem:/etc/nginx/ssl/key.pem:ro
    depends_on:
      - backend
      - frontend
    networks:
      - flyrank_network
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_prod_data:
    driver: local

networks:
  flyrank_network:
    driver: bridge
```

### Deploy

```bash
# Set production environment variables
export STRIPE_API_KEY=sk_live_...
export STRIPE_WEBHOOK_SECRET=whsec_...
export SECRET_KEY=$(openssl rand -base64 32)
export POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Start production services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verify services
docker-compose ps
curl https://api.example.com/api/health

# View logs
docker-compose logs -f backend
```

---

## Kubernetes Deployment

### Build Images for K8s

```bash
docker build -f Dockerfile.backend -t myregistry/flyrank-backend:v0.1.0 .
docker build -f frontend/Dockerfile -t myregistry/flyrank-frontend:v0.1.0 frontend/

docker push myregistry/flyrank-backend:v0.1.0
docker push myregistry/flyrank-frontend:v0.1.0
```

### Create ConfigMaps and Secrets

```bash
# Create namespace
kubectl create namespace flyrank

# Create secrets
kubectl create secret generic flyrank-secrets \
  --from-literal=stripe-api-key=sk_live_... \
  --from-literal=stripe-webhook-secret=whsec_... \
  --from-literal=secret-key=$(openssl rand -base64 32) \
  --from-literal=db-password=$(openssl rand -base64 32) \
  -n flyrank

# Create configmap
kubectl create configmap flyrank-config \
  --from-literal=environment=production \
  --from-literal=log-level=warning \
  --from-literal=debug=false \
  -n flyrank
```

### Deploy Statefulset for PostgreSQL

```yaml
# postgres-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: flyrank-postgres
  namespace: flyrank
spec:
  serviceName: flyrank-postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: flyrank_billing
        - name: POSTGRES_USER
          value: flyrank_user
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: flyrank-secrets
              key: db-password
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        livenessProbe:
          exec:
            command:
            - /bin/sh
            - -c
            - pg_isready -U flyrank_user
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - /bin/sh
            - -c
            - pg_isready -U flyrank_user
          initialDelaySeconds: 5
          periodSeconds: 10
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: standard
      resources:
        requests:
          storage: 100Gi
---
apiVersion: v1
kind: Service
metadata:
  name: flyrank-postgres
  namespace: flyrank
spec:
  clusterIP: None
  selector:
    app: postgres
  ports:
  - port: 5432
```

### Deploy Backend

```yaml
# backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flyrank-backend
  namespace: flyrank
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
        image: myregistry/flyrank-backend:v0.1.0
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          value: "postgresql://flyrank_user:$(DB_PASSWORD)@flyrank-postgres:5432/flyrank_billing"
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: flyrank-secrets
              key: db-password
        - name: STRIPE_API_KEY
          valueFrom:
            secretKeyRef:
              name: flyrank-secrets
              key: stripe-api-key
        - name: STRIPE_WEBHOOK_SECRET
          valueFrom:
            secretKeyRef:
              name: flyrank-secrets
              key: stripe-webhook-secret
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: flyrank-secrets
              key: secret-key
        - name: ENVIRONMENT
          valueFrom:
            configMapKeyRef:
              name: flyrank-config
              key: environment
        - name: LOG_LEVEL
          valueFrom:
            configMapKeyRef:
              name: flyrank-config
              key: log-level
        - name: DEBUG
          valueFrom:
            configMapKeyRef:
              name: flyrank-config
              key: debug
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: flyrank-backend
  namespace: flyrank
spec:
  type: ClusterIP
  selector:
    app: backend
  ports:
  - port: 8000
    targetPort: 8000
```

### Deploy Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: flyrank-ingress
  namespace: flyrank
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.example.com
    secretName: flyrank-tls
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: flyrank-backend
            port:
              number: 8000
```

### Deploy

```bash
# Apply configurations
kubectl apply -f postgres-statefulset.yaml
kubectl apply -f backend-deployment.yaml
kubectl apply -f ingress.yaml

# Verify
kubectl get pods -n flyrank
kubectl logs -n flyrank -f deployment/flyrank-backend

# Run migrations
kubectl exec -n flyrank -it pod/flyrank-backend-xxxx -- \
  alembic upgrade head
```

---

## AWS ECS Deployment

### Create ECS Cluster

```bash
aws ecs create-cluster --cluster-name flyrank-prod
```

### Create Task Definition

```bash
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
```

### Create Service

```bash
aws ecs create-service \
  --cluster flyrank-prod \
  --service-name flyrank-backend \
  --task-definition flyrank-backend:1 \
  --desired-count 2 \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:...
```

---

## Cloud Run (Google Cloud)

### Build and Push

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/flyrank-backend:latest
gcloud builds submit -f frontend/Dockerfile --tag gcr.io/PROJECT_ID/flyrank-frontend:latest
```

### Deploy Backend

```bash
gcloud run deploy flyrank-backend \
  --image gcr.io/PROJECT_ID/flyrank-backend:latest \
  --platform managed \
  --region us-central1 \
  --memory 512Mi \
  --set-env-vars="DATABASE_URL=${DB_URL},STRIPE_API_KEY=${STRIPE_KEY}" \
  --allow-unauthenticated
```

---

## Monitoring & Observability

### Application Monitoring (DataDog)

```python
# Add to main.py
from ddtrace import patch_all

patch_all()
```

### Error Tracking (Sentry)

```python
import sentry_sdk

sentry_sdk.init(dsn="https://...@sentry.io/...", environment="production")
```

### Logging (ELK/CloudWatch)

Configure in environment variables for log destination.

### Database Monitoring

- Use CloudWatch or DataDog for PostgreSQL metrics
- Monitor query performance
- Alert on slow queries (>1s)

---

## Backup & Recovery

### Database Backups

```bash
# Daily backup
0 2 * * * pg_dump -h postgres -U flyrank_user flyrank_billing | gzip > /backups/db-$(date +\%Y\%m\%d).sql.gz

# Weekly full backup to S3
0 3 * * 0 aws s3 cp /backups/db-$(date +\%Y\%m\%d).sql.gz s3://flyrank-backups/weekly/
```

### Point-in-Time Recovery

```bash
# Restore from backup
gunzip < /backups/db-20240915.sql.gz | psql -h postgres -U flyrank_user flyrank_billing
```

---

## Scaling

### Horizontal Scaling

```bash
# Scale backend replicas
docker-compose up -d --scale backend=3

# Or in Kubernetes
kubectl scale deployment flyrank-backend --replicas=5 -n flyrank
```

### Database Connection Pooling

Use PgBouncer or connection pooling in SQLAlchemy:

```python
# app/database.py
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
)
```

---

## Performance Tuning

### PostgreSQL Configuration

```sql
-- Optimize for 8GB RAM server
shared_buffers = 2GB
effective_cache_size = 6GB
work_mem = 50MB
maintenance_work_mem = 512MB
```

### Nginx Caching

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m;

location /api/ {
    proxy_cache api_cache;
    proxy_cache_valid 200 1m;
}
```

---

## Disaster Recovery

### Regular Testing

- Test backups weekly
- Perform failover drills monthly
- Document RTO (Recovery Time Objective) and RPO (Recovery Point Objective)

### Failover Plan

1. Promote standby database
2. Update connection strings
3. Verify application connectivity
4. Monitor error rates
5. Document incident

---

## Security in Production

### HTTPS/TLS

- Use Let's Encrypt for certificates (free)
- Auto-renew with certbot
- Use strong ciphers (TLS 1.2+)

### Database Security

- Use VPC/Security Groups to restrict access
- Enable encryption at rest
- Enable encryption in transit
- Regular security patches

### Secrets Management

- Use managed secrets (AWS Secrets Manager, Vault)
- Rotate credentials regularly
- Audit access logs

---

## Support & Troubleshooting

### Application Won't Start

```bash
docker-compose logs backend
# Check DATABASE_URL, STRIPE keys, SECRET_KEY
```

### Database Connection Issues

```bash
docker-compose exec postgres psql -U flyrank_user -d flyrank_billing -c "SELECT 1"
```

### Memory Issues

```bash
docker stats
# Increase container limits or scale horizontally
```

---

**Last Updated**: September 2026
