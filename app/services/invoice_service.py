"""Invoice service - generates and manages monthly billing statements."""

from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models_invoice import Invoice, InvoiceLineItem, InvoiceStatus
from app.models import UsageEvent, Plan
from app.config_pricing import PricingConfig
from app.utils.db_helpers import generate_id, get_billing_period_start, get_billing_period_end
from app.services.cost_service import CostService


class InvoiceService:
    """Service for invoice generation and management."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.cost_service = CostService(db)

    def generate_invoice(
        self,
        tenant_id: str,
        billing_period: str,
        notes: Optional[str] = None,
    ) -> Invoice:
        """
        Generate invoice for a billing period.

        Creates invoice with line items from usage events.

        Args:
            tenant_id: Tenant ID
            billing_period: Billing period (YYYY-MM)
            notes: Optional invoice notes

        Returns:
            Generated Invoice object

        Raises:
            ValueError: If invoice already exists for period
        """
        # Check if invoice already exists
        existing = self.db.query(Invoice).filter_by(
            tenant_id=tenant_id,
            billing_period=billing_period,
        ).first()

        if existing:
            raise ValueError(
                f"Invoice already exists for {billing_period}: {existing.invoice_number}"
            )

        # Get usage events for period
        events = (
            self.db.query(UsageEvent)
            .filter_by(tenant_id=tenant_id, billing_period=billing_period)
            .all()
        )

        if not events:
            raise ValueError(f"No usage events found for {billing_period}")

        # Generate invoice number (format: INV-YYYY-MM-XXXX)
        invoice_count = (
            self.db.query(Invoice)
            .filter_by(tenant_id=tenant_id)
            .count()
        )
        invoice_number = f"INV-{billing_period}-{invoice_count + 1:04d}"

        # Create invoice
        invoice = Invoice(
            id=generate_id(),
            tenant_id=tenant_id,
            billing_period=billing_period,
            invoice_number=invoice_number,
            status=InvoiceStatus.DRAFT,
            notes=notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Aggregate usage by type
        usage_by_type = {}
        for event in events:
            if event.usage_type not in usage_by_type:
                usage_by_type[event.usage_type] = 0
            usage_by_type[event.usage_type] += event.quantity

        # Create line items
        total_subtotal = 0
        line_item_count = 0

        for usage_type, quantity in usage_by_type.items():
            # Calculate unit price and total
            if usage_type == "api_calls":
                unit_price_cents = PricingConfig.API_CALL_COST_CENTS
                description = f"API Calls - {billing_period}"
            elif usage_type == "ai_tokens":
                unit_price_cents = PricingConfig.OUTPUT_TOKENS_PER_MILLION // 1_000_000
                description = f"AI Tokens - {billing_period}"
            else:
                continue

            # Calculate line item total
            subtotal_cents = (quantity * unit_price_cents) // 1_000_000 if usage_type == "ai_tokens" else quantity * unit_price_cents
            if usage_type == "ai_tokens":
                subtotal_cents = PricingConfig.calculate_token_cost(output_tokens=quantity)

            # Create line item
            line_item = InvoiceLineItem(
                id=generate_id(),
                invoice_id=invoice.id,
                description=description,
                usage_type=usage_type,
                quantity=quantity,
                unit_price_cents=unit_price_cents,
                subtotal_cents=subtotal_cents,
                discount_cents=0,
                tax_cents=0,
                total_cents=subtotal_cents,
                created_at=datetime.utcnow(),
            )

            self.db.add(line_item)
            total_subtotal += subtotal_cents
            line_item_count += 1

        # Update invoice totals
        invoice.subtotal_cents = total_subtotal
        invoice.discount_cents = 0
        invoice.tax_cents = 0
        invoice.total_cents = total_subtotal
        invoice.line_items_count = line_item_count

        # Save invoice
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)

        return invoice

    def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """
        Get invoice by ID.

        Args:
            invoice_id: Invoice ID

        Returns:
            Invoice object or None
        """
        return self.db.query(Invoice).filter_by(id=invoice_id).first()

    def get_invoice_by_number(self, invoice_number: str) -> Optional[Invoice]:
        """
        Get invoice by invoice number.

        Args:
            invoice_number: Invoice number (INV-YYYY-MM-XXXX)

        Returns:
            Invoice object or None
        """
        return self.db.query(Invoice).filter_by(invoice_number=invoice_number).first()

    def get_tenant_invoices(
        self,
        tenant_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Invoice], int]:
        """
        Get invoices for a tenant (paginated).

        Args:
            tenant_id: Tenant ID
            limit: Max number of results
            offset: Number of results to skip

        Returns:
            Tuple of (invoices list, total count)
        """
        query = self.db.query(Invoice).filter_by(tenant_id=tenant_id)
        total_count = query.count()

        invoices = (
            query
            .order_by(desc(Invoice.created_at))
            .limit(limit)
            .offset(offset)
            .all()
        )

        return invoices, total_count

    def get_invoice_line_items(self, invoice_id: str) -> List[InvoiceLineItem]:
        """
        Get line items for an invoice.

        Args:
            invoice_id: Invoice ID

        Returns:
            List of InvoiceLineItem objects
        """
        return (
            self.db.query(InvoiceLineItem)
            .filter_by(invoice_id=invoice_id)
            .all()
        )

    def issue_invoice(self, invoice_id: str) -> Invoice:
        """
        Issue an invoice (change status to ISSUED).

        Args:
            invoice_id: Invoice ID

        Returns:
            Updated Invoice object

        Raises:
            ValueError: If invoice not found or already issued
        """
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError(
                f"Cannot issue invoice with status {invoice.status}"
            )

        invoice.status = InvoiceStatus.ISSUED
        invoice.issued_at = datetime.utcnow()
        invoice.due_at = datetime.utcnow() + timedelta(days=30)
        invoice.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def mark_paid(
        self,
        invoice_id: str,
        paid_at: Optional[datetime] = None,
    ) -> Invoice:
        """
        Mark invoice as paid.

        Args:
            invoice_id: Invoice ID
            paid_at: Payment date (default: now)

        Returns:
            Updated Invoice object

        Raises:
            ValueError: If invoice not found
        """
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = paid_at or datetime.utcnow()
        invoice.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def cancel_invoice(self, invoice_id: str) -> Invoice:
        """
        Cancel an invoice.

        Args:
            invoice_id: Invoice ID

        Returns:
            Updated Invoice object

        Raises:
            ValueError: If invoice not found or already paid
        """
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        if invoice.status == InvoiceStatus.PAID:
            raise ValueError("Cannot cancel a paid invoice")

        invoice.status = InvoiceStatus.CANCELLED
        invoice.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def get_invoice_html(self, invoice_id: str) -> str:
        """
        Generate HTML representation of invoice.

        Useful for email, PDF generation, etc.

        Args:
            invoice_id: Invoice ID

        Returns:
            HTML string

        Raises:
            ValueError: If invoice not found
        """
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        line_items = self.get_invoice_line_items(invoice_id)

        # Build HTML
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .invoice {{ max-width: 800px; margin: 20px; }}
                .header {{ border-bottom: 2px solid #333; padding-bottom: 20px; }}
                .line-items {{ margin: 20px 0; }}
                .line-item {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }}
                .total {{ font-weight: bold; font-size: 18px; }}
                .label {{ font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="invoice">
                <div class="header">
                    <h1>Invoice {invoice.invoice_number}</h1>
                    <p>Billing Period: {invoice.billing_period}</p>
                    <p>Status: {invoice.status.value}</p>
                </div>
                
                <div class="line-items">
                    <h3>Usage Summary</h3>
        """

        for item in line_items:
            html += f"""
                    <div class="line-item">
                        <span>{item.description}</span>
                        <span>${item.total_cents/100:.2f}</span>
                    </div>
            """

        html += f"""
                </div>
                
                <div class="totals">
                    <div class="line-item">
                        <span class="label">Subtotal:</span>
                        <span>${invoice.subtotal_cents/100:.2f}</span>
                    </div>
                    <div class="line-item">
                        <span class="label">Discount:</span>
                        <span>${invoice.discount_cents/100:.2f}</span>
                    </div>
                    <div class="line-item">
                        <span class="label">Tax:</span>
                        <span>${invoice.tax_cents/100:.2f}</span>
                    </div>
                    <div class="line-item total">
                        <span>TOTAL DUE:</span>
                        <span>${invoice.total_cents/100:.2f}</span>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def get_tenant_invoice_summary(self, tenant_id: str) -> dict:
        """
        Get invoice summary for a tenant.

        Shows total billed, paid, outstanding, etc.

        Args:
            tenant_id: Tenant ID

        Returns:
            Dictionary with invoice statistics
        """
        invoices = (
            self.db.query(Invoice)
            .filter_by(tenant_id=tenant_id)
            .all()
        )

        total_billed = 0
        total_paid = 0
        total_outstanding = 0
        by_status = {}

        for invoice in invoices:
            total_billed += invoice.total_cents

            if invoice.status == InvoiceStatus.PAID:
                total_paid += invoice.total_cents
            elif invoice.status in [InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE]:
                total_outstanding += invoice.total_cents

            status_name = invoice.status.value
            if status_name not in by_status:
                by_status[status_name] = {"count": 0, "total_cents": 0}
            by_status[status_name]["count"] += 1
            by_status[status_name]["total_cents"] += invoice.total_cents

        return {
            "tenant_id": tenant_id,
            "total_invoices": len(invoices),
            "total_billed_cents": total_billed,
            "total_billed_dollars": round(total_billed / 100, 2),
            "total_paid_cents": total_paid,
            "total_paid_dollars": round(total_paid / 100, 2),
            "total_outstanding_cents": total_outstanding,
            "total_outstanding_dollars": round(total_outstanding / 100, 2),
            "by_status": by_status,
        }
