"""Stripe service - manages Stripe checkout and subscription operations."""

from typing import Optional, Dict, Tuple
from datetime import datetime
import hmac
import hashlib
import json
import os

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Tenant, Plan, Subscription
from app.repositories.tenant_repository import TenantRepository
from app.utils.db_helpers import generate_id, get_current_billing_period


class StripeService:
    """Service for Stripe integration - checkout and subscriptions."""

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.tenant_repo = TenantRepository(db)
        self.stripe_api_key = settings.stripe_secret_key
        self.webhook_secret = settings.stripe_webhook_secret

    def create_checkout_session(
        self,
        tenant_id: str,
        plan_id: str,
        success_url: str,
        cancel_url: str,
    ) -> Dict:
        """
        Create Stripe Checkout session.

        Args:
            tenant_id: Tenant ID
            plan_id: Target plan ID (to upgrade/downgrade to)
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel

        Returns:
            Dict with:
            - checkout_url: URL to redirect user to Stripe Checkout
            - session_id: Stripe session ID
            - expires_at: Session expiration time

        Raises:
            ValueError: If tenant or plan not found
        """
        # Get tenant
        tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Get target plan
        plan = self.db.query(Plan).filter_by(id=plan_id).first()
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        # Create session data
        # In test mode, we simulate Stripe Checkout session
        session_id = generate_id()
        checkout_url = (
            f"{settings.stripe_checkout_base_url}?session_id={session_id}"
        )

        # Store session reference (in production, this would be from Stripe)
        # For test mode, we create a minimal session record
        session_data = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "plan_id": plan_id,
            "status": "open",
            "expires_at": datetime.utcnow().timestamp() + 3600,  # 1 hour
            "created_at": datetime.utcnow().isoformat(),
        }

        return {
            "checkout_url": checkout_url,
            "session_id": session_id,
            "expires_at": session_data["expires_at"],
            "plan_id": plan_id,
        }

    def handle_checkout_session_completed(
        self,
        session_id: str,
        customer_id: str,
        subscription_id: str,
        plan_id: str,
    ) -> Tuple[Subscription, bool]:
        """
        Handle checkout.session.completed webhook event.

        Updates tenant's subscription and plan based on Stripe event.

        Args:
            session_id: Stripe checkout session ID
            customer_id: Stripe customer ID
            subscription_id: Stripe subscription ID (from event)
            plan_id: Plan ID to upgrade to

        Returns:
            Tuple of (Subscription, is_new)
            - Subscription: Created or updated subscription
            - is_new: True if new subscription, False if updated

        Raises:
            ValueError: If tenant or plan not found
        """
        # Get plan
        plan = self.db.query(Plan).filter_by(id=plan_id).first()
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        # Find tenant by plan (in test mode, we look up by session or use direct ID)
        # For production, we'd look up customer in our database
        # For now, we'll assume tenant_id passed separately (from session context)
        # This is handled in the route handler which has authentication context

        # Get current subscription
        existing_sub = self.db.query(Subscription).filter_by(
            stripe_subscription_id=subscription_id
        ).first()

        if existing_sub:
            # Update existing subscription
            existing_sub.status = "active"
            existing_sub.stripe_subscription_id = subscription_id
            existing_sub.stripe_customer_id = customer_id
            existing_sub.current_period_start = datetime.utcnow()
            existing_sub.current_period_end = None  # Will be set by webhook
            existing_sub.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing_sub)
            return existing_sub, False

        else:
            # This shouldn't happen in normal flow (should have subscription object)
            # But handle gracefully
            raise ValueError(
                f"Subscription {subscription_id} not found in database"
            )

    def handle_subscription_updated(
        self,
        subscription_id: str,
        customer_id: str,
        status: str,
        current_period_end: Optional[int] = None,
    ) -> Subscription:
        """
        Handle customer.subscription.updated webhook event.

        Updates subscription status and period information.

        Args:
            subscription_id: Stripe subscription ID
            customer_id: Stripe customer ID
            status: Subscription status (active, past_due, canceled, etc.)
            current_period_end: Unix timestamp of period end

        Returns:
            Updated Subscription object

        Raises:
            ValueError: If subscription not found
        """
        # Get subscription
        subscription = self.db.query(Subscription).filter_by(
            stripe_subscription_id=subscription_id
        ).first()

        if not subscription:
            raise ValueError(
                f"Subscription {subscription_id} not found in database"
            )

        # Update subscription
        subscription.status = status
        subscription.stripe_customer_id = customer_id
        if current_period_end:
            subscription.current_period_end = datetime.fromtimestamp(
                current_period_end
            )
        subscription.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def handle_subscription_deleted(
        self,
        subscription_id: str,
    ) -> Subscription:
        """
        Handle customer.subscription.deleted webhook event.

        Marks subscription as canceled.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Updated Subscription object

        Raises:
            ValueError: If subscription not found
        """
        # Get subscription
        subscription = self.db.query(Subscription).filter_by(
            stripe_subscription_id=subscription_id
        ).first()

        if not subscription:
            raise ValueError(
                f"Subscription {subscription_id} not found in database"
            )

        # Mark as canceled
        subscription.status = "canceled"
        subscription.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature_header: str,
    ) -> bool:
        """
        Verify Stripe webhook signature.

        Uses HMAC-SHA256 to verify the webhook came from Stripe.

        Args:
            payload: Raw webhook request body (bytes)
            signature_header: Stripe-Signature header value

        Returns:
            True if signature is valid, False otherwise

        Security Note:
            Always use constant-time comparison to prevent timing attacks
        """
        if not self.webhook_secret:
            # If no webhook secret configured, cannot verify
            # This should only happen in development
            return False

        # Stripe signature format: t=timestamp,v1=signature
        try:
            # Parse signature header
            parts = signature_header.split(",")
            timestamp = None
            signature = None

            for part in parts:
                if part.startswith("t="):
                    timestamp = part[2:]
                elif part.startswith("v1="):
                    signature = part[3:]

            if not timestamp or not signature:
                return False

            # Create signed content: timestamp.payload
            signed_content = f"{timestamp}.{payload.decode('utf-8')}"

            # Compute HMAC
            expected_signature = hmac.new(
                self.webhook_secret.encode(),
                signed_content.encode(),
                hashlib.sha256,
            ).hexdigest()

            # Constant-time comparison
            return hmac.compare_digest(expected_signature, signature)

        except (ValueError, AttributeError):
            return False

    def get_tenant_from_checkout_session(
        self,
        session_id: str,
    ) -> Optional[str]:
        """
        Get tenant ID from checkout session.

        In test mode, we can store this in memory or database.
        In production, Stripe stores this in metadata.

        Args:
            session_id: Stripe checkout session ID

        Returns:
            Tenant ID or None if not found
        """
        # In test mode, look up session in database
        # This is a simplified implementation
        # In production, you'd use Stripe API to fetch session details
        # For now, return None and let webhook handler figure it out
        return None

    def create_subscription_for_tenant(
        self,
        tenant_id: str,
        plan_id: str,
        stripe_subscription_id: str,
        stripe_customer_id: str,
    ) -> Subscription:
        """
        Create subscription record for tenant.

        Called after Stripe Checkout completes.

        Args:
            tenant_id: Tenant ID
            plan_id: Plan ID
            stripe_subscription_id: Stripe subscription ID
            stripe_customer_id: Stripe customer ID

        Returns:
            Created Subscription object

        Raises:
            ValueError: If tenant or plan not found
        """
        # Get tenant
        tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Get plan
        plan = self.db.query(Plan).filter_by(id=plan_id).first()
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        # Create subscription
        subscription = Subscription(
            id=generate_id(),
            tenant_id=tenant_id,
            plan_id=plan_id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            status="active",
            current_period_start=datetime.utcnow(),
            current_period_end=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def get_subscription_by_stripe_id(
        self,
        stripe_subscription_id: str,
    ) -> Optional[Subscription]:
        """
        Get subscription by Stripe subscription ID.

        Args:
            stripe_subscription_id: Stripe subscription ID

        Returns:
            Subscription or None if not found
        """
        return self.db.query(Subscription).filter_by(
            stripe_subscription_id=stripe_subscription_id
        ).first()

    def update_tenant_plan(
        self,
        tenant_id: str,
        plan_id: str,
    ) -> Tenant:
        """
        Update tenant's plan.

        Called after subscription is confirmed.

        Args:
            tenant_id: Tenant ID
            plan_id: New plan ID

        Returns:
            Updated Tenant object

        Raises:
            ValueError: If tenant or plan not found
        """
        # Get tenant
        tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Get plan (verify it exists)
        plan = self.db.query(Plan).filter_by(id=plan_id).first()
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        # Update tenant
        tenant.plan_id = plan_id
        self.db.commit()
        self.db.refresh(tenant)
        return tenant
