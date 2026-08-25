# DATABASE.md - FlyRank Database Schema & Design

---

## Database Overview

- **System**: PostgreSQL 16
- **ORM**: SQLAlchemy 2.x
- **Migrations**: Alembic
- **Connection Pool**: 5-20 connections

---

## Core Tables

### tenants
Primary tenant (customer organization).

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    company_name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_tenants_email (email),
    INDEX idx_tenants_status (status)
);
```

**Fields**:
- `id`: Unique tenant identifier
- `email`: Contact email (unique)
- `company_name`: Organization name
- `status`: active, suspended, canceled
- `created_at`, `updated_at`: Timestamps

---

### subscription_plans
Available plan tiers.

```sql
CREATE TABLE subscription_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    price_cents INTEGER NOT NULL,
    api_calls_limit INTEGER NOT NULL,
    ai_tokens_limit INTEGER NOT NULL,
    features JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(name)
);
```

**Seed Data**:
```sql
INSERT INTO subscription_plans (name, price_cents, api_calls_limit, ai_tokens_limit) VALUES
('Free', 0, 1000, 100000),
('Pro', 2999, 100000, 10000000);
```

**Fields**:
- `price_cents`: Monthly price in cents (integer for precision)
- `api_calls_limit`: Monthly API call allowance
- `ai_tokens_limit`: Monthly token allowance
- `features`: JSON array of feature strings

---

### subscriptions
Tenant's current subscription.

```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL UNIQUE,
    plan_id UUID NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    stripe_subscription_id VARCHAR(255),
    stripe_customer_id VARCHAR(255),
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES subscription_plans(id),
    
    UNIQUE(tenant_id),
    INDEX idx_subscriptions_tenant_id (tenant_id),
    INDEX idx_subscriptions_stripe_id (stripe_subscription_id),
    INDEX idx_subscriptions_status (status)
);
```

**Fields**:
- `tenant_id`: Which tenant (UNIQUE = one subscription per tenant)
- `plan_id`: Current plan
- `status`: active, past_due, canceled
- `stripe_subscription_id`: Stripe's ID for webhooks
- `stripe_customer_id`: Stripe customer ID
- `current_period_start/end`: Billing cycle dates

---

### usage_events
Individual usage recordings (immutable after creation).

```sql
CREATE TABLE usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    quantity INTEGER NOT NULL,
    cost_cents INTEGER NOT NULL DEFAULT 0,
    idempotency_key VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- CRITICAL: Uniqueness constraint prevents double-counting
    UNIQUE(tenant_id, idempotency_key),
    
    INDEX idx_usage_events_tenant_id (tenant_id),
    INDEX idx_usage_events_created_at (created_at),
    INDEX idx_usage_events_event_type (event_type),
    INDEX idx_usage_events_tenant_created (tenant_id, created_at)
);
```

**Fields**:
- `tenant_id`: Which tenant
- `event_type`: api_call, ai_tokens_input, ai_tokens_cached_input, ai_tokens_output, ai_tokens_reasoning
- `quantity`: Number of calls/tokens
- `cost_cents`: Cost in cents (never float)
- `idempotency_key`: Prevents duplicates (UNIQUE constraint at DB level)
- `created_at`: When recorded

**Event Types**:
```sql
-- API Calls
INSERT INTO usage_events (tenant_id, event_type, quantity, cost_cents, idempotency_key)
VALUES (tenant_id, 'api_call', 1, 0.001 * 100, 'req_123');

