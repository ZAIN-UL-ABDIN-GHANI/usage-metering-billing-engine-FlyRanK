"""Usage repository for database operations."""

from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import UsageEvent
from app.utils.db_helpers import generate_id, get_current_billing_period


class UsageRepository:
    """Data access layer for usage event operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def create(
        self,
        tenant_id: str,
        usage_type: str,
        quantity: int,
        idempotency_key: str,
        cost_cents: Optional[int] = None,
        billing_period: Optional[str] = None,
    ) -> UsageEvent:
        """
        Create a new usage event.

        Uses database UNIQUE constraint on (tenant_id, idempotency_key)
        to guarantee idempotency - same key cannot create duplicate events.

        Args:
            tenant_id: Tenant ID
            usage_type: Type of usage ('api_calls' or 'ai_tokens')
            quantity: Quantity of usage
            idempotency_key: Unique key for idempotency
            cost_cents: Cost in cents (optional)
            billing_period: Billing period YYYY-MM (optional, defaults to current)

        Returns:
            Created UsageEvent object

        Raises:
            IntegrityError: If idempotency key already exists for tenant
        """
        if billing_period is None:
            billing_period = get_current_billing_period()

        usage_event = UsageEvent(
            id=generate_id(),
            tenant_id=tenant_id,
            usage_type=usage_type,
            quantity=quantity,
            idempotency_key=idempotency_key,
            cost_cents=cost_cents,
            billing_period=billing_period,
            created_at=datetime.utcnow(),
        )
        self.db.add(usage_event)
        self.db.commit()
        self.db.refresh(usage_event)
        return usage_event

    def get_by_idempotency_key(
        self,
        tenant_id: str,
        idempotency_key: str,
    ) -> Optional[UsageEvent]:
        """
        Get usage event by idempotency key.

        Args:
            tenant_id: Tenant ID
            idempotency_key: Idempotency key

        Returns:
            UsageEvent object or None if not found
        """
        return (
            self.db.query(UsageEvent)
            .filter_by(tenant_id=tenant_id, idempotency_key=idempotency_key)
            .first()
        )

    def get_by_id(self, usage_event_id: str) -> Optional[UsageEvent]:
        """
        Get usage event by ID.

        Args:
            usage_event_id: Usage event ID

        Returns:
            UsageEvent object or None if not found
        """
        return self.db.query(UsageEvent).filter_by(id=usage_event_id).first()

    def get_tenant_usage_in_period(
        self,
        tenant_id: str,
        usage_type: str,
        billing_period: str,
    ) -> int:
        """
        Get total usage for tenant in billing period by type.

        Args:
            tenant_id: Tenant ID
            usage_type: Type of usage ('api_calls' or 'ai_tokens')
            billing_period: Billing period YYYY-MM

        Returns:
            Total quantity used
        """
        result = (
            self.db.query(UsageEvent)
            .filter_by(
                tenant_id=tenant_id,
                usage_type=usage_type,
                billing_period=billing_period,
            )
            .all()
        )
        return sum(event.quantity for event in result)

    def get_tenant_cost_in_period(
        self,
        tenant_id: str,
        billing_period: str,
    ) -> int:
        """
        Get total cost for tenant in billing period (in cents).

        Args:
            tenant_id: Tenant ID
            billing_period: Billing period YYYY-MM

        Returns:
            Total cost in cents
        """
        result = (
            self.db.query(UsageEvent)
            .filter_by(tenant_id=tenant_id, billing_period=billing_period)
            .all()
        )
        total = sum(
            event.cost_cents for event in result if event.cost_cents is not None
        )
        return total

    def get_tenant_events_in_period(
        self,
        tenant_id: str,
        billing_period: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[UsageEvent]:
        """
        Get all usage events for tenant in billing period (paginated).

        Args:
            tenant_id: Tenant ID
            billing_period: Billing period YYYY-MM
            limit: Max number of results
            offset: Number of results to skip

        Returns:
            List of UsageEvent objects
        """
        return (
            self.db.query(UsageEvent)
            .filter_by(tenant_id=tenant_id, billing_period=billing_period)
            .order_by(UsageEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def count_tenant_events_in_period(
        self,
        tenant_id: str,
        billing_period: str,
    ) -> int:
        """
        Count usage events for tenant in billing period.

        Args:
            tenant_id: Tenant ID
            billing_period: Billing period YYYY-MM

        Returns:
            Number of events
        """
        return (
            self.db.query(UsageEvent)
            .filter_by(tenant_id=tenant_id, billing_period=billing_period)
            .count()
        )

    def get_current_period_usage(
        self,
        tenant_id: str,
        usage_type: str,
    ) -> int:
        """
        Get usage for current billing period.

        Args:
            tenant_id: Tenant ID
            usage_type: Type of usage

        Returns:
            Total quantity in current period
        """
        current_period = get_current_billing_period()
        return self.get_tenant_usage_in_period(
            tenant_id,
            usage_type,
            current_period,
        )

    def get_current_period_cost(self, tenant_id: str) -> int:
        """
        Get cost for current billing period (in cents).

        Args:
            tenant_id: Tenant ID

        Returns:
            Total cost in cents for current period
        """
        current_period = get_current_billing_period()
        return self.get_tenant_cost_in_period(tenant_id, current_period)

    def delete_event(self, usage_event_id: str) -> bool:
        """
        Delete a usage event (hard delete for testing/cleanup).

        Args:
            usage_event_id: Usage event ID

        Returns:
            True if deleted, False if not found
        """
        event = self.get_by_id(usage_event_id)
        if not event:
            return False
        self.db.delete(event)
        self.db.commit()
        return True
