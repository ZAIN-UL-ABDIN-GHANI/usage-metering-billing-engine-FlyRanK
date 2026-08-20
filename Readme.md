# FlyRank Usage Metering & Billing Engine

Production-ready usage metering and billing engine with Stripe integration for SaaS platforms.

## Overview

This service answers three critical questions every SaaS product must handle:

1. **How much has this customer used?** - Metering and tracking usage
2. **How much should they pay?** - Cost calculation with complex pricing rules
3. **Have they reached their plan limits?** - Quota enforcement

The system is built for **correctness under retries, failures, and real-world conditions** with:

- ✅ Exactly-once metering (no double-counting on retries)
- ✅ Precise quota enforcement with proper HTTP status codes
- ✅ Complex token pricing (cached input, reasoning tokens)
- ✅ Stripe test-mode integration with webhook verification
- ✅ Multi-tenant architecture with data isolation
- ✅ Production-grade testing and documentation

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│      FastAPI Application            │
├─────────────────────────────────────┤
│ • Tenant Management                 │
│ • Billable Endpoints                │
│ • Usage Metering & Quotas           │
│ • Cost Calculation                  │
│ • Stripe Checkout & Webhooks        │
└──────┬──────────────┬────────────────┘
       │              │
       ▼              ▼
  ┌────────────┐  ┌──────────────┐
  │ PostgreSQL │  │ Stripe (Test)│
  │  Database  │  │    API       │
  └────────────┘  └──────────────┘
```

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.10+ |
| Framework | FastAPI | 0.104.1 |
| ORM | SQLAlchemy | 2.0.23 |
| Database | PostgreSQL | 15 |
| Migrations | Alembic | 1.12.1 |
| Payments | Stripe | 7.4.0 |
| Validation | Pydantic | 2.5.0 |
| Testing | pytest | 7.4.3 |
| Container | Docker | Compose |

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (or PostgreSQL 15)
- Stripe test account
- Git

### 1. Clone & Setup

```bash
# Clone the repository
git clone https://github.com/flyrank/flyrank-capstone-metering-billing.git
cd flyrank-capstone-metering-billing

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` with your values:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/metering_billing_db

# Stripe (Test Mode Only)
STRIPE_API_KEY=sk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_secret_here
SECRET_KEY=your-minimum-32-character-secret-key-for-production
```

### 3. Run with Docker Compose

```bash
# Start services (PostgreSQL + FastAPI)
docker-compose up -d

# Wait for database to be ready
docker-compose logs -f app

# Database migrations run automatically
```

The application will be available at `http://localhost:8000`

### 4. Verify Setup

```bash
# Health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs
```

## Running Without Docker

### 1. Install Dependencies

```bash
# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup Database

```bash
# Start PostgreSQL (using Docker)
docker run -d \
  --name metering_postgres \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=metering_billing_db \
  -p 5432:5432 \
  postgres:15-alpine

# Wait for database to be ready
sleep 5

# Run migrations
alembic upgrade head
```

### 3. Start Application

```bash
# Set environment variables
export DATABASE_URL=postgresql://user:password@localhost:5432/metering_billing_db
export STRIPE_API_KEY=sk_test_your_key_here
export STRIPE_WEBHOOK_SECRET=whsec_your_secret_here
export SECRET_KEY=your-32-char-minimum-secret-key

# Run application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Database Migrations

### View Current Status

```bash
alembic current
```

### Apply All Pending Migrations

```bash
alembic upgrade head
```

### Create New Migration

```bash
# Auto-generate migration
alembic revision --autogenerate -m "Description of change"

# Or create empty migration
alembic revision -m "Description of change"

# Apply immediately
alembic upgrade head
```

## Stripe Setup for Testing

### 1. Stripe Account

Create a free Stripe account at https://stripe.com

### 2. API Keys

Copy your **test mode** keys from Dashboard → Developers → API keys:
- Publishable key: `pk_test_...`
- Secret key: `sk_test_...`

### 3. Webhook Secret

1. Go to Dashboard → Developers → Webhooks
2. Add endpoint: `http://localhost:8000/webhooks/stripe`
3. Subscribe to events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copy the signing secret: `whsec_...`

### 4. Test Stripe CLI (Local Webhook Testing)

