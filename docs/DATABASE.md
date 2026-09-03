# Database Schema Documentation

Complete database schema for FlyRank Billing Engine.

---

## Overview

**Database**: PostgreSQL 16  
**ORM**: SQLAlchemy 2.0  
**Migrations**: Alembic  
**Tables**: 16  
**Indexes**: 40+  
**Constraints**: Foreign keys, unique constraints, check constraints  

---

## Database Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       CORE BILLING TABLES                        │
├─────────────────────────────────────────────────────────────────┤
│ ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│ │     tenants      │  │   plans          │  │  subscriptions   │ │
│ ├──────────────────┤  ├──────────────────┤  ├──────────────────┤ │
│ │ id (PK)          │  │ id (PK)          │  │ id (PK)          │ │
│ │ name             │  │ name             │  │ tenant_id (FK)   │ │
│ │ email            │  │ description      │  │ plan_id (FK)     │ │
│ │ created_at       │  │ api_calls_limit  │  │ status           │ │
│ │ updated_at       │  │ ai_tokens_limit  │  │ stripe_sub_id    │ │
│ │ is_active        │  │ price_cents      │  │ created_at       │ │
│ └──────────────────┘  │ created_at       │  │ updated_at       │ │
│        │              └──────────────────┘  └──────────────────┘ │
│        │                      ▲                       ▲            │
│        │                      │                       │            │
│        └──────────────────────┴───────────────────────┘            │
│                                                                    │
├─────────────────────────────────────────────────────────────────┤
│ ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│ │   usage_events   │  │  webhook_events  │  │     users        │ │
│ ├──────────────────┤  ├──────────────────┤  ├──────────────────┤ │
│ │ id (PK)          │  │ id (PK)          │  │ id (PK)          │ │
│ │ tenant_id (FK)   │  │ event_id (unique)│  │ tenant_id (FK)   │ │
│ │ type             │  │ event_type       │  │ email            │ │
│ │ quantity         │  │ data             │  │ hashed_password  │ │
│ │ cost_cents       │  │ processed        │  │ is_active        │ │
│ │ idempotency_key  │  │ created_at       │  │ created_at       │ │
│ │ timestamp        │  └──────────────────┘  └──────────────────┘ │
│ └──────────────────┘                                              │
│        ▲                                           ▲               │
│        └───────────────────────────────────────────┘               │
│                                                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Tables

### 1. tenants

Multi-tenant customer organizations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique tenant identifier |
| `name` | VARCHAR(255) | NOT NULL | Organization name |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | Primary contact email |
| `stripe_customer_id` | VARCHAR(255) | UNIQUE | Stripe customer ID |
| `is_active` | BOOLEAN | DEFAULT true | Account active status |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

**Indexes**:
- `tenants_email_idx` - UNIQUE on email
- `tenants_stripe_customer_id_idx` - For Stripe lookups
- `tenants_is_active_idx` - For filtering active tenants

**Notes**:
- All data is isolated per tenant
- Stripe customer ID links to Stripe account
- Email is unique per tenant

---

### 2. plans

Billing plans (Free, Pro, etc.)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | VARCHAR(50) | PRIMARY KEY | Plan identifier (free, pro) |
| `name` | VARCHAR(255) | NOT NULL | Display name |
| `description` | TEXT | | Plan description |
| `api_calls_limit` | INTEGER | NOT NULL | Monthly API call quota |
| `ai_tokens_limit` | INTEGER | NOT NULL | Monthly AI token quota |
| `price_cents` | INTEGER | NOT NULL | Monthly price in cents |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

**Sample Data**:
```sql
INSERT INTO plans VALUES
('free', 'Free', 'Basic plan', 1000, 100000, 0, NOW(), NOW()),
('pro', 'Professional', 'Advanced plan', 100000, 10000000, 2999, NOW(), NOW());
```

**Notes**:
- Plan IDs are fixed (free, pro, etc.)
- Prices stored as cents (integers)
- Quotas are monthly limits

---

### 3. subscriptions

Tenant → Plan associations (current subscription).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique subscription ID |
| `tenant_id` | UUID | NOT NULL, FK → tenants | Tenant reference |
| `plan_id` | VARCHAR(50) | NOT NULL, FK → plans | Plan reference |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'active' | active, past_due, canceled |
| `stripe_subscription_id` | VARCHAR(255) | UNIQUE | Stripe subscription ID |
| `stripe_customer_id` | VARCHAR(255) | | Stripe customer ID |
| `billing_cycle_start` | TIMESTAMP | | Current cycle start |
| `billing_cycle_end` | TIMESTAMP | | Current cycle end |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

