"""Overage service - tracks and bills usage beyond plan quotas."""

from typing import Optional, Tuple, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.models_overage import OverageCharge, OveragePolicy, OverageStatus
from app.models import Tenant, Subscription, Plan, UsageEvent
from app.utils.db_helpers import generate_id, get_current_billing_period
from app.config_pricing import PricingConfig


class OverageService:
    """Service for overage billing and tracking."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def check_and_create_overage_charges(
        self,
        tenant_id: str,
        billing_period: Optional[str] = None,
    ) -> List[OverageCharge]:
        """
        Check for overage usage and create charges.

        Compares actual usage against plan quotas and creates
        OverageCharge records for any usage beyond limits.

        Args:
            tenant_id: Tenant ID
            billing_period: Billing period (default: current)

        Returns:
            List of created OverageCharge objects
        """
        if not billing_period:
            billing_period = get_current_billing_period()

        charges = []

        # Get tenant and subscription
        tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            return charges

        subscription = (
            self.db.query(Subscription)
            .filter_by(tenant_id=tenant_id)
            .first()
        )
        if not subscription:
            return charges

        # Get plan
        plan = self.db.query(Plan).filter_by(id=subscription.plan_id).first()
        if not plan:
            return charges

        # Get overage policy for plan
        policy = (
            self.db.query(OveragePolicy)
            .filter_by(plan_id=plan.id)
            .first()
        )
        if not policy or not policy.allows_overage:
            return charges

        # Check API calls
        api_call_usage = (
            self.db.query(UsageEvent)
            .filter_by(
                tenant_id=tenant_id,
                usage_type="api_calls",
                billing_period=billing_period,
            )
            .with_entities(UsageEvent.quantity)
        )
        api_call_total = sum(q[0] for q in api_call_usage) or 0

        if api_call_total > plan.api_calls_limit:
            overage_qty = api_call_total - plan.api_calls_limit
            charge = self._create_overage_charge(
                tenant_id=tenant_id,
                subscription_id=subscription.id,
                billing_period=billing_period,
                usage_type="api_calls",
                quota_limit=plan.api_calls_limit,
                quota_used=plan.api_calls_limit,
                overage_quantity=overage_qty,
                unit_price_cents=policy.api_calls_overage_price_cents,
            )
            charges.append(charge)

        # Check AI tokens
        token_usage = (
            self.db.query(UsageEvent)
            .filter_by(
                tenant_id=tenant_id,
                usage_type="ai_tokens",
                billing_period=billing_period,
            )
            .with_entities(UsageEvent.quantity)
        )
        token_total = sum(q[0] for q in token_usage) or 0

        if token_total > plan.ai_tokens_limit:
            overage_qty = token_total - plan.ai_tokens_limit
            charge = self._create_overage_charge(
                tenant_id=tenant_id,
                subscription_id=subscription.id,
                billing_period=billing_period,
                usage_type="ai_tokens",
                quota_limit=plan.ai_tokens_limit,
                quota_used=plan.ai_tokens_limit,
                overage_quantity=overage_qty,
                unit_price_cents=policy.ai_tokens_overage_price_cents,
            )
            charges.append(charge)

        return charges

    def _create_overage_charge(
        self,
        tenant_id: str,
        subscription_id: str,
        billing_period: str,
        usage_type: str,
        quota_limit: int,
        quota_used: int,
        overage_quantity: int,
        unit_price_cents: int,
    ) -> OverageCharge:
        """
        Create overage charge record.

        Args:
            tenant_id: Tenant ID
            subscription_id: Subscription ID
            billing_period: Billing period
            usage_type: Type of usage
            quota_limit: Plan quota limit
            quota_used: Used within quota
            overage_quantity: Quantity over quota
            unit_price_cents: Per-unit overage price

        Returns:
            Created OverageCharge
        """
        total_cost = overage_quantity * unit_price_cents

        # Check if charge already exists for this period/type
        existing = (
            self.db.query(OverageCharge)
            .filter_by(
                tenant_id=tenant_id,
                billing_period=billing_period,
                usage_type=usage_type,
            )
            .first()
        )

        if existing:
            # Update existing charge
            existing.overage_quantity = overage_quantity
            existing.overage_total_cost_cents = total_cost
            self.db.commit()
            self.db.refresh(existing)
            return existing

        # Create new charge
        charge = OverageCharge(
            id=generate_id(),
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            billing_period=billing_period,
            usage_type=usage_type,
            quota_limit=quota_limit,
            quota_used=quota_used,
            overage_quantity=overage_quantity,
            overage_unit_price_cents=unit_price_cents,
            overage_total_cost_cents=total_cost,
            detected_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

        self.db.add(charge)
        self.db.commit()
        self.db.refresh(charge)

        return charge

    def get_charge(self, charge_id: str) -> Optional[OverageCharge]:
        """
        Get overage charge by ID.

        Args:
            charge_id: Charge ID

        Returns:
            OverageCharge or None
        """
        return self.db.query(OverageCharge).filter_by(id=charge_id).first()

    def get_tenant_charges(
        self,
        tenant_id: str,
        billing_period: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[OverageCharge], int]:
        """
        Get overage charges for tenant (paginated).

        Args:
            tenant_id: Tenant ID
            billing_period: Optional filter by period
            limit: Max results
            offset: Results to skip

        Returns:
            Tuple of (charges list, total count)
        """
        query = self.db.query(OverageCharge).filter_by(tenant_id=tenant_id)

        if billing_period:
            query = query.filter_by(billing_period=billing_period)

        total_count = query.count()

        charges = (
            query
            .order_by(OverageCharge.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        return charges, total_count

    def get_period_overage_summary(
        self,
        tenant_id: str,
        billing_period: Optional[str] = None,
    ) -> dict:
        """
        Get overage summary for billing period.

        Args:
            tenant_id: Tenant ID
            billing_period: Billing period (default: current)

        Returns:
            Dictionary with summary statistics
        """
        if not billing_period:
            billing_period = get_current_billing_period()

        charges = (
            self.db.query(OverageCharge)
            .filter_by(tenant_id=tenant_id, billing_period=billing_period)
            .all()
        )

        total_cost = sum(c.overage_total_cost_cents for c in charges)
        total_qty = sum(c.overage_quantity for c in charges)
        invoiced_cost = sum(
            c.overage_total_cost_cents for c in charges if c.invoiced
        )
        pending_cost = total_cost - invoiced_cost

        api_cost = sum(
            c.overage_total_cost_cents for c in charges if c.usage_type == "api_calls"
        )
        token_cost = sum(
            c.overage_total_cost_cents for c in charges if c.usage_type == "ai_tokens"
        )

        return {
            "billing_period": billing_period,
            "total_overage_charges_cents": total_cost,
            "total_overage_charges_dollars": round(total_cost / 100, 2),
            "total_overage_quantity": total_qty,
            "api_call_overage_cents": api_cost,
            "token_overage_cents": token_cost,
            "invoiced_cents": invoiced_cost,
            "pending_cents": pending_cost,
            "charge_count": len(charges),
        }

    def mark_charge_invoiced(self, charge_id: str, invoice_id: str) -> OverageCharge:
        """
        Mark overage charge as invoiced.

        Args:
            charge_id: Charge ID
            invoice_id: Invoice ID

        Returns:
            Updated OverageCharge

        Raises:
            ValueError: If charge not found
        """
        charge = self.get_charge(charge_id)
        if not charge:
            raise ValueError(f"Charge {charge_id} not found")

        charge.invoiced = True
        charge.invoice_id = invoice_id

        self.db.commit()
        self.db.refresh(charge)

        return charge

    def get_or_create_policy(self, plan_id: str) -> OveragePolicy:
        """
        Get or create overage policy for plan.

        Args:
            plan_id: Plan ID

        Returns:
            OveragePolicy
        """
        policy = (
            self.db.query(OveragePolicy)
            .filter_by(plan_id=plan_id)
            .first()
        )

        if not policy:
            policy = OveragePolicy(
                id=generate_id(),
                plan_id=plan_id,
                allows_overage=False,
                api_calls_overage_price_cents=0,
                ai_tokens_overage_price_cents=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            self.db.add(policy)
            self.db.commit()
            self.db.refresh(policy)

        return policy

    def update_policy(
        self,
        plan_id: str,
        allows_overage: Optional[bool] = None,
        api_calls_price: Optional[int] = None,
        tokens_price: Optional[int] = None,
        max_amount: Optional[int] = None,
        max_quantity: Optional[int] = None,
        suspend_on_exceeded: Optional[bool] = None,
    ) -> OveragePolicy:
        """
        Update overage policy for plan.

        Args:
            plan_id: Plan ID
            allows_overage: Allow overages
            api_calls_price: API call overage price
            tokens_price: Token overage price
            max_amount: Max overage charge
            max_quantity: Max overage quantity
            suspend_on_exceeded: Suspend on limit exceeded

        Returns:
            Updated OveragePolicy
        """
        policy = self.get_or_create_policy(plan_id)

        if allows_overage is not None:
            policy.allows_overage = allows_overage
        if api_calls_price is not None:
            policy.api_calls_overage_price_cents = api_calls_price
        if tokens_price is not None:
            policy.ai_tokens_overage_price_cents = tokens_price
        if max_amount is not None:
            policy.max_overage_amount_cents = max_amount
        if max_quantity is not None:
            policy.max_overage_quantity = max_quantity
        if suspend_on_exceeded is not None:
            policy.suspend_on_overage_exceeded = suspend_on_exceeded

        policy.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(policy)

        return policy

    def get_overage_status(
        self,
        subscription_id: str,
        billing_period: Optional[str] = None,
    ) -> dict:
        """
        Get current overage status for subscription.

        Args:
            subscription_id: Subscription ID
            billing_period: Billing period (default: current)

        Returns:
            Dictionary with overage status
        """
        if not billing_period:
            billing_period = get_current_billing_period()

        subscription = (
            self.db.query(Subscription)
            .filter_by(id=subscription_id)
            .first()
        )
        if not subscription:
            return {}

        plan = self.db.query(Plan).filter_by(id=subscription.plan_id).first()
        if not plan:
            return {}

        policy = (
            self.db.query(OveragePolicy)
            .filter_by(plan_id=plan.id)
            .first()
        )

        charges = (
            self.db.query(OverageCharge)
            .filter_by(
                subscription_id=subscription_id,
                billing_period=billing_period,
            )
            .all()
        )

        total_cost = sum(c.overage_total_cost_cents for c in charges)
        total_qty = sum(c.overage_quantity for c in charges)

        will_suspend = False
        if policy and policy.suspend_on_overage_exceeded:
            if policy.max_overage_amount_cents and total_cost > policy.max_overage_amount_cents:
                will_suspend = True
            if policy.max_overage_quantity and total_qty > policy.max_overage_quantity:
                will_suspend = True

        message = "No overages"
        if charges:
            message = f"{total_qty} units over quota, ${total_cost/100:.2f} in charges"

        return {
            "subscription_id": subscription_id,
            "allows_overage": policy.allows_overage if policy else False,
            "current_period_overage_cents": total_cost,
            "current_period_overage_dollars": round(total_cost / 100, 2),
            "current_period_overage_quantity": total_qty,
            "max_allowed_cents": policy.max_overage_amount_cents if policy else None,
            "max_allowed_quantity": policy.max_overage_quantity if policy else None,
            "will_suspend": will_suspend,
            "message": message,
        }
