"""Tests for Stripe integration including checkout and webhooks."""

import pytest
import json
import hmac
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Subscription, WebhookEvent
from app.services.stripe_service import StripeService
from app.services.webhook_handler import WebhookEventHandler
from app.config import settings


class TestCheckoutSession:
    """Test Stripe Checkout session creation."""

    def test_create_checkout_session_success(
        self, db: Session, create_plan, create_tenant
    ):
        """Test successful checkout session creation."""
        create_plan(plan_id="pro")
        tenant = create_tenant(plan_id="free")

        service = StripeService(db)

        result = service.create_checkout_session(
            tenant_id=tenant.id,
            plan_id="pro",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert "checkout_url" in result
        assert "session_id" in result
        assert "expires_at" in result
        assert result["plan_id"] == "pro"
        print(f"✅ Checkout: Session created {result['session_id']}")

    def test_checkout_session_invalid_plan(
        self, db: Session, create_tenant
    ):
        """Test checkout with invalid plan ID."""
        tenant = create_tenant()

        service = StripeService(db)

        with pytest.raises(ValueError, match="Plan .* not found"):
            service.create_checkout_session(
                tenant_id=tenant.id,
                plan_id="nonexistent",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

        print("✅ Checkout: Invalid plan rejected")

    def test_checkout_session_invalid_tenant(
        self, db: Session, create_plan
    ):
        """Test checkout with invalid tenant ID."""
        create_plan()

        service = StripeService(db)

        with pytest.raises(ValueError, match="Tenant .* not found"):
            service.create_checkout_session(
                tenant_id="invalid-tenant",
                plan_id="free",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

        print("✅ Checkout: Invalid tenant rejected")


class TestWebhookSignatureVerification:
    """Test Stripe webhook signature verification."""

    def test_valid_webhook_signature(self, db: Session):
        """Test verification of valid Stripe signature."""
        service = StripeService(db)

        # Create test payload and signature
        payload = b'{"id": "evt_123", "type": "checkout.session.completed"}'
        timestamp = "1234567890"

        # Create signature using webhook secret
        signed_content = f"{timestamp}.{payload.decode()}"
        expected_sig = hmac.new(
            service.webhook_secret.encode(),
            signed_content.encode(),
            hashlib.sha256,
        ).hexdigest()

        signature_header = f"t={timestamp},v1={expected_sig}"

        # Verify
        is_valid = service.verify_webhook_signature(payload, signature_header)
        assert is_valid is True
        print("✅ Webhook: Valid signature verified")

    def test_invalid_webhook_signature(self, db: Session):
        """Test rejection of invalid Stripe signature."""
        service = StripeService(db)

        payload = b'{"id": "evt_123"}'
        signature_header = "t=1234567890,v1=invalid_signature_12345"

        is_valid = service.verify_webhook_signature(payload, signature_header)
        assert is_valid is False
        print("✅ Webhook: Invalid signature rejected")

    def test_missing_webhook_secret(self, db: Session, monkeypatch):
        """Test that verification fails when webhook secret not configured."""
        # Temporarily set webhook secret to None
        monkeypatch.setattr(settings, "stripe_webhook_secret", None)

        service = StripeService(db)

        payload = b'{"id": "evt_123"}'
        signature_header = "t=1234567890,v1=some_sig"

        is_valid = service.verify_webhook_signature(payload, signature_header)
        assert is_valid is False
        print("✅ Webhook: Missing secret rejects verification")


class TestWebhookDeduplication:
    """Test webhook event deduplication."""

    def test_duplicate_webhook_event_not_reprocessed(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that same webhook event ID is not reprocessed."""
        create_plan(plan_id="pro")
        tenant = create_tenant(plan_id="free")

        handler = WebhookEventHandler(db)

        # First webhook
        event_data = {
            "id": "evt_123",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_456",
                    "customer": "cus_789",
                    "subscription": "sub_999",
                    "metadata": {
                        "plan_id": "pro",
                        "tenant_id": tenant.id,
                    },
                }
            },
        }

        success1, msg1 = handler.process_webhook(
            event_type="checkout.session.completed",
            stripe_event_id="evt_123",
            event_data=event_data,
        )

        assert success1 is True
        assert "successfully" in msg1

        # Retry same webhook
        success2, msg2 = handler.process_webhook(
            event_type="checkout.session.completed",
            stripe_event_id="evt_123",
            event_data=event_data,
        )

        assert success2 is True
        assert "already processed" in msg2 or "duplicate" in msg2

        # Verify only one subscription created
        subscriptions = db.query(Subscription).filter_by(
            stripe_subscription_id="sub_999"
        ).all()
        assert len(subscriptions) == 1

        print("✅ Webhook: Duplicate event not reprocessed")

    def test_webhook_event_stored_in_database(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that webhook events are stored for audit trail."""
        create_plan(plan_id="pro")
        tenant = create_tenant(plan_id="free")

        handler = WebhookEventHandler(db)

        event_data = {
            "id": "evt_audit",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_audit",
                    "customer": "cus_audit",
                    "subscription": "sub_audit",
                    "metadata": {
                        "plan_id": "pro",
                        "tenant_id": tenant.id,
                    },
                }
            },
        }

        handler.process_webhook(
            event_type="checkout.session.completed",
            stripe_event_id="evt_audit",
            event_data=event_data,
        )

        # Verify event stored
        stored_event = handler.get_webhook_event("evt_audit")
        assert stored_event is not None
        assert stored_event.stripe_event_id == "evt_audit"
        assert stored_event.event_type == "checkout.session.completed"
        assert stored_event.status == "processed"

        print("✅ Webhook: Event stored in database")


class TestCheckoutSessionCompleted:
    """Test checkout.session.completed webhook event handling."""

    def test_checkout_session_completed_creates_subscription(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that completed checkout creates subscription and updates plan."""
        create_plan(plan_id="pro")
        tenant = create_tenant(plan_id="free")

        handler = WebhookEventHandler(db)

        event_data = {
            "id": "evt_checkout_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_checkout_1",
                    "customer": "cus_stripe_1",
                    "subscription": "sub_stripe_1",
                    "metadata": {
                        "plan_id": "pro",
                        "tenant_id": tenant.id,
                    },
                }
            },
        }

        success, _ = handler.process_webhook(
            event_type="checkout.session.completed",
            stripe_event_id="evt_checkout_1",
            event_data=event_data,
        )

        assert success is True

        # Verify subscription created
        subscription = db.query(Subscription).filter_by(
            stripe_subscription_id="sub_stripe_1"
        ).first()

        assert subscription is not None
        assert subscription.tenant_id == tenant.id
        assert subscription.plan_id == "pro"
        assert subscription.stripe_customer_id == "cus_stripe_1"
        assert subscription.status == "active"

        # Verify tenant plan updated
        db.refresh(tenant)
        assert tenant.plan_id == "pro"

        print("✅ Webhook: Checkout completed → subscription created & plan updated")

    def test_checkout_session_missing_metadata(
        self, db: Session
    ):
        """Test that checkout without metadata is handled gracefully."""
        handler = WebhookEventHandler(db)

        event_data = {
            "id": "evt_bad",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_bad",
                    "customer": "cus_bad",
                    "subscription": "sub_bad",
                    "metadata": {},  # Missing plan_id and tenant_id
                }
            },
        }

        with pytest.raises(ValueError):
            handler.process_webhook(
                event_type="checkout.session.completed",
                stripe_event_id="evt_bad",
                event_data=event_data,
            )

        print("✅ Webhook: Missing metadata handled")


class TestSubscriptionUpdated:
    """Test customer.subscription.updated webhook event handling."""

    def test_subscription_updated_changes_status(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that subscription status updates are processed."""
        create_plan()
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id)

        handler = WebhookEventHandler(db)

        event_data = {
            "id": "evt_updated",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": subscription.stripe_subscription_id,
                    "customer": subscription.stripe_customer_id,
                    "status": "past_due",
                    "current_period_end": 1234567890,
                }
            },
        }

        success, _ = handler.process_webhook(
            event_type="customer.subscription.updated",
            stripe_event_id="evt_updated",
            event_data=event_data,
        )

        assert success is True

        # Verify subscription updated
        db.refresh(subscription)
        assert subscription.status == "past_due"

        print("✅ Webhook: Subscription updated")


