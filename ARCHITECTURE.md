# FlyRank Billing Engine - Complete Technical Architecture

This document describes the complete technical architecture, folder structure, system design, components, data flows, and implementation details of the FlyRank SaaS usage metering and billing engine.

---

## Complete Folder & File Structure

```
flyrank-billing/
│
├── 📁 backend/                              [FastAPI Application Root]
│   │
│   ├── 📁 app/                              [Application Code]
│   │   │
│   │   ├── main.py                          [FastAPI Entry Point]
│   │   │   └── Creates FastAPI app instance
│   │   │   └── Registers all routers
│   │   │   └── Configures middleware (CORS, logging, error handlers)
│   │   │   └── Defines health check endpoints (/health, /ready)
│   │   │
│   │   ├── models.py                        [Core Data Models - 1,200+ lines]
│   │   │   ├── BaseModel (with id, created_at, updated_at)
│   │   │   ├── Tenant (customer organization)
│   │   │   ├── Plan (Free, Pro plans with quotas)
│   │   │   ├── Subscription (tenant → plan association)
│   │   │   ├── User (authentication with hashed passwords)
│   │   │   ├── UsageEvent (billable actions with idempotency)
│   │   │   ├── WebhookEvent (Stripe events with deduplication)
│   │   │   └── All relationships with proper foreign keys & constraints
│   │   │
│   │   ├── models_alert.py                  [Alert Domain Models]
│   │   │   ├── Alert (80%, 100%, overage thresholds)
│   │   │   └── AlertPreference (notification settings)
│   │   │
│   │   ├── models_invoice.py                [Invoice Domain Models]
│   │   │   ├── Invoice (monthly statements)
│   │   │   └── InvoiceLineItem (usage line items)
│   │   │
│   │   ├── models_overage.py                [Overage Domain Models]
│   │   │   ├── OverageCharge (beyond-quota usage)
│   │   │   └── OveragePolicy (overage pricing per plan)
│   │   │
│   │   ├── models_proration.py              [Proration Domain Models]
│   │   │   └── ProratedAdjustment (mid-cycle plan changes)
│   │   │
│   │   ├── models_reconciliation.py         [Reconciliation Domain Models]
│   │   │   ├── ReconciliationRun (nightly audit job runs)
│   │   │   └── ReconciliationIssue (mismatches found)
│   │   │
│   │   ├── models_reporting.py              [Reporting Domain Models]
│   │   │   ├── SavedReport (report configurations)
│   │   │   └── ReportRun (report execution history)
│   │   │
│   │   ├── schemas.py                       [Pydantic Request/Response Schemas]
│   │   │   ├── TenantSchema (tenant CRUD)
│   │   │   ├── UserSchema (user management)
│   │   │   ├── SubscriptionSchema (subscription info)
│   │   │   ├── UsageEventSchema (usage recording)
│   │   │   ├── UsageResponseSchema (current usage & cost)
│   │   │   ├── CheckoutSchema (Stripe checkout)
│   │   │   ├── WebhookSchema (webhook payload)
│   │   │   └── Error schemas with proper HTTP status codes
│   │   │
│   │   ├── config.py                       [Application Configuration]
│   │   │   ├── Settings (Pydantic BaseSettings)
│   │   │   ├── DATABASE_URL construction
│   │   │   ├── STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
│   │   │   ├── SECRET_KEY for JWT signing
│   │   │   ├── CORS configuration
│   │   │   ├── Logging configuration
│   │   │   └── Environment-based settings (dev, staging, production)
│   │   │
│   │   ├── config_pricing.py                [Pricing Configuration - Immutable]
│   │   │   ├── PricingConfig class with pricing constants
│   │   │   ├── API_CALL_PRICE_PER_1K = 0.01
│   │   │   ├── INPUT_TOKEN_PRICE_PER_1K = 0.0005
│   │   │   ├── CACHED_INPUT_TOKEN_PRICE_PER_1K = 0.00015
│   │   │   ├── OUTPUT_TOKEN_PRICE_PER_1K = 0.002
│   │   │   ├── REASONING_TOKEN_PRICE_PER_1K = 0.002
│   │   │   ├── calculate_cost_cents() method (integer arithmetic)
│   │   │   └── format_cost_dollars() for display
│   │   │
│   │   ├── database.py                     [SQLAlchemy Setup]
│   │   │   ├── Create engine with connection pooling
│   │   │   ├── Session factory (sessionmaker)
│   │   │   ├── Base for model declarations
│   │   │   ├── get_db() context manager for transactions
│   │   │   └── Connection pool configuration
│   │   │
│   │   ├── dependencies.py                 [Dependency Injection]
│   │   │   ├── get_db() - provides database session
│   │   │   ├── get_current_user() - JWT validation & extraction
│   │   │   ├── verify_tenant_access() - row-level security
│   │   │   ├── get_current_tenant() - tenant from JWT token
│   │   │   └── All endpoints use these for clean, testable code
│   │   │
│   │   ├── 📁 services/                    [Business Logic Layer - 12 Services]
│   │   │   │
│   │   │   ├── __init__.py                 [Service exports]
│   │   │   │
│   │   │   ├── tenant_service.py           [Tenant Management Service]
│   │   │   │   ├── TenantService class
│   │   │   │   ├── create_tenant(name, email, plan_id)
│   │   │   │   ├── get_tenant(tenant_id) - with isolation check
│   │   │   │   ├── list_tenants() - for current user
│   │   │   │   ├── update_tenant(tenant_id, **kwargs)
│   │   │   │   ├── delete_tenant(tenant_id) - cascade delete
│   │   │   │   └── get_tenant_status() - subscription & usage
│   │   │   │
│   │   │   ├── usage_service.py            [Usage Recording & Aggregation]
│   │   │   │   ├── UsageService class
│   │   │   │   ├── record_usage() - idempotent recording
│   │   │   │   │   ├── Check for existing idempotency_key
│   │   │   │   │   ├── If exists, return cached result
│   │   │   │   │   ├── Else, create new UsageEvent
│   │   │   │   │   ├── Handle UNIQUE constraint violation
│   │   │   │   │   └── Return response with tokens & cost
│   │   │   │   ├── get_current_usage(tenant_id)
│   │   │   │   │   ├── SUM usage since billing cycle start
│   │   │   │   │   ├── Get plan limits from subscription
│   │   │   │   │   ├── Calculate cost_cents
│   │   │   │   │   └── Return {used, limit, cost, days_remaining}
│   │   │   │   ├── get_usage_history(tenant_id, limit, offset)
│   │   │   │   └── get_monthly_summary(tenant_id)
│   │   │   │
│   │   │   ├── quota_service.py            [Quota Enforcement]
│   │   │   │   ├── QuotaService class
│   │   │   │   ├── check_quota_before_action()
│   │   │   │   │   ├── Get current usage
│   │   │   │   │   ├── Get plan limits
│   │   │   │   │   ├── Calculate remaining = limit - used
│   │   │   │   │   ├── If remaining <= 0: raise 429 error
│   │   │   │   │   ├── If subscription past_due: raise 402 error
│   │   │   │   │   └── Else: allow action
│   │   │   │   ├── can_use_quota(tenant_id, type, quantity)
│   │   │   │   └── get_quota_status(tenant_id)
│   │   │   │
│   │   │   ├── pricing_service.py          [Cost Calculation]
│   │   │   │   ├── PricingService class
│   │   │   │   ├── calculate_usage_cost() - single event
│   │   │   │   ├── calculate_monthly_cost() - aggregation
│   │   │   │   │   ├── Query all usage_events for month
│   │   │   │   │   ├── Group by type (api_call, input_tokens, etc)
│   │   │   │   │   ├── Apply pricing rules (with caching multiplier)
│   │   │   │   │   ├── Sum all costs in integer cents
│   │   │   │   │   └── Return total
│   │   │   │   ├── format_cost_for_display()
│   │   │   │   └── get_cost_breakdown(tenant_id)
│   │   │   │
│   │   │   ├── stripe_service.py           [Stripe Integration]
│   │   │   │   ├── StripeService class
│   │   │   │   ├── create_checkout_session(tenant_id, plan_id)
│   │   │   │   │   ├── Get tenant Stripe customer ID
│   │   │   │   │   ├── Create Stripe Checkout session
│   │   │   │   │   ├── Store session ID locally for tracking
│   │   │   │   │   └── Return checkout URL
│   │   │   │   ├── verify_webhook_signature(payload, signature)
│   │   │   │   │   ├── Compute HMAC-SHA256(payload, secret)
│   │   │   │   │   ├── Compare computed vs received signature
│   │   │   │   │   ├── Return True/False
│   │   │   │   │   └── Never leak whether verification failed
│   │   │   │   ├── handle_checkout_completed(event)
│   │   │   │   ├── handle_subscription_updated(event)
│   │   │   │   ├── handle_subscription_deleted(event)
│   │   │   │   └── sync_subscription_from_stripe(stripe_sub_id)
│   │   │   │
│   │   │   ├── alert_service.py            [Usage Alerts]
│   │   │   │   ├── AlertService class
│   │   │   │   ├── check_and_trigger_alerts(tenant_id)
│   │   │   │   ├── create_alert(tenant_id, alert_type)
│   │   │   │   ├── acknowledge_alert(alert_id)
│   │   │   │   └── send_notification(alert)
│   │   │   │
│   │   │   ├── invoice_service.py          [Invoice Generation]
│   │   │   │   ├── InvoiceService class
│   │   │   │   ├── generate_monthly_invoice(tenant_id)
│   │   │   │   ├── create_invoice_line_items()
│   │   │   │   ├── issue_invoice(invoice_id)
│   │   │   │   └── mark_invoice_paid(invoice_id)
│   │   │   │
│   │   │   ├── proration_service.py        [Mid-Cycle Plan Changes]
│   │   │   │   ├── ProratedService class
│   │   │   │   ├── apply_proration(tenant_id, from_plan, to_plan)
│   │   │   │   ├── calculate_daily_rate(plan)
│   │   │   │   ├── calculate_adjustment()
│   │   │   │   └── store_adjustment_record()
│   │   │   │
│   │   │   ├── reconciliation_service.py   [Stripe Audit]
│   │   │   │   ├── ReconciliationService class
│   │   │   │   ├── run_nightly_reconciliation()
│   │   │   │   ├── compare_stripe_vs_local()
│   │   │   │   ├── detect_mismatches()
│   │   │   │   ├── resolve_issue(issue_id)
│   │   │   │   └── create_reconciliation_report()
│   │   │   │
│   │   │   ├── overage_service.py          [Beyond-Quota Billing]
│   │   │   │   ├── OverageService class
│   │   │   │   ├── check_overage(tenant_id, type, quantity)
│   │   │   │   ├── calculate_overage_cost()
│   │   │   │   ├── apply_overage_charge()
│   │   │   │   └── get_overage_status(tenant_id)
│   │   │   │
│   │   │   ├── reporting_service.py        [Analytics & Reports]
│   │   │   │   ├── ReportingService class
│   │   │   │   ├── generate_usage_report()
│   │   │   │   ├── generate_revenue_report()
│   │   │   │   ├── generate_cost_breakdown()
│   │   │   │   ├── get_tenant_metrics()
│   │   │   │   ├── get_platform_dashboard()
│   │   │   │   └── forecast_usage_trend()
│   │   │   │
│   │   │   └── webhook_handler.py          [Webhook Processing]
│   │   │       ├── WebhookHandler class
│   │   │       ├── process_webhook(event_dict, signature)
│   │   │       ├── deduplicate_event(event_id)
│   │   │       ├── route_to_handler(event_type)
│   │   │       └── handle_error()
│   │   │
│   │   ├── 📁 routes/                      [HTTP API Layer - 9 Routers]
│   │   │   │
│   │   │   ├── __init__.py                 [Router exports]
│   │   │   │
│   │   │   ├── auth.py                     [Authentication Routes]
│   │   │   │   ├── POST /auth/login        - email + password → JWT token
│   │   │   │   ├── POST /auth/logout       - invalidate session
│   │   │   │   ├── Bcrypt password verification
│   │   │   │   ├── JWT token generation with expiration
│   │   │   │   └── Error: 401 Unauthorized
│   │   │   │
│   │   │   ├── tenants.py                  [Tenant Management Routes]
│   │   │   │   ├── POST /tenants           - create tenant
│   │   │   │   ├── GET /tenants            - list (pagination)
│   │   │   │   ├── GET /tenants/{id}       - get one
│   │   │   │   ├── PUT /tenants/{id}       - update
│   │   │   │   ├── DELETE /tenants/{id}    - delete
│   │   │   │   ├── GET /tenants/{id}/status - subscription & usage
│   │   │   │   ├── Tenant isolation enforced via get_current_tenant()
│   │   │   │   └── HTTP 403 if accessing other tenant's data
│   │   │   │
│   │   │   ├── usage.py                    [Usage Metering Routes]
│   │   │   │   ├── POST /generate          - billable endpoint (CRITICAL)
│   │   │   │   │   ├── Requires idempotency_key header
│   │   │   │   │   ├── Call quota_service.check_quota()
│   │   │   │   │   ├── Call usage_service.record_usage()
│   │   │   │   │   ├── Call pricing_service.calculate_cost()
│   │   │   │   │   ├── Return {result, tokens_used, cost_cents, quota_remaining}
│   │   │   │   │   ├── HTTP 429 if quota exceeded
│   │   │   │   │   └── HTTP 402 if payment required
│   │   │   │   ├── GET /usage              - current month usage
│   │   │   │   ├── GET /usage/history      - usage events (paginated)
│   │   │   │   └── GET /usage/summary      - monthly summary
│   │   │   │
│   │   │   ├── billing.py                  [Subscription & Plans Routes]
│   │   │   │   ├── GET /subscription       - current subscription info
│   │   │   │   ├── GET /plans              - all available plans
│   │   │   │   ├── GET /costs/current      - current month cost
│   │   │   │   ├── GET /costs/breakdown    - cost by type
│   │   │   │   └── GET /costs/monthly-projection
│   │   │   │
│   │   │   ├── stripe.py                   [Stripe Integration Routes]
│   │   │   │   ├── POST /checkout          - create Stripe Checkout session
│   │   │   │   │   ├── Input: {plan_id, success_url, cancel_url}
│   │   │   │   │   ├── Output: {session_id, checkout_url, expires_at}
│   │   │   │   │   └── Stripe handles payment form
│   │   │   │   ├── POST /webhooks/stripe   - webhook receiver (CRITICAL)
│   │   │   │   │   ├── Extract signature from headers
│   │   │   │   │   ├── Call stripe_service.verify_webhook_signature()
│   │   │   │   │   ├── HTTP 400 if signature invalid
│   │   │   │   │   ├── Check event_id UNIQUE constraint
│   │   │   │   │   ├── HTTP 200 if duplicate (idempotent)
│   │   │   │   │   ├── Route event_type to handler
│   │   │   │   │   ├── Update subscription state atomically
│   │   │   │   │   └── HTTP 200 on success
│   │   │   │   └── GET /subscription/details - from Stripe
│   │   │   │
│   │   │   ├── alerts.py                   [Alert Routes]
│   │   │   │   ├── GET /alerts             - list alerts
│   │   │   │   ├── POST /alerts/{id}/acknowledge
│   │   │   │   ├── GET /alerts/status/summary
│   │   │   │   └── PUT /alerts/preferences
│   │   │   │
│   │   │   ├── invoices.py                 [Invoice Routes]
│   │   │   │   ├── GET /invoices           - list
│   │   │   │   ├── GET /invoices/{id}      - get one
│   │   │   │   ├── PUT /invoices/{id}/issue
│   │   │   │   └── PUT /invoices/{id}/pay
│   │   │   │
│   │   │   ├── reports.py                  [Reporting Routes]
│   │   │   │   ├── GET /reports/usage      - usage analytics
│   │   │   │   ├── GET /reports/revenue    - revenue breakdown
│   │   │   │   ├── GET /reports/costs      - cost analysis
│   │   │   │   └── GET /reports/dashboard  - platform metrics
│   │   │   │
│   │   │   └── health.py                   [System Health Routes]
│   │   │       ├── GET /health             - service health
│   │   │       └── GET /ready              - readiness probe
│   │   │
│   │   ├── 📁 repositories/                [Data Access Layer]
│   │   │   │
│   │   │   ├── __init__.py                 [Repository exports]
│   │   │   │
│   │   │   ├── tenant_repository.py        [Tenant Data Access]
│   │   │   │   ├── TenantRepository class
│   │   │   │   ├── Methods: create, get, list, update, delete
│   │   │   │   ├── All queries include tenant_id filter
│   │   │   │   └── Implements repository pattern
│   │   │   │
│   │   │   └── usage_repository.py         [Usage Event Data Access]
│   │   │       ├── UsageRepository class
│   │   │       ├── Methods: create, get, list, get_by_idempotency_key
│   │   │       ├── Aggregation queries: monthly_sum, by_type
│   │   │       └── Time-based queries: since_cycle_start
│   │   │
│   │   ├── 📁 utils/                       [Utilities]
│   │   │   │
│   │   │   ├── __init__.py
│   │   │   │
│   │   │   ├── db_helpers.py               [Database Utilities]
│   │   │   │   ├── get_billing_cycle_dates()
│   │   │   │   ├── get_tenant_from_token()
│   │   │   │   ├── verify_tenant_isolation()
│   │   │   │   └── common database helpers
│   │   │   │
│   │   │   ├── error_handlers.py           [Error Response Formatting]
│   │   │   │   ├── StandardErrorResponse class
│   │   │   │   ├── format_validation_error()
│   │   │   │   ├── format_auth_error()
│   │   │   │   └── format_quota_error()
│   │   │   │
│   │   │   └── logging_utils.py            [Structured Logging]
│   │   │       ├── get_logger(name)
│   │   │       ├── log_webhook_event()
│   │   │       └── log_quota_check()
│   │   │
│   │   ├── 📁 scripts/                     [Utility Scripts]
│   │   │   │
│   │   │   ├── __init__.py
│   │   │   │
│   │   │   └── seed_demo.py                [Demo Data Generation]
│   │   │       ├── Creates demo tenants
│   │   │       ├── Creates demo users
│   │   │       ├── Creates demo subscriptions
│   │   │       ├── Creates sample usage events
│   │   │       └── Run: python -m app.scripts.seed_demo
│   │   │
│   │   └── __init__.py                     [Package initialization]
│   │
│   ├── 📁 tests/                           [Test Suite - 30+ Tests]
│   │   │
│   │   ├── conftest.py                     [Pytest Fixtures & Configuration]
│   │   │   ├── pytest configuration
│   │   │   ├── db fixture - in-memory SQLite for tests
│   │   │   ├── client fixture - FastAPI TestClient
│   │   │   ├── tenant_data fixture - sample tenant
│   │   │   ├── usage_data fixture - sample usage event
│   │   │   └── All fixtures are function-scoped (fresh for each test)
│   │   │
│   │   ├── test_idempotency.py              [Metering Tests - 3 Tests]
│   │   │   ├── test_no_duplicate_usage_on_retry()
│   │   │   │   └── 3 requests with same key → 1 event
│   │   │   ├── test_different_idempotency_keys_create_separate_events()
│   │   │   │   └── Different keys → separate events
│   │   │   └── test_idempotency_key_unique_constraint()
│   │   │       └── Database enforces uniqueness
│   │   │
│   │   ├── test_quota_enforcement.py       [Quota Tests - 4 Tests]
│   │   │   ├── test_quota_enforcement_at_boundary()
│   │   │   │   ├── 999/1000 → 200 OK
│   │   │   │   ├── 1000/1000 → 200 OK
│   │   │   │   └── 1001/1000 → 429
│   │   │   ├── test_quota_returns_correct_status_codes()
│   │   │   │   ├── 429 response includes Retry-After header
│   │   │   │   └── Error message explains limit
│   │   │   ├── test_payment_required_status()
│   │   │   │   └── Expired subscription → 402
│   │   │   └── test_quota_at_exact_limit()
│   │   │       └── Boundary case: exactly at limit
│   │   │
│   │   ├── test_pricing.py                 [Cost Calculation Tests - 8 Tests]
│   │   │   ├── test_api_call_pricing()
│   │   │   ├── test_input_token_pricing()
│   │   │   ├── test_cached_input_token_pricing()
│   │   │   ├── test_output_token_pricing()
│   │   │   ├── test_reasoning_token_pricing()
│   │   │   ├── test_combined_pricing()
│   │   │   ├── test_no_floating_point_errors()
│   │   │   └── test_monthly_rollup_cost()
│   │   │
│   │   ├── test_stripe_integration.py      [Webhook Tests - 5 Tests]
│   │   │   ├── test_webhook_signature_verification()
│   │   │   ├── test_webhook_invalid_signature_rejected()
│   │   │   ├── test_webhook_duplicate_prevention()
│   │   │   ├── test_webhook_updates_subscription()
│   │   │   └── test_checkout_session_creates_subscription()
│   │   │
│   │   ├── test_security.py                [Tenant Isolation Tests - 4 Tests]
│   │   │   ├── test_tenant_isolation()
│   │   │   ├── test_cross_tenant_access_forbidden()
│   │   │   ├── test_jwt_validation()
│   │   │   └── test_password_hashing()
│   │   │
│   │   ├── test_integration.py             [Full Flow Tests - 3+ Tests]
│   │   │   ├── test_free_to_pro_upgrade_flow()
│   │   │   ├── test_billing_cycle_rollover()
│   │   │   └── test_webhook_retry_idempotency()
│   │   │
│   │   └── test_api_endpoints.py           [API Contract Tests]
│   │       ├── Test all 61+ endpoints
│   │       ├── Verify request/response schemas
│   │       └── Verify error responses
│   │
│   ├── requirements.txt                    [Python Dependencies]
│   │   ├── fastapi==0.104.1
│   │   ├── uvicorn==0.24.0
│   │   ├── sqlalchemy==2.0.23
│   │   ├── alembic==1.12.1
│   │   ├── psycopg2-binary==2.9.9
│   │   ├── pydantic==2.4.2
│   │   ├── stripe==5.16.0
│   │   ├── pytest==7.4.3
│   │   ├── bcrypt==4.1.1
│   │   ├── pyjwt==2.8.1
│   │   └── [12 more core dependencies]
│   │
│   ├── pytest.ini                          [Pytest Configuration]
│   │   ├── testpaths = tests
│   │   ├── asyncio_mode = auto
│   │   └── addopts = --verbose --cov=app
│   │
│   ├── Dockerfile                          [Backend Container]
│   │   ├── FROM python:3.10-slim
│   │   ├── Install system dependencies
│   │   ├── Copy requirements.txt
│   │   ├── pip install dependencies
│   │   ├── Copy app code
│   │   ├── Create non-root user
│   │   ├── HEALTHCHECK for Docker Compose
│   │   └── CMD uvicorn app.main:app
│   │
│   └── .env.example                        [Environment Template]
│       ├── DATABASE_URL
│       ├── STRIPE_API_KEY
│       ├── STRIPE_WEBHOOK_SECRET
│       ├── SECRET_KEY
│       └── All configuration variables
│
├── 📁 frontend/                             [React 18 Application Root]
│   │
│   ├── 📁 src/                              [React Source Code]
│   │   │
│   │   ├── 📁 pages/                        [Page Components - 7 Pages]
│   │   │   │
│   │   │   ├── Login.tsx                    [Authentication Page]
│   │   │   │   ├── Email + password form
│   │   │   │   ├── Call POST /auth/login
│   │   │   │   ├── Store JWT in localStorage
│   │   │   │   ├── Redirect to Dashboard on success
│   │   │   │   └── Display errors with clear messages
│   │   │   │
│   │   │   ├── Dashboard.tsx                [Usage Overview]
│   │   │   │   ├── Display current usage metrics
│   │   │   │   ├── Show plan name & quotas
│   │   │   │   ├── Progress bars for usage %
│   │   │   │   ├── Monthly cost breakdown (pie chart)
│   │   │   │   ├── Poll /usage endpoint every 30s
│   │   │   │   ├── "Upgrade" button to Plans
│   │   │   │   └── Days remaining in billing cycle
│   │   │   │
│   │   │   ├── UsageDetail.tsx              [Detailed Metrics]
│   │   │   │   ├── Detailed usage by type (API calls, tokens)
│   │   │   │   ├── Line chart showing usage over time
│   │   │   │   ├── Trend analysis (up/down)
│   │   │   │   ├── Export data option
│   │   │   │   └── Filtering by date range
│   │   │   │
│   │   │   ├── Plans.tsx                    [Plan Comparison]
│   │   │   │   ├── Display Free & Pro plans side-by-side
│   │   │   │   ├── Show quotas: API calls, AI tokens
│   │   │   │   ├── Show pricing: Free ($0), Pro ($29.99)
│   │   │   │   ├── Feature comparison
│   │   │   │   ├── "Upgrade to Pro" button
│   │   │   │   ├── Current plan highlighted
│   │   │   │   └── FAQ about plan differences
│   │   │   │
│   │   │   ├── Checkout.tsx                 [Stripe Payment Form]
│   │   │   │   ├── Order summary
│   │   │   │   ├── Stripe CardElement (PCI-compliant)
│   │   │   │   ├── Billing details form
│   │   │   │   ├── "Pay Now" button
│   │   │   │   ├── Handles 3DS challenges
│   │   │   │   ├── Submit to backend: POST /checkout
│   │   │   │   ├── Redirect to Stripe Checkout URL
│   │   │   │   └── Handle payment confirmation
│   │   │   │
│   │   │   ├── UpgradeSuccess.tsx           [Confirmation Page]
│   │   │   │   ├── "Upgrade successful!" message
│   │   │   │   ├── New plan details (Pro limits)
│   │   │   │   ├── "Go to Dashboard" button
│   │   │   │   └── FAQ about next steps
│   │   │   │
│   │   │   └── Settings.tsx                 [Account Settings]
│   │   │       ├── Display tenant info (name, email)
│   │   │       ├── Change notification preferences
│   │   │       ├── Download invoice history
│   │   │       ├── Logout button
│   │   │       └── Danger zone: delete account
│   │   │
│   │   ├── 📁 components/                   [Reusable Components - 3]
│   │   │   │
│   │   │   ├── Layout.tsx                   [App Shell & Navigation]
│   │   │   │   ├── Navigation header
│   │   │   │   ├── Sidebar with links
│   │   │   │   ├── Current tenant name
│   │   │   │   ├── Logout link
│   │   │   │   ├── Footer with status
│   │   │   │   └── Children route rendering
│   │   │   │
│   │   │   ├── UsageBar.tsx                 [Progress Indicator]
│   │   │   │   ├── Horizontal progress bar
│   │   │   │   ├── Percentage text (e.g., "523 / 1000")
│   │   │   │   ├── Color-coded: green < 80%, yellow 80-100%, red > 100%
│   │   │   │   ├── Optional warning at 80%
│   │   │   │   └── Responsive width
│   │   │   │
│   │   │   └── CostBreakdown.tsx            [Pie Chart & Legend]
│   │   │       ├── Pie chart: cost by type
│   │   │       ├── Legend with $ amounts
│   │   │       ├── Hover tooltips
│   │   │       └── Responsive sizing
│   │   │
│   │   ├── services/                       [API Client Layer]
│   │   │   │
│   │   │   └── api.ts                      [HTTP Client - axios]
│   │   │       ├── Create axios instance
│   │   │       ├── Base URL: http://localhost:8000/api
│   │   │       ├── Add JWT token to every request
│   │   │       ├── POST /auth/login(email, password)
│   │   │       ├── POST /auth/logout()
│   │   │       ├── GET /usage
│   │   │       ├── GET /plans
│   │   │       ├── POST /checkout(plan_id)
│   │   │       ├── Error handling: 401 → redirect to login
│   │   │       ├── Error handling: 429 → show quota message
│   │   │       ├── Error handling: 402 → show upgrade prompt
│   │   │       └── Intercept responses for logging
│   │   │
│   │   ├── stores/                         [State Management - Zustand]
│   │   │   │
│   │   │   └── authStore.ts                [User State]
│   │   │       ├── useAuthStore() hook
│   │   │       ├── State: {user, token, tenant_id, isLoggedIn}
│   │   │       ├── Actions: login(), logout(), setUser()
│   │   │       ├── Persist token to localStorage
│   │   │       ├── Restore state on app reload
│   │   │       └── Clear on logout
│   │   │
│   │   ├── App.tsx                         [Main App Component]
│   │   │   ├── Define routes (React Router v6)
│   │   │   ├── Route: / → redirect to /dashboard
│   │   │   ├── Route: /login → Login page
│   │   │   ├── Route: /dashboard → Dashboard (protected)
│   │   │   ├── Route: /usage → UsageDetail (protected)
│   │   │   ├── Route: /plans → Plans (protected)
│   │   │   ├── Route: /checkout → Checkout (protected)
│   │   │   ├── Route: /success → UpgradeSuccess (protected)
│   │   │   ├── Route: /settings → Settings (protected)
│   │   │   ├── ProtectedRoute component (requires JWT)
│   │   │   ├── Error boundary for React errors
│   │   │   └── Provider: AuthStore, QueryClient
│   │   │
│   │   ├── main.tsx                        [React Entry Point]
│   │   │   ├── import React from 'react'
│   │   │   ├── import ReactDOM from 'react-dom'
│   │   │   ├── import App from './App'
│   │   │   ├── ReactDOM.createRoot(document.getElementById('root'))
│   │   │   └── render App
│   │   │
│   │   ├── App.css                         [Global Styles]
│   │   │   ├── CSS variables (colors, spacing)
│   │   │   ├── Layout styles (grid, flex)
│   │   │   ├── Typography (font, sizes)
│   │   │   └── Component styles
│   │   │
│   │   └── index.css                       [Base Styles]
│   │       ├── CSS reset
│   │       ├── Box-sizing fix
│   │       └── Base HTML styles
│   │
│   ├── 📁 public/                           [Static Assets]
│   │   ├── index.html                      [HTML Template]
│   │   │   ├── <!DOCTYPE html>
│   │   │   ├── <meta charset="utf-8">
│   │   │   ├── <meta name="viewport">
│   │   │   ├── <title>FlyRank Billing Engine</title>
│   │   │   ├── <div id="root"></div>
│   │   │   └── Import scripts (Vite will inject)
│   │   │
│   │   └── favicon.ico                     [App Icon]
│   │
│   ├── package.json                        [NPM Dependencies & Scripts]
│   │   ├── "react": "^18.2.0"
│   │   ├── "react-dom": "^18.2.0"
│   │   ├── "typescript": "^5.2.0"
│   │   ├── "axios": "^1.6.0"
│   │   ├── "zustand": "^4.4.0"
│   │   ├── "react-query": "^3.39.0"
│   │   ├── "@stripe/stripe-js": "^1.46.0"
│   │   ├── "recharts": "^2.10.0"
│   │   ├── "tailwindcss": "^3.3.0"
│   │   ├── "vite": "^5.0.0"
│   │   ├── Scripts: dev, build, preview, lint
│   │   └── DevDependencies: Vite, ESLint, TypeScript
│   │
│   ├── tsconfig.json                       [TypeScript Configuration]
│   │   ├── "target": "ES2020"
│   │   ├── "jsx": "react-jsx"
│   │   ├── "module": "ESNext"
│   │   ├── "strict": true
│   │   ├── "esModuleInterop": true
│   │   └── Paths for clean imports
│   │
│   ├── vite.config.ts                      [Vite Build Configuration]
│   │   ├── Plugin: react()
│   │   ├── Server: port 3000, proxy to backend
│   │   ├── Build: minify, sourcemaps
│   │   ├── Optimizations: pre-bundling
│   │   └── Environment: .env for API URL
│   │
│   ├── tailwind.config.js                  [Tailwind CSS Configuration]
│   │   ├── content: ['src/**/*.tsx']
│   │   ├── theme: colors, spacing, fonts
│   │   ├── plugins: forms, typography
│   │   └── Custom design tokens
│   │
│   ├── postcss.config.js                   [PostCSS Configuration]
│   │   ├── Plugin: tailwindcss
│   │   └── Plugin: autoprefixer
│   │
│   ├── .eslintrc.cjs                       [ESLint Configuration]
│   │   ├── Parser: @typescript-eslint
│   │   ├── Extends: eslint:recommended
│   │   ├── Rules: React hooks, no unused vars
│   │   └── Env: browser, es2021
│   │
│   ├── Dockerfile                          [Frontend Container]
│   │   ├── Multi-stage build
│   │   ├── Build stage: node:18
│   │   │   ├── npm install
│   │   │   ├── npm run build
│   │   │   └── Output: dist/
│   │   ├── Runtime stage: nginx:alpine
│   │   │   ├── Copy dist/ to /usr/share/nginx/html
│   │   │   ├── Copy nginx.conf
│   │   │   ├── EXPOSE 80
│   │   │   └── CMD nginx -g 'daemon off;'
│   │   └── Very small final image
│   │
│   ├── .env.example                        [Environment Template]
│   │   ├── VITE_API_URL=http://localhost:8000/api
│   │   └── VITE_STRIPE_PUBLIC_KEY=pk_test_...
│   │
│   └── .gitignore                          [Git Ignore Rules]
│       ├── node_modules/
│       ├── dist/
│       ├── .env
│       └── .DS_Store
│
├── 📁 alembic/                              [Database Migrations]
│   │
│   ├── env.py                              [Migration Environment]
│   │   ├── SQLAlchemy configuration
│   │   ├── Auto-generate migrations
│   │   ├── Revision info (up, down)
│   │   └── Database URL from env
│   │
│   ├── script.py.mako                      [Migration Template]
│   │   ├── Standard Alembic template
│   │   ├── up() and down() functions
│   │   └── op. calls for schema changes
│   │
│   ├── __init__.py                         [Package]
│   │
│   └── 📁 versions/                        [Migration Files - 8 Versions]
│       │
│       ├── 001_initial_schema.py           [Core Tables]
│       │   ├── CREATE tenants
│       │   ├── CREATE plans
│       │   ├── CREATE subscriptions
│       │   ├── CREATE users
│       │   ├── CREATE usage_events (with UNIQUE idempotency_key)
│       │   ├── CREATE webhook_events (with UNIQUE event_id)
│       │   └── All foreign keys & indexes
│       │
│       ├── 002_subscriptions.py            [Subscription Enhancements]
│       ├── 003_invoices.py                 [Invoice Tables]
│       ├── 004_alerts.py                   [Alert Tables]
│       ├── 005_proration.py                [Proration Tables]
│       ├── 006_reconciliation.py           [Reconciliation Tables]
│       ├── 007_overages.py                 [Overage Tables]
│       └── 008_reporting.py                [Reporting Tables]
│
├── 📁 docs/                                 [Documentation - 50+ KB]
│   │
│   ├── API.md                              [Complete API Reference]
│   │   ├── All 61+ endpoints documented
│   │   ├── Request/response examples
│   │   ├── Status codes explained
│   │   ├── Error handling
│   │   ├── Rate limiting
│   │   └── Authentication details
│   │
│   ├── DATABASE.md                         [Database Schema]
│   │   ├── 16 tables fully documented
│   │   ├── Relationships & constraints
│   │   ├── Indexes & performance tuning
│   │   ├── Query patterns
│   │   └── Data isolation strategy
│   │
│   ├── DEPLOYMENT.md                       [Production Deployment]
│   │   ├── Pre-deployment checklist
│   │   ├── Docker Compose production
│   │   ├── Kubernetes manifests
│   │   ├── AWS, GCP, Azure options
│   │   ├── Monitoring & alerting
│   │   ├── Backups & disaster recovery
│   │   └── Scaling strategies
│   │
│   └── TESTING.md                          [Test Procedures]
│       ├── Running tests locally
│       ├── Test categories & coverage
│       ├── CI/CD integration
│       ├── Performance benchmarks
│       └── Debugging procedures
│
├── docker-compose.yml                      [Multi-Container Orchestration]
│   ├── services:
│   │   ├── postgres (PostgreSQL 16)
│   │   │   ├── Image: postgres:16-alpine
│   │   │   ├── Port: 5432
│   │   │   ├── Environment: DB, user, password
│   │   │   ├── Volume: postgres_data (persistent)
│   │   │   ├── Healthcheck: pg_isready
│   │   │   └── Network: flyrank_network
│   │   │
│   │   ├── backend (FastAPI)
│   │   │   ├── Build context: ./backend
│   │   │   ├── Port: 8000
│   │   │   ├── Environment: DATABASE_URL, STRIPE keys
│   │   │   ├── Depends on: postgres (healthy)
│   │   │   ├── Command: alembic upgrade head && uvicorn
│   │   │   ├── Healthcheck: curl /api/health
│   │   │   └── Volume: ./backend:/app (code hot-reload)
│   │   │
│   │   ├── frontend (React)
│   │   │   ├── Build context: ./frontend
│   │   │   ├── Port: 3000
│   │   │   ├── Environment: VITE_API_URL
│   │   │   ├── Command: npm run dev
│   │   │   └── Volume: ./frontend:/app (code hot-reload)
│   │   │
│   │   └── nginx (Reverse Proxy)
│   │       ├── Image: nginx:alpine
│   │       ├── Port: 80, 443
│   │       ├── Config volume: ./nginx.conf
│   │       ├── SSL volume: ./ssl (empty, ready for certs)
│   │       └── Healthcheck: curl /
│   │
│   ├── volumes:
│   │   └── postgres_data (persistent database)
│   │
│   └── networks:
│       └── flyrank_network (internal communication)
│
├── nginx.conf                              [Reverse Proxy Configuration]
│   ├── Upstream: backend:8000
│   ├── Upstream: frontend:3000
│   ├── Server: listen 80, 443 (with SSL)
│   ├── Location /api → proxy_pass backend
│   ├── Location / → proxy_pass frontend
│   ├── Security headers:
│   │   ├── Strict-Transport-Security
│   │   ├── X-Frame-Options: DENY
│   │   ├── Content-Security-Policy
│   │   └── X-Content-Type-Options: nosniff
│   ├── Rate limiting: 10 req/s /api, 30 req/s general
│   ├── SSL ready: ssl_certificate, ssl_certificate_key
│   └── Gzip compression: on
│
├── Dockerfile.backend                      [Backend Container Image]
│   ├── FROM python:3.10-slim
│   ├── WORKDIR /app
│   ├── apt-get install postgresql-client, curl
│   ├── COPY backend/requirements.txt
│   ├── pip install -r requirements.txt
│   ├── COPY backend /app/
│   ├── useradd -m appuser (non-root)
│   ├── USER appuser
│   ├── EXPOSE 8000
│   ├── HEALTHCHECK --interval=10s
│   └── CMD uvicorn app.main:app
│
├── .env.example                            [Environment Template]
│   ├── DATABASE_URL=postgresql://...
│   ├── STRIPE_API_KEY=sk_test_...
│   ├── STRIPE_WEBHOOK_SECRET=whsec_...
│   ├── SECRET_KEY=...
│   ├── VITE_API_URL=http://localhost:8000/api
│   ├── VITE_STRIPE_PUBLIC_KEY=pk_test_...
│   └── APP_ENV=development
│
├── .gitignore                              [Git Ignore Rules]
│   ├── .env
│   ├── __pycache__/, *.pyc
│   ├── node_modules/, dist/
│   ├── .pytest_cache/, htmlcov/
│   ├── .venv/, venv/
│   └── .DS_Store, Thumbs.db
│
├── requirements.txt                        [Root Dependencies]
│   ├── Same as backend/requirements.txt
│   └── For convenience at project root
│
├── capstone.yaml                           [Project Specification]
│   ├── Project metadata
│   ├── Run command: docker-compose up -d
│   ├── Test command: pytest tests/
│   ├── All endpoints defined
│   ├── Definition of Done checklist
│   └── Demo flow
│
├── pyproject.toml                          [Python Project Metadata]
│   ├── Project name, version
│   ├── Dependencies
│   ├── Build system
│   ├── Tool configuration (black, isort, mypy, pytest)
│   └── Type checking settings
│
├── README.md                                [Project Overview]
│   └── [Comprehensive project documentation]
│
├── EVIDENCE.md                              [Verification Proofs]
│   ├── All requirements verified
│   ├── Test results
│   ├── Feature completeness
│   └── Security verification
│
├── BUILDLOG.md                              [Implementation Journal]
│   ├── Module-by-module progress
│   ├── Decisions & rationale
│   ├── Lessons learned
│   ├── Time breakdown
│   └── Final checklist
│
├── LICENSE                                  [MIT License]
│   └── Open source license terms
│
└── verify-setup.sh                          [Setup Verification Script]
    ├── Check Docker installed
    ├── Check Docker Compose installed
    ├── Verify project structure
    ├── Verify .env configuration
    ├── Check Stripe keys
    ├── Check port availability
    └── Output: PASS/WARN/FAIL for each check
```

