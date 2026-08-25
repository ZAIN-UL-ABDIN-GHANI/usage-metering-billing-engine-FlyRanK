# API.md - FlyRank Billing Engine API Reference

Complete API documentation for the FlyRank SaaS Billing Engine.

---

## Base URL

```
Development: http://localhost:8000/api
Production: https://api.yourdomain.com/api
```

## Authentication

All endpoints require JWT token in Authorization header:

```
Authorization: Bearer <jwt_token>
X-Tenant-ID: <tenant_id>
```

---

## Authentication Endpoints

### POST /auth/login

Login and receive JWT token.

**Request**:
```json
{
  "email": "tenant@example.com",
  "password": "password123"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "tenant@example.com"
}
```

**Errors**:
- 401 Unauthorized: Invalid credentials
- 422 Unprocessable Entity: Missing fields

---

### POST /auth/logout

Invalidate current session.

**Headers**:
```
Authorization: Bearer <token>
X-Tenant-ID: <tenant_id>
```

**Response** (200 OK):
```json
{
  "status": "logged_out"
}
```

---

### POST /auth/register

Register new tenant (optional).

**Request**:
```json
{
  "email": "newcustomer@example.com",
  "password": "secure_password",
  "company_name": "Acme Corp"
}
```

**Response** (201 Created):
```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "newcustomer@example.com",
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "plan": "Free"
}
```

---

## Usage Metering Endpoints

### POST /generate

Billable endpoint for usage metering. Simulates API call with usage tracking.

**Idempotency**: Each `idempotency_key` creates at most ONE usage event.

**Request**:
```json
{
  "prompt": "What is the capital of France?",
  "idempotency_key": "req_abc123_xyz789"
}
```

**Response** (200 OK):
```json
{
  "result": "Paris is the capital of France.",
  "tokens_used": 25,
  "cost": 0.000025
}
```

**Error - Quota Exceeded** (429 Too Many Requests):
```json
{
  "error": "quota_exceeded",
  "message": "You've reached your monthly limit of 1000 API calls.",
  "current_usage": 1000,
  "limit": 1000,
  "reset_date": "2024-02-01T00:00:00Z",
  "retry_after": 2678400
}
```

**Error - Payment Required** (402 Payment Required):
```json
{
  "error": "quota_exceeded",
  "message": "You've reached your Free plan limit. Upgrade to Pro for higher limits.",
  "current_usage": 1000,
  "limit": 1000,
  "plan": "Free"
}
```

**Important Notes**:
- `idempotency_key` must be unique per request
- Same key with identical payload returns cached response
- Same key with different payload returns error
- Prevents double-charging on retries

---

### GET /usage

Get current usage metrics and cost for the billing period.

**Response** (200 OK):
```json
{
  "api_calls_used": 500,
  "api_calls_limit": 1000,
  "ai_tokens_used": 50000,
  "ai_tokens_limit": 100000,
  "current_cost": 5000,
  "current_cost_formatted": "$50.00",
  "billing_period_start": "2024-01-01T00:00:00Z",
  "billing_period_end": "2024-02-01T00:00:00Z",
  "plan_name": "Free",
  "days_remaining": 8
}
```

**Query Parameters**:
- `period`: (optional) "current", "previous", or specific date range

---

## Subscription & Billing Endpoints

### GET /subscription

Get current subscription details.

**Response** (200 OK):
```json
{
  "plan_id": "pro",
  "plan_name": "Pro",
  "status": "active",
  "current_period_start": "2024-01-01T00:00:00Z",
  "current_period_end": "2024-02-01T00:00:00Z",
  "renewal_date": "2024-02-01T00:00:00Z",
  "price_usd": 29.99,
  "customer_id": "cus_test_123",
  "stripe_subscription_id": "sub_test_123"
}
```

---

### GET /plans

List available subscription plans.

