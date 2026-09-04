"""Reconciliation model and schemas for Stripe sync auditing."""

import enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ReconciliationType(str, enum.Enum):
    """Reconciliation type enumeration."""

    SUBSCRIPTION_MISMATCH = "subscription_mismatch"  # Plan mismatch
    PAYMENT_MISMATCH = "payment_mismatch"  # Payment status mismatch
    WEBHOOK_MISSED = "webhook_missed"  # Event not processed locally
    STRIPE_OFFLINE = "stripe_offline"  # Could not reach Stripe
    MANUAL_SYNC = "manual_sync"  # Manual reconciliation


class ReconciliationStatus(str, enum.Enum):
    """Reconciliation status enumeration."""

    PENDING = "pending"  # Found but not resolved
    RESOLVED = "resolved"  # Fixed the mismatch
    IGNORED = "ignored"  # Accepted as-is
    NEEDS_REVIEW = "needs_review"  # Requires manual intervention


class ReconciliationRun(Base):
    """Reconciliation run record - one run per scheduled job."""

    __tablename__ = "reconciliation_runs"

    # Primary key
    id = Column(String(50), primary_key=True)

    # Run details
    run_type = Column(String(50), nullable=False)  # scheduled, manual
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Results
    total_tenants_checked = Column(Integer, nullable=False, default=0)
    total_subscriptions_checked = Column(Integer, nullable=False, default=0)
    total_mismatches_found = Column(Integer, nullable=False, default=0)
    total_issues_resolved = Column(Integer, nullable=False, default=0)

    # Status
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<ReconciliationRun {self.run_type}: {self.total_mismatches_found} issues>"


class ReconciliationIssue(Base):
    """Individual reconciliation issue found."""

    __tablename__ = "reconciliation_issues"

    # Primary key
    id = Column(String(50), primary_key=True)

    # Relationships
    run_id = Column(
        String(50),
        ForeignKey("reconciliation_runs.id"),
        nullable=False,
        index=True,
    )
    run = relationship("ReconciliationRun")

    # FIXED: Updated foreign key string references to plural database table names
    tenant_id = Column(
        String(50), ForeignKey("tenants.id"), nullable=False, index=True
    )
    tenant = relationship("Tenant")

    subscription_id = Column(
        String(50), ForeignKey("subscriptions.id"), nullable=True, index=True
    )
    subscription = relationship("Subscription")

    # Issue details
    issue_type = Column(
        SQLEnum(ReconciliationType), nullable=False, index=True
    )

    # What was found
    local_value = Column(String(500), nullable=True)  # Local database value
    stripe_value = Column(String(500), nullable=True)  # Stripe API value

    # Stripe details
    stripe_object_id = Column(
        String(255), nullable=True
    )  # subscription ID, customer ID, etc
    stripe_object_type = Column(
        String(50), nullable=True
    )  # subscription, customer, etc

    # Resolution
    status = Column(
        SQLEnum(ReconciliationStatus),
        nullable=False,
        default=ReconciliationStatus.PENDING,
        index=True,
    )
    resolution_action = Column(
        String(500), nullable=True
    )  # What was done to fix it
    resolved_at = Column(DateTime, nullable=True)

    # Message
    message = Column(Text, nullable=False)

    # Timestamps
    created_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self):
        return f"<ReconciliationIssue {self.issue_type.value}: {self.status.value}>"


# Pydantic schemas for API


class ReconciliationIssueResponse(BaseModel):
    """Reconciliation issue response schema."""

    id: str
    issue_type: str
    local_value: Optional[str]
    stripe_value: Optional[str]
    stripe_object_id: Optional[str]
    stripe_object_type: Optional[str]
    status: str
    resolution_action: Optional[str]
    message: str
    created_at: datetime
    resolved_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ReconciliationRunResponse(BaseModel):
    """Reconciliation run response schema."""

    id: str
    run_type: str
    started_at: datetime
    completed_at: Optional[datetime]
    total_tenants_checked: int
    total_subscriptions_checked: int
    total_mismatches_found: int
    total_issues_resolved: int
    success: bool
    error_message: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReconciliationRunDetailResponse(BaseModel):
    """Detailed reconciliation run with issues."""

    run: ReconciliationRunResponse
    issues: List[ReconciliationIssueResponse]
    unresolved_count: int

    model_config = ConfigDict(from_attributes=True)


class ManualReconciliationRequest(BaseModel):
    """Request to run manual reconciliation."""

    tenant_id: Optional[str] = Field(
        None, description="Specific tenant to reconcile"
    )
    resolve_issues: bool = Field(
        False, description="Auto-resolve mismatches if possible"
    )


class ReconciliationSummaryResponse(BaseModel):
    """Summary of recent reconciliation runs."""

    last_run: Optional[ReconciliationRunResponse]
    last_successful_run: Optional[ReconciliationRunResponse]
    total_runs: int
    total_issues_found: int
    total_issues_resolved: int
    total_pending_issues: int
    latest_issues: List[ReconciliationIssueResponse]