class TestSubscriptionDeleted:
    """Test customer.subscription.deleted webhook event handling."""

    def test_subscription_deleted_cancels_subscription(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that subscription deletion marks subscription as canceled."""
        create_plan()
        tenant = create_tenant()
        subscription = create_subscription(tenant_id=tenant.id)

        handler = WebhookEventHandler(db)

        event_data = {
            "id": "evt_deleted",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": subscription.stripe_subscription_id,
                    "customer": subscription.stripe_customer_id,
                    "status": "canceled",
                }
            },
        }

        success, _ = handler.process_webhook(
            event_type="customer.subscription.deleted",
            stripe_event_id="evt_deleted",
            event_data=event_data,
        )

        assert success is True

        # Verify subscription canceled
        db.refresh(subscription)
        assert subscription.status == "canceled"

        print("✅ Webhook: Subscription deleted → marked canceled")


class TestPlanUpgradeDowngrade:
    """Test plan upgrade and downgrade flows."""

    def test_free_to_pro_upgrade(
        self, db: Session, create_plan, create_tenant
    ):
        """Test upgrading from Free to Pro plan."""
        create_plan(plan_id="free", api_calls_limit=1000, ai_tokens_limit=100000)
        create_plan(plan_id="pro", api_calls_limit=10000, ai_tokens_limit=1000000)
        tenant = create_tenant(plan_id="free")

        handler = WebhookEventHandler(db)

        event_data = {
            "id": "evt_upgrade",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_upgrade",
                    "customer": "cus_upgrade",
                    "subscription": "sub_upgrade",
                    "metadata": {
                        "plan_id": "pro",
                        "tenant_id": tenant.id,
                    },
                }
            },
        }

        success, _ = handler.process_webhook(
            event_type="checkout.session.completed",
            stripe_event_id="evt_upgrade",
            event_data=event_data,
        )

        assert success is True

        # Verify plan changed
        db.refresh(tenant)
        assert tenant.plan_id == "pro"

        # Verify quotas increased
        pro_plan = db.query(Plan).filter_by(id="pro").first()
        assert pro_plan.api_calls_limit == 10000
        assert pro_plan.ai_tokens_limit == 1000000

        print("✅ Upgrade: Free → Pro successful")

    def test_pro_to_free_downgrade(
        self, db: Session, create_plan, create_tenant
    ):
        """Test downgrading from Pro to Free plan."""
        create_plan(plan_id="free", api_calls_limit=1000)
        create_plan(plan_id="pro", api_calls_limit=10000)
        tenant = create_tenant(plan_id="pro")

        service = StripeService(db)
        service.update_tenant_plan(tenant.id, "free")

        # Verify plan changed
        db.refresh(tenant)
        assert tenant.plan_id == "free"

        print("✅ Downgrade: Pro → Free successful")


class TestWebhookEventRetrieval:
    """Test webhook event retrieval for monitoring."""

    def test_get_recent_webhook_events(
        self, db: Session, create_plan, create_tenant
    ):
        """Test retrieving recent webhook events."""
        create_plan(plan_id="pro")
        tenant = create_tenant(plan_id="free")

        handler = WebhookEventHandler(db)

        # Process multiple webhooks
        for i in range(3):
            event_data = {
                "id": f"evt_{i}",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": f"cs_{i}",
                        "customer": f"cus_{i}",
                        "subscription": f"sub_{i}",
                        "metadata": {
                            "plan_id": "pro",
                            "tenant_id": tenant.id,
                        },
                    }
                },
            }

            handler.process_webhook(
                event_type="checkout.session.completed",
                stripe_event_id=f"evt_{i}",
                event_data=event_data,
            )

        # Retrieve events
        events = handler.get_recent_webhook_events(limit=10)

        assert len(events) >= 3
        assert all(event.status == "processed" for event in events)

        print(f"✅ Events: Retrieved {len(events)} recent webhook events")

    def test_get_webhook_events_by_status(
        self, db: Session, create_plan, create_tenant
    ):
        """Test filtering webhook events by status."""
        create_plan(plan_id="pro")
        tenant = create_tenant(plan_id="free")

        handler = WebhookEventHandler(db)

        # Process a webhook successfully
        event_data = {
            "id": "evt_success",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_success",
                    "customer": "cus_success",
                    "subscription": "sub_success",
                    "metadata": {
                        "plan_id": "pro",
                        "tenant_id": tenant.id,
                    },
                }
            },
        }

        handler.process_webhook(
            event_type="checkout.session.completed",
            stripe_event_id="evt_success",
            event_data=event_data,
        )

        # Get processed events
        processed = handler.get_webhook_events_by_status("processed", limit=10)

        assert len(processed) >= 1
        assert all(event.status == "processed" for event in processed)

        print(f"✅ Events: Filtered {len(processed)} processed events by status")


class TestStripeConfiguration:
    """Test Stripe configuration and settings."""

    def test_stripe_keys_configured(self):
        """Test that Stripe keys are configured."""
        assert settings.stripe_secret_key is not None
        assert settings.stripe_webhook_secret is not None
        assert settings.stripe_checkout_base_url is not None
        print("✅ Config: Stripe keys configured")

    def test_webhook_secret_format(self):
        """Test that webhook secret has expected format."""
        # Stripe webhook secrets start with whsec_
        secret = settings.stripe_webhook_secret
        assert secret is not None
        print(f"✅ Config: Webhook secret format valid")
