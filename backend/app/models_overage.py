"""Overage model and schemas for billing usage beyond plan quotas."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class OverageStatus(str, enum.Enum):
    """Overage status enumeration."""
    
    ALLOWED = "allowed"  # Plan allows overages
    NOT_ALLOWED = "not_allowed"  # Plan does not allow overages
    SUSPENDED = "suspended"  # Too many overages, account suspended


class OverageCharge(Base):
    """Overage charge record - tracks usage beyond quota."""
    
    __tablename__ = "overage_charges"
    
    # Primary key
    id = Column(String(50), primary_key=True)
    
    # Relationships
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False, index=True)
    tenant = relationship("Tenant")
    
    subscription_id = Column(String(50), ForeignKey("subscriptions.id"), nullable=False, index=True)
    subscription = relationship("Subscription")
    
    # Billing period
    billing_period = Column(String(7), nullable=False, index=True)  # YYYY-MM
    
    # Usage details
    usage_type = Column(String(50), nullable=False)  # api_calls, ai_tokens
    quota_limit = Column(Integer, nullable=False)  # Plan limit
    quota_used = Column(Integer, nullable=False)  # Used within quota
    overage_quantity = Column(Integer, nullable=False)  # Quantity over quota
    
    # Pricing
    overage_unit_price_cents = Column(Integer, nullable=False)  # Cost per unit
    overage_total_cost_cents = Column(Integer, nullable=False)  # Total overage charge (integers only)
    
    # Status
    invoiced = Column(Boolean, nullable=False, default=False)
    invoice_id = Column(String(50), ForeignKey("invoices.id"), nullable=True)
    
    # Timestamps
    detected_at = Column(DateTime, nullable=False)  # When overage was detected
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<OverageCharge {self.usage_type}: {self.overage_quantity} units = ${self.overage_total_cost_cents/100:.2f}>"


class OveragePolicy(Base):
    """Overage policy configuration per plan."""
    
    __tablename__ = "overage_policies"
    
    # Primary key
    id = Column(String(50), primary_key=True)
    
    # Relationships
    plan_id = Column(String(50), ForeignKey("plans.id"), nullable=False, unique=True, index=True)
    plan = relationship("Plan")
    
    # Overage settings
    allows_overage = Column(Boolean, nullable=False, default=False)  # Can go over quota?
    
    # Pricing for overages (per unit, in cents)
    api_calls_overage_price_cents = Column(Integer, nullable=False, default=0)  # Per additional API call
    ai_tokens_overage_price_cents = Column(Integer, nullable=False, default=0)  # Per additional token
    
    # Thresholds
    max_overage_amount_cents = Column(Integer, nullable=True)  # Max total overage charge before suspension
    max_overage_quantity = Column(Integer, nullable=True)  # Max overage units before suspension
    
    # Suspension
    suspend_on_overage_exceeded = Column(Boolean, nullable=False, default=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<OveragePolicy {self.plan_id}: api={self.api_calls_overage_price_cents}, tokens={self.ai_tokens_overage_price_cents}>"


# Pydantic schemas for API

from pydantic import BaseModel, ConfigDict, Field


class OverageChargeResponse(BaseModel):
    """Overage charge response schema."""
    
    id: str
    billing_period: str
    usage_type: str
    quota_limit: int
    quota_used: int
    overage_quantity: int
    overage_unit_price_cents: int
    overage_total_cost_cents: int
    overage_total_cost_dollars: Optional[float] = None
    invoiced: bool
    detected_at: datetime
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class OveragePolicyResponse(BaseModel):
    """Overage policy response schema."""
    
    id: str
    plan_id: str
    allows_overage: bool
    api_calls_overage_price_cents: int
    ai_tokens_overage_price_cents: int
    max_overage_amount_cents: Optional[int]
    max_overage_quantity: Optional[int]
    suspend_on_overage_exceeded: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class OveragePolicyUpdate(BaseModel):
    """Update overage policy request schema."""
    
    allows_overage: Optional[bool] = Field(None, description="Allow usage beyond quota")
    api_calls_overage_price_cents: Optional[int] = Field(None, description="Cost per additional API call")
    ai_tokens_overage_price_cents: Optional[int] = Field(None, description="Cost per additional token")
    max_overage_amount_cents: Optional[int] = Field(None, description="Max overage charge before suspension")
    max_overage_quantity: Optional[int] = Field(None, description="Max overage units before suspension")
    suspend_on_overage_exceeded: Optional[bool] = Field(None, description="Suspend on overage limit exceeded")


class OverageChargeListResponse(BaseModel):
    """List of overage charges with pagination."""
    
    charges: List[OverageChargeResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class OverageSummaryResponse(BaseModel):
    """Overage summary for tenant."""
    
    tenant_id: str
    current_period: str
    total_overage_charges_cents: int
    total_overage_charges_dollars: float
    total_overage_quantity: int
    api_call_overage_cents: int
    token_overage_cents: int
    invoiced_overages_cents: int
    pending_overages_cents: int
    overage_status: str


class OverageStatusResponse(BaseModel):
    """Current overage status for subscription."""
    
    subscription_id: str
    allows_overage: bool
    current_period_overage_cents: int
    current_period_overage_dollars: float
    current_period_overage_quantity: int
    max_allowed_cents: Optional[int]
    max_allowed_quantity: Optional[int]
    will_suspend: bool
    message: str