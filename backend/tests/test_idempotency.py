"""Tests for idempotent usage recording."""

import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models import Tenant, UsageEvent
from app.services.usage_service import UsageService


@pytest.mark.asyncio
async def test_no_duplicate_usage_on_retry(db: Session, client: TestClient):
    """Test that retrying a request with same idempotency key creates only one usage event."""
    # Setup
    tenant = Tenant(id="tenant-1", name="Test", email="test@example.com")
    db.add(tenant)
    db.commit()

    idempotency_key = "req-123-unique"

    # First request
    response1 = client.post(
        "/api/generate",
        json={"prompt": "hello", "idempotency_key": idempotency_key},
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-1"},
    )
    assert response1.status_code == 200
    result1 = response1.json()

    # Count usage events
    usage_count_1 = db.query(UsageEvent).filter_by(
        tenant_id="tenant-1", idempotency_key=idempotency_key
    ).count()
    assert usage_count_1 == 1, "First request should create exactly one usage event"

    # Retry with same idempotency key
    response2 = client.post(
        "/api/generate",
        json={"prompt": "hello", "idempotency_key": idempotency_key},
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-1"},
    )
    assert response2.status_code == 200
    result2 = response2.json()

    # Verify response is identical (cached)
    assert result1 == result2, "Cached response should be identical to original"

    # Count usage events again
    usage_count_2 = db.query(UsageEvent).filter_by(
        tenant_id="tenant-1", idempotency_key=idempotency_key
    ).count()
    assert usage_count_2 == 1, "Second request should NOT create new usage event"

    # Third retry for good measure
    response3 = client.post(
        "/api/generate",
        json={"prompt": "hello", "idempotency_key": idempotency_key},
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-1"},
    )
    assert response3.status_code == 200
    result3 = response3.json()
    assert result1 == result3

    usage_count_3 = db.query(UsageEvent).filter_by(
        tenant_id="tenant-1", idempotency_key=idempotency_key
    ).count()
    assert usage_count_3 == 1, "Still exactly one usage event after three requests"


@pytest.mark.asyncio
async def test_different_idempotency_keys_create_separate_events(db: Session, client: TestClient):
    """Test that different idempotency keys create separate usage events."""
    tenant = Tenant(id="tenant-2", name="Test", email="test2@example.com")
    db.add(tenant)
    db.commit()

    # First request
    response1 = client.post(
        "/api/generate",
        json={"prompt": "hello", "idempotency_key": "req-1"},
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-2"},
    )
    assert response1.status_code == 200

    # Second request with different key
    response2 = client.post(
        "/api/generate",
        json={"prompt": "world", "idempotency_key": "req-2"},
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-2"},
    )
    assert response2.status_code == 200

    # Verify two separate usage events
    usage_count = db.query(UsageEvent).filter_by(tenant_id="tenant-2").count()
    assert usage_count == 2, "Different keys should create separate events"


@pytest.mark.asyncio
async def test_idempotency_key_unique_constraint(db: Session):
    """Test that database enforces uniqueness on (tenant_id, idempotency_key)."""
    from sqlalchemy.exc import IntegrityError

    tenant = Tenant(id="tenant-3", name="Test", email="test3@example.com")
    db.add(tenant)
    db.commit()

    # Insert first usage event
    event1 = UsageEvent(
        tenant_id="tenant-3",
        usage_type="api_calls",
        quantity=1,
        cost_cents=1,
        idempotency_key="dup-key",
    )
    db.add(event1)
    db.commit()

    # Try to insert duplicate idempotency key
    event2 = UsageEvent(
        tenant_id="tenant-3",
        usage_type="api_calls",
        quantity=1,
        cost_cents=1,
        idempotency_key="dup-key",
    )
    db.add(event2)

    with pytest.raises(IntegrityError):
        db.commit()