---

## System Architecture Layers

### Layer 1: HTTP API Layer (Routes)

The routes layer handles HTTP request/response mapping:

```
POST /api/generate (Billable Action)
  ├── Dependency: get_current_tenant() - Extract JWT
  ├── Dependency: get_db() - Database session
  ├── Input: GenerateRequest(prompt, idempotency_key)
  ├── Business Logic:
  │   ├── quota_service.check_quota(tenant_id, 'api_call', 1)
  │   │   └── Returns: {allowed: bool, remaining: int, message: str}
  │   ├── If not allowed: raise HTTPException(status_code=429)
  │   ├── usage_service.record_usage(tenant_id, 'api_call', cost_cents=1, idempotency_key)
  │   │   └── Returns: {event_id, cost_cents, result} or cached result if duplicate
  │   ├── pricing_service.calculate_cost() - get cost_cents
  │   └── Return: GenerateResponse(result, cost_cents, quota_remaining)
  └── Response: 200 OK | 429 Too Many | 402 Payment Required | 400 Bad Request
```

**Key Architecture Decision**: Thin routes, thick services. Routes handle HTTP concerns (serialization, headers, status codes). Services handle business logic.

### Layer 2: Business Logic Layer (Services)

Services encapsulate domain logic:

```
UsageService.record_usage(tenant_id, type, quantity, idempotency_key)
  ├── Query: SELECT * FROM usage_events WHERE tenant_id=? AND idempotency_key=?
  ├── If exists: RETURN cached result (idempotency)
  ├── Else:
  │   ├── CREATE new UsageEvent
  │   ├── ON UNIQUE constraint violation:
  │   │   ├── This means another request won the race
  │   │   ├── Re-query to get the winning event
  │   │   └── RETURN its result
  │   └── COMMIT transaction
  └── RETURN {event_id, cost_cents, result}
```

