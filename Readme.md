Here is the complete, updated `README.md` file tailored specifically to your actual repository structure (where backend modules live directly in the root as `app/`, `alembic/`, `scripts/`, and `tests/`, rather than a nested `backend/` folder).

Replace the contents of your `Readme.md` file with the following:

```markdown
# FlyRank SaaS Usage Metering & Billing Engine

A production-ready backend service for multi-tenant SaaS applications that handles usage metering, quota enforcement, cost calculation, and Stripe billing integration.

## 🎯 Features

- **Idempotent Usage Metering** - Guarantees exactly-once recording of billable events, even under retries
- **Quota Enforcement** - Real-time checking of usage limits with correct HTTP status codes (429/402)
- **Multi-tenant Isolation** - Secure tenant data separation and independent billing
- **AI Token Pricing** - Advanced pricing rules for cached input, output, and reasoning tokens
- **Stripe Integration** - Seamless subscription management with webhook verification
- **Production-Ready** - Built with FastAPI, PostgreSQL, and comprehensive testing

## 📁 Repository Structure

```text
usage-metering-billing-engine/
├── alembic/                # Database migrations & configuration
├── app/                    # FastAPI backend Application Core
│   ├── api/                # Endpoints (auth, billing, usage, webhooks)
│   ├── core/               # Configuration, security, database setup
│   ├── models/             # SQLAlchemy models (Tenants, Plans, Usage)
│   ├── schemas/            # Pydantic schemas for data validation
│   └── services/           # Metering, Stripe integration & cost engines
├── docs/                   # API, Database, and Deployment documentation
├── frontend/               # React (Vite) Frontend Application
│   ├── src/                # UI components, dashboard, API services
│   └── package.json        # Frontend dependencies
├── Modules-Summaries/      # Project module documentations
├── scripts/                # Utility scripts (seed data, admin tasks)
├── tests/                  # Pytest test suites (unit, integration)
├── .env.example            # Environment variables template
├── docker-compose.yml      # Docker orchestration setup
├── nginx.conf              # Nginx reverse proxy config
├── Readme.md               # Main project documentation
└── requirements.txt        # Python backend dependencies

```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Frontend (React)                       │
│           Dashboard, Plans, Usage Tracking               │
└────────────────┬────────────────────────────────────────┘
                 │
       ┌─────────┴──────────┐
       │                    │
  ┌────▼────────┐    ┌──────▼──────┐
  │ Nginx Proxy │    │ WebSocket   │
  │ Load Balance│    │ Support     │
  └────┬────────┘    └─────────────┘
       │
┌──────▼─────────────────────────────────────────────────┐
│          FastAPI Backend (Python)                       │
│  ├─ Authentication & Authorization                     │
│  ├─ Usage Metering Service (Idempotent)               │
│  ├─ Quota Enforcement                                 │
│  ├─ Cost Calculation Engine                           │
│  ├─ Stripe Webhook Handler                            │
│  └─ PostgreSQL Persistence Layer                      │
└──────┬──────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────┐
│         PostgreSQL Database                             │
│  ├─ Tenants & Subscriptions                            │
│  ├─ Usage Events (Idempotency Keys)                    │
│  ├─ Quotas & Plans                                     │
│  └─ Billing History                                    │
└───────────────────────────────────────────────────────────┘
       │
       └──── Stripe (Test Mode)
            ├─ Payment Processing
            ├─ Subscription Management
            └─ Webhook Events

```

## 📋 Prerequisites

* Docker & Docker Compose
* Python 3.10+ (for local development)
* Node.js 18+ (for frontend development)
* Stripe test account (free)
* Git

## 🚀 Quick Start (Docker)

### 1. Clone Repository

```bash
git clone [https://github.com/yourusername/flyrank-billing.git](https://github.com/yourusername/flyrank-billing.git)
cd usage-metering-billing-engine

```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your Stripe API keys and secret configs

```

### 3. Start Services

```bash
# Using Docker Compose
docker-compose up -d

```

### 4. Initialize Database & Seed Demo Data

```bash
# Run migrations (runs automatically, or manually via):
docker-compose exec backend alembic upgrade head

# Seed demo data
docker-compose exec backend python -m app.scripts.seed_demo

```

## 💻 Local Setup (Without Docker)

### Backend Setup (Root Directory)

```bash
# Navigate to project root directory
cd usage-metering-billing-engine

# Create & activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start FastAPI development server
uvicorn app.main:app --reload

```

### Frontend Setup

```bash
# Navigate to frontend folder
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

```

### Local Stripe Webhook Testing

```bash
# Forward webhooks using Stripe CLI
stripe login
stripe listen --forward-to localhost:8000/api/webhooks/stripe

# Trigger test events in a separate terminal
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated

```

## 📡 API Endpoints

### Authentication

* `POST /api/auth/login` - Login (returns JWT token)
* `POST /api/auth/logout` - Logout
* `POST /api/auth/register` - Register new tenant

### Usage Metering

* `GET /api/usage` - Get current usage & cost
* `POST /api/generate` - Billable endpoint (dummy)
* `POST /api/usage/record` - Record usage event (internal)

### Billing & Subscriptions

* `GET /api/subscription` - Get subscription details
* `GET /api/plans` - List available plans
* `POST /api/checkout` - Create Stripe checkout session
* `POST /api/webhooks/stripe` - Stripe webhook receiver

### System

* `GET /api/health` - Health check
* `GET /api/metrics` - Prometheus metrics

## 🧪 Testing

```bash
# Run all Pytest backend tests from root directory
pytest

# Run specific test module
pytest tests/test_metering.py

# Run tests via Docker
docker-compose exec backend pytest

```

## 🛠️ Tech Stack

* **Backend**: FastAPI (Python 3.10+), SQLAlchemy 2.x, Alembic, PostgreSQL 16
* **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Zustand
* **Infrastructure**: Docker Compose, Nginx Proxy, Stripe CLI

## 📝 License

MIT License - See LICENSE file for details.

```

```