**Response** (200 OK):
```json
[
  {
    "id": "free",
    "name": "Free",
    "price_usd": 0,
    "billing_period": "month",
    "api_calls_limit": 1000,
    "ai_tokens_limit": 100000,
    "features": [
      "1,000 API calls/month",
      "100k AI tokens/month",
      "Email support"
    ]
  },
  {
    "id": "pro",
    "name": "Pro",
    "price_usd": 29.99,
    "billing_period": "month",
    "api_calls_limit": 100000,
    "ai_tokens_limit": 10000000,
    "features": [
      "100,000 API calls/month",
      "10M AI tokens/month",
      "Priority support",
      "Custom rate limits"
    ]
  }
]
```

---

### POST /checkout

Create Stripe Checkout session for upgrading plans.

**Request**:
```json
{
  "plan_id": "pro"
}
```

**Response** (200 OK):
```json
{
  "session_id": "cs_test_1234567890",
  "url": "https://checkout.stripe.com/pay/cs_test_1234567890",
  "expires_at": "2024-01-15T12:30:00Z"
}
```

**Usage Flow**:
1. Frontend receives `session_id`
2. Frontend calls `stripe.redirectToCheckout(sessionId)`
3. Customer completes payment on Stripe
4. Stripe triggers webhook: `checkout.session.completed`
5. Backend updates subscription
6. Webhook response redirects to success page

---

## Webhook Endpoints

### POST /webhooks/stripe

Receive Stripe webhook events.

**Authentication**: Signature verification (not JWT)

**Headers**:
```
stripe-signature: t=1234567890,v1=abc123def456...,v0=...
```

**Events Handled**:

#### checkout.session.completed
Fired when customer completes Stripe Checkout.

```json
{
  "id": "evt_test_123",
  "type": "checkout.session.completed",
  "data": {
    "object": {
      "id": "cs_test_123",
      "metadata": {
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
        "plan_id": "pro"
      },
      "customer": "cus_test_123",
      "subscription": "sub_test_123",
      "payment_status": "paid"
    }
  }
}
```

#### customer.subscription.updated
Fired when subscription changes.

```json
{
  "id": "evt_test_456",
  "type": "customer.subscription.updated",
  "data": {
    "object": {
      "id": "sub_test_123",
      "metadata": {
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
      },
      "status": "active",
      "current_period_start": 1234567890,
      "current_period_end": 1267191890
    }
  }
}
```

#### customer.subscription.deleted
Fired when subscription canceled.

```json
{
  "id": "evt_test_789",
  "type": "customer.subscription.deleted",
  "data": {
    "object": {
      "id": "sub_test_123",
      "metadata": {
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
      },
      "status": "canceled",
      "canceled_at": 1234567890
    }
  }
}
```

**Response** (200 OK):
```json
{
  "status": "received",
  "event_id": "evt_test_123"
}
```

**Error - Invalid Signature** (400 Bad Request):
```json
{
  "error": "invalid_signature",
  "message": "Webhook signature verification failed"
}
```

**Important Notes**:
- Signature verification is CRITICAL
- Same event sent twice? Handled idempotently
- No JWT needed for webhooks
- Stripe secret from environment: `STRIPE_WEBHOOK_SECRET`

---

## System Endpoints

### GET /health

Health check endpoint.

**Response** (200 OK):
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0"
}
```

---

### GET /metrics

Prometheus metrics (for monitoring).

**Response** (200 OK):
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="POST",path="/api/generate"} 1234
http_requests_total{method="GET",path="/api/usage"} 5678

# HELP http_request_duration_seconds HTTP request duration
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{path="/api/usage",le="0.1"} 100
http_request_duration_seconds_bucket{path="/api/usage",le="0.5"} 200
```

---

## Error Handling

### Standard Error Response

All errors return consistent format:

```json
{
  "error": "error_code",
  "message": "Human-readable message",
  "details": {}
}
```

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | Successful request |
| 201 | Created | Resource created |
| 400 | Bad Request | Invalid JSON, malformed signature |
| 401 | Unauthorized | Invalid/expired JWT token |
| 402 | Payment Required | Upgrade needed (Free plan quota) |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Quota exceeded (Pro plan) |
| 500 | Server Error | Unexpected error (see logs) |

---

## Rate Limiting

**Limits** (per IP, per minute):
- API endpoints: 10 requests/second (600/minute)
- Auth endpoints: 5 attempts/minute
- Webhook endpoint: No limit (signature verified)