```bash
# Install Stripe CLI: https://stripe.com/docs/stripe-cli

# Forward webhooks to local app
stripe listen --forward-to localhost:8000/webhooks/stripe

# Copy the signing secret output to .env STRIPE_WEBHOOK_SECRET

# In another terminal, trigger test events
stripe trigger payment_intent.succeeded
stripe trigger checkout.session.completed
```

## Core API Endpoints

### Health & Status

```bash
# Health check
GET /health

# Readiness check
GET /ready

# Root info
GET /
```

### Tenants

```bash
# Create tenant
POST /tenants
{
  "name": "Acme Corp",
  "email": "hello@acme.com"
}

# Get tenant
GET /tenants/{tenant_id}

# Update tenant
PUT /tenants/{tenant_id}
```

### Usage Metering

```bash
# Record usage (billable action - idempotent)
POST /usage/record
{
  "tenant_id": "tenant-123",
  "usage_type": "api_calls",
  "quantity": 100,
  "idempotency_key": "req-456"
}

# Get usage summary
GET /usage/{tenant_id}?period=2024-01
```

### Billing

```bash
# Create Stripe checkout
POST /billing/checkout
{
  "tenant_id": "tenant-123",
  "plan_id": "pro",
  "return_url": "https://app.example.com/success"
}

# Webhook receiver (auto-invoked by Stripe)
POST /webhooks/stripe
```

## Testing

### Run All Tests

```bash
pytest -v
```

### Run with Coverage

```bash
pytest --cov=app --cov-report=html
```

### Run Specific Test File

```bash
pytest tests/test_metering.py -v
```

### Run Tests Matching Pattern

```bash
pytest -k "idempotency" -v
```

### Important Test Suites

- `tests/test_idempotency.py` - Double-counting prevention
- `tests/test_quotas.py` - Quota enforcement & boundaries
- `tests/test_cost_calculation.py` - Token pricing rules
- `tests/test_stripe_webhooks.py` - Webhook verification & deduplication
- `tests/test_tenant_isolation.py` - Multi-tenant security

## Project Structure

```
flyrank-capstone-metering-billing/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration (Pydantic Settings)
│   ├── database.py          # SQLAlchemy setup
│   ├── models.py            # Database models
│   ├── schemas.py           # Pydantic schemas
│   ├── dependencies.py      # Shared dependencies
│   ├── routes/
│   │   ├── tenants.py
│   │   ├── usage.py
│   │   ├── billing.py
│   │   └── webhooks.py
│   ├── services/
│   │   ├── tenant_service.py
│   │   ├── metering_service.py
│   │   ├── quota_service.py
│   │   ├── cost_service.py
│   │   └── stripe_service.py
│   ├── repositories/
│   │   ├── tenant_repository.py
│   │   ├── usage_repository.py
│   │   ├── subscription_repository.py
│   │   └── webhook_repository.py
│   └── utils/
│       ├── idempotency.py
│       ├── pricing.py
│       └── exceptions.py
├── tests/
│   ├── conftest.py
│   ├── test_idempotency.py
│   ├── test_quotas.py
│   ├── test_cost_calculation.py
│   ├── test_stripe_webhooks.py
│   └── test_tenant_isolation.py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── SDLC.md
├── EVIDENCE.md
└── BUILDLOG.md
```

## Key Features

### 1. Exactly-Once Metering

Duplicate requests with the same idempotency key create exactly one usage event:

```python
# Retry doesn't double-count
POST /usage/record
{
  "tenant_id": "tenant-123",
  "idempotency_key": "unique-key-123",  # Database uniqueness enforced
  "quantity": 100
}

# Retry with same key returns same result
# Only 1 usage event created
```

### 2. Quota Enforcement

Precise boundary checking with correct HTTP status codes:

```python
# At quota: 429 Too Many Requests
# Request over limit: 429 Too Many Requests
# Unpaid plan: 402 Payment Required
# Upgrade available: 402 Payment Required
```

### 3. Token Pricing

Correctly handles complex AI token pricing:

```python
input_tokens = 1000
cached_input_tokens = 500  # Cheaper rate
output_tokens = 200
reasoning_tokens = 100     # Counted as output

# Pricing calculation respects each category
total_cost = (
  (input_tokens * input_rate) +
  (cached_input_tokens * cached_rate) +
  ((output_tokens + reasoning_tokens) * output_rate)
)
```

### 4. Stripe Integration

