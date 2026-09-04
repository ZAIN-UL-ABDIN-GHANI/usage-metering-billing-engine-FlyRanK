"""Invoice model and schemas for billing statements."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class InvoiceStatus(str, enum.Enum):
    """Invoice status enumeration."""
    
    DRAFT = "draft"  # Generated but not finalized
    ISSUED = "issued"  # Ready for customer viewing
    PAID = "paid"  # Payment received
    OVERDUE = "overdue"  # Not paid within terms
    CANCELLED = "cancelled"  # Voided


class Invoice(Base):
    """Invoice database model."""
    
    __tablename__ = "invoices"
    
    # Primary key
    id = Column(String(50), primary_key=True)
    
    # Relationships
    # ✅ FIX 1: Point to 'tenants.id' (plural) to match Tenant.__tablename__
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False, index=True)
    tenant = relationship("Tenant", back_populates="invoices")
    
    # ✅ FIX 2: Added relationship to link line items back to the parent invoice
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")
    
    # Invoice details
    billing_period = Column(String(7), nullable=False)  # YYYY-MM format
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    
    # Amounts (in cents, integers only)
    subtotal_cents = Column(Integer, nullable=False, default=0)  # Before discounts/taxes
    discount_cents = Column(Integer, nullable=False, default=0)  # Total discounts
    tax_cents = Column(Integer, nullable=False, default=0)  # Total tax
    total_cents = Column(Integer, nullable=False, default=0)  # Final amount due
    
    # Line items count
    line_items_count = Column(Integer, nullable=False, default=0)
    
    # Status and dates
    status = Column(
        SQLEnum(InvoiceStatus),
        nullable=False,
        default=InvoiceStatus.DRAFT,
        index=True
    )
    issued_at = Column(DateTime, nullable=True)  # When issued to customer
    due_at = Column(DateTime, nullable=True)  # Payment due date
    paid_at = Column(DateTime, nullable=True)  # When payment received
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Metadata
    stripe_invoice_id = Column(String(100), nullable=True, unique=True)  # Stripe invoice ID if synced
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Invoice {self.invoice_number}: ${self.total_cents/100:.2f}>"


class InvoiceLineItem(Base):
    """Invoice line item (usage breakdown)."""
    
    __tablename__ = "invoice_line_items"
    
    # Primary key
    id = Column(String(50), primary_key=True)
    
    # Relationships
    invoice_id = Column(String(50), ForeignKey("invoices.id"), nullable=False, index=True)
    # ✅ FIX 3: Added back_populates="line_items"
    invoice = relationship("Invoice", back_populates="line_items")
    
    # Line item details
    description = Column(String(500), nullable=False)  # e.g., "API Calls - January 2024"
    usage_type = Column(String(50), nullable=False)  # api_calls, ai_tokens, etc.
    
    # Quantity and rates
    quantity = Column(Integer, nullable=False)  # Number of units
    unit_price_cents = Column(Integer, nullable=False)  # Cost per unit (in cents)
    
    # Totals (in cents)
    subtotal_cents = Column(Integer, nullable=False)  # quantity × unit_price
    discount_cents = Column(Integer, nullable=False, default=0)
    tax_cents = Column(Integer, nullable=False, default=0)
    total_cents = Column(Integer, nullable=False)  # Final line item cost
    
    # Additional info
    extra_metadata = Column("metadata", Text, nullable=True)  # JSON for additional details
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<LineItem {self.description}: ${self.total_cents/100:.2f}>"


# Add relationship to Tenant model
def add_invoice_relationship_to_tenant():
    """Add invoices relationship to Tenant model (called during migration)."""
    if not hasattr(Base.metadata.tables.get('tenants'), 'invoices'):
        # Relationship will be added when models are loaded
        pass


# Pydantic schemas for API

from pydantic import BaseModel, ConfigDict, Field


class InvoiceLineItemResponse(BaseModel):
    """Invoice line item response schema."""
    
    id: str
    description: str
    usage_type: str
    quantity: int
    unit_price_cents: int
    subtotal_cents: int
    discount_cents: int
    tax_cents: int
    total_cents: int
    
    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    """Invoice response schema."""
    
    id: str
    invoice_number: str
    billing_period: str
    
    # Amounts
    subtotal_cents: int
    discount_cents: int
    tax_cents: int
    total_cents: int
    
    # Status and dates
    status: str
    issued_at: Optional[datetime]
    due_at: Optional[datetime]
    paid_at: Optional[datetime]
    
    # Metadata
    line_items_count: int
    stripe_invoice_id: Optional[str]
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class InvoiceDetailedResponse(InvoiceResponse):
    """Detailed invoice response with line items."""
    
    line_items: List[InvoiceLineItemResponse] = []


class InvoiceCreate(BaseModel):
    """Create invoice request schema."""
    
    billing_period: str = Field(..., description="Billing period (YYYY-MM)")
    notes: Optional[str] = Field(None, description="Optional invoice notes")


class InvoiceUpdate(BaseModel):
    """Update invoice request schema."""
    
    status: Optional[str] = Field(None, description="New invoice status")
    notes: Optional[str] = Field(None, description="Updated notes")
    paid_at: Optional[datetime] = Field(None, description="Mark as paid")


class InvoiceListResponse(BaseModel):
    """Invoice list response with pagination."""
    
    invoices: List[InvoiceResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int