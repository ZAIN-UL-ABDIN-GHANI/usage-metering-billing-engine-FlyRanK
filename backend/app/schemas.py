"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field


# ============================================================================
# Tenant Schemas
# ============================================================================


class TenantCreate(BaseModel):
    """Schema for creating a tenant."""

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr


class TenantUpdate(BaseModel):
    """Schema for updating a tenant."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    status: Optional[str] = None


class TenantResponse(BaseModel):
    """Schema for tenant response."""

    id: str
    name: str
    email: str
    stripe_customer_id: Optional[str]
    plan_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Plan Schemas
# ============================================================================


class PlanCreate(BaseModel):
    """Schema for creating a plan."""

    id: str = Field(..., min_length=1, max_length=36)
    name: str = Field(..., min_length=1, max_length=100)
    stripe_price_id: Optional[str] = None
    monthly_cost_cents: int = Field(default=0, ge=0)
    api_calls_limit: int = Field(..., gt=0)
    ai_tokens_limit: int = Field(..., gt=0)


class PlanResponse(BaseModel):
    """Schema for plan response."""

    id: str
    name: str
    stripe_price_id: Optional[str]
    monthly_cost_cents: int
    api_calls_limit: int
    ai_tokens_limit: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Subscription Schemas
# ============================================================================


class SubscriptionCreate(BaseModel):
    """Schema for creating a subscription."""

    tenant_id: str
    plan_id: str
    stripe_subscription_id: Optional[str] = None
    current_period_start: datetime
    current_period_end: datetime


class SubscriptionUpdate(BaseModel):
    """Schema for updating a subscription."""

    status: Optional[str] = None
    plan_id: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None


class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""

    id: str
    tenant_id: str
    stripe_subscription_id: Optional[str]
    plan_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Usage Event Schemas
# ============================================================================


class UsageEventCreate(BaseModel):
    """Schema for creating a usage event."""

    tenant_id: str
    usage_type: str = Field(..., pattern="^(api_calls|ai_tokens)$")
    quantity: int = Field(..., gt=0)
    idempotency_key: str = Field(..., min_length=1)
    billing_period: str = Field(..., pattern=r"^\d{4}-\d{2}$")


class UsageEventResponse(BaseModel):
    """Schema for usage event response."""

    id: str
    tenant_id: str
    usage_type: str
    quantity: int
    idempotency_key: str
    cost_cents: Optional[int]
    billing_period: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Usage Summary Schemas
# ============================================================================


class UsageSummary(BaseModel):
    """Schema for usage summary."""

    usage_type: str
    used: int
    limit: int
    percentage: float
    cost_cents: int


class UsageResponse(BaseModel):
    """Schema for complete usage response."""

    tenant_id: str
    billing_period: str
    plan_id: str
    plan_name: str
    api_calls: UsageSummary
    ai_tokens: UsageSummary
    total_cost_cents: int
    remaining_quota: bool
    next_billing_date: Optional[datetime]
    updated_at: datetime


# ============================================================================
# Stripe Schemas
# ============================================================================


class StripeCheckoutCreate(BaseModel):
    """Schema for initiating Stripe checkout."""

    tenant_id: str
    plan_id: str
    return_url: str


class StripeCheckoutResponse(BaseModel):
    """Schema for Stripe checkout response."""

    checkout_url: str
    session_id: str


class StripeWebhookEvent(BaseModel):
    """Schema for Stripe webhook event."""

    id: str
    type: str
    data: dict


# ============================================================================
# Error Schemas
# ============================================================================


class ErrorResponse(BaseModel):
    """Schema for error response."""

    status: int
    message: str
    error_code: Optional[str] = None
    details: Optional[dict] = None


class ValidationError(BaseModel):
    """Schema for validation error."""

    status: int = 422
    message: str = "Validation error"
    errors: List[dict]
