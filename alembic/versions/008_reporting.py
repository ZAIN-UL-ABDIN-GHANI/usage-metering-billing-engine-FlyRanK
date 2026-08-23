"""Add reporting tables to database.

Revision ID: 008_reporting
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '008_reporting'
down_revision = '007_overages'
branch_labels = None
depends_on = None


def upgrade():
    """Create reporting tables."""
    # Create saved_reports table
    op.create_table(
        'saved_reports',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('frequency', sa.String(20), nullable=False),
        sa.Column('include_charts', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('include_summary', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('include_trends', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('parameters', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_generated_at', sa.DateTime, nullable=True),
        sa.Column('next_generation_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_saved_reports_tenant_id', 'tenant_id'),
        sa.Index('ix_saved_reports_report_type', 'report_type'),
        sa.Index('ix_saved_reports_created_at', 'created_at'),
    )

    # Create report_runs table
    op.create_table(
        'report_runs',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('saved_report_id', sa.String(50), nullable=True),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('date_range_start', sa.DateTime, nullable=False),
        sa.Column('date_range_end', sa.DateTime, nullable=False),
        sa.Column('total_records', sa.Integer, nullable=False, server_default='0'),
        sa.Column('summary_data', sa.Text, nullable=True),
        sa.Column('success', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime, nullable=False),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['saved_report_id'], ['saved_reports.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_report_runs_saved_report_id', 'saved_report_id'),
        sa.Index('ix_report_runs_created_at', 'created_at'),
    )


def downgrade():
    """Drop reporting tables."""
    op.drop_table('report_runs')
    op.drop_table('saved_reports')
