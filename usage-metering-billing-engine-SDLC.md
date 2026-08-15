# FlyRank Usage Metering & Billing Engine
## System Design & Architecture Document

**Version:** 1.0  
**Status:** Design Phase Complete  
**Date:** August 2026  
**Lead Engineer:** Senior Backend Engineer  

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Goals & Objectives](#goals--objectives)
3. [Scope](#scope)
4. [Functional Requirements](#functional-requirements)
5. [Non-Functional Requirements](#non-functional-requirements)
6. [Solution Overview](#solution-overview)
7. [System Architecture](#system-architecture)
8. [Module Architecture](#module-architecture)
9. [Database Design](#database-design)
10. [API Design](#api-design)
11. [Data Flow](#data-flow)
12. [Idempotency Design](#idempotency-design)
13. [Quota Enforcement Design](#quota-enforcement-design)
14. [Cost Calculation Design](#cost-calculation-design)
15. [Stripe/Billing Integration](#stripebilling-integration)
16. [Security Design](#security-design)
17. [Testing Strategy](#testing-strategy)
18. [Deployment Design](#deployment-design)
19. [Implementation Plan](#implementation-plan)
20. [Definition of Done](#definition-of-done)

---

## Problem Statement

SaaS products must track three critical pieces of information:
1. **How much has this customer used?** (metering)
2. **How much should they pay?** (cost calculation)
3. **Have they reached their plan limits?** (quota enforcement)

Current challenges:
- **Duplicate Metering:** Network retries must not create duplicate charges
- **Quota Accuracy:** Quota boundaries must be exact; ambiguity at limits causes revenue loss or abuse
- **Complex Pricing:** AI token pricing includes cached input, reasoning tokens, and output tokens—simple addition fails
- **Subscription Sync:** Plan changes via Stripe webhooks must update tenant state atomically
- **Audit Trail:** Every billable action must be recorded immutably for compliance

Without a reliable metering engine, SaaS platforms face:
- Double-charging (reputational damage, legal exposure)
- Revenue leakage (undercharging or free unlimited access)
- Customer frustration (arbitrary quota rejections)
- Audit failures (inability to explain billing)

---

## Goals & Objectives

### Primary Goal
Build a production-ready, distributed-system-safe metering and billing engine that:
- Records usage exactly once per billable action (idempotent)
- Enforces quotas precisely at plan limits
- Calculates costs correctly under real-world pricing rules
- Synchronizes subscription state from Stripe via verified webhooks
- Remains correct under retries, failures, and concurrent load

### Core Objectives
1. **Exact-Once Metering:** Implement idempotent usage recording with database-level uniqueness
2. **Boundary-Honest Quota:** Test and prove quota enforcement at 999, 1000, 1001 units
3. **Correct Token Pricing:** Implement AI token pricing with cached inputs and reasoning tokens
4. **Webhook Verification:** Verify Stripe signatures, deduplicate events, atomically update state
5. **Tenant Isolation:** Guarantee no data leakage between tenants
6. **Automated Safety:** Comprehensive tests covering failure cases, not just happy path

### Success Criteria
- All § 6 checkboxes from capstone brief completed
- All 5 acceptance probes (idempotency, boundary, checkout, webhook security, pricing math) pass
- Zero double-charges under any retry scenario
- All automated tests pass deterministically
- Production-ready code ready to run on day 1

---

## Scope

### In Scope
- **Metering:** Track API calls and AI tokens per tenant per month
- **Plans:** Free (1K API calls, 100K tokens) and Pro (higher limits, exact TBD in Phase 1 design)
- **Quotas:** Monthly reset, per-tenant, plan-specific limits
- **Usage API:** GET /usage → {used, limit, cost}
- **Billable Endpoint:** POST /generate → simulates AI generation, creates usage event, checks quota
- **Stripe Checkout:** Test-mode Checkout session → subscription created
- **Stripe Webhooks:** `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
- **Cost Calculation:** Convert usage to monthly cost with correct token pricing
- **Tenant Isolation:** Multi-tenant data isolation enforced at database level
- **Security:** Input validation, authentication, authorization, secret management
- **Testing:** Unit, integration, acceptance tests covering happy path and failure cases

### Out of Scope (Core)
- Invoicing/statements (stretch goal)
- Proration (stretch goal)
- Overage billing (stretch goal)
- Usage alerts (stretch goal)
- Reconciliation job (stretch goal)
- Real AI calls (simulated; capstone is metering numbers, not AI)
- Real credit card processing (Stripe test mode only)
- Live Stripe integration (test mode only)
- User-facing dashboard (API only)
- Historical usage export (not in core)
- Usage-based auto-scaling (not in core)

---

## Functional Requirements

### FR-1: Tenant Management
- **FR-1.1:** Create tenant with unique identifier and metadata
- **FR-1.2:** Retrieve tenant by ID
- **FR-1.3:** Tenant data isolated; no cross-tenant data leakage
- **FR-1.4:** Soft-delete support for compliance

### FR-2: Plan Definition
- **FR-2.1:** Define plans: Free, Pro (exact limits TBD in Phase 1)
- **FR-2.2:** Plan includes monthly quota per usage type (API calls, AI tokens)
- **FR-2.3:** Plan has a unit cost mapping
- **FR-2.4:** Plans immutable once created (new version for changes)

### FR-3: Subscription Management
- **FR-3.1:** Tenant assigned to one active plan
- **FR-3.2:** Subscription records plan, start date, status (active, cancelled, paused)
- **FR-3.3:** Subscription synced from Stripe via webhook
- **FR-3.4:** Plan change atomically updates tenant active plan

### FR-4: Usage Metering (Idempotent)
- **FR-4.1:** Every billable action creates one usage event
- **FR-4.2:** Usage event includes: tenant_id, type (API_CALL | AI_TOKENS), quantity, timestamp, idempotency_key
- **FR-4.3:** Same idempotency key → same response, no new event (exactly-once guarantee)
- **FR-4.4:** Idempotency enforced at database level (unique constraint)
- **FR-4.5:** Duplicate request returns original response (not re-calculated)

### FR-5: Quota Enforcement
- **FR-5.1:** Before billable action: check current usage + requested quantity vs. plan quota
- **FR-5.2:** If usage + quantity ≤ quota → allow, record event
- **FR-5.3:** If usage + quantity > quota → reject with 429 / 402
- **FR-5.4:** Quota check is point-in-time; concurrent requests may exceed quota (acceptable per SaaS standards)
- **FR-5.5:** Quota resets monthly (calendar month or 30 days per config)
- **FR-5.6:** Error response includes: status code, reason, current usage, limit, retry guidance

### FR-6: Usage Rollup & Reporting
- **FR-6.1:** GET /usage → {used_api_calls, limit_api_calls, used_tokens, limit_tokens, cost_this_month}
- **FR-6.2:** Usage aggregated from usage_events table (exact sum, not estimate)
- **FR-6.3:** Cost calculated per pricing rules (next section)
- **FR-6.4:** Month boundary correct (not off-by-one)

### FR-7: Cost Calculation
- **FR-7.1:** Define per-unit costs: API_CALL, AI_TOKEN, CACHED_INPUT_TOKEN, REASONING_TOKEN
- **FR-7.2:** Costs stored as integers (cents)
- **FR-7.3:** API calls: count × unit_cost
- **FR-7.4:** AI tokens: input + cached_input + output + reasoning (separate pricing rules per category)
- **FR-7.5:** Pricing rules: cached input cheaper than fresh input; reasoning priced as output
- **FR-7.5:** Cost calculation deterministic and testable (no AI calls needed)

### FR-8: Stripe Checkout (Test Mode)
- **FR-8.1:** POST /checkout → create Stripe Checkout session (test mode)
- **FR-8.2:** Checkout links to test plan (e.g., Pro)
- **FR-8.3:** Response includes Stripe session URL
- **FR-8.4:** Customer pays with test card (4242 4242 4242 4242, any future expiry)
- **FR-8.5:** Checkout creates Stripe customer + subscription

### FR-9: Stripe Webhooks
- **FR-9.1:** Endpoint: POST /webhooks/stripe
- **FR-9.2:** Verify webhook signature; reject invalid (400)
- **FR-9.3:** Handle `checkout.session.completed` → create/update subscription
- **FR-9.4:** Handle `customer.subscription.updated` → update tenant plan/status
- **FR-9.5:** Handle `customer.subscription.deleted` → mark subscription cancelled
- **FR-9.6:** Deduplicate events by event_id; replay ignored
- **FR-9.7:** Webhook processing atomic (all-or-nothing update)

### FR-10: Billable Endpoint (POST /generate)
- **FR-10.1:** Endpoint: POST /generate → simulates billable action
- **FR-10.2:** Request: {tenant_id, idempotency_key, api_calls_used, tokens_used}
- **FR-10.3:** If idempotency_key exists → return original response
- **FR-10.4:** Check quota: current + request > limit → 429/402
- **FR-10.5:** Record usage_event
- **FR-10.6:** Return: {success, usage_event_id, cost}
- **FR-10.7:** All errors include clear, actionable messages

---

## Non-Functional Requirements

### NFR-1: Correctness
- **NFR-1.1:** No double-counting under any retry scenario
- **NFR-1.2:** Quota checks never race; boundary is exact
- **NFR-1.3:** Cost calculations use integer arithmetic only (no floats for money)
- **NFR-1.4:** Database transactions ACID-compliant

### NFR-2: Resilience
- **NFR-2.1:** Survive network failures (retries idempotent)
- **NFR-2.2:** Survive duplicate webhooks (deduplicated)
- **NFR-2.3:** Survive missing Stripe state (recreate from events)
- **NFR-2.4:** Survive partial request (rollback, no orphaned events)

### NFR-3: Performance
- **NFR-3.1:** POST /generate < 200ms p99 (single tenant)
- **NFR-3.2:** GET /usage < 100ms p99
- **NFR-3.3:** Webhook processing < 500ms
- **NFR-3.4:** Indexed for: tenant_id, created_at, usage_type

### NFR-4: Security
- **NFR-4.1:** Tenant isolation: no SQL injection, no cross-tenant queries
- **NFR-4.2:** Stripe secrets: environment-only, never logged, git-ignored
- **NFR-4.3:** Input validation: strict types, size limits, range checks
- **NFR-4.4:** Authentication: tenant_id from request auth context (bearer token or session)
- **NFR-4.5:** Authorization: tenant can only access own data
- **NFR-4.6:** Rate limiting: per-tenant, Stripe webhook, standard endpoints

### NFR-5: Scalability
- **NFR-5.1:** Horizontal: stateless; load-balanced behind reverse proxy
- **NFR-5.2:** Database: connection pooling (10–20 per instance)
- **NFR-5.3:** Idempotency: index on (tenant_id, idempotency_key) for fast lookup
- **NFR-5.4:** Quota: per-tenant; no global locks
- **NFR-5.5:** Webhook: queue + retry for high load (async processing)

### NFR-6: Auditability
- **NFR-6.1:** Every usage_event immutable (no updates)
- **NFR-6.2:** Every subscription change logged (created_at, updated_at, event source)
- **NFR-6.3:** Stripe event_id stored with webhook record
- **NFR-6.4:** Cost calculations reproducible from usage_events + pricing snapshot

### NFR-7: Testability
- **NFR-7.1:** Unit tests for every service function
- **NFR-7.2:** Integration tests for quota, idempotency, cost
- **NFR-7.3:** Acceptance tests for Stripe workflow
- **NFR-7.4:** Tests deterministic; no flakiness from timing

---

## Solution Overview

### Architecture Principle: Layered & Modular

```
Client Request
    ↓
HTTP Router (FastAPI)
    ↓
Middleware (auth, logging, error)
    ↓
Schema Validation (Pydantic)
    ↓
Service Layer (business logic)
    ├── MeteringService (record usage, idempotency)
    ├── QuotaService (enforce limits)
    ├── CostService (calculate pricing)
    ├── SubscriptionService (manage plans)
    └── StripeService (Stripe integration)
    ↓
Repository Layer (database queries)
    ├── UsageRepository
    ├── TenantRepository
    ├── SubscriptionRepository
    └── IdempotencyRepository
    ↓
PostgreSQL (persistence, constraints, transactions)
    ├── tenants
    ├── plans
    ├── subscriptions
    ├── usage_events
    ├── idempotency_keys
    ├── stripe_events
    └── pricing_configs
```

### Core Design Decisions

**1. Idempotency via Database Uniqueness**
- Every metering request includes an `idempotency_key` (UUID or custom)
- Database enforces unique constraint: `UNIQUE(tenant_id, idempotency_key)`
- Before recording usage: query idempotency table → if found, return cached result
- If not found: record usage, store idempotency record, return result
- Guarantees exactly-once at database level, not application level

**2. Quota as Snapshot Query**
- No background jobs; quota checked at request time
- Query: `SELECT COALESCE(SUM(quantity), 0) FROM usage_events WHERE tenant_id = ? AND type = ? AND created_at > month_start`
- Fetch plan quota: `SELECT quota FROM plans WHERE id = (SELECT plan_id FROM subscriptions WHERE tenant_id = ?)`
- Compare: `current_usage + request_quantity > plan_quota` → reject
- Indexes on (tenant_id, type, created_at) for speed

**3. Cost Calculation: Deterministic & Testable**
- Pricing constants in `pricing_config` table (not hardcoded)
- Each usage_event has a `type` and `quantity`
- Types: `API_CALL`, `INPUT_TOKENS`, `CACHED_INPUT_TOKENS`, `OUTPUT_TOKENS`, `REASONING_TOKENS`
- Cost = sum over events of (quantity × unit_cost for that type)
- No AI calls; quantities are simulated inputs
- All cost calculations use integer arithmetic (cents)

**4. Stripe Webhooks: Async-Safe, Deduplicated**
- Webhook endpoint signs request, verifies signature
- Store event in `stripe_events` table: `(event_id, event_type, data, processed, created_at)`
- Before processing: check `stripe_events WHERE event_id = ? AND processed = true` → if found, return 200 (idempotent)
- Process event: update subscription, plan, tenant status
- Mark processed: `UPDATE stripe_events SET processed = true WHERE event_id = ?`
- All in single transaction

**5. Tenant Isolation: Row-Level**
- Every table has `tenant_id` foreign key
- No query returns data without WHERE tenant_id = ?
- Tests verify cross-tenant leakage impossible
- Database triggers (optional) enforce for safety

---

## System Architecture

### High-Level Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Client/SaaS Platform                    │
└────────────┬──────────────────────────────────────┬──────────┘
             │                                      │
     POST /generate                         GET /usage
   (billable action)                      (usage report)
             │                                      │
             ▼                                      ▼
   ┌──────────────────────────────────────────────────────┐
   │         FastAPI Application                          │
   │  ┌────────────────────────────────────────────────┐  │
   │  │ HTTP Routes                                     │  │
   │  │  - POST /generate (idempotent)                 │  │
   │  │  - GET /usage (aggregated)                     │  │
   │  │  - POST /checkout (Stripe session)             │  │
   │  │  - POST /webhooks/stripe (verified)            │  │
   │  └────────────────────────────────────────────────┘  │
   │  ┌────────────────────────────────────────────────┐  │
   │  │ Middleware                                      │  │
   │  │  - Auth (tenant_id from bearer token)          │  │
   │  │  - Error handling                              │  │
   │  │  - Logging                                      │  │
   │  └────────────────────────────────────────────────┘  │
   │  ┌────────────────────────────────────────────────┐  │
   │  │ Service Layer                                   │  │
   │  │  - MeteringService                             │  │
   │  │  - QuotaService                                │  │
   │  │  - CostService                                 │  │
   │  │  - SubscriptionService                         │  │
   │  │  - StripeService                               │  │
   │  └────────────────────────────────────────────────┘  │
   │  ┌────────────────────────────────────────────────┐  │
   │  │ Repository Layer                                │  │
   │  │  - UsageRepository                             │  │
   │  │  - TenantRepository                            │  │
   │  │  - SubscriptionRepository                      │  │
   │  │  - IdempotencyRepository                       │  │
   │  │  - StripeEventRepository                       │  │
   │  └────────────────────────────────────────────────┘  │
   └────────────────┬──────────────────────────────────────┘
                    │
      ┌─────────────┴─────────────┐
      │                           │
      ▼                           ▼
┌──────────────────┐    ┌──────────────────┐
│   PostgreSQL     │    │  Stripe API      │
│   (persistence)  │    │  (test mode)     │
│                  │    │                  │
│  - tenants       │    │  - Checkout      │
│  - plans         │    │  - Subscriptions │
│  - subscriptions │    │  - Events        │
│  - usage_events  │    │  - Webhooks      │
│  - idempotency   │    └──────────────────┘
│  - stripe_events │
│  - pricing       │
└──────────────────┘

      ↑
      │ Webhooks (HTTPS)
      │
   Stripe Webhook Service (test mode with Stripe CLI)
```

### Data Flow: POST /generate (Billable Action)

```
Client Request: POST /generate
  {
    "tenant_id": "tenant-123",
    "idempotency_key": "req-abc-xyz",
    "api_calls_used": 5,
    "tokens_used": 2500
  }

    ↓ Auth Middleware: verify tenant_id from bearer token

    ↓ Validation: check schema, ranges

    ↓ MeteringService.record()
      - Query idempotency: SELECT * FROM idempotency WHERE tenant_id=? AND key=?
      - If found: return cached result (no new event)
      - If not found:
        - BEGIN TRANSACTION
        - Query current usage: SELECT SUM(quantity) FROM usage_events WHERE tenant_id=? AND type IN (...)
        - Query plan quota: SELECT quota FROM plans WHERE id=(SELECT plan_id FROM subscriptions WHERE tenant_id=?)
        - Check: current + request > quota?
          - YES: ROLLBACK, return 429/402
          - NO: INSERT INTO usage_events, INSERT INTO idempotency, COMMIT
        - Return result with usage_event_id

Response: 200 OK
  {
    "success": true,
    "usage_event_id": "event-123",
    "cost_cents": 275,
    "current_usage": {
      "api_calls": 15,
      "api_calls_limit": 1000,
      "tokens": 12500,
      "tokens_limit": 100000
    }
  }

Or: 429 Too Many Requests
  {
    "error": "Quota exceeded",
    "reason": "API calls: 995/1000 used, request asks for 10 more",
    "current_usage": 995,
    "limit": 1000,
    "retry_after_seconds": 2592000
  }
```

---

## Module Architecture

Organized as layered Python modules with clear dependencies:

```
app/
├── __init__.py              (app factory, FastAPI init)
├── config.py                (settings, environment)
├── main.py                  (entry, server startup)
├── middleware.py            (auth, error handling)
├── schemas/                 (Pydantic models)
│   ├── tenant.py
│   ├── plan.py
│   ├── subscription.py
│   ├── usage.py
│   ├── stripe_event.py
│   └── error.py
├── models/                  (SQLAlchemy ORM)
│   ├── base.py              (Base class, timestamps)
│   ├── tenant.py
│   ├── plan.py
│   ├── subscription.py
│   ├── usage_event.py
│   ├── idempotency_key.py
│   ├── stripe_event.py
│   └── pricing_config.py
├── routes/                  (HTTP endpoints)
│   ├── generate.py          (POST /generate)
│   ├── usage.py             (GET /usage)
│   ├── checkout.py          (POST /checkout)
│   ├── webhooks.py          (POST /webhooks/stripe)
│   └── health.py            (GET /health)
├── services/                (business logic)
│   ├── metering.py          (record usage, idempotency)
│   ├── quota.py             (check limits)
│   ├── cost.py              (calculate pricing)
│   ├── subscription.py      (manage plans)
│   ├── stripe_service.py    (Stripe API calls)
│   └── tenant.py            (tenant CRUD)
├── repositories/            (data access)
│   ├── base.py              (Base repo class)
│   ├── usage.py
│   ├── tenant.py
│   ├── subscription.py
│   ├── idempotency.py
│   ├── stripe_event.py
│   └── pricing.py
├── database.py              (SQLAlchemy setup, session)
├── exceptions.py            (custom exceptions)
├── utils.py                 (helpers)
├── constants.py             (enums, fixed values)
└── tests/                   (pytest suite)
    ├── conftest.py          (fixtures)
    ├── test_metering.py     (idempotency, double-count)
    ├── test_quota.py        (boundary tests)
    ├── test_cost.py         (pricing, token rules)
    ├── test_stripe.py       (webhooks, signatures)
    ├── test_tenant.py       (isolation)
    └── integration/
        ├── test_generate_flow.py
        ├── test_checkout_flow.py
        └── test_webhook_flow.py

migrations/                  (Alembic)
├── env.py
├── script.py.mako
└── versions/
    ├── 001_initial_schema.py
    ├── 002_usage_indexes.py
    └── ...
```

---

## Database Design

### Schema Overview

```sql
-- Tenants: SaaS customers
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    stripe_customer_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);

-- Plans: billing tiers
CREATE TABLE plans (
    id UUID PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,  -- 'Free', 'Pro'
    api_calls_monthly_limit INTEGER NOT NULL,
    tokens_monthly_limit INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Subscriptions: tenant → plan assignment
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    plan_id UUID NOT NULL REFERENCES plans(id),
    stripe_subscription_id VARCHAR(255) UNIQUE,
    status VARCHAR(50) NOT NULL,  -- 'active', 'cancelled', 'paused'
    billing_period_start DATE NOT NULL,
    billing_period_end DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id)  -- one active subscription per tenant
);

-- Usage Events: every billable action
CREATE TABLE usage_events (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    type VARCHAR(50) NOT NULL,  -- 'API_CALL', 'INPUT_TOKENS', 'OUTPUT_TOKENS', etc.
    quantity BIGINT NOT NULL,  -- count
    cost_cents INTEGER NOT NULL,  -- cost at record time
    idempotency_key VARCHAR(255) NOT NULL,  -- for deduplication
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, idempotency_key),
    INDEX (tenant_id, type, created_at),
    INDEX (tenant_id, created_at)
);

-- Idempotency Keys: cache for retried requests
CREATE TABLE idempotency_keys (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    key VARCHAR(255) NOT NULL,
    request_hash VARCHAR(64),  -- hash of full request
    response_json JSONB NOT NULL,  -- cached response
    usage_event_id UUID REFERENCES usage_events(id),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '24 hours',
    UNIQUE(tenant_id, key)
);

-- Stripe Events: webhook deduplication & audit trail
CREATE TABLE stripe_events (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    stripe_event_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_event_type VARCHAR(100) NOT NULL,  -- 'checkout.session.completed', etc.
    data JSONB NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX (stripe_event_id),
    INDEX (processed)
);

-- Pricing Config: unit costs
CREATE TABLE pricing_configs (
    id UUID PRIMARY KEY,
    type VARCHAR(50) UNIQUE NOT NULL,  -- 'API_CALL', 'INPUT_TOKENS', etc.
    cost_per_unit_cents BIGINT NOT NULL,  -- integer cents
    effective_from DATE NOT NULL,
    effective_until DATE NULL,  -- NULL = current
    created_at TIMESTAMP DEFAULT NOW()
);
```

### ER Diagram

```
┌─────────────┐
│  tenants    │
├─────────────┤
│ id (PK)     │
│ name        │
│ stripe_cust │
│ created_at  │
│ updated_at  │
│ deleted_at  │
└──────┬──────┘
       │
       │ 1:1
       ├──────────────────────┐
       │                      │
       ▼                      ▼
  ┌──────────────┐    ┌──────────────────┐
  │subscriptions │    │  usage_events    │
  ├──────────────┤    ├──────────────────┤
  │ id (PK)      │    │ id (PK)          │
  │ tenant_id(FK)│    │ tenant_id (FK)   │
  │ plan_id (FK) │    │ type             │
  │ stripe_sub   │    │ quantity         │
  │ status       │    │ cost_cents       │
  │ period_start │    │ idempotency_key  │
  │ period_end   │    │ created_at       │
  │ created_at   │    │ UNIQUE(t_id,key) │
  │ updated_at   │    └──────────────────┘
  └──────┬───────┘
         │ N:1
         │
         ▼
    ┌────────────┐
    │  plans     │
    ├────────────┤
    │ id (PK)    │
    │ name       │
    │ api_limit  │
    │ tok_limit  │
    └────────────┘

┌─────────────────────────────────────┐
│  idempotency_keys                   │
├─────────────────────────────────────┤
│ id, tenant_id, key, request_hash    │
│ response_json, usage_event_id       │
│ UNIQUE(tenant_id, key)              │
└─────────────────────────────────────┘

┌──────────────────────────┐
│  stripe_events           │
├──────────────────────────┤
│ id, tenant_id, event_id  │
│ event_type, data         │
│ processed, processed_at  │
└──────────────────────────┘

┌──────────────────────────┐
│  pricing_configs         │
├──────────────────────────┤
│ id, type, cost_per_unit  │
│ effective_from/until     │
└──────────────────────────┘
```

### Key Constraints

- **Tenant Isolation:** Every query filters by `tenant_id`
- **Idempotency Uniqueness:** `UNIQUE(tenant_id, idempotency_key)` on usage_events
- **Subscription Uniqueness:** `UNIQUE(tenant_id)` only one active subscription per tenant
- **Referential Integrity:** Foreign keys enforced
- **Audit Trail:** No deletes; soft-delete via `deleted_at` on tenants
- **Immutable Events:** No UPDATE on usage_events or stripe_events after creation

### Indexes (Performance)

```sql
-- Quota queries
INDEX (usage_events: tenant_id, type, created_at)
INDEX (usage_events: tenant_id, created_at)

-- Webhook processing
INDEX (stripe_events: stripe_event_id)
INDEX (stripe_events: processed)

-- Idempotency lookup
INDEX (idempotency_keys: tenant_id, key)

-- Subscription lookup
INDEX (subscriptions: tenant_id)

-- Cleanup/expiry
INDEX (idempotency_keys: expires_at)
```

---

## API Design

### 1. POST /generate (Billable Action, Idempotent)

**Request:**
```http
POST /generate HTTP/1.1
Authorization: Bearer <tenant_token>
Content-Type: application/json
Idempotency-Key: req-abc-xyz-1

{
  "api_calls_used": 5,
  "tokens_used": 2500
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "usage_event_id": "evt-123",
  "cost_cents": 275,
  "current_usage": {
    "api_calls": 15,
    "api_calls_limit": 1000,
    "tokens": 12500,
    "tokens_limit": 100000
  }
}
```

**Response (429 Too Many Requests):**
```json
{
  "error": "Quota exceeded",
  "reason": "API calls: 995/1000 used, request asks for 10 more",
  "current_usage": 995,
  "limit": 1000,
  "retry_after_seconds": 2592000
}
```

**Response (402 Payment Required):**
```json
{
  "error": "Payment required",
  "reason": "Subscription inactive or cancelled",
  "status": "cancelled",
  "action": "Renew subscription or upgrade plan"
}
```

### 2. GET /usage (Usage Report)

**Request:**
```http
GET /usage HTTP/1.1
Authorization: Bearer <tenant_token>
```

**Response (200 OK):**
```json
{
  "billing_period": {
    "start": "2026-08-01",
    "end": "2026-08-31"
  },
  "usage": {
    "api_calls": {
      "used": 500,
      "limit": 1000,
      "cost_cents": 50
    },
    "tokens": {
      "input": 10000,
      "cached_input": 2000,
      "output": 8000,
      "reasoning": 1000,
      "total": 21000,
      "limit": 100000,
      "cost_cents": 210
    }
  },
  "total_cost_cents": 260,
  "subscription": {
    "plan": "Free",
    "status": "active",
    "started": "2026-08-01"
  }
}
```

### 3. POST /checkout (Stripe Checkout Session)

**Request:**
```http
POST /checkout HTTP/1.1
Authorization: Bearer <tenant_token>
Content-Type: application/json

{
  "plan_id": "plan-pro-123",
  "success_url": "https://app.example.com/dashboard?session_id={CHECKOUT_SESSION_ID}",
  "cancel_url": "https://app.example.com/pricing"
}
```

**Response (200 OK):**
```json
{
  "session_id": "cs_test_xyz",
  "url": "https://checkout.stripe.com/pay/cs_test_xyz",
  "status": "open"
}
```

### 4. POST /webhooks/stripe (Stripe Webhook Handler)

**Request:**
```http
POST /webhooks/stripe HTTP/1.1
Content-Type: application/json
Stripe-Signature: t=1234567890,v1=abc123xyz

{
  "id": "evt_test_xyz",
  "type": "checkout.session.completed",
  "data": {
    "object": {
      "id": "cs_test_xyz",
      "customer": "cus_test_abc",
      "subscription": "sub_test_123"
    }
  }
}
```

**Response (200 OK):**
```json
{
  "received": true
}
```

**Response (400 Bad Request, Invalid Signature):**
```json
{
  "error": "Invalid webhook signature",
  "status": 400
}
```

### 5. GET /health (Health Check)

**Request:**
```http
GET /health HTTP/1.1
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "database": "connected",
  "stripe": "configured"
}
```

---

## Data Flow

### Flow 1: Normal Billable Action (Happy Path)

```
POST /generate
  │
  ├─ Auth: validate token → tenant_id = "t-123"
  ├─ Validate: schema, quantity ranges
  │
  ├─ MeteringService.record()
  │  ├─ Query: SELECT * FROM idempotency_keys WHERE tenant_id='t-123' AND key='req-abc'
  │  │  ├─ FOUND: return cached response
  │  │  └─ NOT FOUND: continue
  │  │
  │  ├─ BEGIN TRANSACTION
  │  │
  │  ├─ Query subscription: SELECT * FROM subscriptions WHERE tenant_id='t-123' AND status='active'
  │  │  └─ FOUND: plan_id = 'plan-free-123'
  │  │
  │  ├─ Query plan: SELECT * FROM plans WHERE id='plan-free-123'
  │  │  └─ api_calls_limit = 1000, tokens_limit = 100000
  │  │
  │  ├─ QuotaService.check()
  │  │  ├─ Query usage: SELECT SUM(quantity) FROM usage_events WHERE tenant_id='t-123' AND type='API_CALL' AND created_at > month_start
  │  │  │  └─ current = 495
  │  │  ├─ Compare: current + request (5) = 500 ≤ 1000
  │  │  └─ ALLOWED
  │  │
  │  ├─ CostService.calculate()
  │  │  ├─ Query pricing: SELECT cost_per_unit_cents FROM pricing_configs WHERE type='API_CALL' AND effective_until IS NULL
  │  │  │  └─ cost = 10 cents
  │  │  ├─ Calc: 5 * 10 = 50 cents
  │  │  └─ cost_cents = 50
  │  │
  │  ├─ INSERT INTO usage_events (id, tenant_id, type, quantity, cost_cents, idempotency_key, created_at)
  │  │  VALUES (uuid(), 't-123', 'API_CALL', 5, 50, 'req-abc', NOW())
  │  │
  │  ├─ INSERT INTO idempotency_keys (...)
  │  │  VALUES (..., response={success:true, ...}, usage_event_id, expires_at)
  │  │
  │  ├─ COMMIT TRANSACTION
  │  │
  │  └─ return {success: true, usage_event_id, cost_cents: 50, current_usage: {...}}
  │
  └─ Response 200 OK
```

### Flow 2: Duplicate Request (Idempotency)

```
POST /generate (same idempotency_key as request 1)
  │
  ├─ Auth: tenant_id = "t-123"
  ├─ Validate schema
  │
  ├─ MeteringService.record()
  │  ├─ Query: SELECT * FROM idempotency_keys WHERE tenant_id='t-123' AND key='req-abc'
  │  │  └─ FOUND: response_json = {success: true, usage_event_id: 'evt-123', cost_cents: 50, ...}
  │  │
  │  └─ return cached response (no new DB writes)
  │
  └─ Response 200 OK (identical to request 1)

-- Verification: usage_events table has ONE record for tenant_id='t-123' + idempotency_key='req-abc'
```

### Flow 3: Over-Quota Request

```
POST /generate (tenant at 995 usage, request 10)
  │
  ├─ Auth, Validate
  │
  ├─ MeteringService.record()
  │  ├─ Query idempotency: NOT FOUND
  │  │
  │  ├─ BEGIN TRANSACTION
  │  │
  │  ├─ QuotaService.check()
  │  │  ├─ current = 995
  │  │  ├─ Compare: 995 + 10 = 1005 > 1000 (LIMIT)
  │  │  └─ DENIED
  │  │
  │  ├─ ROLLBACK TRANSACTION (no usage_event created)
  │  │
  │  └─ throw QuotaExceededException(...)
  │
  └─ Response 429 Too Many Requests
     {
       "error": "Quota exceeded",
       "current_usage": 995,
       "limit": 1000,
       ...
     }

-- Verification: usage_events table unchanged (no record for this request)
```

### Flow 4: Stripe Webhook (checkout.session.completed)

```
Stripe → POST /webhooks/stripe
  │
  ├─ Extract Stripe-Signature header
  ├─ Verify signature using STRIPE_WEBHOOK_SECRET
  │  └─ Invalid: return 400, do not process
  │
  ├─ Parse JSON body: event_id = 'evt_test_xyz', type = 'checkout.session.completed'
  │
  ├─ StripeService.handle_webhook()
  │  ├─ Query: SELECT * FROM stripe_events WHERE stripe_event_id='evt_test_xyz'
  │  │  ├─ FOUND & processed=true: return 200 (idempotent)
  │  │  └─ NOT FOUND or processed=false: continue
  │  │
  │  ├─ BEGIN TRANSACTION
  │  │
  │  ├─ Parse event data: session_id, customer_id, subscription_id
  │  │
  │  ├─ Query: SELECT tenant_id FROM tenants WHERE stripe_customer_id=?
  │  │  └─ tenant_id = 't-123'
  │  │
  │  ├─ Query Stripe API: get subscription details (plan, billing_period)
  │  │  └─ plan_id = 'plan-pro-123'
  │  │
  │  ├─ UPDATE subscriptions SET plan_id='plan-pro-123', status='active', stripe_subscription_id='sub_test_123' WHERE tenant_id='t-123'
  │  │
  │  ├─ INSERT INTO stripe_events (..., processed=true, processed_at=NOW())
  │  │
  │  ├─ COMMIT TRANSACTION
  │  │
  │  └─ return {received: true}
  │
  └─ Response 200 OK

-- Verification: subscription.plan_id changed, usage_events resets for new billing period
```

---

## Idempotency Design

### Problem
Network retries, process crashes, and duplicate requests must not create duplicate usage events or charges.

### Solution: Database-Level Uniqueness + Cached Responses

**Data Model:**
```python
# usage_events table
UNIQUE(tenant_id, idempotency_key)

# idempotency_keys table
UNIQUE(tenant_id, key)
Stores: (tenant_id, key, request_hash, response_json, usage_event_id, expires_at)
```

**Algorithm:**

1. **Before processing:** Query idempotency_keys for (tenant_id, key)
2. **If found:**
   - Return cached response immediately
   - No database writes
   - No cost re-calculation (use cached value)
3. **If not found:**
   - Process request normally
   - Insert usage_event (fails if duplicate key exists → database constraint error → catch, re-query cache)
   - Insert idempotency record
   - Return response

**Guarantees:**
- Exactly one usage_event per (tenant_id, idempotency_key)
- Exactly one cost charge per request
- Retry within 24 hours returns identical response
- No race conditions (database constraint is authoritative)

**Test Case:**
```python
def test_duplicate_request_no_double_count():
    # Request 1: idempotency_key='req-1'
    r1 = client.post('/generate', json={...}, headers={'Idempotency-Key': 'req-1'})
    assert r1.status_code == 200
    event_id_1 = r1.json()['usage_event_id']
    
    # Request 2: same key
    r2 = client.post('/generate', json={...}, headers={'Idempotency-Key': 'req-1'})
    assert r2.status_code == 200
    event_id_2 = r2.json()['usage_event_id']
    
    # Verify: same event
    assert event_id_1 == event_id_2
    
    # Verify: only one usage_event in database
    events = db.query(UsageEvent).filter(UsageEvent.tenant_id == tenant_id).all()
    assert len(events) == 1
```

---

## Quota Enforcement Design

### Problem
Quota must be exact: at-limit rejection, concurrent requests must not race.

### Solution: Point-in-Time Snapshot Query + Transaction Isolation

**Algorithm:**

1. **Query current usage:**
   ```sql
   SELECT COALESCE(SUM(quantity), 0) as used
   FROM usage_events
   WHERE tenant_id = ? AND type = ? AND created_at >= month_start
   ```

2. **Fetch plan quota:**
   ```sql
   SELECT api_calls_limit
   FROM plans
   WHERE id = (SELECT plan_id FROM subscriptions WHERE tenant_id = ? AND status = 'active')
   ```

3. **Check:**
   ```python
   if current_usage + request_quantity > plan_quota:
       return 429 / 402
   else:
       record usage
   ```

4. **Race Condition Handling:**
   - Concurrent requests to same tenant may both pass quota check (both see same `current_usage`)
   - Both write usage_events → database accepts both
   - **Result:** quota may be exceeded slightly in high-concurrency scenarios (acceptable per SaaS standards)
   - **Alternative (if strict required):** use pessimistic locking (SELECT FOR UPDATE) or distributed lock

**Boundary Test Cases:**

```python
def test_quota_boundary_exact():
    # Setup: plan limit = 1000, current usage = 999
    
    # Test 1: at boundary (1 unit left)
    r = client.post('/generate', json={'quantity': 1}, ...)
    assert r.status_code == 200  # allowed
    
    # Test 2: over boundary by 1
    r = client.post('/generate', json={'quantity': 1}, ...)
    assert r.status_code == 429  # rejected
    assert r.json()['current_usage'] == 1000
    assert r.json()['limit'] == 1000

def test_quota_resets_monthly():
    # Jan: use 500 of 1000
    # Feb 1st: quota resets, available = 1000 again
    usage_jan = query_usage_for_month(tenant, 'January')
    usage_feb = query_usage_for_month(tenant, 'February')
    assert usage_jan == 500
    assert usage_feb == 0
```

**Status Codes:**

- **429 Too Many Requests:** Usage limit exceeded (quota)
- **402 Payment Required:** Subscription inactive/cancelled (upgrade needed)
- Both include clear reason + current_usage + limit in response

---

## Cost Calculation Design

### Problem
AI token pricing includes multiple categories (input, cached input, output, reasoning) with different rates. Simple addition fails.

### Solution: Type-Based Pricing Lookup + Integer Arithmetic

**Pricing Model:**

```python
# pricing_configs table
type: 'API_CALL' | 'INPUT_TOKENS' | 'CACHED_INPUT_TOKENS' | 'OUTPUT_TOKENS' | 'REASONING_TOKENS'
cost_per_unit_cents: int (e.g., 10 cents per API call, 1 cent per token)

# usage_events table
type: matches pricing_configs.type
quantity: int
cost_cents: int (calculated at record time)
```

**Calculation (at record time):**

```python
def calculate_cost(usage_type, quantity):
    pricing = pricing_repo.get_by_type(usage_type, effective_date=today)
    cost_cents = quantity * pricing.cost_per_unit_cents
    return cost_cents  # int, never float
```

**Pricing Rules (AI Tokens):**

```
Input Tokens (fresh):       1 cent per 1000 tokens
Cached Input Tokens:        0.1 cent per 1000 tokens (10x cheaper)
Output Tokens:              3 cents per 1000 tokens
Reasoning Tokens:           3 cents per 1000 tokens (counted as output)

Total Cost = Σ(token_type_quantity × type_rate)
```

**Examples:**

```python
# Request uses: 10k fresh input, 2k cached input, 5k output, 1k reasoning
costs = {
    'INPUT_TOKENS': 10000 * 0.001,           # 10 cents
    'CACHED_INPUT_TOKENS': 2000 * 0.0001,   # 0.2 cents
    'OUTPUT_TOKENS': 5000 * 0.003,           # 15 cents
    'REASONING_TOKENS': 1000 * 0.003,       # 3 cents
}
total_cents = int(sum(costs) * 100)  # 28.2 cents → 2820 micro-cents (or scaled to integer)
```

**Test Coverage:**

```python
def test_token_pricing_cached_input_cheaper():
    fresh = 10000
    cached = 10000
    
    cost_fresh = calculate_cost('INPUT_TOKENS', fresh)
    cost_cached = calculate_cost('CACHED_INPUT_TOKENS', cached)
    
    assert cost_cached < cost_fresh  # cached is cheaper

def test_reasoning_priced_as_output():
    output = 1000
    reasoning = 1000
    
    cost_output = calculate_cost('OUTPUT_TOKENS', output)
    cost_reasoning = calculate_cost('REASONING_TOKENS', reasoning)
    
    assert cost_output == cost_reasoning  # same rate

def test_all_categories_not_addable():
    # Verify: tokens of different types priced independently
    # (no "convert all to output and add" nonsense)
    cost_input = calculate_cost('INPUT_TOKENS', 1000)
    cost_output = calculate_cost('OUTPUT_TOKENS', 1000)
    assert cost_input != cost_output  # different rates
```

**Database Immutability:**

- `usage_events.cost_cents` calculated once at insert
- `pricing_configs` versioned by `effective_from` / `effective_until`
- Cost always reproducible: `usage_event.quantity * pricing_config(effective_date).cost_per_unit_cents`

---

## Stripe/Billing Integration

### Architecture: Test Mode + Stripe CLI

**Test Mode Guarantee:**
- No real money moves
- Test cards (4242..., 5555...) work with any future expiry
- Webhook events real; can replay locally
- No credit card required

**Checkout Flow (Test Mode):**

```
1. Client calls POST /checkout → backend creates Stripe Checkout session
2. Backend returns session URL
3. Client opens URL → Stripe Checkout page
4. Customer enters test card (4242 4242 4242 4242), email
5. Stripe processes → creates Customer + Subscription
6. Stripe sends webhook: checkout.session.completed
7. Webhook handler: verify signature → update tenant.plan
8. Client redirected to success_url
```

**Webhook Verification:**

```python
from stripe.webhooks import verify_signature

raw_body = request.body  # MUST be raw bytes, not parsed JSON
sig_header = request.headers.get('Stripe-Signature')

try:
    event = verify_signature(raw_body, sig_header, STRIPE_WEBHOOK_SECRET)
except ValueError:
    return {"error": "Invalid signature"}, 400
```

**Deduplication:**

```python
# Before processing
if stripe_event_repo.exists(event_id=event['id']):
    return {"received": True}, 200

# Process event
update_subscription(...)
mark_event_processed(event['id'])
```

**Webhook Events Handled:**

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Create subscription, update tenant.plan |
| `customer.subscription.updated` | Update subscription status/plan |
| `customer.subscription.deleted` | Mark subscription cancelled |

**Stripe SDK Integration:**

```python
import stripe

stripe.api_key = STRIPE_API_KEY

# Create checkout session
session = stripe.checkout.Session.create(
    customer_email=tenant.email,
    mode='subscription',
    line_items=[{
        'price': STRIPE_PRICE_ID_PRO,
        'quantity': 1
    }],
    success_url='https://app.example.com/success?session_id={CHECKOUT_SESSION_ID}',
    cancel_url='https://app.example.com/pricing'
)

# Retrieve subscription
subscription = stripe.Subscription.retrieve(sub_id)
```

**Webhook Endpoint (Stripe CLI for Local Testing):**

```bash
# Terminal 1: Start local server
python main.py  # listens on http://localhost:8000

# Terminal 2: Stripe CLI
stripe listen --forward-to localhost:8000/webhooks/stripe --events checkout.session.completed,customer.subscription.updated,customer.subscription.deleted

# Terminal 3: Trigger event
stripe trigger checkout.session.completed
# Stripe CLI forwards webhook to localhost:8000/webhooks/stripe
```

---

## Security Design

### 1. Tenant Isolation
- Every query includes `WHERE tenant_id = ?`
- No query without tenant filter
- Database-level row isolation (no cross-tenant joins)
- Test: create two tenants, verify one cannot see other's usage

### 2. Secrets Management
- `.env` git-ignored
- `.env.example` with placeholders
- Stripe API key in env, never logged
- Webhook secret in env, never logged

### 3. Input Validation (Pydantic)
```python
class GenerateRequest(BaseModel):
    api_calls_used: int = Field(..., gt=0, le=10000)
    tokens_used: int = Field(..., gt=0, le=1000000)

# Rejects: negative, zero, out-of-range, wrong type, extra fields
```

### 4. Webhook Signature Verification
```python
# Stripe signs every webhook
# Verify: signature is HMAC-SHA256(raw_body, webhook_secret)
# Reject: forged requests (missing or invalid signature)
# Test: send forged webhook → 400, no state change
```

### 5. Authentication (Bearer Token)
```python
# Request header: Authorization: Bearer <tenant_id_or_token>
# Extract tenant_id from token (implementation TBD: could be JWT, opaque token, etc.)
# Scope all operations to authenticated tenant
```

### 6. Error Messages (No Data Leakage)
```python
# Do NOT return:
# - Internal error traces
# - SQL errors
# - Stack traces
# - Stripe keys (even partial)

# Do return:
# - Clear, actionable error message
# - Appropriate HTTP status code
# - Retry guidance
```

---

## Testing Strategy

### Test Layers

1. **Unit Tests** (Fast, Isolated)
   - Service functions (MeteringService, QuotaService, CostService)
   - Pricing calculations
   - Schema validation

2. **Integration Tests** (Medium, With DB)
   - Idempotency deduplication
   - Quota boundary checks
   - Cost calculation with real DB
   - Subscription updates

3. **Acceptance Tests** (Slow, End-to-End)
   - POST /generate flow (happy path + error)
   - GET /usage aggregation
   - Stripe Checkout session creation
   - Webhook receipt, signature verification, deduplication
   - POST /generate → Stripe Checkout → webhook → plan upgrade

### Critical Test Cases

**Idempotency:**
- Duplicate request with same key → same response, one usage event
- Request 1 succeeds, Request 2 (duplicate) succeeds
- Request 1 fails (quota), Request 2 (duplicate) fails identically

**Quota:**
- Usage = 999/1000, request 1 unit → allowed
- Usage = 1000/1000, request 1 unit → 429
- Concurrent requests (both at limit) → both see same current_usage
- Monthly reset → new period has fresh quota

**Pricing:**
- API_CALL: quantity × rate = cost
- INPUT_TOKENS vs CACHED_INPUT_TOKENS: different rates
- REASONING_TOKENS priced as output (not free)
- No floating-point (all integer cents)

**Stripe:**
- Forged webhook (invalid signature) → 400, no update
- Duplicate webhook (same event_id) → 200, no re-processing
- Checkout → subscription created → plan updated
- Subscription deleted → status = 'cancelled' → 402 on next /generate

**Tenant Isolation:**
- Tenant A creates usage → Tenant B cannot see it
- GET /usage for Tenant A → only A's data
- Quota enforced per-tenant independently

**Error Handling:**
- Missing idempotency key → fail gracefully (optional header)
- Invalid tenant_id → 401 Unauthorized
- Database down → 503 Service Unavailable
- Stripe API down → webhook not processed (retry via Stripe)

### Test Fixtures (pytest)

```python
@pytest.fixture
def db_session():
    # Create test DB, migrate, yield session, rollback

@pytest.fixture
def tenant():
    # Create test tenant, return

@pytest.fixture
def plan():
    # Create test plans (Free, Pro)

@pytest.fixture
def subscription(tenant, plan):
    # Assign plan to tenant

@pytest.fixture
def client(db_session):
    # FastAPI TestClient with DB session injected

@pytest.fixture
def stripe_webhook():
    # Return signed webhook event
```

---

## Deployment Design

### Target Environment
- Python 3.10+
- FastAPI + Uvicorn
- PostgreSQL 14+
- Docker (optional, for local dev)
- Environment variables for secrets

### Docker Compose (Development)
```yaml
version: '3'
services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: metering
  
  app:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    environment:
      DATABASE_URL: postgresql://postgres:dev@postgres:5432/metering
      STRIPE_API_KEY: sk_test_...
      STRIPE_WEBHOOK_SECRET: whsec_...
```

### Database Migrations (Alembic)
```bash
alembic upgrade head  # Apply all migrations
alembic downgrade -1  # Rollback one migration
```

### Environment Variables
```
DATABASE_URL=postgresql://user:pass@localhost/metering
STRIPE_API_KEY=sk_test_xyz
STRIPE_WEBHOOK_SECRET=whsec_xyz
LOG_LEVEL=INFO
PORT=8000
```

### Deployment Checklist
- [ ] Secrets in .env (git-ignored)
- [ ] Database migrations applied
- [ ] Tests passing locally
- [ ] Seed data created
- [ ] Stripe webhook configured (CLI in dev, actual URL in prod)
- [ ] Health check responding
- [ ] /health → {status: healthy, database: connected, stripe: configured}

---

## Implementation Plan

### Phase 1: Foundation (Modules 1–3)
- [ ] Project structure, config, FastAPI app
- [ ] Database: schema, migrations, ORM models
- [ ] Auth: bearer token extraction, tenant context

### Phase 2: Core Metering (Modules 4–7)
- [ ] Plans, subscriptions, usage_events models
- [ ] Idempotency: design, implementation, tests
- [ ] MeteringService: record, deduplicate
- [ ] Quota: check, boundary tests

### Phase 3: Cost & API (Modules 8–10)
- [ ] Pricing configs, calculation service
- [ ] POST /generate endpoint (happy path + errors)
- [ ] GET /usage endpoint

### Phase 4: Stripe Integration (Modules 11–12)
- [ ] Stripe SDK setup, test mode
- [ ] POST /checkout endpoint
- [ ] Webhook endpoint, signature verification, deduplication
- [ ] Subscription state sync

### Phase 5: Hardening & Testing (Modules 13–15)
- [ ] Security: validation, isolation, secrets
- [ ] Comprehensive test suite
- [ ] Final acceptance tests
- [ ] Documentation, README, demo

### Deliverables (Definition of Done)
- [ ] Code: production-ready, no TODOs
- [ ] Tests: all green, coverage > 80%
- [ ] Docs: README, API, SDLC, EVIDENCE, BUILDLOG
- [ ] Deployment: Docker Compose, migrations, .env.example
- [ ] Demo: 5-move flow reproducible

---

## Definition of Done

### Core Checklist (§ 6 from Capstone Brief)

**Metering**
- [ ] A billable action creates exactly one usage event, even under retries
- [ ] Deduplicated by idempotency key
- [ ] Test proves double-counting cannot happen
- [ ] EVIDENCE.md: test name + output

**Quotas**
- [ ] Usage checked against tenant's plan
- [ ] Requests over limit rejected
- [ ] Status codes 429 / 402
- [ ] Message explains why
- [ ] EVIDENCE.md: curl transcript, exact boundary

**Cost Calculation**
- [ ] Monthly usage rolls up into cost
- [ ] AI token pricing: cached input, reasoning tokens, output
- [ ] Pricing constants pinned + tested
- [ ] EVIDENCE.md: test output, /usage response

**Stripe Integration**
- [ ] Checkout works end-to-end (test mode)
- [ ] Webhooks verify signatures
- [ ] Duplicate events ignored
- [ ] Tenant plan/status updated
- [ ] EVIDENCE.md: webhook logs, tenant state before/after

**Data Model & Tests**
- [ ] Database: tenants, plans, subscriptions, usage_events, idempotency, stripe_events
- [ ] Tenant isolation enforced
- [ ] Tests: duplicate prevention, boundary cases, cost, webhook, tenant isolation
- [ ] All green
- [ ] EVIDENCE.md: test run output

**Documentation**
- [ ] README: purpose, architecture, setup, run, test, seed
- [ ] EVIDENCE.md: proof per checkbox
- [ ] BUILDLOG.md: AI usage, changes, decisions
- [ ] SDLC.md: this document

**Gates (Phased)**
- **Gate 1:** Design doc signed off (this SDLC)
- **Gate 2:** Double-count test passes; boundary returns 429/402
- **Gate 3:** Checkout flips Free → Pro via webhook
- **Gate 4:** /usage numbers match tests; all tests green
- **Gate 5:** Demo rehearsed; forged-webhook moment ready

---

## Summary

This SDLC document defines a **production-ready, distributed-system-safe metering and billing engine** for SaaS platforms. The system:

- Records usage **exactly once** (idempotent, database-backed)
- Enforces quotas **precisely** at plan boundaries
- Calculates costs **correctly** with complex token pricing rules
- Syncs subscriptions **safely** from Stripe webhooks
- Isolates tenants **completely** at database level
- Handles failures **gracefully** with clear error messages

Implementation proceeds in **15 modules**, each with **unit/integration/acceptance tests** proving correctness. The final system is ready for production use on day 1.

---

**Document Status:** ✅ Complete  
**Version:** 1.0  
**Last Updated:** August 2026
