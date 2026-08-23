"""Add overage tables to database.

Revision ID: 007_overages
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '007_overages'
down_revision = '006_reconciliation'
branch_labels = None
depends_on = None


def upgrade():
    """Create overage tables."""
    # Create overage_policies table
    op.create_table(
        'overage_policies',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('plan_id', sa.String(50), nullable=False, unique=True),
        sa.Column('allows_overage', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('api_calls_overage_price_cents', sa.Integer, nullable=False, server_default='0'),
        sa.Column('ai_tokens_overage_price_cents', sa.Integer, nullable=False, server_default='0'),
        sa.Column('max_overage_amount_cents', sa.Integer, nullable=True),
        sa.Column('max_overage_quantity', sa.Integer, nullable=True),
        sa.Column('suspend_on_overage_exceeded', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['plan.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_overage_policies_plan_id', 'plan_id'),
    )

    # Create overage_charges table
    op.create_table(
        'overage_charges',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('subscription_id', sa.String(50), nullable=False),
        sa.Column('billing_period', sa.String(7), nullable=False),
        sa.Column('usage_type', sa.String(50), nullable=False),
        sa.Column('quota_limit', sa.Integer, nullable=False),
        sa.Column('quota_used', sa.Integer, nullable=False),
        sa.Column('overage_quantity', sa.Integer, nullable=False),
        sa.Column('overage_unit_price_cents', sa.Integer, nullable=False),
        sa.Column('overage_total_cost_cents', sa.Integer, nullable=False),
        sa.Column('invoiced', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('invoice_id', sa.String(50), nullable=True),
        sa.Column('detected_at', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscription.id'], ),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoice.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_overage_charges_tenant_id', 'tenant_id'),
        sa.Index('ix_overage_charges_subscription_id', 'subscription_id'),
        sa.Index('ix_overage_charges_billing_period', 'billing_period'),
        sa.Index('ix_overage_charges_created_at', 'created_at'),
    )


def downgrade():
    """Drop overage tables."""
    op.drop_table('overage_charges')
    op.drop_table('overage_policies')
