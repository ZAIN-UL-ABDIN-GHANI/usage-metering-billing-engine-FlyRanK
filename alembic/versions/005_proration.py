"""Add proration tables to database.

Revision ID: 005_proration
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '005_proration'
down_revision = '004_alerts'
branch_labels = None
depends_on = None


def upgrade():
    """Create prorated_adjustments table."""
    op.create_table(
        'prorated_adjustments',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('subscription_id', sa.String(50), nullable=False),
        sa.Column('from_plan_id', sa.String(50), nullable=False),
        sa.Column('to_plan_id', sa.String(50), nullable=False),
        sa.Column('proration_type', sa.String(50), nullable=False),
        sa.Column('billing_period_start', sa.DateTime, nullable=False),
        sa.Column('billing_period_end', sa.DateTime, nullable=False),
        sa.Column('change_date', sa.DateTime, nullable=False),
        sa.Column('days_in_period', sa.Integer, nullable=False),
        sa.Column('days_remaining', sa.Integer, nullable=False),
        sa.Column('old_plan_daily_rate_cents', sa.Integer, nullable=False),
        sa.Column('new_plan_daily_rate_cents', sa.Integer, nullable=False),
        sa.Column('days_used_old_plan', sa.Integer, nullable=False),
        sa.Column('cost_old_plan_used_cents', sa.Integer, nullable=False),
        sa.Column('cost_old_plan_remaining_cents', sa.Integer, nullable=False),
        sa.Column('cost_new_plan_remaining_cents', sa.Integer, nullable=False),
        sa.Column('credit_cents', sa.Integer, nullable=False, server_default='0'),
        sa.Column('charge_cents', sa.Integer, nullable=False, server_default='0'),
        sa.Column('net_adjustment_cents', sa.Integer, nullable=False),
        sa.Column('applied', sa.DateTime, nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscription.id'], ),
        sa.ForeignKeyConstraint(['from_plan_id'], ['plan.id'], ),
        sa.ForeignKeyConstraint(['to_plan_id'], ['plan.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_prorated_adjustments_tenant_id', 'tenant_id'),
        sa.Index('ix_prorated_adjustments_subscription_id', 'subscription_id'),
        sa.Index('ix_prorated_adjustments_proration_type', 'proration_type'),
        sa.Index('ix_prorated_adjustments_created_at', 'created_at'),
    )


def downgrade():
    """Drop proration tables."""
    op.drop_table('prorated_adjustments')
