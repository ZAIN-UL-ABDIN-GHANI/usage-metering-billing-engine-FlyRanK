"""Initial schema migration."""

from alembic import op
import sqlalchemy as sa
from datetime import datetime


def upgrade() -> None:
    """Create initial schema."""
    
    # Create Tenant table
    op.create_table(
        'tenant',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('api_key', sa.String(255), nullable=False, unique=True),
        sa.Column('current_plan_id', sa.String(36), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='active'),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True, unique=True),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_tenant_api_key', 'tenant', ['api_key'])
    op.create_index('ix_tenant_stripe_customer_id', 'tenant', ['stripe_customer_id'])
    
    # Create Plan table
    op.create_table(
        'plan',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('slug', sa.String(50), nullable=False, unique=True),
        sa.Column('monthly_cost', sa.Integer, nullable=False),  # in cents
        sa.Column('api_call_limit', sa.Integer, nullable=False),
        sa.Column('token_limit', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    
    # Create Subscription table
    op.create_table(
        'subscription',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('plan_id', sa.String(36), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True, unique=True),
        sa.Column('status', sa.String(50), nullable=False, default='active'),
        sa.Column('current_period_start', sa.DateTime, nullable=False),
        sa.Column('current_period_end', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['plan.id']),
    )
    op.create_index('ix_subscription_tenant_id', 'subscription', ['tenant_id'])
    op.create_index('ix_subscription_stripe_subscription_id', 'subscription', ['stripe_subscription_id'])
    
    # Create Usage Event table
    op.create_table(
        'usage_event',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),  # 'api_call' or 'token'
        sa.Column('quantity', sa.Integer, nullable=False),
        sa.Column('idempotency_key', sa.String(255), nullable=True),
        sa.Column('month', sa.String(7), nullable=False),  # YYYY-MM
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('tenant_id', 'idempotency_key', name='uq_idempotency'),
    )
    op.create_index('ix_usage_event_tenant_id', 'usage_event', ['tenant_id'])
    op.create_index('ix_usage_event_month', 'usage_event', ['month'])
    op.create_index('ix_usage_event_type', 'usage_event', ['type'])
    
    # Create Webhook Event table
    op.create_table(
        'webhook_event',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('stripe_event_id', sa.String(255), nullable=False, unique=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=True),
        sa.Column('data', sa.JSON, nullable=False),
        sa.Column('processed', sa.Boolean, nullable=False, default=False),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_webhook_event_stripe_event_id', 'webhook_event', ['stripe_event_id'])
    op.create_index('ix_webhook_event_processed', 'webhook_event', ['processed'])
    
    # Create Invoice table
    op.create_table(
        'invoice',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('invoice_number', sa.String(50), nullable=False, unique=True),
        sa.Column('period_start', sa.DateTime, nullable=False),
        sa.Column('period_end', sa.DateTime, nullable=False),
        sa.Column('total_amount', sa.Integer, nullable=False),  # in cents
        sa.Column('status', sa.String(50), nullable=False, default='draft'),
        sa.Column('paid_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_invoice_tenant_id', 'invoice', ['tenant_id'])
    op.create_index('ix_invoice_status', 'invoice', ['status'])
    
    # Create Invoice Line Item table
    op.create_table(
        'invoice_line_item',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('invoice_id', sa.String(36), nullable=False),
        sa.Column('description', sa.String(255), nullable=False),
        sa.Column('quantity', sa.Integer, nullable=False),
        sa.Column('unit_price', sa.Integer, nullable=False),  # in cents
        sa.Column('total_price', sa.Integer, nullable=False),  # in cents
        sa.ForeignKeyConstraint(['invoice_id'], ['invoice.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_invoice_line_item_invoice_id', 'invoice_line_item', ['invoice_id'])
    
    # Create Alert table
    op.create_table(
        'alert',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('alert_type', sa.String(50), nullable=False),  # 'usage_threshold', 'quota_exceeded'
        sa.Column('threshold_percent', sa.Integer, nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='active'),
        sa.Column('acknowledged_at', sa.DateTime, nullable=True),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_alert_tenant_id', 'alert', ['tenant_id'])
    op.create_index('ix_alert_status', 'alert', ['status'])
    
    # Create Alert Preference table
    op.create_table(
        'alert_preference',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False, unique=True),
        sa.Column('email_notifications', sa.Boolean, nullable=False, default=True),
        sa.Column('alert_at_80_percent', sa.Boolean, nullable=False, default=True),
        sa.Column('alert_at_100_percent', sa.Boolean, nullable=False, default=True),
        sa.Column('alert_on_overage', sa.Boolean, nullable=False, default=True),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_alert_preference_tenant_id', 'alert_preference', ['tenant_id'])
    
    # Create Prorated Adjustment table
    op.create_table(
        'prorated_adjustment',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('subscription_id', sa.String(36), nullable=False),
        sa.Column('old_plan_id', sa.String(36), nullable=False),
        sa.Column('new_plan_id', sa.String(36), nullable=False),
        sa.Column('adjustment_amount', sa.Integer, nullable=False),  # in cents
        sa.Column('adjustment_type', sa.String(50), nullable=False),  # 'credit' or 'charge'
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscription.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['old_plan_id'], ['plan.id']),
        sa.ForeignKeyConstraint(['new_plan_id'], ['plan.id']),
    )
    op.create_index('ix_prorated_adjustment_tenant_id', 'prorated_adjustment', ['tenant_id'])
    
    # Create Reconciliation Run table
    op.create_table(
        'reconciliation_run',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('issues_found', sa.Integer, nullable=False, default=0),
        sa.Column('issues_resolved', sa.Integer, nullable=False, default=0),
        sa.Column('started_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
    )
    op.create_index('ix_reconciliation_run_status', 'reconciliation_run', ['status'])
    
    # Create Reconciliation Issue table
    op.create_table(
        'reconciliation_issue',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('issue_type', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.ForeignKeyConstraint(['run_id'], ['reconciliation_run.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_reconciliation_issue_run_id', 'reconciliation_issue', ['run_id'])
    op.create_index('ix_reconciliation_issue_tenant_id', 'reconciliation_issue', ['tenant_id'])
    op.create_index('ix_reconciliation_issue_status', 'reconciliation_issue', ['status'])
    
    # Create Overage Charge table
    op.create_table(
        'overage_charge',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('subscription_id', sa.String(36), nullable=False),
        sa.Column('overage_amount', sa.Integer, nullable=False),  # units over limit
        sa.Column('charge_amount', sa.Integer, nullable=False),  # in cents
        sa.Column('month', sa.String(7), nullable=False),  # YYYY-MM
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscription.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_overage_charge_tenant_id', 'overage_charge', ['tenant_id'])
    op.create_index('ix_overage_charge_month', 'overage_charge', ['month'])
    
    # Create Overage Policy table
    op.create_table(
        'overage_policy',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('plan_id', sa.String(36), nullable=False, unique=True),
        sa.Column('allow_overage', sa.Boolean, nullable=False, default=False),
        sa.Column('overage_price_per_unit_api_call', sa.Integer, nullable=False, default=10),  # in cents
        sa.Column('overage_price_per_unit_token', sa.Integer, nullable=False, default=1),  # in cents
        sa.Column('suspension_threshold', sa.Integer, nullable=True),  # units
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.ForeignKeyConstraint(['plan_id'], ['plan.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_overage_policy_plan_id', 'overage_policy', ['plan_id'])
    
    # Create Saved Report table
    op.create_table(
        'saved_report',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('report_type', sa.String(100), nullable=False),
        sa.Column('filters', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_saved_report_tenant_id', 'saved_report', ['tenant_id'])
    
    # Create Report Run table
    op.create_table(
        'report_run',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('report_id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('data', sa.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.ForeignKeyConstraint(['report_id'], ['saved_report.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_report_run_report_id', 'report_run', ['report_id'])
    op.create_index('ix_report_run_tenant_id', 'report_run', ['tenant_id'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('report_run')
    op.drop_table('saved_report')
    op.drop_table('overage_policy')
    op.drop_table('overage_charge')
    op.drop_table('reconciliation_issue')
    op.drop_table('reconciliation_run')
    op.drop_table('prorated_adjustment')
    op.drop_table('alert_preference')
    op.drop_table('alert')
    op.drop_table('invoice_line_item')
    op.drop_table('invoice')
    op.drop_table('webhook_event')
    op.drop_table('usage_event')
    op.drop_table('subscription')
    op.drop_table('plan')
    op.drop_table('tenant')
