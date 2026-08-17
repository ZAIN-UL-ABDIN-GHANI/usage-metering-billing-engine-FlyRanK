"""Initial migration: create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema."""
    
    # Create plans table
    op.create_table(
        "plans",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("stripe_price_id", sa.String(255), nullable=True),
        sa.Column("monthly_cost_cents", sa.Integer(), nullable=False),
        sa.Column("api_calls_limit", sa.Integer(), nullable=False),
        sa.Column("ai_tokens_limit", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_plans_name"),
        sa.UniqueConstraint("stripe_price_id", name="uq_plans_stripe_price_id"),
    )
    op.create_index("ix_plans_stripe_price_id", "plans", ["stripe_price_id"])
    op.create_index("ix_plans_id", "plans", ["id"])

    # Create tenants table
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_tenants_email"),
        sa.UniqueConstraint("stripe_customer_id", name="uq_tenants_stripe_customer_id"),
    )
    op.create_index("ix_tenants_stripe_customer_id", "tenants", ["stripe_customer_id"])
    op.create_index("ix_tenants_email", "tenants", ["email"])
    op.create_index("ix_tenants_id", "tenants", ["id"])

    # Create subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("current_period_start", sa.DateTime(), nullable=False),
        sa.Column("current_period_end", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_subscription_id", name="uq_subscriptions_stripe_subscription_id"),
    )
    op.create_index("ix_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"])
    op.create_index("ix_subscriptions_tenant_id", "subscriptions", ["tenant_id"])
    op.create_index("ix_subscriptions_id", "subscriptions", ["id"])

    # Create usage_events table (CRITICAL: unique constraint on idempotency)
    op.create_table(
        "usage_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("usage_type", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("cost_cents", sa.Integer(), nullable=True),
        sa.Column("billing_period", sa.String(7), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_tenant_idempotency"),
    )
    op.create_index("ix_usage_events_billing_period", "usage_events", ["billing_period"])
    op.create_index("ix_usage_events_usage_type", "usage_events", ["usage_type"])
    op.create_index("ix_usage_events_tenant_id", "usage_events", ["tenant_id"])
    op.create_index("ix_usage_events_id", "usage_events", ["id"])

    # Create webhook_events table (CRITICAL: unique on stripe_event_id)
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("stripe_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_event_id", name="uq_webhook_events_stripe_event_id"),
    )
    op.create_index("ix_webhook_events_tenant_id", "webhook_events", ["tenant_id"])
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"])
    op.create_index("ix_webhook_events_stripe_event_id", "webhook_events", ["stripe_event_id"])
    op.create_index("ix_webhook_events_id", "webhook_events", ["id"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index("ix_webhook_events_id", table_name="webhook_events")
    op.drop_index("ix_webhook_events_stripe_event_id", table_name="webhook_events")
    op.drop_index("ix_webhook_events_event_type", table_name="webhook_events")
    op.drop_index("ix_webhook_events_tenant_id", table_name="webhook_events")
    op.drop_table("webhook_events")

    op.drop_index("ix_usage_events_id", table_name="usage_events")
    op.drop_index("ix_usage_events_tenant_id", table_name="usage_events")
    op.drop_index("ix_usage_events_usage_type", table_name="usage_events")
    op.drop_index("ix_usage_events_billing_period", table_name="usage_events")
    op.drop_table("usage_events")

    op.drop_index("ix_subscriptions_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_tenant_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_stripe_subscription_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_tenants_id", table_name="tenants")
    op.drop_index("ix_tenants_email", table_name="tenants")
    op.drop_index("ix_tenants_stripe_customer_id", table_name="tenants")
    op.drop_table("tenants")

    op.drop_index("ix_plans_id", table_name="plans")
    op.drop_index("ix_plans_stripe_price_id", table_name="plans")
    op.drop_table("plans")
