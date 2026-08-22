"""Tests for proration and mid-cycle plan change billing."""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models_proration import ProratedAdjustment, ProrationType
from app.services.proration_service import ProrationService


class TestProrationCalculations:
    """Test proration calculations for plan changes."""

    def test_upgrade_charge_calculation(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that upgrade to more expensive plan creates charge."""
        free_plan = create_plan(name="Free", monthly_price_cents=0)
        pro_plan = create_plan(name="Pro", monthly_price_cents=9900)  # $99/month
        
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=free_plan.id)

        service = ProrationService(db)
        change_date = datetime.utcnow()
        
        adjustment = service.calculate_proration(subscription, pro_plan, change_date)

        assert adjustment.proration_type == ProrationType.UPGRADE
        assert adjustment.charge_cents > 0
        assert adjustment.credit_cents == 0
        assert adjustment.net_adjustment_cents > 0

        print(f"✅ Proration: Upgrade charge ${adjustment.charge_cents/100:.2f}")

    def test_downgrade_credit_calculation(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that downgrade to cheaper plan creates credit."""
        pro_plan = create_plan(name="Pro", monthly_price_cents=9900)  # $99/month
        free_plan = create_plan(name="Free", monthly_price_cents=0)
        
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=pro_plan.id)

        service = ProrationService(db)
        change_date = datetime.utcnow()
        
        adjustment = service.calculate_proration(subscription, free_plan, change_date)

        assert adjustment.proration_type == ProrationType.DOWNGRADE
        assert adjustment.credit_cents > 0
        assert adjustment.charge_cents == 0
        assert adjustment.net_adjustment_cents < 0

        print(f"✅ Proration: Downgrade credit ${adjustment.credit_cents/100:.2f}")

    def test_same_price_plan_no_adjustment(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that same-price plan has no proration."""
        plan1 = create_plan(name="Plan A", monthly_price_cents=9900)
        plan2 = create_plan(name="Plan B", monthly_price_cents=9900)
        
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=plan1.id)

        service = ProrationService(db)
        change_date = datetime.utcnow()
        
        adjustment = service.calculate_proration(subscription, plan2, change_date)

        assert adjustment.charge_cents == 0
        assert adjustment.credit_cents == 0
        assert adjustment.net_adjustment_cents == 0

        print("✅ Proration: No adjustment for same-price plans")

    def test_proration_respects_days_remaining(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that proration accounts for remaining days in period."""
        free_plan = create_plan(name="Free", monthly_price_cents=0)
        pro_plan = create_plan(name="Pro", monthly_price_cents=3000)  # $30/month = $1/day
        
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=free_plan.id)

        service = ProrationService(db)
        
        # Mid-month change (approximately 15 days remaining)
        change_date = datetime.utcnow().replace(day=15, hour=12)
        
        adjustment = service.calculate_proration(subscription, pro_plan, change_date)

        # With ~15 days remaining at $1/day = ~$15 charge
        assert adjustment.charge_cents > 0
        assert adjustment.days_remaining > 0

        print(f"✅ Proration: Respects {adjustment.days_remaining} days remaining")

    def test_cannot_prorate_same_plan(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that proratingto same plan raises error."""
        plan = create_plan()
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = ProrationService(db)

        with pytest.raises(ValueError, match="same plan"):
            service.calculate_proration(subscription, plan)

        print("✅ Proration: Same plan change rejected")


class TestPlanChange:
    """Test plan change with subscription update."""

    def test_apply_plan_change_updates_subscription(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that plan change updates subscription."""
        old_plan = create_plan(name="Free", monthly_price_cents=0)
        new_plan = create_plan(name="Pro", monthly_price_cents=9900)
        
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=old_plan.id)
        old_sub_id = subscription.id

        service = ProrationService(db)
        updated_sub, adjustment = service.apply_plan_change(
            tenant_id=tenant.id,
            new_plan_id=new_plan.id,
        )

        assert updated_sub.id == old_sub_id
        assert updated_sub.plan_id == new_plan.id
        assert adjustment is not None

        print("✅ Plan Change: Subscription updated")

    def test_plan_change_creates_adjustment(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that plan change creates proration adjustment."""
        old_plan = create_plan(name="Free", monthly_price_cents=0)
        new_plan = create_plan(name="Pro", monthly_price_cents=9900)
        
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=old_plan.id)

        service = ProrationService(db)
        sub, adjustment = service.apply_plan_change(
            tenant_id=tenant.id,
            new_plan_id=new_plan.id,
        )

        assert adjustment is not None
        assert adjustment.tenant_id == tenant.id
        assert adjustment.from_plan_id == old_plan.id
        assert adjustment.to_plan_id == new_plan.id
        assert adjustment.applied is not None

        print("✅ Plan Change: Adjustment created and applied")

    def test_plan_change_no_subscription_error(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that plan change without subscription raises error."""
        plan = create_plan()
        tenant = create_tenant()
        # No subscription created

        service = ProrationService(db)

        with pytest.raises(ValueError, match="No active subscription"):
            service.apply_plan_change(
                tenant_id=tenant.id,
                new_plan_id=plan.id,
            )

        print("✅ Plan Change: No subscription error handled")

    def test_plan_change_invalid_plan_error(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that plan change to invalid plan raises error."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = ProrationService(db)

        with pytest.raises(ValueError, match="not found"):
            service.apply_plan_change(
                tenant_id=tenant.id,
                new_plan_id="invalid-plan",
            )

        print("✅ Plan Change: Invalid plan error handled")


class TestAdjustmentRetrieval:
    """Test adjustment retrieval and querying."""

    def test_get_adjustment_by_id(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test getting adjustment by ID."""
        old_plan = create_plan(monthly_price_cents=0)
        new_plan = create_plan(monthly_price_cents=9900)
        
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=old_plan.id)

        service = ProrationService(db)
        adjustment = service.calculate_proration(subscription, new_plan)

        retrieved = service.get_adjustment(adjustment.id)

        assert retrieved is not None
        assert retrieved.id == adjustment.id

        print("✅ Adjustment: Retrieved by ID")

    def test_get_tenant_adjustments(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test getting all adjustments for tenant."""
        old_plan = create_plan(monthly_price_cents=0)
        mid_plan = create_plan(monthly_price_cents=4900)
        new_plan = create_plan(monthly_price_cents=9900)
        
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=old_plan.id)

        service = ProrationService(db)
        
        # Multiple plan changes
        service.calculate_proration(subscription, mid_plan)
        service.calculate_proration(subscription, new_plan)

        adjustments, total = service.get_tenant_adjustments(tenant.id)

        assert len(adjustments) >= 2
        assert total >= 2

        print(f"✅ Adjustment: Retrieved {len(adjustments)} for tenant")

    def test_get_subscription_adjustments(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test getting adjustments for specific subscription."""
        old_plan = create_plan(monthly_price_cents=0)
        new_plan = create_plan(monthly_price_cents=9900)
        
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=old_plan.id)

        service = ProrationService(db)
        service.calculate_proration(subscription, new_plan)

        adjustments = service.get_subscription_adjustments(subscription.id)

        assert len(adjustments) > 0
        assert all(a.subscription_id == subscription.id for a in adjustments)

        print(f"✅ Adjustment: Retrieved {len(adjustments)} for subscription")


class TestDailyRateCalculation:
    """Test daily rate calculations."""

    def test_daily_rate_from_monthly(
        self, db: Session, create_plan
    ):
        """Test that daily rate is calculated from monthly price."""
        plan = create_plan(monthly_price_cents=3000)  # $30/month

        service = ProrationService(db)
        daily_rate = service.calculate_daily_rate(plan)

        # $30/30 = $1/day = 100 cents
        assert daily_rate == 100

        print(f"✅ Daily Rate: ${plan.monthly_price_cents/100}/month = ${daily_rate/100:.2f}/day")

    def test_remaining_period_cost(
        self, db: Session, create_plan
    ):
        """Test cost calculation for remaining period."""
        plan = create_plan(monthly_price_cents=3000)  # $30/month = $1/day

        service = ProrationService(db)
        cost = service.calculate_remaining_period_cost(plan, days_remaining=15)

        # 15 days * $1/day = $15 = 1500 cents
        assert cost == 1500

        print(f"✅ Remaining Period: 15 days = ${cost/100:.2f}")


class TestUpgradeDetection:
    """Test upgrade vs downgrade detection."""

    def test_upgrade_detection(
        self, db: Session, create_plan
    ):
        """Test that upgrade is correctly detected."""
        old_plan = create_plan(monthly_price_cents=0)
        new_plan = create_plan(monthly_price_cents=9900)

        service = ProrationService(db)
        is_upgrade = service.should_charge_for_upgrade(old_plan, new_plan)

        assert is_upgrade is True

        print("✅ Detection: Upgrade detected correctly")

    def test_downgrade_detection(
        self, db: Session, create_plan
    ):
        """Test that downgrade is correctly detected."""
        old_plan = create_plan(monthly_price_cents=9900)
        new_plan = create_plan(monthly_price_cents=0)

        service = ProrationService(db)
        is_downgrade = service.should_credit_for_downgrade(old_plan, new_plan)

        assert is_downgrade is True

        print("✅ Detection: Downgrade detected correctly")

    def test_lateral_move_not_detected_as_upgrade(
        self, db: Session, create_plan
    ):
        """Test that same-price plan is not an upgrade."""
        plan1 = create_plan(monthly_price_cents=9900)
        plan2 = create_plan(monthly_price_cents=9900)

        service = ProrationService(db)
        is_upgrade = service.should_charge_for_upgrade(plan1, plan2)

        assert is_upgrade is False

        print("✅ Detection: Lateral move not detected as upgrade")


class TestAdjustmentSummary:
    """Test adjustment summary and statistics."""

    def test_adjustment_summary(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test getting adjustment summary for tenant."""
        plan1 = create_plan(monthly_price_cents=0)
        plan2 = create_plan(monthly_price_cents=9900)
        plan3 = create_plan(monthly_price_cents=4900)
        
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=plan1.id)

        service = ProrationService(db)
        service.calculate_proration(subscription, plan2)

        summary = service.get_adjustment_summary(tenant.id)

        assert summary["tenant_id"] == tenant.id
        assert summary["total_adjustments"] > 0
        assert summary["total_charges_cents"] > 0

        print(f"✅ Summary: {summary['total_adjustments']} adjustments, "
              f"${summary['total_charges_dollars']:.2f} in charges")

    def test_summary_tracks_upgrades_downgrades(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that summary tracks upgrade and downgrade counts."""
        plan1 = create_plan(monthly_price_cents=0)
        plan2 = create_plan(monthly_price_cents=9900)
        plan3 = create_plan(monthly_price_cents=4900)
        
        tenant = create_tenant()
        sub1 = create_subscription(tenant_id=tenant.id, plan_id=plan1.id)
        sub2 = create_subscription(tenant_id=tenant.id, plan_id=plan2.id)

        service = ProrationService(db)
        
        # Upgrade: plan1 → plan2
        service.calculate_proration(sub1, plan2)
        # Downgrade: plan2 → plan3
        service.calculate_proration(sub2, plan3)

        summary = service.get_adjustment_summary(tenant.id)

        # At least one upgrade and one downgrade
        assert summary["upgrades"] >= 1
        assert summary["downgrades"] >= 1

        print(f"✅ Summary: {summary['upgrades']} upgrades, "
              f"{summary['downgrades']} downgrades")


class TestProrationEdgeCases:
    """Test edge cases in proration."""

    def test_month_boundary_proration(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test proration at month boundaries."""
        old_plan = create_plan(monthly_price_cents=0)
        new_plan = create_plan(monthly_price_cents=9900)
        
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=old_plan.id)

        service = ProrationService(db)
        
        # Change at end of month
        last_day = datetime.utcnow().replace(day=28, hour=23, minute=59, second=59)
        adjustment = service.calculate_proration(subscription, new_plan, last_day)

        # Should have very few days remaining
        assert adjustment.days_remaining <= 2

        print(f"✅ Proration: {adjustment.days_remaining} days remaining at month-end")

    def test_zero_days_remaining(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test proration with minimal days remaining."""
        old_plan = create_plan(monthly_price_cents=0)
        new_plan = create_plan(monthly_price_cents=9900)
        
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=old_plan.id)

        service = ProrationService(db)
        
        # Change on last second of month
        now = datetime.utcnow()
        last_day = (now.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        
        adjustment = service.calculate_proration(subscription, new_plan, last_day)

        # Should still calculate correctly even with 0-1 days
        assert adjustment.days_remaining >= 0

        print(f"✅ Proration: {adjustment.days_remaining} days remaining at period end")

    def test_integer_cent_precision(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that all costs are in integer cents."""
        old_plan = create_plan(monthly_price_cents=0)
        new_plan = create_plan(monthly_price_cents=9999)  # Odd number
        
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id, plan_id=old_plan.id)

        service = ProrationService(db)
        adjustment = service.calculate_proration(subscription, new_plan)

        # All amounts should be integers
        assert isinstance(adjustment.charge_cents, int)
        assert isinstance(adjustment.credit_cents, int)
        assert isinstance(adjustment.net_adjustment_cents, int)

        print("✅ Proration: All amounts are integer cents")


class TestTenantIsolation:
    """Test tenant isolation in adjustments."""

    def test_adjustments_isolated_by_tenant(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that adjustments are isolated by tenant."""
        plan1 = create_plan(monthly_price_cents=0)
        plan2 = create_plan(monthly_price_cents=9900)
        
        tenant1 = create_tenant()
        tenant2 = create_tenant()
        
        sub1 = create_subscription(tenant_id=tenant1.id, plan_id=plan1.id)
        sub2 = create_subscription(tenant_id=tenant2.id, plan_id=plan1.id)

        service = ProrationService(db)
        
        # Create adjustment for tenant1
        service.calculate_proration(sub1, plan2)

        # Get adjustments for tenant2
        tenant2_adjustments, _ = service.get_tenant_adjustments(tenant2.id)

        # Tenant2 should see no adjustments
        assert len(tenant2_adjustments) == 0

        print("✅ Tenant Isolation: Adjustments isolated by tenant")
