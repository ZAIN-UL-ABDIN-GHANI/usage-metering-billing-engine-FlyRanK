"""SQLAlchemy database models."""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    Index,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Tenant(Base):
    """Tenant model representing a customer organization."""

    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    stripe_customer_id = Column(String(255), unique=True, nullable=True)
    plan_id = Column(String(36), ForeignKey("plans.id"), nullable=False, default="free")
    status = Column(String(50), default="active", nullable=False)  # active, suspended, deleted
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    plan = relationship("Plan", back_populates="tenants")
    subscriptions = relationship("Subscription", back_populates="tenant", cascade="all, delete-orphan")
    usage_events = relationship("UsageEvent", back_populates="tenant", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="tenant", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="tenant", cascade="all, delete-orphan")
    alert_preferences = relationship("AlertPreference", back_populates="tenant", uselist=False, cascade="all, delete-orphan")


class Plan(Base):
    """Plan model representing subscription tiers."""

    __tablename__ = "plans"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    stripe_price_id = Column(String(255), nullable=True, unique=True)
    monthly_cost_cents = Column(Integer, default=0, nullable=False)  # In cents (USD)

    # Quotas
    api_calls_limit = Column(Integer, nullable=False)
    ai_tokens_limit = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenants = relationship("Tenant", back_populates="plan")


class Subscription(Base):
    """Subscription model representing active subscriptions."""

    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    stripe_subscription_id = Column(String(255), unique=True, nullable=True)
    plan_id = Column(String(36), ForeignKey("plans.id"), nullable=False)
    status = Column(
        String(50),
        default="active",
        nullable=False,
    )  # active, past_due, canceled, trialing
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = relationship("Tenant", back_populates="subscriptions")


class UsageEvent(Base):
    """Usage event model for tracking metered usage."""

    __tablename__ = "usage_events"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    usage_type = Column(String(50), nullable=False, index=True)  # api_calls, ai_tokens
    quantity = Column(Integer, nullable=False)  # Exact integer count
    idempotency_key = Column(String(255), nullable=False, index=True)
    cost_cents = Column(Integer, nullable=True)  # In cents, calculated later
    billing_period = Column(String(7), nullable=False, index=True)  # YYYY-MM format
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    tenant = relationship("Tenant", back_populates="usage_events")

    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_tenant_idempotency"),
    )


class WebhookEvent(Base):
    """Webhook event model for deduplicating Stripe webhooks."""

    __tablename__ = "webhook_events"

    id = Column(String(36), primary_key=True)
    stripe_event_id = Column(String(255), unique=True, nullable=False)
    event_type = Column(String(100), nullable=False, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    processed = Column(Boolean, default=False, nullable=False)
    payload = Column(Text, nullable=False)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)


# Re-export models defined in secondary model modules
from app.models_invoice import Invoice, InvoiceLineItem  # noqa: F401