**Indexes**:
- `subscriptions_tenant_id_idx` - For tenant lookups
- `subscriptions_stripe_subscription_id_idx` - UNIQUE on Stripe ID
- `subscriptions_status_idx` - For status filtering

**Constraints**:
- Foreign key on tenant_id (CASCADE on delete)
- Foreign key on plan_id (RESTRICT on delete)
- CHECK status IN ('active', 'past_due', 'canceled')

**Notes**:
- One subscription per tenant (current plan)
- Stripe IDs link to Stripe account
- Status tracks subscription health

---

### 4. users

Tenant users (for authentication).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique user ID |
| `tenant_id` | UUID | NOT NULL, FK → tenants | Tenant reference |
| `email` | VARCHAR(255) | NOT NULL | User email (unique per tenant) |
| `hashed_password` | VARCHAR(255) | NOT NULL | bcrypt hashed password |
| `is_active` | BOOLEAN | DEFAULT true | Account active status |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

**Indexes**:
- `users_tenant_id_email_idx` - UNIQUE on (tenant_id, email)
- `users_tenant_id_idx` - For tenant lookups

**Constraints**:
- Foreign key on tenant_id (CASCADE on delete)
- UNIQUE (tenant_id, email) - Email unique per tenant only

**Notes**:
- Passwords hashed with bcrypt (cost 12)
- Email unique within tenant scope
- is_active allows soft deactivation

---

### 5. usage_events

Metering records (billable actions).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique event ID |
| `tenant_id` | UUID | NOT NULL, FK → tenants | Tenant reference |
| `type` | VARCHAR(50) | NOT NULL | api_call, ai_tokens, etc. |
| `quantity` | INTEGER | NOT NULL | Number of units |
| `cost_cents` | INTEGER | NOT NULL | Cost in cents |
| `idempotency_key` | VARCHAR(255) | NOT NULL | Deduplication key |
| `metadata` | JSONB | | Additional data |
| `timestamp` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Event time |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Record creation time |

**Indexes**:
- `usage_events_tenant_id_type_timestamp_idx` - Main query index
- `usage_events_tenant_id_idempotency_key_idx` - For deduplication
- `usage_events_timestamp_idx` - For time-based queries

**Constraints**:
- Foreign key on tenant_id (CASCADE on delete)
- UNIQUE (tenant_id, idempotency_key) - **Critical for idempotency**
- CHECK quantity > 0
- CHECK cost_cents >= 0

**Notes**:
- **UNIQUE (tenant_id, idempotency_key)** prevents double-charging
- Timestamp is event occurrence time
- cost_cents pre-calculated for quick rollups
- metadata stores extra info (model, tokens, etc.)

---

### 6. webhook_events

Stripe webhook event deduplication.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique record ID |
| `event_id` | VARCHAR(255) | NOT NULL, UNIQUE | Stripe event ID |
| `event_type` | VARCHAR(255) | NOT NULL | Event type (checkout.session.completed) |
| `data` | JSONB | NOT NULL | Full webhook payload |
| `processed` | BOOLEAN | DEFAULT false | Processing status |
| `error_message` | TEXT | | Error details if failed |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Received timestamp |
| `processed_at` | TIMESTAMP | | Processing completion time |

**Indexes**:
- `webhook_events_event_id_idx` - UNIQUE on event_id
- `webhook_events_event_type_idx` - For type filtering
- `webhook_events_processed_idx` - For unprocessed events

**Constraints**:
- UNIQUE event_id - **Prevents duplicate processing**

**Notes**:
- Idempotent webhook handling
- Stores complete payload for replay
- processed flag tracks completion
- error_message for debugging

---

## Advanced Feature Tables

### 7. invoices

Generated monthly invoices.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique invoice ID |
| `tenant_id` | UUID | NOT NULL, FK → tenants | Tenant reference |
| `invoice_number` | VARCHAR(50) | NOT NULL, UNIQUE | INV-YYYY-MM-NNNN |
| `period_start` | TIMESTAMP | NOT NULL | Billing period start |
| `period_end` | TIMESTAMP | NOT NULL | Billing period end |
| `total_cents` | INTEGER | NOT NULL | Invoice total in cents |
| `status` | VARCHAR(50) | NOT NULL | DRAFT, ISSUED, PAID, CANCELED |
| `stripe_invoice_id` | VARCHAR(255) | | Stripe invoice ID |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `issued_at` | TIMESTAMP | | Issued timestamp |
| `paid_at` | TIMESTAMP | | Payment timestamp |
| `due_date` | TIMESTAMP | | Due date |

