"""Add alert tables to database.

Revision ID: 004_alerts
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '004_alerts'
down_revision = '003_invoices'
branch_labels = None
depends_on = None


def upgrade():
    """Create alerts and alert_preferences tables."""
    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('billing_period', sa.String(7), nullable=False),
        sa.Column('usage_type', sa.String(50), nullable=False),
        sa.Column('current_usage', sa.Integer, nullable=False),
        sa.Column('quota_limit', sa.Integer, nullable=False),
        sa.Column('usage_percent', sa.Float, nullable=False),
        sa.Column('threshold_percent', sa.Integer, nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('sent_at', sa.DateTime, nullable=True),
        sa.Column('acknowledged_at', sa.DateTime, nullable=True),
        sa.Column('message', sa.String(500), nullable=True),
        sa.Column('notification_method', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_alerts_tenant_id', 'tenant_id'),
        sa.Index('ix_alerts_alert_type', 'alert_type'),
        sa.Index('ix_alerts_billing_period', 'billing_period'),
        sa.Index('ix_alerts_status', 'status'),
        sa.Index('ix_alerts_created_at', 'created_at'),
    )

    # Create alert_preferences table
    op.create_table(
        'alert_preferences',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False, unique=True),
        sa.Column('email_address', sa.String(255), nullable=False),
        sa.Column('email_on_80_percent', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('email_on_100_percent', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('email_on_overage', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('notify_daily_summary', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_alert_preferences_tenant_id', 'tenant_id'),
    )


def downgrade():
    """Drop alert tables."""
    op.drop_table('alert_preferences')
    op.drop_table('alerts')
