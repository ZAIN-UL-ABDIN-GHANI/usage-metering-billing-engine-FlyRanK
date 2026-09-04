"""Reporting model and schemas for analytics, trends, and dashboards."""

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ReportType(str, enum.Enum):
    """Report type enumeration."""

    USAGE_ANALYTICS = "usage_analytics"  # Usage by type over time
    REVENUE_ANALYSIS = "revenue_analysis"  # Revenue by plan/customer
    COST_BREAKDOWN = "cost_breakdown"  # Cost analysis by component
    TENANT_METRICS = "tenant_metrics"  # Tenant-specific metrics
    FORECAST = "forecast"  # Usage/revenue forecast
    CUSTOM = "custom"  # Custom query report


class ReportFrequency(str, enum.Enum):
    """Report generation frequency."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    ONCE = "once"


class SavedReport(Base):
    """Saved report configuration for recurring generation."""

    __tablename__ = "saved_reports"

    # Primary key
    id = Column(String(50), primary_key=True)

    # Relationships - FIXED: Updated foreign key target to 'tenants.id'
    tenant_id = Column(
        String(50), ForeignKey("tenants.id"), nullable=True, index=True
    )
    tenant = relationship("Tenant")

    # Report details
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    report_type = Column(SQLEnum(ReportType), nullable=False, index=True)

    # Configuration
    frequency = Column(SQLEnum(ReportFrequency), nullable=False)
    include_charts = Column(Boolean, nullable=False, default=True)
    include_summary = Column(Boolean, nullable=False, default=True)
    include_trends = Column(Boolean, nullable=False, default=True)

    # Parameters (stored as JSON string)
    parameters = Column(Text, nullable=True)  # JSON config for report

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    last_generated_at = Column(DateTime, nullable=True)
    next_generation_at = Column(DateTime, nullable=True)

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
        return f"<SavedReport {self.name}: {self.report_type.value}>"


class ReportRun(Base):
    """Single report execution record."""

    __tablename__ = "report_runs"

    # Primary key
    id = Column(String(50), primary_key=True)

    # Relationships
    saved_report_id = Column(
        String(50), ForeignKey("saved_reports.id"), nullable=True
    )
    saved_report = relationship("SavedReport")

    # Report details
    report_type = Column(SQLEnum(ReportType), nullable=False)
    date_range_start = Column(DateTime, nullable=False)
    date_range_end = Column(DateTime, nullable=False)

    # Results summary
    total_records = Column(Integer, nullable=False, default=0)
    summary_data = Column(Text, nullable=True)  # JSON summary

    # Status
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)

    # Timestamps
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    def __repr__(self):
        return (
            f"<ReportRun {self.report_type.value}: {self.total_records} records>"
        )


# Pydantic schemas for API


class UsageAnalyticsResponse(BaseModel):
    """Usage analytics response."""

    period: str
    api_calls_total: int
    api_calls_average_daily: float
    tokens_total: int
    tokens_average_daily: float
    peak_usage_date: Optional[str]
    peak_usage_value: Optional[int]
    trend: str  # "up", "down", "flat"
    trend_percent: float

    model_config = ConfigDict(from_attributes=True)


class RevenueAnalyticsResponse(BaseModel):
    """Revenue analytics response."""

    period: str
    total_revenue_cents: int
    total_revenue_dollars: float
    revenue_by_plan: Dict[str, float]
    revenue_by_type: Dict[str, float]  # api_calls, tokens, overages, etc
    average_revenue_per_tenant: float
    month_over_month_growth: float


class CostBreakdownResponse(BaseModel):
    """Cost breakdown response."""

    period: str
    total_cost_cents: int
    total_cost_dollars: float
    cost_by_usage_type: Dict[str, float]
    cost_by_component: Dict[str, float]  # metering, storage, compute, etc
    cost_variance_percent: float


class TenantMetricsResponse(BaseModel):
    """Tenant-specific metrics."""

    tenant_id: str
    period: str
    usage_api_calls: int
    usage_tokens: int
    revenue_generated_cents: int
    revenue_generated_dollars: float
    active_days: int
    churn_risk: str  # "low", "medium", "high"


class DashboardMetricsResponse(BaseModel):
    """Dashboard overview metrics."""

    current_period: str
    total_active_tenants: int
    total_active_subscriptions: int
    total_revenue_cents: int
    total_revenue_dollars: float
    total_usage_api_calls: int
    total_usage_tokens: int
    total_cost_cents: int
    total_cost_dollars: float
    gross_margin_percent: float
    churn_rate: float
    growth_rate_percent: float


class TrendDataResponse(BaseModel):
    """Trend data over time."""

    metric_name: str
    period_type: str  # daily, weekly, monthly
    data_points: List[
        Dict[str, Any]
    ]  # [{"date": "2026-08-19", "value": 1000}, ...]
    trend_direction: str  # "up", "down", "flat"
    trend_strength: float  # 0-1
    forecast_next_period: Optional[float]


class SavedReportResponse(BaseModel):
    """Saved report configuration."""

    id: str
    name: str
    report_type: str
    frequency: str
    is_active: bool
    last_generated_at: Optional[datetime]
    next_generation_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportRunResponse(BaseModel):
    """Report run result."""

    id: str
    report_type: str
    date_range_start: datetime
    date_range_end: datetime
    total_records: int
    success: bool
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]


class ReportListResponse(BaseModel):
    """List of saved reports."""

    reports: List[SavedReportResponse]
    total_count: int


class TrendForecastResponse(BaseModel):
    """Forecast data."""

    metric: str
    current_value: float
    forecast_7days: Optional[float]
    forecast_30days: Optional[float]
    forecast_90days: Optional[float]
    confidence: float  # 0-1
    factors: List[str]  # What's driving the trend