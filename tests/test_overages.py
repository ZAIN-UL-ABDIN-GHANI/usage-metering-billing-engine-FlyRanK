"""Tests for overage billing and policy management."""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime

from app.models_overage import OverageCharge, OveragePolicy
from app.services.overage_service import OverageService


class TestOverageDetection:
    """Test overage detection and charge creation."""

    def test_detects_overage_api_calls(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test detection of API call overage."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create overage policy
        service = OverageService(db)
        policy = service.update_policy(
            plan_id=plan.id,
            allows_overage=True,
            api_calls_price=1,  # 1 cent per call
        )

        # Create usage exceeding limit
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=1500,  # 500 over limit
        )

        charges = service.check_and_create_overage_charges(tenant.id)

        assert len(charges) > 0
        assert charges[0].usage_type == "api_calls"
        assert charges[0].overage_quantity == 500
        assert charges[0].overage_total_cost_cents == 500

        print(f"✅ Overage: Detected {charges[0].overage_quantity} units = ${charges[0].overage_total_cost_cents/100:.2f}")

    def test_detects_overage_tokens(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test detection of token overage."""
        plan = create_plan(ai_tokens_limit=1_000_000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create overage policy
        service = OverageService(db)
        service.update_policy(
            plan_id=plan.id,
            allows_overage=True,
            tokens_price=1,  # 1 cent per 1000 tokens
        )

        # Create usage exceeding limit
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="ai_tokens",
            quantity=1_500_000,  # 500k over limit
        )

        charges = service.check_and_create_overage_charges(tenant.id)

        assert any(c.usage_type == "ai_tokens" for c in charges)

        print("✅ Overage: Token overage detected")

    def test_no_overage_if_under_quota(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that no overage is created when under quota."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(plan_id=plan.id, allows_overage=True, api_calls_price=1)

        # Create usage under limit
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=500,
        )

        charges = service.check_and_create_overage_charges(tenant.id)

        assert len(charges) == 0

        print("✅ Overage: No overage when under quota")

    def test_no_overage_if_policy_disallows(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that overage is not created if policy disallows."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        # Do not allow overages
        service.get_or_create_policy(plan.id)

        # Create usage exceeding limit
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=1500,
        )

        charges = service.check_and_create_overage_charges(tenant.id)

        assert len(charges) == 0

        print("✅ Overage: Not created when policy disallows")


class TestOverageChargeCalculation:
    """Test overage charge calculations."""

    def test_calculates_correct_cost(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test correct overage cost calculation."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(
            plan_id=plan.id,
            allows_overage=True,
            api_calls_price=5,  # 5 cents per call
        )

        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=1100,  # 100 over
        )

        charges = service.check_and_create_overage_charges(tenant.id)

        assert charges[0].overage_total_cost_cents == 500  # 100 * 5

        print(f"✅ Overage Cost: 100 units × 5¢ = ${charges[0].overage_total_cost_cents/100:.2f}")

    def test_multiple_overages_combined(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test multiple overage types are tracked separately."""
        plan = create_plan(api_calls_limit=1000, ai_tokens_limit=1_000_000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(
            plan_id=plan.id,
            allows_overage=True,
            api_calls_price=1,
            tokens_price=1,
        )

        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=1100,
        )
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="ai_tokens",
            quantity=1_100_000,
        )

        charges = service.check_and_create_overage_charges(tenant.id)

        assert len(charges) == 2

        print(f"✅ Overage Cost: Created {len(charges)} charges for multiple types")


class TestOveragePolicy:
    """Test overage policy management."""

    def test_get_or_create_policy(
        self, db: Session, create_plan
    ):
        """Test creating default policy."""
        plan = create_plan()

        service = OverageService(db)
        policy = service.get_or_create_policy(plan.id)

        assert policy is not None
        assert policy.plan_id == plan.id
        assert policy.allows_overage is False

        print("✅ Policy: Default policy created")

    def test_update_policy_settings(
        self, db: Session, create_plan
    ):
        """Test updating policy settings."""
        plan = create_plan()

        service = OverageService(db)
        policy = service.update_policy(
            plan_id=plan.id,
            allows_overage=True,
            api_calls_price=2,
            tokens_price=3,
            max_amount=10000,
        )

        assert policy.allows_overage is True
        assert policy.api_calls_overage_price_cents == 2
        assert policy.ai_tokens_overage_price_cents == 3
        assert policy.max_overage_amount_cents == 10000

        print("✅ Policy: Updated successfully")

    def test_policy_suspension_settings(
        self, db: Session, create_plan
    ):
        """Test policy suspension settings."""
        plan = create_plan()

        service = OverageService(db)
        policy = service.update_policy(
            plan_id=plan.id,
            allows_overage=True,
            suspend_on_exceeded=True,
            max_amount=5000,
        )

        assert policy.suspend_on_overage_exceeded is True
        assert policy.max_overage_amount_cents == 5000

        print("✅ Policy: Suspension settings configured")


