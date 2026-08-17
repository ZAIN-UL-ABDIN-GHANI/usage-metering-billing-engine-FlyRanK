"""Database connection and schema integrity tests."""

from datetime import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session


class TestDatabaseConnection:
    """Test database connectivity."""

    def test_database_connection(self, db: Session):
        """Test that database connection works."""
        result = db.execute("SELECT 1").scalar()
        assert result == 1

    def test_database_session_works(self, db: Session):
        """Test that session is active."""
        assert db.is_active


class TestDatabaseSchema:
    """Test database schema integrity."""

    def test_tables_exist(self, db: Session):
        """Test that all required tables exist."""
        inspector = inspect(db.bind)
        tables = inspector.get_table_names()

        required_tables = [
            "plans",
            "tenants",
            "subscriptions",
            "usage_events",
            "webhook_events",
        ]

        for table in required_tables:
            assert table in tables, f"Table {table} not found in database"

    def test_plans_table_schema(self, db: Session):
        """Test plans table has correct columns."""
        inspector = inspect(db.bind)
        columns = {col["name"] for col in inspector.get_columns("plans")}

        required_columns = {
            "id",
            "name",
            "stripe_price_id",
            "monthly_cost_cents",
            "api_calls_limit",
            "ai_tokens_limit",
            "created_at",
            "updated_at",
        }

        assert required_columns.issubset(columns), f"Missing columns in plans table"

    def test_tenants_table_schema(self, db: Session):
        """Test tenants table has correct columns."""
        inspector = inspect(db.bind)
        columns = {col["name"] for col in inspector.get_columns("tenants")}

        required_columns = {
            "id",
            "name",
            "email",
            "stripe_customer_id",
            "plan_id",
            "status",
            "created_at",
            "updated_at",
        }

        assert required_columns.issubset(columns), f"Missing columns in tenants table"

    def test_subscriptions_table_schema(self, db: Session):
        """Test subscriptions table has correct columns."""
        inspector = inspect(db.bind)
        columns = {col["name"] for col in inspector.get_columns("subscriptions")}

        required_columns = {
            "id",
            "tenant_id",
            "stripe_subscription_id",
            "plan_id",
            "status",
            "current_period_start",
            "current_period_end",
            "created_at",
            "updated_at",
        }

        assert required_columns.issubset(columns), f"Missing columns in subscriptions table"

    def test_usage_events_table_schema(self, db: Session):
        """Test usage_events table has correct columns."""
        inspector = inspect(db.bind)
        columns = {col["name"] for col in inspector.get_columns("usage_events")}

        required_columns = {
            "id",
            "tenant_id",
            "usage_type",
            "quantity",
            "idempotency_key",
            "cost_cents",
            "billing_period",
            "created_at",
        }

        assert required_columns.issubset(columns), f"Missing columns in usage_events table"

    def test_webhook_events_table_schema(self, db: Session):
        """Test webhook_events table has correct columns."""
        inspector = inspect(db.bind)
        columns = {col["name"] for col in inspector.get_columns("webhook_events")}

        required_columns = {
            "id",
            "stripe_event_id",
            "event_type",
            "tenant_id",
            "processed",
            "payload",
            "created_at",
            "processed_at",
        }

        assert required_columns.issubset(columns), f"Missing columns in webhook_events table"

    def test_indexes_exist(self, db: Session):
        """Test that critical indexes exist."""
        inspector = inspect(db.bind)

        # Test usage_events indexes
        usage_events_indexes = {idx["name"] for idx in inspector.get_indexes("usage_events")}
        assert "ix_usage_events_tenant_id" in usage_events_indexes

        # Test webhook_events indexes
        webhook_indexes = {idx["name"] for idx in inspector.get_indexes("webhook_events")}
        assert "ix_webhook_events_stripe_event_id" in webhook_indexes

    def test_unique_constraints_exist(self, db: Session):
        """Test that unique constraints exist."""
        inspector = inspect(db.bind)

        # Test tenant uniqueness constraints
        tenant_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("tenants")
        }
        assert "uq_tenants_email" in tenant_constraints

        # Test usage_events idempotency uniqueness
        usage_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("usage_events")
        }
        assert "uq_tenant_idempotency" in usage_constraints

        # Test webhook_events uniqueness
        webhook_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("webhook_events")
        }
        assert "uq_webhook_events_stripe_event_id" in webhook_constraints