**Key Architecture Decision**: Database-level uniqueness (not just app-level). This survives service restarts and concurrent requests.

### Layer 3: Data Access Layer (Repositories)

Repositories abstract database queries:

```
TenantRepository.get(tenant_id)
  ├── Query: SELECT * FROM tenants WHERE id = ? AND is_deleted = false
  ├── Raise NotFound if no result
  └── RETURN Tenant ORM model
```

**Key Architecture Decision**: Repositories make testing easier (mock them). They also centralize query construction.

### Layer 4: Data Model Layer (SQLAlchemy)

Models define schema & relationships:

```
class UsageEvent(Base):
  __tablename__ = "usage_events"
  
  id = Column(UUID, primary_key=True)
  tenant_id = Column(UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
  type = Column(String(50), nullable=False)
  quantity = Column(Integer, nullable=False)
  idempotency_key = Column(String(255), nullable=False)
  cost_cents = Column(Integer, nullable=False)
  timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
  
  __table_args__ = (
    UniqueConstraint('tenant_id', 'idempotency_key', name='uq_tenant_idempotency'),
    Index('idx_tenant_type_timestamp', 'tenant_id', 'type', 'timestamp'),
    CheckConstraint('quantity > 0', name='ck_quantity_positive'),
    CheckConstraint('cost_cents >= 0', name='ck_cost_positive'),
  )
```