**Indexes**:
- `invoices_tenant_id_period_idx` - For tenant period lookups
- `invoices_invoice_number_idx` - UNIQUE on number
- `invoices_status_idx` - For status filtering

---

### 8. invoice_line_items

Invoice detail rows.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique line item ID |
| `invoice_id` | UUID | NOT NULL, FK → invoices | Invoice reference |
| `description` | VARCHAR(255) | NOT NULL | Item description |
| `quantity` | INTEGER | NOT NULL | Quantity |
| `unit_price_cents` | INTEGER | NOT NULL | Price per unit |
| `total_cents` | INTEGER | NOT NULL | Line total |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

**Constraints**:
- Foreign key on invoice_id (CASCADE on delete)

---

### 9. alerts

Usage alerts (80%, 100%, overage).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique alert ID |
| `tenant_id` | UUID | NOT NULL, FK → tenants | Tenant reference |
| `alert_type` | VARCHAR(50) | NOT NULL | threshold_80, threshold_100, overage |
| `threshold_percent` | INTEGER | | Alert threshold |
| `status` | VARCHAR(50) | NOT NULL | active, acknowledged, resolved |
| `triggered_at` | TIMESTAMP | NOT NULL | When alert triggered |
| `acknowledged_at` | TIMESTAMP | | When acknowledged |
| `resolved_at` | TIMESTAMP | | When resolved |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

---

### 10. alert_preferences

Notification settings per tenant.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique preference ID |
| `tenant_id` | UUID | NOT NULL, FK → tenants | Tenant reference |
| `alert_type` | VARCHAR(50) | NOT NULL | Alert type |
| `email_enabled` | BOOLEAN | DEFAULT true | Send email |
| `webhook_enabled` | BOOLEAN | DEFAULT false | Send webhook |
| `webhook_url` | VARCHAR(500) | | Webhook URL |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

---

### 11. prorated_adjustments

Mid-cycle plan change billing.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique adjustment ID |
| `tenant_id` | UUID | NOT NULL, FK → tenants | Tenant reference |
| `from_plan_id` | VARCHAR(50) | NOT NULL, FK → plans | Original plan |
| `to_plan_id` | VARCHAR(50) | NOT NULL, FK → plans | New plan |
| `adjustment_cents` | INTEGER | NOT NULL | Credit/charge in cents |
| `daily_rate_from` | INTEGER | NOT NULL | From plan daily rate |
| `daily_rate_to` | INTEGER | NOT NULL | To plan daily rate |
| `days_remaining` | INTEGER | NOT NULL | Days in billing cycle |
| `adjustment_type` | VARCHAR(50) | NOT NULL | credit, charge |
| `applied_at` | TIMESTAMP | NOT NULL | When applied |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

---

### 12. reconciliation_runs

Nightly Stripe vs DB sync audit.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique run ID |
| `run_date` | TIMESTAMP | NOT NULL | When run executed |
| `total_tenants` | INTEGER | NOT NULL | Tenants checked |
| `issues_found` | INTEGER | NOT NULL | Mismatches found |
| `issues_resolved` | INTEGER | NOT NULL | Issues fixed |
| `duration_seconds` | INTEGER | NOT NULL | Execution time |
| `status` | VARCHAR(50) | NOT NULL | success, partial, failed |
| `error_message` | TEXT | | Error details if failed |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

---

### 13. reconciliation_issues

Issues found during reconciliation.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique issue ID |
| `run_id` | UUID | NOT NULL, FK → reconciliation_runs | Run reference |
| `tenant_id` | UUID | NOT NULL, FK → tenants | Tenant reference |
| `issue_type` | VARCHAR(50) | NOT NULL | subscription_mismatch, etc. |
| `description` | TEXT | NOT NULL | Issue details |
| `stripe_data` | JSONB | | Stripe data snapshot |
| `local_data` | JSONB | | Local data snapshot |
| `resolved` | BOOLEAN | DEFAULT false | Resolution status |
| `resolved_at` | TIMESTAMP | | When resolved |
| `resolution_action` | VARCHAR(255) | | What was done |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

---

### 14. overage_charges

Usage beyond quota billing.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique charge ID |
| `tenant_id` | UUID | NOT NULL, FK → tenants | Tenant reference |
| `subscription_id` | UUID | NOT NULL, FK → subscriptions | Subscription reference |
| `usage_type` | VARCHAR(50) | NOT NULL | api_call, ai_tokens |
| `overage_quantity` | INTEGER | NOT NULL | Units over quota |
| `unit_price_cents` | INTEGER | NOT NULL | Price per unit |
| `total_cents` | INTEGER | NOT NULL | Total overage charge |
| `period_start` | TIMESTAMP | NOT NULL | Billing period start |
| `period_end` | TIMESTAMP | NOT NULL | Billing period end |
| `status` | VARCHAR(50) | NOT NULL | pending, charged, failed |
| `stripe_charge_id` | VARCHAR(255) | | Stripe charge ID |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `charged_at` | TIMESTAMP | | When charged |

