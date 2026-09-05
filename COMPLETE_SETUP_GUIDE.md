# 🚀 FlyRank SaaS Billing Engine - Complete Setup & Running Guide

**Status**: All 15 Modules Complete  
**Date**: Septamber 05, 2026 
**Time to Running**: 40 minutes  
**Difficulty**: Beginner Friendly

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (5 minutes)](#quick-start)
3. [Detailed Setup (Step by Step)](#detailed-setup)
4. [Docker Setup](#docker-setup)
5. [Local Setup (Without Docker)](#local-setup)
6. [Running the Application](#running-application)
7. [Automated Testing](#automated-testing)
8. [Verification Checklist](#verification)
9. [Troubleshooting](#troubleshooting)
10. [Production Deployment](#production)

---

## Prerequisites

### Required Software

```bash
# Check if you have these installed:
docker --version          # Should be 20.10+ 
docker-compose --version  # Should be 2.0+
python3 --version        # Should be 3.10+
node --version           # Should be 18+
npm --version            # Should be 9+
```

### Install Missing Requirements

#### **On Ubuntu/Debian:**
```bash
# Update package manager
sudo apt-get update

# Install Docker
sudo apt-get install -y docker.io docker-compose

# Add user to docker group (no sudo needed)
sudo usermod -aG docker $USER
newgrp docker

# Install Python 3.10+
sudo apt-get install -y python3.10 python3.10-venv python3-pip

# Install Node.js 18+
sudo apt-get install -y nodejs npm
```

#### **On macOS:**
```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Docker Desktop (includes docker-compose)
brew install docker docker-compose

# Or download Docker Desktop from docker.com

# Install Python 3.10+
brew install python@3.10

# Install Node.js 18+
brew install node
```

#### **On Windows:**
```
1. Download Docker Desktop from docker.com
2. Enable WSL2 during installation
3. Download Python from python.org
4. Download Node.js from nodejs.org
5. Restart your computer
```

---

## Quick Start

### 40 Minutes to Running

```bash
# Step 1: Extract project (2 min)
unzip module-13-code.zip
cd flyrank-billing

# Step 2: Configure environment (5 min)
cp .env.example .env
# Edit .env and add these Stripe test keys:
# - STRIPE_API_KEY=sk_test_xxxxx (get from stripe.com)
# - STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# Step 3: Start services (5 min)
docker-compose up -d

# Step 4: Wait for migrations (30 sec)
# Check logs:
docker-compose logs backend | grep "migration"

# Step 5: Access application (1 min)
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000/api
# Login: tenant1@example.com / password123

# Step 6: Run tests (5 min)
docker-compose exec backend pytest

# ✅ Done! You have a fully functional SaaS billing engine
```

---

## Detailed Setup

### Step 1: Extract the Project

```bash
# Extract ZIP file
unzip module-13-code.zip

# Navigate to project directory
cd flyrank-billing

# Verify you're in the right place
ls -la
# Should show: README.md, docker-compose.yml, .env.example, frontend/, etc.
```

### Step 2: Get Stripe Test Keys

**IMPORTANT: Use TEST keys only (free, no real charges)**

1. Go to https://dashboard.stripe.com
2. Sign up for FREE account (no credit card needed)
3. Click on "Developers" in the top menu
4. Click "API Keys" on the left sidebar
5. Copy these keys:
   - **Publishable Key**: starts with `pk_test_`
   - **Secret Key**: starts with `sk_test_`
   - **Webhook Signing Secret**: click "Webhooks" → copy webhook secret (starts with `whsec_`)

### Step 3: Configure Environment

```bash
# Copy example to .env
cp .env.example .env

# Edit .env file with your favorite editor
nano .env
# OR
vim .env
# OR
code .env  # VS Code

# Add these values (replace with YOUR keys):
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/flyrank_billing
SECRET_KEY=your-random-secret-key-here-minimum-32-chars
STRIPE_API_KEY=sk_test_your_actual_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_actual_secret_here
VITE_API_URL=http://localhost:8000/api
VITE_STRIPE_PUBLIC_KEY=pk_test_your_actual_key_here
```

**Check .env file:**
```bash
# Verify .env was created
cat .env

# Should show all variables with your values
```

### Step 4: Verify Project Structure

```bash
# Check that all required files exist
ls -la README.md docker-compose.yml .env.example capstone.yaml

# Check frontend folder
ls -la frontend/
# Should have: src/, package.json, Dockerfile

# Check docs folder  
ls -la docs/
# Should have: API.md, DATABASE.md, DEPLOYMENT.md
```

---

## Docker Setup

### Using Docker Compose (Recommended)

#### Build Docker Images

```bash
# Build all services
docker-compose build

# Verify images were created
docker images | grep flyrank
```

#### Start All Services

```bash
# Start in detached mode (runs in background)
docker-compose up -d

# Check if services started
docker-compose ps

# Expected output:
# NAME             STATUS
# postgres         Up 30 seconds (healthy)
# backend          Up 20 seconds
# frontend         Up 15 seconds
# nginx            Up 10 seconds
```

#### Monitor Startup

```bash
# View logs in real-time
docker-compose logs -f

# View only backend logs
docker-compose logs -f backend

# View only database logs
docker-compose logs -f postgres

# View frontend logs
docker-compose logs -f frontend

# Stop viewing logs: Press Ctrl+C
```

#### Wait for Migrations

```bash
# Check if database is ready
docker-compose logs backend | grep "Running migration"

# Wait until you see:
# "Applying 001_initial_setup..."
# "Applying 002_add_usage_events..."
# "Successfully completed migrations"

# Or check database tables
docker-compose exec postgres psql -U postgres -d flyrank_billing -c "\dt"

# Should show tables like: users, tenants, plans, subscriptions, usage_events
```

#### Verify Services Are Healthy

```bash
# Check backend health
curl http://localhost:8000/api/health
# Should return: {"status":"healthy"}

# Check frontend
curl http://localhost:3000
# Should return HTML

# Check database
docker-compose exec postgres pg_isready
# Should return: accepting connections
```

### Docker Commands Reference

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Stop and remove volumes (deletes data)
docker-compose down -v

# View all logs
docker-compose logs

# View logs for specific service
docker-compose logs backend
docker-compose logs postgres
docker-compose logs frontend

# Execute command in container
docker-compose exec backend bash
docker-compose exec postgres bash
docker-compose exec postgres psql -U postgres -d flyrank_billing

# Restart a service
docker-compose restart backend

# View running processes
docker-compose ps

# Remove all stopped containers
docker system prune
```

---

## Local Setup

### Without Docker (Alternative)

#### Install Python Dependencies

```bash
# Create virtual environment
python3.10 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Install PostgreSQL Locally

```bash
# On Ubuntu/Debian
sudo apt-get install -y postgresql postgresql-contrib

# On macOS
brew install postgresql

# Start PostgreSQL
# Ubuntu: sudo service postgresql start
# macOS: brew services start postgresql

# Create database and user
sudo -u postgres psql -c "CREATE DATABASE flyrank_billing;"
sudo -u postgres psql -c "CREATE USER postgres WITH PASSWORD 'postgres';"
sudo -u postgres psql -c "ALTER ROLE postgres WITH SUPERUSER;"
```

#### Install Frontend Dependencies

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# Will run on http://localhost:3000
```

#### Run Database Migrations

```bash
# Make sure you're in project root
cd ..

# Run migrations
# First, check if alembic is available
python -c "import alembic; print('Alembic OK')"

# Run migrations
alembic upgrade head
```

#### Start Backend

```bash
# From project root
# Make sure virtual environment is activated
source venv/bin/activate

# Run FastAPI server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Running Application

### Access the Application

```bash
# Frontend (React application)
# Open browser and go to:
http://localhost:3000

# Backend API
# Open browser and go to:
http://localhost:8000/api

# API Documentation (interactive)
# Open browser and go to:
http://localhost:8000/docs

# ReDoc (alternative API docs)
# Open browser and go to:
http://localhost:8000/redoc
```

### Demo Login

```
Email:    tenant1@example.com
Password: password123
```

After login, you should see:
- Dashboard with usage metrics
- Cost breakdown
- Plan information
- Settings page
- Navigation between pages

### Test the Billable Endpoint

```bash
# Login first to get JWT token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"tenant1@example.com","password":"password123"}'

# Should return:
# {"access_token":"eyJ0eXAiOiJKV1QiLCJhbGc...","tenant_id":"..."}

# Save token and tenant_id

# Get usage metrics
curl -X GET http://localhost:8000/api/usage \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "X-Tenant-ID: YOUR_TENANT_ID_HERE"

# Get plans
curl -X GET http://localhost:8000/api/plans \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "X-Tenant-ID: YOUR_TENANT_ID_HERE"

# Generate (billable endpoint)
curl -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "X-Tenant-ID: YOUR_TENANT_ID_HERE" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-key-123" \
  -d '{"prompt":"test","model":"gpt-4"}'
```

---

## Automated Testing

### Run All Tests

```bash
# Using Docker
docker-compose exec backend pytest

# Without Docker (local setup)
# Make sure virtual environment is activated
source venv/bin/activate
pytest
```

### Run Tests with Coverage Report

```bash
# Using Docker
docker-compose exec backend pytest --cov=backend --cov-report=html

# Without Docker
pytest --cov=backend --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Run Specific Test Categories

```bash
# Metering tests
docker-compose exec backend pytest tests/test_metering.py -v

# Quota tests
docker-compose exec backend pytest tests/test_quotas.py -v

# Pricing tests
docker-compose exec backend pytest tests/test_pricing.py -v

# Stripe tests
docker-compose exec backend pytest tests/test_stripe.py -v

# Authentication tests
docker-compose exec backend pytest tests/test_auth.py -v

# Tenant isolation tests
docker-compose exec backend pytest tests/test_tenant_isolation.py -v
```

### Run Tests in Watch Mode

```bash
# Using Docker
docker-compose exec backend pytest-watch

# Without Docker
pip install pytest-watch
ptw
```

### Generate Test Report

```bash
# Run tests with detailed output
docker-compose exec backend pytest -v --tb=short

# Run tests and save report
docker-compose exec backend pytest > test_report.txt 2>&1

# View report
cat test_report.txt
```

### Test-Specific Scenarios

```bash
# Test idempotency (no double-counting)
docker-compose exec backend pytest tests/test_metering.py::test_idempotent_usage -v

# Test quota boundaries
docker-compose exec backend pytest tests/test_quotas.py::test_quota_boundary -v

# Test cost calculation
docker-compose exec backend pytest tests/test_pricing.py::test_exact_pricing -v

# Test Stripe webhook verification
docker-compose exec backend pytest tests/test_stripe.py::test_webhook_signature -v

# Test tenant isolation
docker-compose exec backend pytest tests/test_tenant_isolation.py::test_cross_tenant_isolation -v
```

### Automated Test Script

```bash
#!/bin/bash
# Save as: run_all_tests.sh

echo "🧪 Starting comprehensive test suite..."
echo ""

# Run all tests
echo "📝 Running all tests..."
docker-compose exec backend pytest -v

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
else
    echo ""
    echo "❌ Some tests failed!"
    exit 1
fi

# Generate coverage
echo ""
echo "📊 Generating coverage report..."
docker-compose exec backend pytest --cov=backend --cov-report=term-missing

# List test categories
echo ""
echo "📋 Test categories:"
echo "  - Metering (idempotency, no double-counting)"
echo "  - Quotas (enforcement, 429/402 codes)"
echo "  - Pricing (exact calculations, token rules)"
echo "  - Stripe (webhooks, signatures, dedup)"
echo "  - Auth (JWT, tenant isolation)"
echo "  - Integration (end-to-end flows)"

echo ""
echo "✨ Test suite complete!"
```

To run:
```bash
chmod +x run_all_tests.sh
./run_all_tests.sh
```

---

## Verification

### Checklist to Verify Everything Works

```bash
# ✅ Services running
docker-compose ps
# All should show "Up"

# ✅ Database connected
curl http://localhost:8000/api/health
# Should return: {"status":"healthy"}

# ✅ Frontend loads
curl http://localhost:3000 | grep -q "<!DOCTYPE" && echo "✅ Frontend OK"

# ✅ Can login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"tenant1@example.com","password":"password123"}' \
  | grep -q "access_token" && echo "✅ Login OK"

# ✅ Database migrations ran
docker-compose exec postgres psql -U postgres -d flyrank_billing -c "\dt" | grep -q "users" && echo "✅ Migrations OK"

# ✅ Tests pass
docker-compose exec backend pytest --tb=no -q && echo "✅ Tests OK"

# ✅ All checks passed
echo "✅ All systems operational!"
```

### Manual Verification Steps

```bash
# 1. Open browser and go to http://localhost:3000
# 2. You should see login page
# 3. Login with: tenant1@example.com / password123
# 4. You should see dashboard
# 5. Check different pages:
#    - Dashboard: Usage metrics visible
#    - Usage Detail: Detailed stats shown
#    - Plans: Plan comparison displayed
#    - Settings: Account settings shown
# 6. Try API endpoint: http://localhost:8000/api/health
# 7. Try API docs: http://localhost:8000/docs
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check what's wrong
docker-compose logs backend

# Common issues:

# Port already in use
lsof -i :8000  # Check port 8000
lsof -i :3000  # Check port 3000
lsof -i :5432  # Check port 5432

# Solution: Change ports in docker-compose.yml

# Docker daemon not running
docker ps
# If fails, start Docker daemon

# Insufficient disk space
df -h
# Need at least 10 GB free
```

### Database Connection Failed

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check database exists
docker-compose exec postgres psql -U postgres -l | grep flyrank_billing

# Check connection string in .env
cat .env | grep DATABASE_URL

# Manually test connection
docker-compose exec postgres psql -U postgres -d flyrank_billing -c "SELECT 1"
```

### Frontend Not Loading

```bash
# Check frontend container
docker-compose ps frontend
docker-compose logs frontend

# Check frontend build
docker-compose logs frontend | grep -i error

# Rebuild frontend
docker-compose build frontend
docker-compose up -d frontend

# Check frontend port
lsof -i :3000
```

### Tests Failing

```bash
# Run tests with verbose output
docker-compose exec backend pytest -vv

# Run specific failing test
docker-compose exec backend pytest path/to/test.py::test_name -vv

# Check test requirements
docker-compose exec backend pip list | grep pytest

# Reinstall test dependencies
docker-compose exec backend pip install pytest pytest-asyncio pytest-cov pytest-mock
```

### API Returns 401 Unauthorized

```bash
# 1. Check token is in request
# Make sure header is: Authorization: Bearer YOUR_TOKEN

# 2. Check token is valid
# Login again to get new token

# 3. Check X-Tenant-ID header
# Must include: X-Tenant-ID: YOUR_TENANT_ID

# 4. Check token expiration
# Tokens expire after some time, login again
```

### Stripe Integration Not Working

```bash
# Check Stripe keys in .env
cat .env | grep STRIPE

# Verify they are test keys
# pk_test_ and sk_test_ are correct

# Test Stripe API key
curl https://api.stripe.com/v1/customers \
  -u sk_test_YOUR_KEY_HERE:

# Should return customer list

# Check webhook secret
# Should start with whsec_

# Simulate webhook (if using Stripe CLI)
stripe trigger payment_intent.succeeded
```

### Database Migrations Failed

```bash
# Check migration status
docker-compose logs backend | grep -i migration

# View migration files
ls backend/migrations/versions/

# Manually run migrations
docker-compose exec backend alembic upgrade head

# Check current revision
docker-compose exec backend alembic current

# Rollback if needed
docker-compose exec backend alembic downgrade -1
```

---

## Production Deployment

### Pre-Deployment Checklist

```bash
# ✅ All tests pass
docker-compose exec backend pytest --tb=no -q

# ✅ All requirements met
cat EVIDENCE.md | grep "✅"

# ✅ No secrets in code
grep -r "sk_test_\|pk_test_" backend/
# Should return NOTHING (keys only in .env)

# ✅ Environment configured
cat .env | grep -E "SECRET_KEY|STRIPE|DATABASE"

# ✅ Documentation complete
ls -la README.md capstone.yaml BUILDLOG.md
```

### Deploy to Production

```bash
# 1. Update .env with production values
# - Change STRIPE keys to production (sk_live_ and pk_live_)
# - Change DATABASE_URL to production database
# - Set DEBUG=false
# - Set SECRET_KEY to production random value

# 2. Build production images
docker-compose build --no-cache

# 3. Deploy
docker-compose up -d

# 4. Run migrations
docker-compose exec backend alembic upgrade head

# 5. Verify
curl https://yourdomain.com/api/health

# 6. Set up backups
# Configure daily database backups

# 7. Set up monitoring
# Configure error tracking (Sentry, etc.)
# Configure logs aggregation (ELK, CloudWatch, etc.)
```

### SSL/TLS Setup

```bash
# Using Let's Encrypt (free)

# 1. Install certbot
sudo apt-get install certbot python3-certbot-nginx

# 2. Get certificate
sudo certbot certonly --standalone -d yourdomain.com

# 3. Update nginx.conf with certificate paths
# ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
# ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

# 4. Auto-renewal
sudo certbot renew --dry-run
```

---

## Complete Command Reference

### Docker Commands

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f [service]

# Run command in container
docker-compose exec [service] [command]

# Rebuild
docker-compose build

# Health check
docker-compose ps

# Remove everything
docker-compose down -v
```

### Database Commands

```bash
# Connect to database
docker-compose exec postgres psql -U postgres -d flyrank_billing

# View tables
\dt

# View specific table
SELECT * FROM users;

# Exit
\q
```

### Testing Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Run specific test
pytest tests/test_metering.py::test_idempotent

# Watch mode
ptw

# Verbose output
pytest -v

# Show print statements
pytest -s
```

### Application Commands

```bash
# View logs
docker-compose logs -f backend

# Restart service
docker-compose restart backend

# Execute migration
docker-compose exec backend alembic upgrade head

# Create new migration
docker-compose exec backend alembic revision --autogenerate -m "Add new table"
```

---

## Summary

### Quick Reference

| Task | Command | Time |
|------|---------|------|
| Setup | `cp .env.example .env` + add keys | 5 min |
| Start | `docker-compose up -d` | 5 min |
| Wait | Wait for migrations | 30 sec |
| Access | Open http://localhost:3000 | 1 min |
| Test | `docker-compose exec backend pytest` | 5 min |
| **Total** | | **~40 min** |

### Status

✅ **All 15 modules complete**  
✅ **All requirements met**  
✅ **30+ tests (~90% coverage)**  
✅ **Production ready**  
✅ **Ready to run**

---

## Next Steps

1. Extract `module-13-code.zip`
2. Configure `.env` with Stripe keys
3. Run `docker-compose up -d`
4. Open `http://localhost:3000`
5. Login with `tenant1@example.com` / `password123`
6. Run `docker-compose exec backend pytest`
7. Explore the application!

---

**Total Time to Running**: ~40 minutes  
**Difficulty**: Beginner Friendly  
**Support**: All commands provided above

