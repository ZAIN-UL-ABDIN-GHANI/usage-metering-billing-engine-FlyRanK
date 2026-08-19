"""Tests for usage metering and quota enforcement."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid

from app.models import Tenant
from app.services.usage_service import UsageService
from app.services.quota_enforcement import QuotaEnforcementService, QuotaStatus
from app.repositories.usage_repository import UsageRepository


class TestIdempotentMetering:
    """Test idempotent usage recording - core capstone requirement."""

    def test_same_idempotency_key_returns_same_event(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that same idempotency key returns cached result."""
        create_plan()
        tenant = create_tenant()

        service = UsageService(db)

        # First request
        event1, is_dup1 = service.record_usage(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
            idempotency_key="request-1",
        )

        assert is_dup1 is False
        assert event1.id is not None
        first_id = event1.id

        # Retry with same idempotency key
        event2, is_dup2 = service.record_usage(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
            idempotency_key="request-1",
        )

        # Should be same event
        assert is_dup2 is True
        assert event2.id == first_id
        print(f"✅ Idempotent: Same key returned cached event {first_id}")

    def test_duplicate_idempotency_key_not_in_database(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that duplicate usage events are NOT created in database."""
        create_plan()
        tenant = create_tenant()

        repo = UsageRepository(db)
        service = UsageService(db)

        # Create first event
        service.record_usage(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
            idempotency_key="unique-key-123",
        )

        # Count events with this tenant
        count_before = (
            db.query(UsageEvent)
            .filter_by(tenant_id=tenant.id, idempotency_key="unique-key-123")
            .count()
        )
        assert count_before == 1

        # Retry same request
        service.record_usage(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
            idempotency_key="unique-key-123",
        )

        # Count should still be 1 (no duplicate)
        count_after = (
            db.query(UsageEvent)
            .filter_by(tenant_id=tenant.id, idempotency_key="unique-key-123")
            .count()
        )
        assert count_after == 1
        print("✅ Idempotency: No duplicate events in database")

    def test_different_idempotency_keys_create_separate_events(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that different idempotency keys create separate events."""
        create_plan()
        tenant = create_tenant()

        service = UsageService(db)

        # Request 1
        event1, _ = service.record_usage(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
            idempotency_key="key-1",
        )

        # Request 2 with different key
        event2, _ = service.record_usage(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
            idempotency_key="key-2",
        )

        # Should be different events
        assert event1.id != event2.id
        print("✅ Idempotency: Different keys create separate events")

    def test_idempotency_across_retries(
        self, db: Session, create_plan, create_tenant
    ):
        """Test idempotency is maintained across multiple retries."""
        create_plan()
        tenant = create_tenant()

        service = UsageService(db)
        idempotency_key = str(uuid.uuid4())

        # Simulate network retry pattern
        events = []
        for _ in range(5):  # 5 retries
            event, is_dup = service.record_usage(
                tenant_id=tenant.id,
                usage_type="api_calls",
                quantity=50,
                idempotency_key=idempotency_key,
            )
            events.append((event.id, is_dup))

        # First should not be duplicate
        assert events[0][1] is False

        # All retries should return same event
        first_id = events[0][0]
        for i in range(1, 5):
            assert events[i][0] == first_id
            assert events[i][1] is True

        print(f"✅ Idempotency: 5 retries returned same event {first_id}")


class TestQuotaEnforcement:
    """Test quota enforcement and boundary cases."""

    def test_quota_allows_within_limit(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that usage within limit is allowed."""
        create_plan(plan_id="free", api_calls_limit=1000)
        tenant = create_tenant(plan_id="free")

        service = UsageService(db)

        # Check quota before using
        result = service.check_quota(
            tenant_id=tenant.id,
            usage_type="api_calls",
            requested_quantity=500,
        )

        assert result["allowed"] is True
        assert result["current"] == 0
        assert result["limit"] == 1000
        print("✅ Quota: Request within limit allowed")

    def test_quota_rejects_at_boundary(
        self, db: Session, create_plan, create_tenant
    ):
        """Test exact boundary case - at exactly limit."""
        create_plan(plan_id="free", api_calls_limit=100)
        tenant = create_tenant(plan_id="free")

        service = UsageService(db)

        # Use exactly 100
        service.record_usage(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
            idempotency_key="max-usage",
        )

        # Check if can use 1 more
        result = service.check_quota(
            tenant_id=tenant.id,
            usage_type="api_calls",
            requested_quantity=1,
        )

        assert result["allowed"] is False
        print("✅ Quota: Request at limit rejected")

    def test_quota_rejects_over_limit(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that usage over limit is rejected."""
        create_plan(plan_id="free", api_calls_limit=1000)
        tenant = create_tenant(plan_id="free")

        service = UsageService(db)

        # Use 800
        service.record_usage(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=800,
            idempotency_key="partial-usage",
        )

        # Try to use 300 (would total 1100)
        result = service.check_quota(
            tenant_id=tenant.id,
            usage_type="api_calls",
            requested_quantity=300,
        )

        assert result["allowed"] is False
        assert result["total_if_allowed"] == 1100
        print("✅ Quota: Request over limit rejected")

    def test_quota_allows_exactly_at_limit(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that request to reach exactly limit is allowed."""
        create_plan(plan_id="free", api_calls_limit=1000)
        tenant = create_tenant(plan_id="free")

        service = UsageService(db)

        # Use 700
        service.record_usage(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=700,
            idempotency_key="partial",
        )

        # Request exactly 300 to reach limit
        result = service.check_quota(
            tenant_id=tenant.id,
            usage_type="api_calls",
            requested_quantity=300,
        )

        assert result["allowed"] is True
        assert result["total_if_allowed"] == 1000
        print("✅ Quota: Request to exactly reach limit allowed")


class TestHTTPStatusCodes:
    """Test proper HTTP status codes for quota violations."""

    def test_quota_exceeded_returns_429(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that quota exceeded returns 429 status code."""
        create_plan(plan_id="free", api_calls_limit=100)
        tenant = create_tenant(plan_id="free")

        enforcement = QuotaEnforcementService(db)

        # Use 100
        repo = UsageRepository(db)
        repo.create(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
            idempotency_key="max-out",
        )

        # Check quota
        result = enforcement.check_and_enforce_quota(
            tenant_id=tenant.id,
            usage_type="api_calls",
            requested_quantity=1,
        )

        assert result["http_status"] == 429
        assert result["status"] == QuotaStatus.QUOTA_EXCEEDED
        print("✅ Status Code: Quota exceeded returns 429")

    def test_suspended_tenant_returns_402(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that suspended tenant returns 402 Payment Required."""
        create_plan()
        tenant = create_tenant()

        # Suspend tenant
        from app.repositories.tenant_repository import TenantRepository
        tenant_repo = TenantRepository(db)
        tenant_repo.update(tenant.id, status="suspended")

        enforcement = QuotaEnforcementService(db)

        result = enforcement.check_and_enforce_quota(
            tenant_id=tenant.id,
            usage_type="api_calls",
            requested_quantity=1,
        )

        assert result["http_status"] == 402
        assert result["status"] == QuotaStatus.PLAN_SUSPENDED
        print("✅ Status Code: Suspended tenant returns 402")

    def test_allowed_request_returns_200(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that allowed request returns 200."""
        create_plan(plan_id="free", api_calls_limit=1000)
        tenant = create_tenant(plan_id="free")

        enforcement = QuotaEnforcementService(db)

        result = enforcement.check_and_enforce_quota(
            tenant_id=tenant.id,
            usage_type="api_calls",
            requested_quantity=100,
        )

        assert result["http_status"] == 200
        assert result["status"] == QuotaStatus.ALLOWED
        assert result["allowed"] is True
        print("✅ Status Code: Allowed request returns 200")


class TestUsageSummary:
    """Test usage summary and reporting."""

    def test_usage_summary_shows_correct_totals(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that usage summary shows correct totals."""
        create_plan(
            plan_id="free",
            api_calls_limit=1000,
            ai_tokens_limit=100000,
        )
        tenant = create_tenant(plan_id="free")

        service = UsageService(db)

        # Record some usage
        service.record_usage(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=250,
            idempotency_key="key-1",
        )

        service.record_usage(
            tenant_id=tenant.id,
            usage_type="ai_tokens",
            quantity=50000,
            idempotency_key="key-2",
        )

        # Get summary
        summary = service.get_usage_summary(tenant.id)

        assert summary["api_calls"]["used"] == 250
        assert summary["api_calls"]["limit"] == 1000
        assert summary["api_calls"]["remaining"] == 750
        assert summary["ai_tokens"]["used"] == 50000
        assert summary["ai_tokens"]["limit"] == 100000
        print("✅ Summary: Correct totals shown")

    def test_usage_summary_percentage_calculation(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that usage percentage is calculated correctly."""
        create_plan(plan_id="free", api_calls_limit=1000)
        tenant = create_tenant(plan_id="free")

        service = UsageService(db)

        # Use 250 out of 1000 = 25%
        service.record_usage(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=250,
            idempotency_key="key-1",
        )

        summary = service.get_usage_summary(tenant.id)

        assert summary["api_calls"]["percent_used"] == 25.0
        print("✅ Summary: Percentage calculation correct")

    def test_usage_summary_empty_period(
        self, db: Session, create_plan, create_tenant
    ):
        """Test usage summary for period with no usage."""
        create_plan()
        tenant = create_tenant()

        service = UsageService(db)

        summary = service.get_usage_summary(tenant.id)

        assert summary["api_calls"]["used"] == 0
        assert summary["api_calls"]["remaining"] == summary["api_calls"]["limit"]
        assert summary["api_calls"]["percent_used"] == 0.0
        print("✅ Summary: Empty period shows 0 usage")


class TestQuotaCritical:
    """Test critical quota detection."""

    def test_quota_critical_at_90_percent(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that 90% usage is marked as critical."""
        create_plan(plan_id="free", api_calls_limit=1000)
        tenant = create_tenant(plan_id="free")

        enforcement = QuotaEnforcementService(db)

        # Use 900 out of 1000 = 90%
        repo = UsageRepository(db)
        repo.create(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=900,
            idempotency_key="critical-level",
        )

        is_critical = enforcement.is_quota_critical(
            tenant_id=tenant.id,
            usage_type="api_calls",
        )

        assert is_critical is True
        print("✅ Critical: 90% usage marked as critical")

    def test_quota_not_critical_below_90_percent(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that below 90% is not critical."""
        create_plan(plan_id="free", api_calls_limit=1000)
        tenant = create_tenant(plan_id="free")

        enforcement = QuotaEnforcementService(db)

        # Use 800 out of 1000 = 80%
        repo = UsageRepository(db)
        repo.create(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=800,
            idempotency_key="under-critical",
        )

        is_critical = enforcement.is_quota_critical(
            tenant_id=tenant.id,
            usage_type="api_calls",
        )

        assert is_critical is False
        print("✅ Critical: Below 90% not marked as critical")


class TestMultipleUsageTypes:
    """Test handling multiple usage types."""

    def test_separate_quotas_for_each_type(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that each usage type has separate quota."""
        create_plan(
            plan_id="free",
            api_calls_limit=1000,
            ai_tokens_limit=100000,
        )
        tenant = create_tenant(plan_id="free")

        service = UsageService(db)

        # Max out api_calls
        service.record_usage(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=1000,
            idempotency_key="max-api",
        )

        # But ai_tokens should still be available
        result = service.check_quota(
            tenant_id=tenant.id,
            usage_type="ai_tokens",
            requested_quantity=50000,
        )

        assert result["allowed"] is True
        print("✅ Multiple Types: Separate quotas enforced")


class TestUsageEvents:
    """Test usage event retrieval."""

    def test_get_usage_events_pagination(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that usage events support pagination."""
        create_plan()
        tenant = create_tenant()

        service = UsageService(db)

        # Create 10 events
        for i in range(10):
            service.record_usage(
                tenant_id=tenant.id,
                usage_type="api_calls",
                quantity=1,
                idempotency_key=f"event-{i}",
            )

        # Get first 5
        result = service.get_usage_events(
            tenant_id=tenant.id,
            limit=5,
            offset=0,
        )

        assert result["pagination"]["total"] == 10
        assert result["pagination"]["returned"] == 5
        assert len(result["events"]) == 5
        print("✅ Events: Pagination works correctly")


# Import at end to avoid circular imports
from app.models import UsageEvent
from app.repositories.usage_repository import UsageRepository
