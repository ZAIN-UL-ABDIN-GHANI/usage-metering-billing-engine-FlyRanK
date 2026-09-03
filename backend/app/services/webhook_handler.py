"""Webhook event handler - manages Stripe webhook processing and deduplication."""

from typing import Dict, Optional, Tuple
from datetime import datetime
import json

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import WebhookEvent, Subscription, Tenant, Plan
from app.services.stripe_service import StripeService
from app.utils.db_helpers import generate_id


class WebhookEventHandler:
    """Handles Stripe webhook events with deduplication."""

    def __init__(self, db: Session):
        """Initialize handler with database session."""
        self.db = db
        self.stripe_service = StripeService(db)

    def process_webhook(
        self,
        event_type: str,
        stripe_event_id: str,
        event_data: Dict,
    ) -> Tuple[bool, str]:
        """
        Process webhook event with deduplication.

        If same stripe_event_id seen before, returns cached result.
        Prevents double-processing on Stripe retries.

        Args:
            event_type: Type of event (checkout.session.completed, etc.)
            stripe_event_id: Unique Stripe event ID
            event_data: Event data from Stripe

        Returns:
            Tuple of (success, message)
            - success: True if processed successfully
            - message: Description of what happened

        Raises:
            ValueError: If event processing fails
        """
        # Check for duplicate
        existing = self.get_webhook_event(stripe_event_id)
        if existing:
            # Already processed
            return True, f"Event {stripe_event_id} already processed (duplicate)"

        # Create webhook event record
        webhook_event = WebhookEvent(
            id=generate_id(),
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            event_data=json.dumps(event_data),
            status="processing",
            created_at=datetime.utcnow(),
        )

        try:
            self.db.add(webhook_event)
            self.db.flush()  # Flush before commit to check constraint
        except IntegrityError:
            # Another thread processed it first
            self.db.rollback()
            return True, f"Event {stripe_event_id} already processing (race condition)"

        # Process based on event type
        try:
            if event_type == "checkout.session.completed":
                self._handle_checkout_session_completed(event_data, webhook_event)

            elif event_type == "customer.subscription.updated":
                self._handle_subscription_updated(event_data, webhook_event)

            elif event_type == "customer.subscription.deleted":
                self._handle_subscription_deleted(event_data, webhook_event)

            else:
                # Unknown event type, still mark as processed
                webhook_event.status = "processed"
                webhook_event.processed_at = datetime.utcnow()
                self.db.commit()
                return True, f"Event {event_type} received but not processed (unknown type)"

            # Mark as processed
            webhook_event.status = "processed"
            webhook_event.processed_at = datetime.utcnow()
            self.db.commit()

            return True, f"Event {event_type} processed successfully"

        except Exception as e:
            # Mark as failed
            webhook_event.status = "failed"
            webhook_event.error = str(e)
            webhook_event.processed_at = datetime.utcnow()
            self.db.commit()
            raise ValueError(f"Failed to process webhook: {str(e)}")

    def _handle_checkout_session_completed(
        self,
        event_data: Dict,
        webhook_event: WebhookEvent,
    ) -> None:
        """
        Handle checkout.session.completed event.

        Creates subscription and updates tenant plan.

        Args:
            event_data: Event data from Stripe
            webhook_event: WebhookEvent database record
        """
        # Extract data from event
        session = event_data.get("data", {}).get("object", {})
        session_id = session.get("id")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        metadata = session.get("metadata", {})
        plan_id = metadata.get("plan_id")
        tenant_id = metadata.get("tenant_id")

        if not all([session_id, customer_id, subscription_id, plan_id, tenant_id]):
            raise ValueError(
                f"Incomplete checkout session data: "
                f"session_id={session_id}, customer_id={customer_id}, "
                f"subscription_id={subscription_id}, plan_id={plan_id}, tenant_id={tenant_id}"
            )

        # Get tenant and verify it exists
        tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Create subscription record
        subscription = self.stripe_service.create_subscription_for_tenant(
            tenant_id=tenant_id,
            plan_id=plan_id,
            stripe_subscription_id=subscription_id,
            stripe_customer_id=customer_id,
        )

        # Update tenant plan
        self.stripe_service.update_tenant_plan(tenant_id, plan_id)

        # Store in webhook event
        webhook_event.subscription_id = subscription.id
        webhook_event.tenant_id = tenant_id

    def _handle_subscription_updated(
        self,
        event_data: Dict,
        webhook_event: WebhookEvent,
    ) -> None:
        """
        Handle customer.subscription.updated event.

        Updates subscription status and period information.

        Args:
            event_data: Event data from Stripe
            webhook_event: WebhookEvent database record
        """
        # Extract data from event
        subscription = event_data.get("data", {}).get("object", {})
        subscription_id = subscription.get("id")
        customer_id = subscription.get("customer")
        status = subscription.get("status")
        current_period_end = subscription.get("current_period_end")

        if not all([subscription_id, customer_id, status]):
            raise ValueError(
                f"Incomplete subscription data: "
                f"subscription_id={subscription_id}, customer_id={customer_id}, status={status}"
            )

        # Update subscription
        sub = self.stripe_service.handle_subscription_updated(
            subscription_id=subscription_id,
            customer_id=customer_id,
            status=status,
            current_period_end=current_period_end,
        )

        # Store in webhook event
        webhook_event.subscription_id = sub.id
        webhook_event.tenant_id = sub.tenant_id

    def _handle_subscription_deleted(
        self,
        event_data: Dict,
        webhook_event: WebhookEvent,
    ) -> None:
        """
        Handle customer.subscription.deleted event.

        Marks subscription as canceled.

        Args:
            event_data: Event data from Stripe
            webhook_event: WebhookEvent database record
        """
        # Extract data from event
        subscription = event_data.get("data", {}).get("object", {})
        subscription_id = subscription.get("id")

        if not subscription_id:
            raise ValueError(f"Missing subscription ID in deletion event")

        # Delete subscription (mark as canceled)
        sub = self.stripe_service.handle_subscription_deleted(
            subscription_id=subscription_id
        )

        # Store in webhook event
        webhook_event.subscription_id = sub.id
        webhook_event.tenant_id = sub.tenant_id

    def get_webhook_event(
        self,
        stripe_event_id: str,
    ) -> Optional[WebhookEvent]:
        """
        Get webhook event by Stripe event ID.

        Args:
            stripe_event_id: Stripe event ID

        Returns:
            WebhookEvent or None if not found
        """
        return self.db.query(WebhookEvent).filter_by(
            stripe_event_id=stripe_event_id
        ).first()

    def get_webhook_events_by_status(
        self,
        status: str,
        limit: int = 100,
    ) -> list:
        """
        Get webhook events by status.

        Useful for monitoring failed events.

        Args:
            status: Event status (processing, processed, failed)
            limit: Max number of results

        Returns:
            List of WebhookEvent objects
        """
        return (
            self.db.query(WebhookEvent)
            .filter_by(status=status)
            .order_by(WebhookEvent.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_recent_webhook_events(
        self,
        limit: int = 50,
    ) -> list:
        """
        Get recent webhook events.

        Useful for debugging and monitoring.

        Args:
            limit: Max number of results

        Returns:
            List of WebhookEvent objects (most recent first)
        """
        return (
            self.db.query(WebhookEvent)
            .order_by(WebhookEvent.created_at.desc())
            .limit(limit)
            .all()
        )