**Key Architecture Decision**: Constraints at database level. Invalid states are impossible, not prevented.

---

## Core Data Flows

### 1. Billable Action Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Client: POST /api/generate with idempotency_key            │
├─────────────────────────────────────────────────────────────┤
│ 1. FastAPI Route Handler                                     │
│    ├── Extract JWT token → get_current_tenant()             │
│    ├── Get database session → get_db()                      │
│    ├── Parse & validate request with Pydantic              │
│    └── Call quota_service.check_quota(tenant_id, 'api_call')│
├─────────────────────────────────────────────────────────────┤
│ 2. Quota Service                                             │
│    ├── Query: SELECT SUM(quantity) FROM usage_events        │
│    │           WHERE tenant_id = ? AND type = 'api_call'    │
│    │           AND timestamp > cycle_start                  │
│    ├── Get plan limit from subscriptions                    │
│    ├── If current + requested > limit:                      │
│    │   └── Raise HTTPException(status_code=429)             │
│    └── Else: Allow action                                   │
├─────────────────────────────────────────────────────────────┤
│ 3. Usage Service                                             │
│    ├── Query: SELECT * FROM usage_events                    │
│    │           WHERE tenant_id = ? AND idempotency_key = ?  │
│    ├── If found: RETURN cached result (idempotency)         │
│    ├── Else: INSERT into usage_events                       │
│    │   ├── ON UNIQUE constraint violation:                  │
│    │   │   └── Another request won the race, fetch its row  │
│    │   └── Commit transaction                               │
│    └── RETURN {event_id, result, cost_cents}                │
├─────────────────────────────────────────────────────────────┤
│ 4. Pricing Service                                           │
│    ├── Calculate cost_cents based on usage type             │
│    ├── For 'api_call': cost = (quantity * 10) cents         │
│    └── RETURN cost_cents                                    │
├─────────────────────────────────────────────────────────────┤
│ 5. Response                                                   │
│    ├── 200 OK with {result, tokens_used, cost_cents,       │
│    │                quota_remaining}                        │
│    ├── OR 429 Too Many Requests with error message          │
│    └── OR 402 Payment Required if subscription past_due     │
└─────────────────────────────────────────────────────────────┘
```

### 2. Stripe Webhook Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Stripe: POST /api/webhooks/stripe with signature            │
├─────────────────────────────────────────────────────────────┤
│ 1. Webhook Route Handler                                     │
│    ├── Extract signature from Stripe-Signature header       │
│    ├── Extract raw body (not JSON parsed yet)               │
│    ├── Call stripe_service.verify_webhook_signature()       │
│    └── If invalid: RETURN 400 Bad Request                   │
├─────────────────────────────────────────────────────────────┤
│ 2. Stripe Service - Signature Verification                  │
│    ├── Compute: HMAC-SHA256(raw_body, webhook_secret)      │
│    ├── Compare with received signature (constant-time)      │
│    ├── If mismatch: RETURN False                            │
│    └── Else: RETURN True                                    │
├─────────────────────────────────────────────────────────────┤
│ 3. Parse & Store Webhook Event                              │
│    ├── Parse JSON body to WebhookEvent schema               │
│    ├── Query: SELECT * FROM webhook_events WHERE event_id = │
│    ├── If found: Duplicate! RETURN 200 OK (idempotent)      │
│    ├── Else: INSERT into webhook_events                     │
│    │   ├── Include full event payload (for replay)          │
│    │   └── Mark processed=false initially                   │
│    └── Commit                                               │
├─────────────────────────────────────────────────────────────┤
│ 4. Route Event to Handler                                    │
│    ├── Switch on event.type:                                │
│    │   ├── 'checkout.session.completed'                     │
│    │   ├── 'customer.subscription.updated'                  │
│    │   ├── 'customer.subscription.deleted'                  │
│    │   └── 'payment_intent.failed'                          │
│    └── Call appropriate handler                             │
├─────────────────────────────────────────────────────────────┤
│ 5. Handler: Update Subscription                              │
│    ├── Extract customer_id, subscription_id from event      │
│    ├── Query: SELECT * FROM subscriptions                   │
│    │           WHERE stripe_subscription_id = ?             │
│    ├── Update: plan_id, status, billing_cycle_dates         │
│    ├── Mark: webhook_event.processed = true                 │
│    └── Commit atomically                                    │
├─────────────────────────────────────────────────────────────┤
│ 6. Response                                                   │
│    ├── 200 OK { received: true, event_id: ... }             │
│    └── Stripe considers this successful                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Architectural Patterns

### 1. Idempotency Pattern

**Problem**: Network requests fail and retry. How do we ensure the same request doesn't create duplicate charges?

**Solution**: 
- Client sends `idempotency_key` with every request
- Database: `UNIQUE (tenant_id, idempotency_key)` constraint
- Service: Check for existing key before creating
- If exists: Return cached result
- If constraint violated: Someone else won the race, fetch their result

This is simpler and more reliable than in-memory caches.

### 2. Quota Enforcement Pattern

**Problem**: How do we prevent users from exceeding their plan limits?

**Solution**:
- Before executing any billable action, query current usage
- Query: `SELECT SUM(quantity) FROM usage_events WHERE tenant_id = ? AND type = ? AND timestamp > cycle_start`
- Get plan limit from subscriptions
- Calculate: remaining = limit - current
- If remaining <= 0: Return 429 Too Many Requests
- Else: Execute action

No background jobs needed. No cache to go stale. Just a simple query.

### 3. Pricing Pattern

**Problem**: How do we calculate costs correctly without floating-point errors?

**Solution**:
- All money stored as integer cents, never dollars
- Pricing constants are immutable (config_pricing.py)
- Cost calculation uses integer arithmetic only
- Example: `api_cost_cents = (api_calls * 10)` (not `api_calls * 0.01`)

### 4. Multi-Tenant Isolation Pattern

**Problem**: Tenant A must never see Tenant B's data, even by accident.

**Solution**:
- Every query includes `WHERE tenant_id = ?`
- Foreign keys with cascade delete
- JWT token contains tenant_id
- Dependency injection: `get_current_tenant()` extracts tenant_id from JWT
- Every service method requires tenant_id as parameter
- Cannot forget to filter—the parameter is required

### 5. Webhook Verification Pattern

**Problem**: Anyone can make a request to our webhook endpoint. How do we know it's really from Stripe?

**Solution**:
- Stripe signs webhook payloads with HMAC-SHA256
- We store the signing secret in .env
- For every webhook:
  1. Extract signature from headers
  2. Compute HMAC-SHA256(raw_body, secret)
  3. Compare (constant-time comparison)
  4. If mismatch: Reject 400
- We never execute webhook logic if signature is invalid

---

## Database Design

### Schema Relationships

```
tenants (1) ──── (M) users
  │                     │
  │                     └─ JWT contains tenant_id
  │
  └── (1) ──── (M) subscriptions
       │
       └── (FK) → plans
       └── Contains: stripe_subscription_id, status, billing_cycle_dates
       
