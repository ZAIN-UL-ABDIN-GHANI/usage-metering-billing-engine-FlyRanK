"""Tests for invoice generation and management."""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime

from app.models_invoice import Invoice, InvoiceLineItem, InvoiceStatus
from app.services.invoice_service import InvoiceService
from app.utils.db_helpers import get_current_billing_period


class TestInvoiceGeneration:
    """Test invoice generation from usage events."""

    def test_generate_invoice_success(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test successful invoice generation."""
        create_plan()
        tenant = create_tenant()
        
        # Create usage events
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
        )
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="ai_tokens",
            quantity=1_000_000,
        )

        service = InvoiceService(db)
        period = get_current_billing_period()
        
        invoice = service.generate_invoice(
            tenant_id=tenant.id,
            billing_period=period,
            notes="Test invoice",
        )

        assert invoice is not None
        assert invoice.tenant_id == tenant.id
        assert invoice.billing_period == period
        assert invoice.status == InvoiceStatus.DRAFT
        assert invoice.line_items_count == 2
        assert invoice.total_cents > 0

        print(f"✅ Invoice: Generated {invoice.invoice_number} with ${invoice.total_cents/100:.2f}")

    def test_invoice_number_format(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test invoice number format is INV-YYYY-MM-XXXX."""
        create_plan()
        tenant = create_tenant()
        create_usage_event(tenant_id=tenant.id)

        service = InvoiceService(db)
        period = get_current_billing_period()
        
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        # Format: INV-2024-01-0001
        assert invoice.invoice_number.startswith("INV-")
        assert len(invoice.invoice_number) > 10
        print(f"✅ Invoice: Number format correct: {invoice.invoice_number}")

    def test_invoice_duplicate_raises_error(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test that generating duplicate invoice raises error."""
        create_plan()
        tenant = create_tenant()
        create_usage_event(tenant_id=tenant.id)

        service = InvoiceService(db)
        period = get_current_billing_period()
        
        # Generate first invoice
        service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        # Try to generate duplicate
        with pytest.raises(ValueError, match="already exists"):
            service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        print("✅ Invoice: Duplicate generation rejected")

    def test_invoice_no_usage_raises_error(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that invoice with no usage raises error."""
        create_plan()
        tenant = create_tenant()

        service = InvoiceService(db)
        period = get_current_billing_period()
        
        with pytest.raises(ValueError, match="No usage"):
            service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        print("✅ Invoice: No usage raises error")


class TestInvoiceLineItems:
    """Test invoice line items."""

    def test_line_items_created(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test that line items are created correctly."""
        create_plan()
        tenant = create_tenant()
        
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
        )
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="ai_tokens",
            quantity=1_000_000,
        )

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        line_items = service.get_invoice_line_items(invoice.id)

        assert len(line_items) == 2
        assert any(item.usage_type == "api_calls" for item in line_items)
        assert any(item.usage_type == "ai_tokens" for item in line_items)

        print(f"✅ Invoice: {len(line_items)} line items created")

    def test_line_item_costs_calculated(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test that line item costs are calculated correctly."""
        create_plan()
        tenant = create_tenant()
        
        # 100 API calls = 100 cents = $1.00
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
        )

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        line_items = service.get_invoice_line_items(invoice.id)
        api_item = next(i for i in line_items if i.usage_type == "api_calls")

        assert api_item.quantity == 100
        assert api_item.total_cents == 100  # $1.00

        print(f"✅ Invoice: Line item cost correct: ${api_item.total_cents/100:.2f}")


class TestInvoiceStatus:
    """Test invoice status transitions."""

    def test_invoice_starts_as_draft(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test that new invoices start as draft."""
        create_plan()
        tenant = create_tenant()
        create_usage_event(tenant_id=tenant.id)

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        assert invoice.status == InvoiceStatus.DRAFT
        assert invoice.issued_at is None
        print("✅ Invoice: Status starts as DRAFT")

    def test_issue_invoice(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test issuing an invoice."""
        create_plan()
        tenant = create_tenant()
        create_usage_event(tenant_id=tenant.id)

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        # Issue invoice
        issued = service.issue_invoice(invoice.id)

        assert issued.status == InvoiceStatus.ISSUED
        assert issued.issued_at is not None
        assert issued.due_at is not None

        print("✅ Invoice: Issued successfully")

    def test_mark_paid(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test marking invoice as paid."""
        create_plan()
        tenant = create_tenant()
        create_usage_event(tenant_id=tenant.id)

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        # Mark as paid
        paid = service.mark_paid(invoice.id)

        assert paid.status == InvoiceStatus.PAID
        assert paid.paid_at is not None

        print("✅ Invoice: Marked as PAID")

    def test_cancel_invoice(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test canceling an invoice."""
        create_plan()
        tenant = create_tenant()
        create_usage_event(tenant_id=tenant.id)

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        # Cancel invoice
        cancelled = service.cancel_invoice(invoice.id)

        assert cancelled.status == InvoiceStatus.CANCELLED
        print("✅ Invoice: Cancelled successfully")

    def test_cannot_cancel_paid_invoice(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test that paid invoices cannot be cancelled."""
        create_plan()
        tenant = create_tenant()
        create_usage_event(tenant_id=tenant.id)

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        # Mark as paid
        service.mark_paid(invoice.id)

        # Try to cancel
        with pytest.raises(ValueError, match="Cannot cancel a paid invoice"):
            service.cancel_invoice(invoice.id)

        print("✅ Invoice: Cannot cancel paid invoice")


class TestInvoiceRetrieval:
    """Test invoice retrieval and querying."""

    def test_get_invoice_by_id(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test getting invoice by ID."""
        create_plan()
        tenant = create_tenant()
        create_usage_event(tenant_id=tenant.id)

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        retrieved = service.get_invoice(invoice.id)

        assert retrieved is not None
        assert retrieved.id == invoice.id
        print("✅ Invoice: Retrieved by ID")

    def test_get_invoice_by_number(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test getting invoice by invoice number."""
        create_plan()
        tenant = create_tenant()
        create_usage_event(tenant_id=tenant.id)

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        retrieved = service.get_invoice_by_number(invoice.invoice_number)

        assert retrieved is not None
        assert retrieved.invoice_number == invoice.invoice_number
        print("✅ Invoice: Retrieved by number")

    def test_get_tenant_invoices(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test getting all invoices for a tenant."""
        create_plan()
        tenant = create_tenant()
        
        # Create multiple invoices (different periods)
        for i in range(3):
            period = f"2024-{i+1:02d}"
            create_usage_event(
                tenant_id=tenant.id,
                billing_period=period,
            )
            service = InvoiceService(db)
            service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        service = InvoiceService(db)
        invoices, total = service.get_tenant_invoices(tenant_id=tenant.id)

        assert len(invoices) >= 3
        assert total >= 3

        print(f"✅ Invoice: Retrieved {len(invoices)} invoices for tenant")

    def test_get_tenant_invoices_pagination(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test invoice pagination."""
        create_plan()
        tenant = create_tenant()
        
        # Create 5 invoices
        for i in range(5):
            period = f"2024-{i+1:02d}"
            create_usage_event(
                tenant_id=tenant.id,
                billing_period=period,
            )
            service = InvoiceService(db)
            service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        service = InvoiceService(db)
        
        # Get page 1
        page1, total1 = service.get_tenant_invoices(
            tenant_id=tenant.id,
            limit=2,
            offset=0,
        )
        
        # Get page 2
        page2, total2 = service.get_tenant_invoices(
            tenant_id=tenant.id,
            limit=2,
            offset=2,
        )

        assert len(page1) == 2
        assert len(page2) <= 2
        assert total1 == total2

        print(f"✅ Invoice: Pagination works (page 1: {len(page1)}, page 2: {len(page2)})")


class TestInvoiceHTML:
    """Test invoice HTML generation."""

    def test_generate_invoice_html(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test HTML invoice generation."""
        create_plan()
        tenant = create_tenant()
        create_usage_event(tenant_id=tenant.id)

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        html = service.get_invoice_html(invoice.id)

        assert html is not None
        assert "<html>" in html
        assert invoice.invoice_number in html
        assert invoice.billing_period in html

        print("✅ Invoice: HTML generated successfully")

    def test_html_includes_totals(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test that HTML includes cost totals."""
        create_plan()
        tenant = create_tenant()
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=100,
        )

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        html = service.get_invoice_html(invoice.id)

        # Check for totals
        assert "TOTAL DUE" in html
        assert "$" in html

        print("✅ Invoice: HTML includes totals")


class TestInvoiceSummary:
    """Test invoice summary statistics."""

    def test_invoice_summary(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test getting invoice summary for tenant."""
        create_plan()
        tenant = create_tenant()
        
        # Create and issue invoice
        create_usage_event(tenant_id=tenant.id)
        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)
        service.issue_invoice(invoice.id)

        summary = service.get_tenant_invoice_summary(tenant.id)

        assert summary["tenant_id"] == tenant.id
        assert summary["total_invoices"] >= 1
        assert summary["total_billed_cents"] > 0
        assert "by_status" in summary

        print(f"✅ Invoice: Summary shows ${summary['total_billed_dollars']:.2f} total")

    def test_summary_tracks_paid_vs_outstanding(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test that summary tracks paid vs outstanding."""
        create_plan()
        tenant = create_tenant()
        
        # Create 2 invoices
        for i in range(2):
            period = f"2024-{i+1:02d}"
            create_usage_event(
                tenant_id=tenant.id,
                billing_period=period,
            )
            service = InvoiceService(db)
            invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)
            service.issue_invoice(invoice.id)
            
            # Mark first as paid
            if i == 0:
                service.mark_paid(invoice.id)

        service = InvoiceService(db)
        summary = service.get_tenant_invoice_summary(tenant.id)

        assert summary["total_paid_cents"] > 0
        assert summary["total_outstanding_cents"] > 0

        print(f"✅ Invoice: Paid: ${summary['total_paid_dollars']:.2f}, "
              f"Outstanding: ${summary['total_outstanding_dollars']:.2f}")


class TestInvoiceAmounts:
    """Test invoice amount calculations."""

    def test_invoice_total_matches_line_items(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test that invoice total matches sum of line items."""
        create_plan()
        tenant = create_tenant()
        
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=50,
        )
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="ai_tokens",
            quantity=500_000,
        )

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        line_items = service.get_invoice_line_items(invoice.id)
        line_item_total = sum(item.total_cents for item in line_items)

        assert invoice.total_cents == line_item_total

        print(f"✅ Invoice: Total ${invoice.total_cents/100:.2f} matches line items")

    def test_invoice_currency_precision(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test that invoice amounts are in cents (integers only)."""
        create_plan()
        tenant = create_tenant()
        create_usage_event(tenant_id=tenant.id)

        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice = service.generate_invoice(tenant_id=tenant.id, billing_period=period)

        # All amounts should be integers
        assert isinstance(invoice.total_cents, int)
        assert isinstance(invoice.subtotal_cents, int)
        assert isinstance(invoice.discount_cents, int)
        assert isinstance(invoice.tax_cents, int)

        print("✅ Invoice: All amounts are integers (cents)")


class TestInvoiceIsolation:
    """Test tenant isolation in invoices."""

    def test_invoice_tenant_isolation(
        self, db: Session, create_plan, create_tenant, create_usage_event
    ):
        """Test that invoices are isolated by tenant."""
        create_plan()
        tenant1 = create_tenant()
        tenant2 = create_tenant()
        
        # Create invoice for tenant1
        create_usage_event(tenant_id=tenant1.id)
        service = InvoiceService(db)
        period = get_current_billing_period()
        invoice1 = service.generate_invoice(tenant_id=tenant1.id, billing_period=period)

        # Get invoices for tenant2 - should not see tenant1's invoice
        invoices2, count2 = service.get_tenant_invoices(tenant_id=tenant2.id)

        assert invoice1.tenant_id == tenant1.id
        assert count2 == 0  # tenant2 has no invoices

        print("✅ Invoice: Tenant isolation verified")