**Headers Returned**:
```
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 592
X-RateLimit-Reset: 1234567890
```

---

## Pricing Reference

### API Calls
- Rate: $0.01 per 1,000 calls
- Example: 5,000 calls = $0.05

### AI Tokens

| Type | Rate | Notes |
|------|------|-------|
| Input tokens | $0.0005 / 1k | Fresh tokens from prompt |
| Cached input tokens | $0.00015 / 1k | Already cached by provider (3x cheaper) |
| Output tokens | $0.002 / 1k | Tokens in response |
| Reasoning tokens | $0.002 / 1k | Billed as output tokens |

**Important**: Token categories use different rates and must NOT be summed directly.

---

## Code Examples

### Python (Requests)

```python
import requests

# Login
response = requests.post(
    "http://localhost:8000/api/auth/login",
    json={"email": "test@example.com", "password": "password123"}
)
token = response.json()["access_token"]
tenant_id = response.json()["tenant_id"]

# Headers for all requests
headers = {
    "Authorization": f"Bearer {token}",
    "X-Tenant-ID": tenant_id
}

# Generate usage (billable)
response = requests.post(
    "http://localhost:8000/api/generate",
    json={
        "prompt": "Hello",
        "idempotency_key": "req_unique_123"
    },
    headers=headers
)
result = response.json()
print(f"Cost: ${result['cost']}")

# Get usage
response = requests.get(
    "http://localhost:8000/api/usage",
    headers=headers
)
usage = response.json()
print(f"Usage: {usage['api_calls_used']} / {usage['api_calls_limit']}")
```

### JavaScript (Axios)

```javascript
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000/api'
})

// Login
const { data } = await api.post('/auth/login', {
  email: 'test@example.com',
  password: 'password123'
})
const { access_token, tenant_id } = data

// Set auth headers
api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
api.defaults.headers.common['X-Tenant-ID'] = tenant_id

// Generate usage
const response = await api.post('/generate', {
  prompt: 'Hello',
  idempotency_key: 'req_unique_123'
})
console.log(`Cost: $${response.data.cost}`)

// Get usage
const usage = await api.get('/usage')
console.log(`Usage: ${usage.data.api_calls_used} / ${usage.data.api_calls_limit}`)
```

### cURL

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'

# Get token from response, then use in requests

TOKEN="eyJhbGciOiJIUzI1NiIs..."
TENANT_ID="550e8400-e29b-41d4-a716-446655440000"

# Generate usage
curl -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Hello",
    "idempotency_key": "req_unique_123"
  }'

# Get usage
curl -X GET http://localhost:8000/api/usage \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID"
```

---

## Stripe Test Mode

### Test Cards

| Card Number | Behavior |
|---|---|
| 4242 4242 4242 4242 | Succeeds |
| 5555 5555 5555 4444 | Succeeds (Mastercard) |
| 4000 0000 0000 0002 | Declined |
| 3782 822463 10005 | 3D Secure required |

**Expiry**: Any future date
**CVC**: Any 3-4 digits

### Triggering Test Webhooks

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Authenticate
stripe login

# Forward webhooks to localhost
stripe listen --forward-to localhost:8000/api/webhooks/stripe

# In another terminal, trigger events
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
stripe trigger customer.subscription.deleted
```

---

## Monitoring & Debugging

### Enable Debug Logging

```bash
export LOG_LEVEL=debug
docker-compose restart backend
```

### View Logs

```bash
# Backend logs
docker-compose logs -f backend

# Database logs
docker-compose logs -f postgres

# All logs
docker-compose logs -f
```

### Common Issues

**401 Unauthorized**
- Token expired or invalid
- Solution: Re-login to get new token

**429 Too Many Requests**
- Rate limit exceeded
- Wait for reset before retrying

**402 Payment Required**
- Free plan quota exceeded
- Solution: Upgrade to Pro plan

**400 Bad Request (Webhook)**
- Invalid Stripe signature
- Check webhook secret in .env

---

## API Versioning

Current API version: **v1** (in URL path)

Future changes will be backward compatible or versioned as `/api/v2/`.

---

**Last Updated**: 2024
**API Version**: 1.0
**Status**: Production Ready