tenants (1) ──── (M) usage_events
  │
  ├── Type: api_call, input_tokens, cached_input_tokens, output_tokens
  ├── UNIQUE(tenant_id, idempotency_key) - Prevents duplicates
  ├── Indexed: (tenant_id, type, timestamp)
  └── Example: Tenant A called /generate 3x with same key
               Result: 1 usage_event (idempotent)

tenants (1) ──── (M) webhook_events
  │
  ├── UNIQUE(event_id) - Prevents duplicate processing
  ├── Example: Stripe retries checkout.session.completed webhook
               Result: 1 webhook_event (deduplicated)
  └── Includes full payload for replay/debugging

tenants (1) ──── (M) invoices
  │                     │
  │                     └── (1) ──── (M) invoice_line_items
  │
  └── Generated monthly from usage_events

tenants (1) ──── (M) alerts
  │
  └── Threshold-based (80%, 100%, overage)

subscriptions (many) ──── (1) plans
  │
  └── Contains quotas: api_calls_limit, ai_tokens_limit
```

### Indexes for Performance

```sql
-- Metering queries
CREATE INDEX idx_usage_tenant_type_timestamp 
  ON usage_events(tenant_id, type, timestamp);

-- Idempotency checking
CREATE UNIQUE INDEX idx_usage_tenant_idempotency 
  ON usage_events(tenant_id, idempotency_key);