-- AI Tokens (different rates)
INSERT INTO usage_events (tenant_id, event_type, quantity, cost_cents, idempotency_key) VALUES
(tenant_id, 'ai_tokens_input', 1000, 50, 'req_124'),         -- $0.0005 per 1k
(tenant_id, 'ai_tokens_cached_input', 1000, 15, 'req_125'),  -- $0.00015 per 1k (cheaper)
(tenant_id, 'ai_tokens_output', 500, 100, 'req_126'),        -- $0.002 per 1k
(tenant_id, 'ai_tokens_reasoning', 500, 100, 'req_127');     -- $0.002 per 1k (output rate)
```

**Critical Design Notes**:
- Immutable after creation (no updates)
- Quantity always positive
- Cost stored in cents (integer precision)
- Idempotency key uniqueness at DB level
- Indexed by tenant_id for query performance

---

### idempotency_keys
Cached responses for retry-safe operations.

```sql
CREATE TABLE idempotency_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    key VARCHAR(255) NOT NULL,
    request_body JSONB,
    response_body JSONB NOT NULL,
    status_code INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP + INTERVAL '24 hours',
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- CRITICAL: Uniqueness prevents duplicate processing
    UNIQUE(tenant_id, key),
    
    INDEX idx_idempotency_keys_tenant_id (tenant_id),
    INDEX idx_idempotency_keys_expires_at (expires_at)
);
```

**Fields**:
- `key`: Client-provided idempotency key
- `request_body`: Original request (JSONB for verification)
- `response_body`: Cached response to return
- `status_code`: HTTP status to return
- `expires_at`: Auto-cleanup old keys

**Flow**:
1. Client sends request with `idempotency_key`
2. Check if key exists in table
3. If exists, return cached response (same status + body)
4. If not, process request
5. Store request + response + status in table
6. Return response

---

### webhook_events
Stripe webhooks (immutable log for audit).

```sql
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id VARCHAR(255) UNIQUE NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    tenant_id UUID,
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE SET NULL,
    
    -- CRITICAL: Uniqueness prevents duplicate event processing
    UNIQUE(event_id),
    
    INDEX idx_webhook_events_event_id (event_id),
    INDEX idx_webhook_events_tenant_id (tenant_id),
    INDEX idx_webhook_events_processed (processed),
    INDEX idx_webhook_events_created_at (created_at)
);
```

**Fields**:
- `event_id`: Stripe's event ID (e.g., evt_test_123)
- `event_type`: checkout.session.completed, customer.subscription.updated
- `payload`: Full Stripe event JSON
- `processed`: Whether we processed this event
- `processed_at`: When it was processed

**Critical Notes**:
- `event_id` is UNIQUE across all time
- Prevents Stripe webhook retries from creating duplicates
- Stripe event IDs are guaranteed unique per account

---

### users (Authentication)
User accounts (optional, for future multi-user support).

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    
    UNIQUE(tenant_id, email),
    INDEX idx_users_tenant_id (tenant_id),
    INDEX idx_users_email (email)
);
```

---

## Query Patterns

### Get Current Usage (Aggregation)

```sql
SELECT
  SUM(CASE WHEN event_type = 'api_call' THEN quantity ELSE 0 END) as api_calls_used,
  SUM(CASE WHEN event_type LIKE 'ai_tokens_%' THEN quantity ELSE 0 END) as ai_tokens_used,
  SUM(cost_cents) as total_cost_cents
FROM usage_events
WHERE tenant_id = $1
  AND created_at >= date_trunc('month', CURRENT_TIMESTAMP)
  AND created_at < date_trunc('month', CURRENT_TIMESTAMP) + INTERVAL '1 month';
```

### Check Quota Before Recording

```sql
-- Get current usage
WITH monthly_usage AS (
  SELECT
    SUM(CASE WHEN event_type = 'api_call' THEN quantity ELSE 0 END) as api_calls_used
  FROM usage_events
  WHERE tenant_id = $1
    AND created_at >= date_trunc('month', CURRENT_TIMESTAMP)
)
SELECT
  p.api_calls_limit,
  mu.api_calls_used,
  (p.api_calls_limit - COALESCE(mu.api_calls_used, 0)) as remaining
FROM subscriptions s
JOIN subscription_plans p ON s.plan_id = p.id
CROSS JOIN monthly_usage mu
WHERE s.tenant_id = $1;
```

### Prevent Duplicate Usage (Idempotency Check)

```sql
-- Check if idempotency key already processed
SELECT response_body, status_code
FROM idempotency_keys
WHERE tenant_id = $1 AND key = $2;

-- If exists, return cached response
-- If not exists, insert new usage event with idempotency key

-- Database will reject duplicate if key already exists (UNIQUE constraint)
```

### Monthly Cost Breakdown by Type

```sql
SELECT
  event_type,
  SUM(quantity) as total_quantity,
  SUM(cost_cents) as total_cost_cents
FROM usage_events
WHERE tenant_id = $1
  AND created_at >= date_trunc('month', CURRENT_TIMESTAMP)
GROUP BY event_type
ORDER BY total_cost_cents DESC;
```

### Tenant Data Isolation

```sql
-- Every query scoped by tenant_id
SELECT * FROM usage_events WHERE tenant_id = $1;  -- Safe
SELECT * FROM usage_events;                        -- WRONG: Gets all data!

-- Example in application code:
query = db.query(UsageEvent).filter_by(tenant_id=current_tenant_id)
```

