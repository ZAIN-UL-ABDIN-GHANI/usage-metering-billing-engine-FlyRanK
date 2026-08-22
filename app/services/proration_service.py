"""Proration service - calculates mid-cycle billing adjustments."""

from typing import Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models_proration import ProratedAdjustment, ProrationType
from app.models import Subscription, Plan, Tenant
from app.utils.db_helpers import generate_id, get_billing_period_start, get_billing_period_end
from app.config_pricing import PricingConfig


class ProrationService:
    """Service for prorated billing calculations."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def calculate_proration(
        self,
        subscription: Subscription,
        new_plan: Plan,
        change_date: Optional[datetime] = None,
    ) -> ProratedAdjustment:
        """
        Calculate prorated billing adjustment for plan change.

        Handles upgrade, downgrade, and lateral moves between plans.

        Args:
            subscription: Current subscription
            new_plan: New plan to change to
            change_date: When change takes effect (default: now)

        Returns:
            ProratedAdjustment with calculations

        Raises:
            ValueError: If plans invalid or same plan
        """
        if not change_date:
            change_date = datetime.utcnow()

        old_plan = self.db.query(Plan).filter_by(id=subscription.plan_id).first()
        if not old_plan:
            raise ValueError(f"Old plan {subscription.plan_id} not found")

        if old_plan.id == new_plan.id:
            raise ValueError("Cannot prorate to same plan")

        # Get billing period for change date
        period_start = get_billing_period_start(change_date)
        period_end = get_billing_period_end(change_date)

        # Calculate days
        days_in_period = (period_end - period_start).days
        days_used = max(0, (change_date - period_start).days)
        days_remaining = max(0, (period_end - change_date).days)

        # Get daily rates (monthly price / 30)
        old_daily_rate = old_plan.monthly_price_cents // 30
        new_daily_rate = new_plan.monthly_price_cents // 30

        # Calculate costs
        # Cost for days already used on old plan
        cost_old_used = old_daily_rate * days_used

        # Cost for remaining days on old plan (what they would have paid)
        cost_old_remaining = old_daily_rate * days_remaining

        # Cost for remaining days on new plan (what they will pay)
        cost_new_remaining = new_daily_rate * days_remaining

        # Calculate net adjustment
        # If new_plan is more expensive: they owe the difference
        # If new_plan is cheaper: they get a credit
        difference = cost_new_remaining - cost_old_remaining
        # Positive = upgrade (charge), Negative = downgrade (credit)

        # Determine proration type
        if new_daily_rate > old_daily_rate:
            proration_type = ProrationType.UPGRADE
            charge_cents = max(0, difference)
            credit_cents = 0
        elif new_daily_rate < old_daily_rate:
            proration_type = ProrationType.DOWNGRADE
            credit_cents = max(0, -difference)
            charge_cents = 0
        else:
            proration_type = ProrationType.PLAN_CHANGE
            charge_cents = 0
            credit_cents = 0

        net_adjustment = charge_cents - credit_cents

        # Create adjustment record
        adjustment = ProratedAdjustment(
            id=generate_id(),
            tenant_id=subscription.tenant_id,
            subscription_id=subscription.id,
            from_plan_id=old_plan.id,
            to_plan_id=new_plan.id,
            proration_type=proration_type,
            billing_period_start=period_start,
            billing_period_end=period_end,
            change_date=change_date,
            days_in_period=days_in_period,
            days_remaining=days_remaining,
            old_plan_daily_rate_cents=old_daily_rate,
            new_plan_daily_rate_cents=new_daily_rate,
            days_used_old_plan=days_used,
            cost_old_plan_used_cents=cost_old_used,
            cost_old_plan_remaining_cents=cost_old_remaining,
            cost_new_plan_remaining_cents=cost_new_remaining,
            credit_cents=credit_cents,
            charge_cents=charge_cents,
            net_adjustment_cents=net_adjustment,
            created_at=datetime.utcnow(),
        )

        self.db.add(adjustment)
        self.db.commit()
        self.db.refresh(adjustment)

        return adjustment

    def apply_plan_change(
        self,
        tenant_id: str,
        new_plan_id: str,
        change_date: Optional[datetime] = None,
    ) -> Tuple[Subscription, Optional[ProratedAdjustment]]:
        """
        Change a tenant's plan with proration.

        Updates subscription and creates adjustment record.

        Args:
            tenant_id: Tenant ID
            new_plan_id: New plan to switch to
            change_date: When to apply (default: now)

        Returns:
            Tuple of (updated Subscription, ProratedAdjustment or None)

        Raises:
            ValueError: If subscription or plan not found
        """
        if not change_date:
            change_date = datetime.utcnow()

        # Get current subscription
        subscription = (
            self.db.query(Subscription)
            .filter_by(tenant_id=tenant_id)
            .first()
        )
        if not subscription:
            raise ValueError(f"No active subscription for tenant {tenant_id}")

        # Get new plan
        new_plan = self.db.query(Plan).filter_by(id=new_plan_id).first()
        if not new_plan:
            raise ValueError(f"Plan {new_plan_id} not found")

        # Calculate proration
        adjustment = self.calculate_proration(subscription, new_plan, change_date)

        # Update subscription to new plan
        old_plan_id = subscription.plan_id
        subscription.plan_id = new_plan_id
        subscription.updated_at = datetime.utcnow()

        # Mark adjustment as applied
        adjustment.applied = datetime.utcnow()

        self.db.commit()
        self.db.refresh(subscription)
        self.db.refresh(adjustment)

        return subscription, adjustment

    def get_adjustment(self, adjustment_id: str) -> Optional[ProratedAdjustment]:
        """
        Get proration adjustment by ID.

        Args:
            adjustment_id: Adjustment ID

        Returns:
            ProratedAdjustment or None
        """
        return (
            self.db.query(ProratedAdjustment)
            .filter_by(id=adjustment_id)
            .first()
        )

    def get_tenant_adjustments(
        self,
        tenant_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[list, int]:
        """
        Get proration adjustments for tenant (paginated).

        Args:
            tenant_id: Tenant ID
            limit: Max results
            offset: Results to skip

        Returns:
            Tuple of (adjustments list, total count)
        """
        query = self.db.query(ProratedAdjustment).filter_by(tenant_id=tenant_id)
        total_count = query.count()

        adjustments = (
            query
            .order_by(ProratedAdjustment.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        return adjustments, total_count

    def get_subscription_adjustments(
        self,
        subscription_id: str,
    ) -> list:
        """
        Get all adjustments for a subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            List of adjustments
        """
        return (
            self.db.query(ProratedAdjustment)
            .filter_by(subscription_id=subscription_id)
            .order_by(ProratedAdjustment.created_at.desc())
            .all()
        )

    def calculate_daily_rate(self, plan: Plan) -> int:
        """
        Calculate daily cost rate for a plan.

        Uses simple 30-day month calculation.

        Args:
            plan: Plan object

        Returns:
            Daily rate in cents
        """
        return plan.monthly_price_cents // 30

    def calculate_remaining_period_cost(
        self,
        plan: Plan,
        days_remaining: int,
    ) -> int:
        """
        Calculate cost for remaining period on plan.

        Args:
            plan: Plan object
            days_remaining: Days left in billing period

        Returns:
            Cost in cents
        """
        daily_rate = self.calculate_daily_rate(plan)
        return daily_rate * days_remaining

    def should_charge_for_upgrade(
        self,
        old_plan: Plan,
        new_plan: Plan,
    ) -> bool:
        """
        Determine if upgrade should result in charge.

        Args:
            old_plan: Previous plan
            new_plan: New plan

        Returns:
            True if new plan costs more
        """
        return new_plan.monthly_price_cents > old_plan.monthly_price_cents

    def should_credit_for_downgrade(
        self,
        old_plan: Plan,
        new_plan: Plan,
    ) -> bool:
        """
        Determine if downgrade should result in credit.

        Args:
            old_plan: Previous plan
            new_plan: New plan

        Returns:
            True if new plan costs less
        """
        return new_plan.monthly_price_cents < old_plan.monthly_price_cents

    def get_adjustment_summary(self, tenant_id: str) -> dict:
        """
        Get summary of prorated adjustments for tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Dictionary with adjustment statistics
        """
        adjustments = (
            self.db.query(ProratedAdjustment)
            .filter_by(tenant_id=tenant_id)
            .all()
        )

        total_credits = sum(a.credit_cents for a in adjustments)
        total_charges = sum(a.charge_cents for a in adjustments)

        upgrades = len([a for a in adjustments if a.proration_type == ProrationType.UPGRADE])
        downgrades = len([a for a in adjustments if a.proration_type == ProrationType.DOWNGRADE])

        return {
            "tenant_id": tenant_id,
            "total_adjustments": len(adjustments),
            "upgrades": upgrades,
            "downgrades": downgrades,
            "total_credits_cents": total_credits,
            "total_credits_dollars": round(total_credits / 100, 2),
            "total_charges_cents": total_charges,
            "total_charges_dollars": round(total_charges / 100, 2),
            "net_adjustment_cents": total_charges - total_credits,
            "net_adjustment_dollars": round((total_charges - total_credits) / 100, 2),
        }
