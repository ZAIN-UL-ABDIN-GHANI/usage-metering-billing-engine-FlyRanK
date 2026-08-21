"""Add invoice tables to database.

Revision ID: 003_invoices
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '003_invoices'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade():
    """Create invoice and invoice_line_items tables."""
    # Create invoices table
    op.create_table(
        'invoices',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('billing_period', sa.String(7), nullable=False),
        sa.Column('invoice_number', sa.String(50), nullable=False, unique=True),
        sa.Column('subtotal_cents', sa.Integer, nullable=False, server_default='0'),
        sa.Column('discount_cents', sa.Integer, nullable=False, server_default='0'),
        sa.Column('tax_cents', sa.Integer, nullable=False, server_default='0'),
        sa.Column('total_cents', sa.Integer, nullable=False, server_default='0'),
        sa.Column('line_items_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('issued_at', sa.DateTime, nullable=True),
        sa.Column('due_at', sa.DateTime, nullable=True),
        sa.Column('paid_at', sa.DateTime, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('stripe_invoice_id', sa.String(100), nullable=True, unique=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_number', name='uq_invoice_number'),
        sa.Index('ix_invoices_tenant_id', 'tenant_id'),
        sa.Index('ix_invoices_billing_period', 'billing_period'),
        sa.Index('ix_invoices_status', 'status'),
        sa.Index('ix_invoices_created_at', 'created_at'),
    )

    # Create invoice_line_items table
    op.create_table(
        'invoice_line_items',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('invoice_id', sa.String(50), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('usage_type', sa.String(50), nullable=False),
        sa.Column('quantity', sa.Integer, nullable=False),
        sa.Column('unit_price_cents', sa.Integer, nullable=False),
        sa.Column('subtotal_cents', sa.Integer, nullable=False),
        sa.Column('discount_cents', sa.Integer, nullable=False, server_default='0'),
        sa.Column('tax_cents', sa.Integer, nullable=False, server_default='0'),
        sa.Column('total_cents', sa.Integer, nullable=False),
        sa.Column('metadata', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_invoice_line_items_invoice_id', 'invoice_id'),
    )


def downgrade():
    """Drop invoice tables."""
    op.drop_table('invoice_line_items')
    op.drop_table('invoices')
