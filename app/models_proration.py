"""Proration model and schemas for mid-cycle billing adjustments."""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class ProrationType(str, enum.Enum):
    """Proration type enumeration."""
    
    UPGRADE = "upgrade"  # Moved to more expensive plan
    DOWNGRADE = "downgrade"  # Moved to cheaper plan
    PLAN_CHANGE = "plan_change"  # Changed plans (could be up or down)


class ProratedAdjustment(Base):
    """Adjustment record for mid-cycle plan changes."""
    
    __tablename__ = "prorated_adjustments"
    
    # Primary key
    id = Column(String(50), primary_key=True)
    
    # Relationships
    tenant_id = Column(String(50), ForeignKey("tenant.id"), nullable=False, index=True)
    tenant = relationship("Tenant")
    
    subscription_id = Column(String(50), ForeignKey("subscription.id"), nullable=False, index=True)
    subscription = relationship("Subscription")
    
    # Plan details
    from_plan_id = Column(String(50), ForeignKey("plan.id"), nullable=False)
    to_plan_id = Column(String(50), ForeignKey("plan.id"), nullable=False)
    from_plan = relationship("Plan", foreign_keys=[from_plan_id])
    to_plan = relationship("Plan", foreign_keys=[to_plan_id])
    
    # Proration type
    proration_type = Column(
        SQLEnum(ProrationType),
        nullable=False,
        index=True
    )
    
    # Billing period info
    billing_period_start = Column(DateTime, nullable=False)  # Start of current period
    billing_period_end = Column(DateTime, nullable=False)  # End of current period
    change_date = Column(DateTime, nullable=False)  # When plan changed
    
    # Usage info at time of change
    days_in_period = Column(Integer, nullable=False)  # Total days in period
    days_remaining = Column(Integer, nullable=False)  # Days left after change
    
    # Cost calculations (in cents, integers only)
    old_plan_daily_rate_cents = Column(Integer, nullable=False)  # Per-day cost of old plan
    new_plan_daily_rate_cents = Column(Integer, nullable=False)  # Per-day cost of new plan
    
    # Used amount of old plan
    days_used_old_plan = Column(Integer, nullable=False)  # How many days used old plan
    cost_old_plan_used_cents = Column(Integer, nullable=False)  # Cost for days used
    
    # Credit/charge for remaining period
    cost_old_plan_remaining_cents = Column(Integer, nullable=False)  # Cost for remaining days (old plan)
    cost_new_plan_remaining_cents = Column(Integer, nullable=False)  # Cost for remaining days (new plan)
    
    # Net adjustment
    credit_cents = Column(Integer, nullable=False, default=0)  # Credit to apply
    charge_cents = Column(Integer, nullable=False, default=0)  # Additional charge
    net_adjustment_cents = Column(Integer, nullable=False)  # Net (credit is negative, charge is positive)
    
    # Status
    applied = Column(datetime, nullable=True)  # When applied to account
    
    # Metadata
    notes = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<ProratedAdjustment {self.proration_type.value}: ${abs(self.net_adjustment_cents)/100:.2f}>"


# Pydantic schemas for API

from pydantic import BaseModel, Field
from typing import List


class ProratedAdjustmentResponse(BaseModel):
    """Prorated adjustment response schema."""
    
    id: str
    subscription_id: str
    from_plan_id: str
    to_plan_id: str
    proration_type: str
    change_date: datetime
    
    # Calculations
    days_in_period: int
    days_remaining: int
    days_used_old_plan: int
    
    # Costs
    old_plan_daily_rate_cents: int
    new_plan_daily_rate_cents: int
    credit_cents: int
    charge_cents: int
    net_adjustment_cents: int
    
    # Status
    applied: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class PlanChangeRequest(BaseModel):
    """Request to change plan (with proration)."""
    
    new_plan_id: str = Field(..., description="ID of new plan to switch to")
    effective_date: Optional[datetime] = Field(None, description="When to apply change (default: now)")


class PlanChangeResponse(BaseModel):
    """Response from plan change (includes proration)."""
    
    success: bool
    subscription_id: str
    old_plan_id: str
    new_plan_id: str
    proration: Optional[ProratedAdjustmentResponse]
    message: str
    
    # If there's a charge/credit
    credit_amount_cents: Optional[int] = None
    credit_amount_dollars: Optional[float] = None
    charge_amount_cents: Optional[int] = None
    charge_amount_dollars: Optional[float] = None


class ProratedAdjustmentListResponse(BaseModel):
    """List of prorated adjustments with pagination."""
    
    adjustments: List[ProratedAdjustmentResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int
