"""Add reconciliation tables to database.

Revision ID: 006_reconciliation
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '006_reconciliation'
down_revision = '005_proration'
branch_labels = None
depends_on = None


def upgrade():
    """Create reconciliation tables."""
    # Create reconciliation_runs table
    op.create_table(
        'reconciliation_runs',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('run_type', sa.String(50), nullable=False),
        sa.Column('started_at', sa.DateTime, nullable=False),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('total_tenants_checked', sa.Integer, nullable=False, server_default='0'),
        sa.Column('total_subscriptions_checked', sa.Integer, nullable=False, server_default='0'),
        sa.Column('total_mismatches_found', sa.Integer, nullable=False, server_default='0'),
        sa.Column('total_issues_resolved', sa.Integer, nullable=False, server_default='0'),
        sa.Column('success', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_reconciliation_runs_created_at', 'created_at'),
        sa.Index('ix_reconciliation_runs_run_type', 'run_type'),
    )

    # Create reconciliation_issues table
    op.create_table(
        'reconciliation_issues',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('run_id', sa.String(50), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('subscription_id', sa.String(50), nullable=True),
        sa.Column('issue_type', sa.String(50), nullable=False),
        sa.Column('local_value', sa.String(500), nullable=True),
        sa.Column('stripe_value', sa.String(500), nullable=True),
        sa.Column('stripe_object_id', sa.String(255), nullable=True),
        sa.Column('stripe_object_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('resolution_action', sa.String(500), nullable=True),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['reconciliation_runs.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscription.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_reconciliation_issues_run_id', 'run_id'),
        sa.Index('ix_reconciliation_issues_tenant_id', 'tenant_id'),
        sa.Index('ix_reconciliation_issues_subscription_id', 'subscription_id'),
        sa.Index('ix_reconciliation_issues_issue_type', 'issue_type'),
        sa.Index('ix_reconciliation_issues_status', 'status'),
        sa.Index('ix_reconciliation_issues_created_at', 'created_at'),
    )


def downgrade():
    """Drop reconciliation tables."""
    op.drop_table('reconciliation_issues')
    op.drop_table('reconciliation_runs')
