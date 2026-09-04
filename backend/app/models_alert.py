"""Alert model and schemas for usage notifications."""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class AlertType(str, enum.Enum):
    """Alert type enumeration."""
    
    THRESHOLD_80 = "threshold_80"  # Usage at 80% of quota
    THRESHOLD_100 = "threshold_100"  # Usage at or exceeds quota
    OVERAGE_WARNING = "overage_warning"  # Usage exceeds quota (overage billing)


class AlertStatus(str, enum.Enum):
    """Alert status enumeration."""
    
    PENDING = "pending"  # Created, not yet notified
    SENT = "sent"  # Notification sent to customer
    ACKNOWLEDGED = "acknowledged"  # Customer acknowledged alert
    RESOLVED = "resolved"  # Usage returned below threshold


class Alert(Base):
    """Alert database model for usage notifications."""
    
    __tablename__ = "alerts"
    
    # Primary key
    id = Column(String(50), primary_key=True)
    
    # Relationships (FIXED: tenants.id instead of tenant.id)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False, index=True)
    tenant = relationship("Tenant", back_populates="alerts")
    
    # Alert details
    alert_type = Column(
        SQLEnum(AlertType),
        nullable=False,
        index=True
    )
    billing_period = Column(String(7), nullable=False, index=True)  # YYYY-MM
    
    # Usage at time of alert
    usage_type = Column(String(50), nullable=False)  # api_calls, ai_tokens
    current_usage = Column(Integer, nullable=False)  # Current quantity
    quota_limit = Column(Integer, nullable=False)  # Plan quota limit
    usage_percent = Column(Float, nullable=False)  # Percentage of quota (0-200+)
    
    # Thresholds
    threshold_percent = Column(Integer, nullable=False)  # 80 or 100
    
    # Status tracking
    status = Column(
        SQLEnum(AlertStatus),
        nullable=False,
        default=AlertStatus.PENDING,
        index=True
    )
    sent_at = Column(DateTime, nullable=True)  # When notification sent
    acknowledged_at = Column(DateTime, nullable=True)  # When acknowledged by customer
    
    # Additional info
    message = Column(String(500), nullable=True)  # Alert message
    notification_method = Column(String(50), nullable=True)  # email, webhook, sms, etc.
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Alert {self.alert_type.value}: {self.usage_percent:.0f}%>"


class AlertPreference(Base):
    """User alert notification preferences."""
    
    __tablename__ = "alert_preferences"
    
    # Primary key
    id = Column(String(50), primary_key=True)
    
    # Relationships (FIXED: tenants.id instead of tenant.id)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False, unique=True, index=True)
    tenant = relationship("Tenant", back_populates="alert_preferences")
    
    # Notification settings
    email_on_80_percent = Column(Boolean, nullable=False, default=True)
    email_on_100_percent = Column(Boolean, nullable=False, default=True)
    email_on_overage = Column(Boolean, nullable=False, default=True)
    
    # Contact info
    email_address = Column(String(255), nullable=False)
    
    # Additional preferences
    notify_daily_summary = Column(Boolean, nullable=False, default=False)  # Daily usage summary
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AlertPreference {self.tenant_id}>"


# Pydantic schemas for API

from pydantic import BaseModel, Field, EmailStr
from typing import List


class AlertResponse(BaseModel):
    """Alert response schema."""
    
    id: str
    alert_type: str
    billing_period: str
    usage_type: str
    current_usage: int
    quota_limit: int
    usage_percent: float
    threshold_percent: int
    status: str
    message: Optional[str]
    notification_method: Optional[str]
    sent_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    """Alert list response with pagination."""
    
    alerts: List[AlertResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class AlertPreferenceResponse(BaseModel):
    """Alert preference response schema."""
    
    id: str
    email_address: str
    email_on_80_percent: bool
    email_on_100_percent: bool
    email_on_overage: bool
    notify_daily_summary: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AlertPreferenceUpdate(BaseModel):
    """Update alert preference request schema."""
    
    email_address: Optional[EmailStr] = Field(None, description="Email address for alerts")
    email_on_80_percent: Optional[bool] = Field(None, description="Alert at 80% usage")
    email_on_100_percent: Optional[bool] = Field(None, description="Alert at 100% usage")
    email_on_overage: Optional[bool] = Field(None, description="Alert on overage")
    notify_daily_summary: Optional[bool] = Field(None, description="Daily usage summary")


class AlertCreate(BaseModel):
    """Create alert request schema."""
    
    alert_type: str = Field(..., description="Alert type")
    usage_type: str = Field(..., description="Usage type (api_calls, ai_tokens)")
    current_usage: int = Field(..., description="Current usage quantity")
    quota_limit: int = Field(..., description="Plan quota limit")
    threshold_percent: int = Field(..., description="Threshold percentage")


class AlertAcknowledge(BaseModel):
    """Acknowledge alert request schema."""
    
    acknowledged: bool = Field(True, description="Mark as acknowledged")