"""Tests for quota enforcement."""

import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models import Tenant, Plan, Subscription, UsageEvent


@pytest.mark.asyncio
async def test_quota_enforcement_at_boundary(db: Session, client: TestClient):
    """Test that quota is enforced exactly at the boundary."""
    # Setup: Create tenant with free plan (1000 API calls)
    tenant = Tenant(id="tenant-quota-1", name="Test", email="quota@example.com")
    plan = Plan(id="free", name="Free", api_calls_limit=1000, ai_tokens_limit=100000)
    subscription = Subscription(
        tenant_id="tenant-quota-1", plan_id="free", status="active"
    )
    
    db.add_all([tenant, plan, subscription])
    db.commit()

    # Create 998 usage events so the next two requests reach the limit.
    for i in range(998):
        event = UsageEvent(
            tenant_id="tenant-quota-1",
            type="api_call",
            quantity=1,
            cost_cents=1,
            idempotency_key=f"req-{i}",
        )
        db.add(event)
    db.commit()

    # Request at exactly 999 should be allowed
    response_at_limit = client.post(
        "/api/generate",
        json={"prompt": "at limit", "idempotency_key": "req-999"},
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-quota-1"},
    )
    assert response_at_limit.status_code == 200, "Request at 999/1000 should be allowed"

    # Request at exactly 1000 should be allowed
    response_at_1000 = client.post(
        "/api/generate",
        json={"prompt": "at 1000", "idempotency_key": "req-1000"},
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-quota-1"},
    )
    assert response_at_1000.status_code == 200, "Request at exactly 1000/1000 should be allowed"

    # Request over limit (1001) should be rejected
    response_over_limit = client.post(
        "/api/generate",
        json={"prompt": "over limit", "idempotency_key": "req-1001"},
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-quota-1"},
    )
    assert (
        response_over_limit.status_code == 429
    ), "Request over 1000/1000 should get 429 Too Many Requests"
    
    error_data = response_over_limit.json()
    assert "limit" in error_data.get("detail", "").lower(), "Error should mention limit"


@pytest.mark.asyncio
async def test_quota_returns_correct_status_codes(db: Session, client: TestClient):
    """Test that quota rejection returns 429 with clear message."""
    tenant = Tenant(id="tenant-quota-2", name="Test", email="quota2@example.com")
    plan = Plan(id="free", name="Free", api_calls_limit=10, ai_tokens_limit=1000)
    subscription = Subscription(
        tenant_id="tenant-quota-2", plan_id="free", status="active"
    )
    
    db.add_all([tenant, plan, subscription])
    db.commit()

    # Max out quota
    for i in range(10):
        event = UsageEvent(
            tenant_id="tenant-quota-2",
            type="api_call",
            quantity=1,
            cost_cents=1,
            idempotency_key=f"req-{i}",
        )
        db.add(event)
    db.commit()

    # Next request should be rejected with 429
    response = client.post(
        "/api/generate",
        json={"prompt": "over", "idempotency_key": "req-over"},
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-quota-2"},
    )
    
    assert response.status_code == 429, "Should return 429 Too Many Requests"
    assert "Retry-After" in response.headers, "Should include Retry-After header"
    
    data = response.json()
    assert "detail" in data, "Should include error detail"
    assert "limit" in data.get("detail", "").lower(), "Message should explain quota"


@pytest.mark.asyncio
async def test_payment_required_status(db: Session, client: TestClient):
    """Test 402 Payment Required for expired subscription."""
    tenant = Tenant(id="tenant-quota-3", name="Test", email="quota3@example.com")
    plan = Plan(id="free", name="Free", api_calls_limit=1000, ai_tokens_limit=100000)
    # Mark subscription as past_due
    subscription = Subscription(
        tenant_id="tenant-quota-3", plan_id="free", status="past_due"
    )
    
    db.add_all([tenant, plan, subscription])
    db.commit()

    # Request should be rejected with 402
    response = client.post(
        "/api/generate",
        json={"prompt": "pay", "idempotency_key": "req-pay"},
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-quota-3"},
    )
    
    assert response.status_code == 402, "Should return 402 Payment Required"
    
    data = response.json()
    assert "payment" in data.get("detail", "").lower() or "upgrade" in data.get("detail", "").lower(), \
        "Message should mention payment or upgrade"