---

## Indexes

**Query Performance**:

```sql
-- Fast tenant lookups
INDEX idx_subscriptions_tenant_id (tenant_id);
INDEX idx_usage_events_tenant_id (tenant_id);
INDEX idx_webhook_events_tenant_id (tenant_id);

-- Fast time-range queries (billing period)
INDEX idx_usage_events_created_at (created_at);
INDEX idx_webhook_events_created_at (created_at);

-- Composite index for common queries
INDEX idx_usage_events_tenant_created (tenant_id, created_at);

-- Deduplication lookups (fast)
UNIQUE idx_idempotency_keys (tenant_id, key);
UNIQUE idx_webhook_events (event_id);
UNIQUE idx_usage_events_idempotency (tenant_id, idempotency_key);
```

---

## Constraints

### Uniqueness Constraints (Data Integrity)

```sql
UNIQUE(tenants.email)                           -- No duplicate emails
UNIQUE(subscription_plans.name)                  -- No duplicate plans
UNIQUE(subscriptions.tenant_id)                  -- One sub per tenant
UNIQUE(subscriptions.stripe_subscription_id)     -- One Stripe ID per sub
UNIQUE(idempotency_keys.tenant_id, key)          -- One key per tenant (deduplication)
UNIQUE(usage_events.tenant_id, idempotency_key)  -- One usage per key (no double-count)
UNIQUE(webhook_events.event_id)                  -- One webhook per Stripe event (deduplication)
```

### Foreign Key Constraints (Referential Integrity)

```sql
FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
-- When tenant deleted, cascade delete their subscriptions and usage

FOREIGN KEY (plan_id) REFERENCES subscription_plans(id)
-- Subscriptions must reference valid plans
```

---

## Data Types

### Important Decisions

**Integers for Money** (NOT floats):
```sql
cost_cents INTEGER  -- Store as cents (e.g., $5.00 = 500)
price_cents INTEGER -- Never use NUMERIC or FLOAT for money
```

**UUID for IDs** (NOT serial integers):
```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid()  -- Secure, distributed
-- NOT: id SERIAL PRIMARY KEY  -- Predictable, can leak data
```

**JSONB for Flexible Data**:
```sql
payload JSONB  -- Stripe webhook payload (unstructured)
features JSONB  -- Plan features (dynamic)
```

**VARCHAR for Strings**:
```sql
event_type VARCHAR(50)  -- Fixed length for performance
email VARCHAR(255)      -- Email addresses
```

**TIMESTAMP for Dates**:
```sql
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
expires_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP + INTERVAL '24 hours'
```

---

## Migrations

All schema changes via Alembic (version controlled).

```bash
# Create migration
alembic revision --autogenerate -m "Add webhook_events table"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# See status
alembic current
```

---

## Backup & Recovery

### Automated Backups
```bash
# Daily backup (cron job)
pg_dump flyrank_billing > /backups/flyrank_$(date +%Y%m%d).sql

# Restore from backup
psql flyrank_billing < /backups/flyrank_20240101.sql
```

### Point-in-Time Recovery
```bash
# With Write-Ahead Logs enabled (WAL)
# Can recover to any point in time within retention period
```

---

## Performance Tuning

### Connection Pooling
```python
# SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
```

### Query Optimization
```python
# Eager loading (avoid N+1 queries)
db.query(Subscription).options(
    joinedload(Subscription.plan)
).filter_by(tenant_id=tenant_id).first()
```

### Slow Query Detection
```sql
-- Enable slow query log
log_min_duration_statement = 1000  -- Log queries >1 second
```

---

## Security

### SQL Injection Prevention
```python
# ✅ SAFE: Parameterized queries (SQLAlchemy)
db.query(UsageEvent).filter_by(tenant_id=tenant_id)

# ❌ UNSAFE: String concatenation
query = f"SELECT * FROM usage_events WHERE tenant_id = '{tenant_id}'"
```

### Tenant Data Isolation
```python
# ✅ SAFE: All queries include tenant filter
events = db.query(UsageEvent).filter_by(tenant_id=current_tenant_id).all()

# ❌ UNSAFE: Missing tenant filter
events = db.query(UsageEvent).all()  # Gets ALL tenants' data!
```

---

**Last Updated**: 2024
**PostgreSQL Version**: 16
**Status**: Production Ready