class TestOverageRetrieval:
    """Test overage charge retrieval."""

    def test_get_charge_by_id(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test getting charge by ID."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(plan_id=plan.id, allows_overage=True, api_calls_price=1)

        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=1100,
        )

        charges = service.check_and_create_overage_charges(tenant.id)
        charge = charges[0]

        retrieved = service.get_charge(charge.id)

        assert retrieved is not None
        assert retrieved.id == charge.id

        print("✅ Retrieval: Charge retrieved by ID")

    def test_get_tenant_charges(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test getting all charges for tenant."""
        plan = create_plan(api_calls_limit=1000, ai_tokens_limit=1_000_000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(
            plan_id=plan.id,
            allows_overage=True,
            api_calls_price=1,
            tokens_price=1,
        )

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1100)
        create_usage_event(tenant_id=tenant.id, usage_type="ai_tokens", quantity=1_100_000)

        service.check_and_create_overage_charges(tenant.id)

        charges, total = service.get_tenant_charges(tenant.id)

        assert len(charges) >= 2
        assert total >= 2

        print(f"✅ Retrieval: Got {len(charges)} charges for tenant")

    def test_filter_charges_by_period(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test filtering charges by billing period."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(plan_id=plan.id, allows_overage=True, api_calls_price=1)

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1100)

        charges = service.check_and_create_overage_charges(tenant.id)
        period = charges[0].billing_period

        filtered, total = service.get_tenant_charges(tenant.id, billing_period=period)

        assert len(filtered) > 0
        assert all(c.billing_period == period for c in filtered)

        print("✅ Retrieval: Charges filtered by period")


class TestOverageSummary:
    """Test overage summary and statistics."""

    def test_period_overage_summary(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test getting period overage summary."""
        plan = create_plan(api_calls_limit=1000, ai_tokens_limit=1_000_000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(
            plan_id=plan.id,
            allows_overage=True,
            api_calls_price=1,
            tokens_price=1,
        )

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1100)
        create_usage_event(tenant_id=tenant.id, usage_type="ai_tokens", quantity=1_100_000)

        service.check_and_create_overage_charges(tenant.id)

        summary = service.get_period_overage_summary(tenant.id)

        assert summary["total_overage_quantity"] > 0
        assert summary["total_overage_charges_cents"] > 0
        assert "api_call_overage_cents" in summary
        assert "token_overage_cents" in summary

        print(f"✅ Summary: Total overage ${summary['total_overage_charges_dollars']:.2f}")

    def test_summary_splits_by_type(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that summary splits costs by usage type."""
        plan = create_plan(api_calls_limit=1000, ai_tokens_limit=1_000_000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(
            plan_id=plan.id,
            allows_overage=True,
            api_calls_price=2,  # 2 cents per call
            tokens_price=1,  # 1 cent per token
        )

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1100)  # 100 over = 200 cents
        create_usage_event(tenant_id=tenant.id, usage_type="ai_tokens", quantity=1_100_000)  # 100k over = 100k cents

        service.check_and_create_overage_charges(tenant.id)

        summary = service.get_period_overage_summary(tenant.id)

        assert summary["api_call_overage_cents"] == 200
        assert summary["token_overage_cents"] == 100000

        print("✅ Summary: Costs split by type correctly")


class TestOverageStatus:
    """Test overage status tracking."""

    def test_get_overage_status(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test getting overage status for subscription."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(plan_id=plan.id, allows_overage=True, api_calls_price=1)

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1100)

        service.check_and_create_overage_charges(tenant.id)

        status = service.get_overage_status(subscription.id)

        assert status["allows_overage"] is True
        assert status["current_period_overage_quantity"] > 0

        print("✅ Status: Overage status retrieved")

    def test_suspension_status_when_exceeded(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test suspension status when limits exceeded."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(
            plan_id=plan.id,
            allows_overage=True,
            api_calls_price=1,
            suspend_on_exceeded=True,
            max_amount=100,  # Max $1 before suspension
        )

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1500)  # 500 over = 500 cents = $5

        service.check_and_create_overage_charges(tenant.id)

        status = service.get_overage_status(subscription.id)

        assert status["will_suspend"] is True

        print("✅ Status: Suspension flagged when exceeded")

    def test_no_suspension_when_under_limit(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test no suspension when under limit."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(
            plan_id=plan.id,
            allows_overage=True,
            api_calls_price=1,
            suspend_on_exceeded=True,
            max_amount=500,  # Max $5
        )

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1100)  # 100 over = 100 cents

        service.check_and_create_overage_charges(tenant.id)

        status = service.get_overage_status(subscription.id)

        assert status["will_suspend"] is False

        print("✅ Status: No suspension when under limit")


class TestOverageInvoicing:
    """Test marking charges as invoiced."""

    def test_mark_charge_invoiced(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test marking charge as invoiced."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(plan_id=plan.id, allows_overage=True, api_calls_price=1)

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1100)

        charges = service.check_and_create_overage_charges(tenant.id)
        charge = charges[0]

        invoiced = service.mark_charge_invoiced(charge.id, "inv_123")

        assert invoiced.invoiced is True
        assert invoiced.invoice_id == "inv_123"

        print("✅ Invoicing: Charge marked as invoiced")

    def test_summary_separates_invoiced_pending(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test summary separates invoiced from pending."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(plan_id=plan.id, allows_overage=True, api_calls_price=1)

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1100)

        charges = service.check_and_create_overage_charges(tenant.id)
        service.mark_charge_invoiced(charges[0].id, "inv_123")

        summary = service.get_period_overage_summary(tenant.id)

        assert summary["invoiced_cents"] > 0
        assert summary["pending_cents"] == 0

        print("✅ Invoicing: Summary separates invoiced/pending")


class TestOverageTenantIsolation:
    """Test tenant isolation in overages."""

    def test_overages_isolated_by_tenant(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that overages are isolated by tenant."""
        plan = create_plan(api_calls_limit=1000)
        tenant1 = create_tenant()
        tenant2 = create_tenant()
        
        create_subscription(tenant_id=tenant1.id, plan_id=plan.id)
        create_subscription(tenant_id=tenant2.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(plan_id=plan.id, allows_overage=True, api_calls_price=1)

        # Create overage for tenant1
        create_usage_event(tenant_id=tenant1.id, usage_type="api_calls", quantity=1100)
        service.check_and_create_overage_charges(tenant1.id)

        # Get charges for tenant2
        tenant2_charges, _ = service.get_tenant_charges(tenant2.id)

        # Tenant2 should see no charges
        assert len(tenant2_charges) == 0

        print("✅ Isolation: Overages isolated by tenant")


class TestOverageEdgeCases:
    """Test edge cases in overage handling."""

    def test_exact_quota_no_overage(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test no overage at exact quota."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(plan_id=plan.id, allows_overage=True, api_calls_price=1)

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1000)

        charges = service.check_and_create_overage_charges(tenant.id)

        assert len(charges) == 0

        print("✅ Edge Case: No overage at exact quota")

    def test_zero_overage_price(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test overage with zero price."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(plan_id=plan.id, allows_overage=True, api_calls_price=0)

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1100)

        charges = service.check_and_create_overage_charges(tenant.id)

        assert charges[0].overage_total_cost_cents == 0

        print("✅ Edge Case: Zero-price overage")

    def test_large_overage_quantity(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test handling large overage quantities."""
        plan = create_plan(api_calls_limit=100)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = OverageService(db)
        service.update_policy(plan_id=plan.id, allows_overage=True, api_calls_price=1)

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=100_000)

        charges = service.check_and_create_overage_charges(tenant.id)

        assert charges[0].overage_quantity == 99_900
        assert charges[0].overage_total_cost_cents == 99_900

        print(f"✅ Edge Case: Large overage {charges[0].overage_quantity:,} units")