---

### 15. overage_policies

Overage pricing configuration per plan.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique policy ID |
| `plan_id` | VARCHAR(50) | NOT NULL, FK → plans | Plan reference |
| `api_calls_price_cents` | INTEGER | NOT NULL | Price per 1000 calls |
| `ai_tokens_price_cents` | INTEGER | NOT NULL | Price per 1000 tokens |
| `suspension_limit_multiplier` | DECIMAL | NOT NULL | Limit before suspension |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

---

### 16. saved_reports & report_runs

Analytics and reporting.

**saved_reports**:
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Unique report ID |
| `tenant_id` | UUID | Tenant reference |
| `report_type` | VARCHAR(50) | usage, revenue, costs |
| `parameters` | JSONB | Report filters |
| `created_at` | TIMESTAMP | Creation timestamp |

**report_runs**:
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Unique run ID |
| `report_id` | UUID | Report reference |
| `data` | JSONB | Report results |
| `generated_at` | TIMESTAMP | Generation timestamp |

---

## Query Patterns

### High-Performance Queries

#### 1. Get Current Month Usage
```sql
SELECT 
  SUM(CASE WHEN type = 'api_call' THEN quantity ELSE 0 END) as api_calls_used,
  SUM(CASE WHEN type = 'ai_tokens' THEN quantity ELSE 0 END) as tokens_used,
  SUM(cost_cents) as total_cost_cents
FROM usage_events
WHERE tenant_id = $1 
  AND timestamp >= date_trunc('month', now())
  AND timestamp < date_trunc('month', now() + interval '1 month');
```

**Index Used**: `usage_events_tenant_id_type_timestamp_idx`

#### 2. Check Idempotency
```sql
SELECT id, cost_cents FROM usage_events
WHERE tenant_id = $1 AND idempotency_key = $2;
```

**Index Used**: `usage_events_tenant_id_idempotency_key_idx`

#### 3. Get Unprocessed Webhooks
```sql
SELECT * FROM webhook_events
WHERE processed = false
ORDER BY created_at ASC;
```

**Index Used**: `webhook_events_processed_idx`

#### 4. Find Overdue Invoices
```sql
SELECT * FROM invoices
WHERE tenant_id = $1 
  AND status != 'PAID'
  AND due_date < NOW();
```

**Index Used**: `invoices_tenant_id_period_idx`

---

## Data Isolation (Tenant Security)

All queries enforce tenant isolation:

```python
# Every query includes tenant_id filter
query = session.query(UsageEvent).filter(
    UsageEvent.tenant_id == tenant_id  # ← ALWAYS required
)
```

**Foreign Key Constraints** ensure data integrity:
- Subscriptions → Tenants (CASCADE delete)
- Usage Events → Tenants (CASCADE delete)
- Invoices → Tenants (CASCADE delete)
- Users → Tenants (CASCADE delete)

---

## Indexing Strategy

**40+ Indexes** optimize for:

1. **Tenant Filtering** - Every query includes tenant_id
2. **Time-Based Queries** - Aggregation by month/day
3. **Uniqueness Constraints** - Idempotency keys, Stripe IDs
4. **Status Filtering** - Active subscriptions, unprocessed webhooks
5. **Stripe Lookups** - Fast synchronization

---

## Migration Management

**Alembic Versions**: 8 migrations

```
001_initial_schema.py      - Core tables
002_subscriptions.py        - Subscription management
003_invoices.py            - Invoicing
004_alerts.py              - Alert system
005_proration.py           - Plan changes
006_reconciliation.py      - Audit jobs
007_overages.py            - Overage billing
008_reporting.py           - Analytics
```

Run migrations:
```bash
alembic upgrade head
```

---

## Backup Strategy

**Daily Backups**:
```bash
# Full backup
pg_dump flyrank_billing | gzip > backup-$(date +%Y%m%d).sql.gz

# Restore
gunzip < backup-20240915.sql.gz | psql flyrank_billing
```

---

## Performance Tuning

**PostgreSQL Configuration**:
```
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 64MB
maintenance_work_mem = 512MB
random_page_cost = 1.1
```

**Connection Pooling**:
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
)
```

---

**Last Updated**: September 2, 2026