class TestModelCreation:
    """Test creating records in database."""

    def test_create_plan(self, db: Session, create_plan):
        """Test creating a plan."""
        plan = create_plan(plan_id="test", name="Test Plan", api_calls_limit=500)

        assert plan.id == "test"
        assert plan.name == "Test Plan"
        assert plan.api_calls_limit == 500
        assert plan.monthly_cost_cents == 0

        # Verify persisted
        from app.models import Plan

        fetched = db.query(Plan).filter_by(id="test").first()
        assert fetched is not None
        assert fetched.name == "Test Plan"

    def test_create_tenant(self, db: Session, create_plan, create_tenant):
        """Test creating a tenant."""
        create_plan(plan_id="free", name="Free")
        tenant = create_tenant(
            name="Test Corp",
            email="test@corp.com",
            plan_id="free"
        )

        assert tenant.name == "Test Corp"
        assert tenant.email == "test@corp.com"
        assert tenant.plan_id == "free"
        assert tenant.status == "active"

        # Verify persisted
        from app.models import Tenant

        fetched = db.query(Tenant).filter_by(email="test@corp.com").first()
        assert fetched is not None
        assert fetched.name == "Test Corp"

    def test_create_subscription(self, db: Session, create_plan, create_tenant, create_subscription):
        """Test creating a subscription."""
        create_plan(plan_id="pro", name="Pro")
        tenant = create_tenant(plan_id="pro")
        sub = create_subscription(tenant_id=tenant.id, plan_id="pro")

        assert sub.tenant_id == tenant.id
        assert sub.plan_id == "pro"
        assert sub.status == "active"
        assert sub.current_period_start is not None
        assert sub.current_period_end is not None

        # Verify persisted
        from app.models import Subscription

        fetched = db.query(Subscription).filter_by(id=sub.id).first()
        assert fetched is not None
        assert fetched.plan_id == "pro"

    def test_create_usage_event(self, db: Session, create_plan, create_tenant, create_usage_event):
        """Test creating a usage event."""
        create_plan()
        tenant = create_tenant()
        event = create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
            idempotency_key="unique-123"
        )

        assert event.tenant_id == tenant.id
        assert event.usage_type == "api_calls"
        assert event.quantity == 100
        assert event.idempotency_key == "unique-123"

        # Verify persisted
        from app.models import UsageEvent

        fetched = db.query(UsageEvent).filter_by(id=event.id).first()
        assert fetched is not None
        assert fetched.quantity == 100

    def test_usage_event_idempotency_constraint(self, db: Session, create_plan, create_tenant, create_usage_event):
        """Test that duplicate idempotency keys are rejected."""
        from sqlalchemy.exc import IntegrityError
        from app.models import UsageEvent

        create_plan()
        tenant = create_tenant()

        # Create first event
        create_usage_event(
            tenant_id=tenant.id,
            idempotency_key="same-key",
            quantity=100
        )

        # Try to create second event with same key - should fail
        with pytest.raises(IntegrityError):
            event2 = UsageEvent(
                id="different-id",
                tenant_id=tenant.id,
                usage_type="api_calls",
                quantity=200,
                idempotency_key="same-key",
                billing_period="2024-01",
                created_at=datetime.utcnow(),
            )
            db.add(event2)
            db.commit()

    def test_webhook_event_deduplication(self, db: Session):
        """Test that duplicate webhook event IDs are rejected."""
        from sqlalchemy.exc import IntegrityError
        from app.models import WebhookEvent
        from app.utils.db_helpers import generate_id

        # Create first webhook event
        event1 = WebhookEvent(
            id=generate_id(),
            stripe_event_id="evt_123",
            event_type="checkout.session.completed",
            processed=False,
            payload="{}",
            created_at=datetime.utcnow(),
        )
        db.add(event1)
        db.commit()

        # Try to create second event with same stripe_event_id - should fail
        with pytest.raises(IntegrityError):
            event2 = WebhookEvent(
                id=generate_id(),
                stripe_event_id="evt_123",  # Duplicate
                event_type="checkout.session.completed",
                processed=False,
                payload="{}",
                created_at=datetime.utcnow(),
            )
            db.add(event2)
            db.commit()


class TestDatabaseRelationships:
    """Test database relationships and foreign keys."""

    def test_tenant_plan_relationship(self, db: Session, create_plan, create_tenant):
        """Test tenant-to-plan relationship."""
        create_plan(plan_id="pro", name="Pro")
        tenant = create_tenant(plan_id="pro")

        # Relationship should work
        assert tenant.plan is not None
        assert tenant.plan.id == "pro"

    def test_subscription_relationships(self, db: Session, create_plan, create_tenant, create_subscription):
        """Test subscription relationships."""
        create_plan(plan_id="pro", name="Pro")
        tenant = create_tenant(plan_id="pro")
        sub = create_subscription(tenant_id=tenant.id, plan_id="pro")

        # Relationships should work
        assert sub.tenant is not None
        assert sub.tenant.id == tenant.id

    def test_cascade_delete_subscriptions(self, db: Session, create_plan, create_tenant, create_subscription):
        """Test that deleting tenant cascades to subscriptions."""
        from app.models import Tenant, Subscription

        create_plan()
        tenant = create_tenant()
        sub = create_subscription(tenant_id=tenant.id)

        assert db.query(Subscription).filter_by(id=sub.id).count() == 1

        # Delete tenant
        db.delete(tenant)
        db.commit()

        # Subscription should be deleted too
        assert db.query(Subscription).filter_by(id=sub.id).count() == 0