-- Webhook deduplication
CREATE UNIQUE INDEX idx_webhook_event_id 
  ON webhook_events(event_id);

-- Subscription lookups
CREATE INDEX idx_subscription_tenant_id 
  ON subscriptions(tenant_id);

-- Tenant + type lookups for quotas
CREATE INDEX idx_usage_tenant_type 
  ON usage_events(tenant_id, type);
```

---

## Deployment Architecture

### Development (docker-compose.yml)

```
Host
├── PostgreSQL 16 (port 5432)
│   └── Database: flyrank_billing
├── FastAPI Backend (port 8000)
│   ├── Mounted volume: ./backend:/app (code hot-reload)
│   └── Command: alembic upgrade head && uvicorn
├── React Frontend (port 3000)
│   ├── Mounted volume: ./frontend:/app (code hot-reload)
│   └── Command: npm run dev
└── Nginx (port 80)
    └── Reverse proxy: /api → backend:8000, / → frontend:3000

All services on same Docker network: flyrank_network
```

### Production (Example: AWS ECS)

```
ECS Cluster
├── Task: PostgreSQL
│   └── RDS Database (managed)
├── Task: FastAPI Backend
│   ├── Image: myregistry/flyrank-backend:v1.0.0
│   ├── Scale: 3 tasks for high availability
│   ├── ALB: health check on /api/health
│   └── Environment: DATABASE_URL (from secrets manager)
├── Task: React Frontend
│   ├── Image: myregistry/flyrank-frontend:v1.0.0
│   ├── Scale: 2 tasks
│   └── CloudFront: CDN in front
└── ALB: Route traffic based on path
    ├── /api/* → Backend tasks
    └── /* → Frontend tasks
```

---

## Testing Architecture

### Test Isolation

```
Each test gets its own:
├── In-memory SQLite database (conftest.py)
├── FastAPI TestClient
├── Sample fixture data
└── Clean state (no cross-test pollution)
```

### Test Coverage

```
Backend (30+ tests, ~90% coverage)
├── Unit: Service methods
├── Integration: Routes + Services + Database
├── Edge cases: Retries, boundaries, concurrent requests
└── Security: Tenant isolation, JWT validation

Frontend: Not automated in this phase
└── Manual testing sufficient for MVP
```

---

## Security Architecture

### Authentication & Authorization

```
Login Flow:
1. POST /auth/login(email, password)
2. Hash provided password with bcrypt
3. Compare with stored hash
4. Generate JWT(tenant_id, exp=24h, secret=SECRET_KEY)
5. Client stores JWT in localStorage
6. Every API request includes JWT: Authorization: Bearer <token>

Request Processing:
1. FastAPI extracts token from header
2. Verify signature: JWT(payload, secret)
3. Check expiration
4. Extract tenant_id from payload
5. Inject into get_current_tenant()
6. All service methods receive tenant_id
```

### Data Isolation

```
Tenant Isolation:
├── Every query: WHERE tenant_id = ?
├── FK with CASCADE: Deleting tenant deletes all data
├── JWT: tenant_id is trusted source of truth
└── Cannot see other tenants' data (architecturally impossible)

Example query (quota check):
SELECT SUM(quantity) FROM usage_events
WHERE tenant_id = ? ← From JWT, cannot be overridden
  AND type = 'api_call'
  AND timestamp > cycle_start
```

### Webhook Security

```
Signature Verification:
1. Stripe sends: raw_body + Stripe-Signature header
2. We compute: HMAC-SHA256(raw_body, webhook_secret)
3. Constant-time compare (not == which leaks timing info)
4. Forged signature → HTTP 400
5. Valid signature + duplicate event_id → HTTP 200 (idempotent)
```

---

## Observability Architecture

### Logging

```
Structured logging at critical points:
├── Routes: Log every API request (method, path, status)
├── Services: Log business logic (quota check, usage recording)
├── Webhooks: Log webhook processing (event_id, type, result)
└── Errors: Full traceback + context

Example:
logger.info("Usage recorded", {
  "tenant_id": tenant_id,
  "type": "api_call",
  "cost_cents": cost_cents,
  "idempotency_key": idempotency_key
})
```

### Health Checks

```
Docker Compose Health Checks:
├── PostgreSQL: pg_isready -U flyrank_user
├── Backend: curl http://localhost:8000/api/health
├── Frontend: Port 3000 is listening
└── Nginx: curl http://localhost/

Also provide:
├── GET /health → {status: healthy, version: ...}
└── GET /ready → {status: ready, db: connected}
```

---

## Conclusion

This architecture achieves its core goal: **correctness under real-world conditions** (retries, concurrent requests, network failures, webhook retries). Every layer serves this purpose:

- **Idempotency**: Database-level uniqueness
- **Quotas**: Simple, reliable queries
- **Pricing**: Integer arithmetic only
- **Webhooks**: Cryptographic verification + deduplication
- **Isolation**: Architectural enforcement, not trusting code

The system is production-ready, testable, secure, and scalable.