Test-mode Stripe checkout and webhook verification:

```bash
# 1. Customer initiates upgrade
POST /billing/checkout
→ Stripe checkout URL

# 2. Complete checkout with test card 4242 4242 4242 4242
# Stripe sends webhook to /webhooks/stripe

# 3. System verifies signature, updates subscription
GET /usage
→ Shows new Pro plan limits
```

### 5. Webhook Deduplication

Replayed webhooks are processed exactly once:

```python
# Webhook received twice (network retry)
→ Processed once
→ Idempotent state update
→ 200 OK for both requests
```

## Configuration

All configuration is environment-based via `.env`:

| Variable | Purpose | Example |
|----------|---------|---------|
| `APP_ENV` | Environment | `development`, `production` |
| `DEBUG` | Debug mode | `True`, `False` |
| `DATABASE_URL` | PostgreSQL connection | `postgresql://user:pass@host/db` |
| `STRIPE_API_KEY` | Stripe test key | `sk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret | `whsec_...` |
| `SECRET_KEY` | JWT signing key | Minimum 32 characters |
| `CORS_ORIGINS` | Allowed origins | `["http://localhost:3000"]` |

## Deployment

### Production Checklist

- [ ] `DEBUG=False`
- [ ] `WORKERS=4` (or higher)
- [ ] Strong `SECRET_KEY` (32+ chars, random)
- [ ] Stripe live keys (not test)
- [ ] Webhook secret from Stripe production
- [ ] Database backups enabled
- [ ] Health checks configured
- [ ] Monitoring/alerts set up
- [ ] API rate limiting enabled
- [ ] CORS origins restricted
- [ ] All tests passing
- [ ] Database migrations applied

### Docker Deployment

```bash
# Build image
docker build -t metering-billing:latest .

# Run with production settings
docker run \
  -e APP_ENV=production \
  -e DEBUG=False \
  -e DATABASE_URL=postgresql://prod-user:prod-pass@prod-db:5432/prod_db \
  -e STRIPE_API_KEY=sk_live_your_live_key \
  -e STRIPE_WEBHOOK_SECRET=whsec_prod_secret \
  -e SECRET_KEY=your-secure-32-char-production-key \
  -p 8000:8000 \
  metering-billing:latest
```

## Monitoring & Logging

Logs are output to stdout:

```bash
# Follow logs
docker-compose logs -f app

# Search logs
docker-compose logs app | grep ERROR
```

Structured logging with timestamps, levels, and context.

## Limitations

### Current Scope

- **Test Mode Only**: Stripe test mode only (no real payments)
- **Two Plans**: Free and Pro (extend as needed)
- **Two Usage Types**: API calls and AI tokens
- **One Billing Cycle**: Monthly billing only
- **No Invoicing**: Usage tracked, invoices not generated
- **No Proration**: Mid-cycle upgrades not adjusted

### Future Enhancements

- Invoicing and PDF generation
- Overage billing
- Usage alerts (80%, 100%)
- Proration for mid-cycle changes
- Reconciliation jobs
- Advanced reporting

## Security

- ✅ No secrets in code (environment only)
- ✅ Stripe webhook signature verification
- ✅ Tenant data isolation
- ✅ SQL injection prevention (ORM + parameterized)
- ✅ Input validation (Pydantic)
- ✅ CORS configured
- ✅ HTTPS-only in production
- ✅ Password hashing (bcrypt)
- ✅ JWT token expiration

See `SDLC.md` → Security Design for details.

## Troubleshooting

### Database Connection Failed

```bash
# Verify PostgreSQL is running
docker ps | grep postgres

# Check connection string
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### Migrations Not Applied

```bash
# Check current revision
alembic current

# List all revisions
alembic history

# Upgrade to latest
alembic upgrade head
```

### Stripe Webhooks Not Received

```bash
# Verify webhook secret
echo $STRIPE_WEBHOOK_SECRET

# Check Stripe CLI forwarding
stripe listen --forward-to localhost:8000/webhooks/stripe

# Trigger test event
stripe trigger checkout.session.completed
```

## Contributing

1. Create feature branch
2. Write tests first
3. Implement feature
4. Run full test suite
5. Create pull request

## License

MIT License - see LICENSE file

## Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Internship**: FlyRank internship community

---

**Built with ❤️ for the FlyRank Backend Track**