"""Usage service - business logic for usage metering operations."""

from typing import Optional, Dict, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import UsageEvent, Tenant, Plan
from app.repositories.usage_repository import UsageRepository
from app.services.tenant_service import TenantService
from app.utils.db_helpers import get_current_billing_period


class UsageService:
    """Business logic for usage metering operations."""

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.repo = UsageRepository(db)
        self.tenant_service = TenantService(db)

    def record_usage(
        self,
        tenant_id: str,
        usage_type: str,
        quantity: int,
        idempotency_key: str,
        cost_cents: Optional[int] = None,
    ) -> Tuple[UsageEvent, bool]:
        """
        Record usage event with idempotency guarantee.

        If same idempotency key is used, returns cached result (no duplicate created).

        Args:
            tenant_id: Tenant ID
            usage_type: Type ('api_calls' or 'ai_tokens')
            quantity: Quantity of usage
            idempotency_key: Unique key for idempotency
            cost_cents: Cost in cents (optional)

        Returns:
            Tuple of (UsageEvent, is_duplicate)
            - is_duplicate=False: New event created
            - is_duplicate=True: Cached result returned (idempotent)

        Raises:
            ValueError: If tenant doesn't exist or invalid usage type
        """
        # Verify tenant exists
        tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Validate usage type
        if usage_type not in ("api_calls", "ai_tokens"):
            raise ValueError(f"Invalid usage type: {usage_type}")

        # Validate quantity
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {quantity}")

        # Check for duplicate using idempotency key
        existing = self.repo.get_by_idempotency_key(tenant_id, idempotency_key)
        if existing:
            # Idempotent: return cached result
            return existing, True

        # Create new event
        try:
            event = self.repo.create(
                tenant_id=tenant_id,
                usage_type=usage_type,
                quantity=quantity,
                idempotency_key=idempotency_key,
                cost_cents=cost_cents,
            )
            return event, False
        except IntegrityError as e:
            # Race condition: another thread created it first
            # Retry lookup
            self.db.rollback()
            existing = self.repo.get_by_idempotency_key(tenant_id, idempotency_key)
            if existing:
                return existing, True
            # Unexpected error
            raise ValueError(f"Failed to create usage event: {str(e)}")

    def check_quota(
        self,
        tenant_id: str,
        usage_type: str,
        requested_quantity: int,
    ) -> Dict:
        """
        Check if tenant can use requested quantity against their plan quota.

        Args:
            tenant_id: Tenant ID
            usage_type: Type of usage ('api_calls' or 'ai_tokens')
            requested_quantity: Quantity requested

        Returns:
            Dict with:
            - allowed: bool (can proceed)
            - current: int (current usage)
            - limit: int (plan limit)
            - remaining: int (remaining quota)
            - percent_used: float (percentage of quota used)

        Raises:
            ValueError: If tenant or plan not found
        """
        # Get tenant and plan
        tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        plan = self.db.query(Plan).filter_by(id=tenant.plan_id).first()
        if not plan:
            raise ValueError(f"Plan {tenant.plan_id} not found")

        # Get limit from plan
        if usage_type == "api_calls":
            limit = plan.api_calls_limit
        elif usage_type == "ai_tokens":
            limit = plan.ai_tokens_limit
        else:
            raise ValueError(f"Invalid usage type: {usage_type}")

        # Get current usage in billing period
        current = self.repo.get_current_period_usage(tenant_id, usage_type)

        # Check if quota would be exceeded
        total_if_allowed = current + requested_quantity
        allowed = total_if_allowed <= limit

        # Calculate remaining
        remaining = max(0, limit - current)

        # Calculate percentage
        percent_used = (current / limit * 100) if limit > 0 else 0

        return {
            "allowed": allowed,
            "current": current,
            "limit": limit,
            "remaining": remaining,
            "requested": requested_quantity,
            "total_if_allowed": total_if_allowed,
            "percent_used": round(percent_used, 2),
        }

    def get_usage_summary(self, tenant_id: str) -> Dict:
        """
        Get usage summary for tenant in current billing period.

        Args:
            tenant_id: Tenant ID

        Returns:
            Dict with usage summary for both api_calls and ai_tokens
        """
        # Get tenant and plan
        tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        plan = self.db.query(Plan).filter_by(id=tenant.plan_id).first()
        if not plan:
            raise ValueError(f"Plan {tenant.plan_id} not found")

        current_period = get_current_billing_period()

        # API calls summary
        api_calls_used = self.repo.get_current_period_usage(
            tenant_id, "api_calls"
        )
        api_calls_limit = plan.api_calls_limit
        api_calls_percent = (
            (api_calls_used / api_calls_limit * 100)
            if api_calls_limit > 0
            else 0
        )

        # AI tokens summary
        tokens_used = self.repo.get_current_period_usage(tenant_id, "ai_tokens")
        tokens_limit = plan.ai_tokens_limit
        tokens_percent = (tokens_used / tokens_limit * 100) if tokens_limit > 0 else 0

        # Cost summary
        cost_cents = self.repo.get_current_period_cost(tenant_id)

        return {
            "billing_period": current_period,
            "plan": {
                "id": plan.id,
                "name": plan.name,
                "monthly_cost_cents": plan.monthly_cost_cents,
            },
            "api_calls": {
                "used": api_calls_used,
                "limit": api_calls_limit,
                "remaining": max(0, api_calls_limit - api_calls_used),
                "percent_used": round(api_calls_percent, 2),
            },
            "ai_tokens": {
                "used": tokens_used,
                "limit": tokens_limit,
                "remaining": max(0, tokens_limit - tokens_used),
                "percent_used": round(tokens_percent, 2),
            },
            "cost": {
                "total_cents": cost_cents,
                "total_dollars": round(cost_cents / 100, 2),
            },
        }

    def get_usage_events(
        self,
        tenant_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict:
        """
        Get usage events for tenant in current billing period (paginated).

        Args:
            tenant_id: Tenant ID
            limit: Max number of results
            offset: Number of results to skip

        Returns:
            Dict with events and metadata
        """
        # Get tenant
        tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        current_period = get_current_billing_period()

        # Get events
        events = self.repo.get_tenant_events_in_period(
            tenant_id,
            current_period,
            limit=limit,
            offset=offset,
        )

        # Get total count
        total_count = self.repo.count_tenant_events_in_period(
            tenant_id,
            current_period,
        )

        return {
            "billing_period": current_period,
            "events": [
                {
                    "id": event.id,
                    "usage_type": event.usage_type,
                    "quantity": event.quantity,
                    "cost_cents": event.cost_cents,
                    "created_at": event.created_at.isoformat(),
                }
                for event in events
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total_count,
                "returned": len(events),
            },
        }

    def reset_period_usage(self, tenant_id: str, billing_period: str) -> int:
        """
        Reset (delete) all usage events for a tenant in a period.

        WARNING: This is for testing/admin only. Deletes actual usage data.

        Args:
            tenant_id: Tenant ID
            billing_period: Billing period YYYY-MM to reset

        Returns:
            Number of events deleted
        """
        # Get all events in period
        events = self.repo.get_tenant_events_in_period(
            tenant_id,
            billing_period,
            limit=10000,  # Get all
        )

        # Delete each event
        count = 0
        for event in events:
            if self.repo.delete_event(event.id):
                count += 1

        return count
