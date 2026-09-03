# API Reference - FlyRank Billing Engine

Complete API documentation for the FlyRank metering and billing engine.

---

## Base URL

```
Development: http://localhost:8000/api
Production: https://api.flyrank.example.com/api
```

---

## Authentication

All endpoints (except `/health`) require JWT token in `Authorization` header:

```bash
curl -H "Authorization: Bearer <your-jwt-token>" http://localhost:8000/api/usage
```

### Login

**Endpoint**: `POST /auth/login`

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
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "tenant_id": "tenant-123",
  "expires_in": 86400
}
```

---

## Usage Metering

### Record Billable Usage

**Endpoint**: `POST /generate`

**Description**: Record usage for a billable action (idempotent).

**Request**:
```json
{
  "prompt": "Explain quantum computing",
  "idempotency_key": "req-123-unique"
}
```

**Response** (200 OK):
```json
{
  "result": "Quantum computing is...",
  "tokens_used": {
    "input": 5000,
    "output": 8000,
    "cached_input": 1000
  },
  "cost_cents": 125,
  "quota_remaining": {
    "api_calls": 999,
    "ai_tokens": 92000
  }
}
```

**Errors**:
- `429 Too Many Requests` - Quota exceeded
- `402 Payment Required` - Subscription expired
- `400 Bad Request` - Invalid input

**Notes**:
- `idempotency_key` ensures exactly-once processing
- Same key returns cached response (no duplicate charge)
- Required headers: `Authorization`, `X-Tenant-ID`

---

### Get Current Usage

**Endpoint**: `GET /usage`

**Description**: Get current billing period usage and cost.

**Response** (200 OK):
```json
{
  "api_calls_used": 234,
  "api_calls_limit": 1000,
  "ai_tokens_used": 52500,
  "ai_tokens_limit": 100000,
  "current_cost_cents": 50000,
  "plan_name": "Free",
  "plan_id": "free",
  "billing_period_start": "2024-09-01T00:00:00Z",
  "billing_period_end": "2024-10-01T00:00:00Z",
  "days_remaining": 28
}
```

---

### Get Usage History

**Endpoint**: `GET /usage/history`

**Query Parameters**:
- `limit` (optional, default 20): Number of events to return
- `offset` (optional, default 0): Pagination offset

**Response** (200 OK):
```json
{
  "events": [
    {
      "type": "api_call",
      "quantity": 1,
      "cost_cents": 1,
      "timestamp": "2024-09-15T10:30:00Z",
      "idempotency_key": "req-123"
    }
  ],
  "total": 234,
  "limit": 20,
  "offset": 0
}
```

---

## Subscriptions & Billing

### Get Current Subscription

**Endpoint**: `GET /subscription`

**Response** (200 OK):
```json
{
  "subscription_id": "sub-123",
  "plan_id": "free",
  "plan_name": "Free",
  "status": "active",
  "stripe_subscription_id": "sub_abc123",
  "stripe_customer_id": "cus_abc123",
  "billing_cycle_start": "2024-09-01T00:00:00Z",
  "billing_cycle_end": "2024-10-01T00:00:00Z"
}
```

---

### List Available Plans

**Endpoint**: `GET /plans`

**Response** (200 OK):
```json
{
  "plans": [
    {
      "id": "free",
      "name": "Free",
      "description": "Starter plan",
      "api_calls_limit": 1000,
      "ai_tokens_limit": 100000,
      "price_cents": 0,
      "price_display": "$0/month"
    },
    {
      "id": "pro",
      "name": "Professional",
      "description": "Professional plan",
      "api_calls_limit": 100000,
      "ai_tokens_limit": 10000000,
      "price_cents": 2999,
      "price_display": "$29.99/month"
    }
  ]
}
```

---

### Create Checkout Session

**Endpoint**: `POST /checkout`

**Description**: Create Stripe Checkout session for plan upgrade.

**Request**:
```json
{
  "plan_id": "pro",
  "success_url": "https://example.com/success",
  "cancel_url": "https://example.com/cancel"
}
```

**Response** (200 OK):
```json
{
  "session_id": "cs_test_12345...",
  "checkout_url": "https://checkout.stripe.com/pay/cs_test_12345...",
  "expires_at": "2024-09-16T12:00:00Z"
}
```

---

## Webhooks

### Stripe Webhook Receiver

**Endpoint**: `POST /webhooks/stripe`

**Headers Required**:
- `stripe-signature`: HMAC-SHA256 signature from Stripe

**Events Handled**:
- `checkout.session.completed` - Checkout finished, create subscription
- `customer.subscription.updated` - Plan changed, update subscription
- `customer.subscription.deleted` - Subscription canceled
- `payment_intent.succeeded` - Payment succeeded
- `payment_intent.failed` - Payment failed

**Example Webhook Payload**:
```json
{
  "id": "evt_1234567890",
  "type": "checkout.session.completed",
  "data": {
    "object": {
      "id": "cs_test_123",
      "customer": "cus_abc123",
      "subscription": "sub_abc123"
    }
  }
}
```

**Response** (200 OK):
```json
{
  "received": true,
  "event_id": "evt_1234567890"
}
```

**Errors**:
- `400 Bad Request` - Invalid signature
- `409 Conflict` - Duplicate event (already processed)

---

## Health & System

### Health Check

**Endpoint**: `GET /health`

**Response** (200 OK):
```json
{
  "status": "healthy",
  "app": "FlyRank Billing Engine",
  "environment": "production"
}
```

---

### Readiness Check

**Endpoint**: `GET /ready`

**Response** (200 OK):
```json
{
  "status": "ready",
  "app": "FlyRank Billing Engine"
}
```

---

### OpenAPI/Swagger Documentation

**Endpoint**: `GET /docs`

Interactive Swagger UI for exploring the API.

**Endpoint**: `GET /openapi.json`

OpenAPI schema in JSON format.

---

## Error Responses

All errors follow this format:

```json
{
  "status": 400,
  "detail": "Error message explaining what went wrong",
  "error_code": "ERROR_CODE"
}
```

### Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Created |
| `204` | No Content |
| `400` | Bad Request (validation error) |
| `401` | Unauthorized (missing/invalid token) |
| `402` | Payment Required (subscription expired) |
| `403` | Forbidden (not authorized for this resource) |
| `404` | Not Found |
| `409` | Conflict (duplicate event/key) |
| `422` | Unprocessable Entity (validation error) |
| `429` | Too Many Requests (quota exceeded) |
| `500` | Internal Server Error |
| `503` | Service Unavailable |

---

## Rate Limiting

API rate limits apply per-tenant:

- **API Endpoints**: 10 requests/second (burst up to 20)
- **General Routes**: 30 requests/second (burst up to 50)

Rate limit info in response headers:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 1694800800
```

---

## Pagination

List endpoints support pagination:

```
GET /usage/history?limit=20&offset=0
```

**Response**:
```json
{
  "items": [...],
  "total": 234,
  "limit": 20,
  "offset": 0,
  "has_next": true
}
```

---

## Sorting

List endpoints support sorting:

```
GET /usage/history?sort=-timestamp
```

**Parameters**:
- Prefix with `-` for descending order
- Default: ascending

---

## Filtering

Usage history can be filtered:

```
GET /usage/history?type=api_call&date_from=2024-09-01&date_to=2024-09-30
```

---

## Best Practices

1. **Always include `idempotency_key`** on POST requests to handle retries safely
2. **Cache API responses** for frequently accessed data (usage, plans)
3. **Handle 429 responses** with exponential backoff
4. **Verify webhook signatures** using `stripe-signature` header
5. **Use pagination** for large result sets
6. **Monitor rate limit** headers to avoid being throttled

---

## SDK Availability

- **Python**: `pip install flyrank-client`
- **Node.js**: `npm install @flyrank/client`
- **Go**: `go get github.com/flyrank/client-go`

---

## Support

- **API Status**: https://status.flyrank.io
- **Docs**: https://docs.flyrank.io
- **Issues**: https://github.com/flyrank/issues
