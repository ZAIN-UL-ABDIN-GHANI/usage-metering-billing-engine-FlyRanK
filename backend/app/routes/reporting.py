"""Reporting routes - API endpoints for analytics and dashboards."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant
from app.models_reporting import (
    ReportType, ReportFrequency,
    UsageAnalyticsResponse, RevenueAnalyticsResponse, CostBreakdownResponse,
    TenantMetricsResponse, DashboardMetricsResponse, TrendDataResponse,
    SavedReportResponse, ReportRunResponse, ReportListResponse,
    TrendForecastResponse
)
from app.services.reporting_service import ReportingService

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)


# ==================== USAGE ANALYTICS ====================

@router.get("/usage", status_code=status.HTTP_200_OK)
async def get_usage_analytics(
    tenant_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get usage analytics for period.

    **Authentication**: Required (API key)

    Shows API calls and token usage trends over time.

    Args:
        tenant_id: Optional filter by tenant (must own tenant)
        days: Number of days to include

    Returns:
        Usage analytics with trends

    Raises:
        401: Unauthorized
        403: Access denied

    Example:
        GET /reports/usage?days=30
        Headers:
          X-API-Key: tenant-id
        Response (200 OK):
          {
            "period": "2026-07-20 to 2026-08-19",
            "api_calls_total": 45000,
            "api_calls_average_daily": 1500.0,
            "tokens_total": 2500000,
            "tokens_average_daily": 83333.33,
            "trend": "up",
            "trend_percent": 12.5
          }
    """
    # Validate access
    if tenant_id and tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    service = ReportingService(db)
    analytics = service.get_usage_analytics(
        tenant_id=tenant_id or current_tenant.id,
        start_date=start_date,
        end_date=end_date,
    )

    return analytics


# ==================== REVENUE ANALYTICS ====================

@router.get("/revenue", status_code=status.HTTP_200_OK)
async def get_revenue_analytics(
    days: int = Query(30, ge=1, le=365),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get revenue analytics for period.

    **Authentication**: Required (API key)

    Shows revenue breakdown by plan and usage type.

    Args:
        days: Number of days to include

    Returns:
        Revenue analytics with breakdown

    Raises:
        401: Unauthorized

    Example:
        GET /reports/revenue?days=30
        Headers:
          X-API-Key: tenant-id
        Response:
          {
            "period": "2026-07-20 to 2026-08-19",
            "total_revenue_cents": 125000,
            "total_revenue_dollars": 1250.0,
            "revenue_by_plan": {
              "pro": 875.0,
              "enterprise": 375.0
            },
            "average_revenue_per_tenant": 425.5
          }
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    service = ReportingService(db)
    analytics = service.get_revenue_analytics(
        start_date=start_date,
        end_date=end_date,
    )

    return analytics


# ==================== COST BREAKDOWN ====================

@router.get("/costs", status_code=status.HTTP_200_OK)
async def get_cost_breakdown(
    days: int = Query(30, ge=1, le=365),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get cost breakdown for period.

    **Authentication**: Required (API key)

    Shows cost analysis by usage type and component.

    Args:
        days: Number of days to include

    Returns:
        Cost breakdown

    Raises:
        401: Unauthorized

    Example:
        GET /reports/costs?days=30
        Headers:
          X-API-Key: tenant-id
        Response:
          {
            "period": "2026-07-20 to 2026-08-19",
            "total_cost_cents": 75000,
            "total_cost_dollars": 750.0,
            "cost_by_usage_type": {
              "api_calls": 300.0,
              "tokens": 375.0,
              "overages": 75.0
            }
          }
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    service = ReportingService(db)
    breakdown = service.get_cost_breakdown(
        start_date=start_date,
        end_date=end_date,
    )

    return breakdown


# ==================== TENANT METRICS ====================

@router.get("/tenants/{tenant_id}/metrics", status_code=status.HTTP_200_OK)
async def get_tenant_metrics(
    tenant_id: str,
    days: int = Query(30, ge=1, le=365),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get tenant-specific metrics.

    **Authentication**: Required (API key)

    Shows usage, revenue, and health metrics for specific tenant.

    Args:
        tenant_id: Tenant ID to analyze
        days: Number of days to include

    Returns:
        Tenant metrics

    Raises:
        401: Unauthorized
        403: Access denied

    Example:
        GET /reports/tenants/tenant_123/metrics?days=30
        Headers:
          X-API-Key: tenant-id
    """
    if tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    service = ReportingService(db)
    metrics = service.get_tenant_metrics(
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
    )

    return metrics


# ==================== DASHBOARD ====================

@router.get("/dashboard", status_code=status.HTTP_200_OK)
async def get_dashboard(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get dashboard overview metrics.

    **Authentication**: Required (API key)

    High-level overview of platform metrics: active tenants, revenue, usage, etc.

    Returns:
        Dashboard metrics

    Raises:
        401: Unauthorized

    Example:
        GET /reports/dashboard
        Headers:
          X-API-Key: tenant-id
        Response:
          {
            "current_period": "2026-08",
            "total_active_tenants": 342,
            "total_active_subscriptions": 425,
            "total_revenue_cents": 125000,
            "total_revenue_dollars": 1250.0,
            "total_usage_api_calls": 4500000,
            "total_usage_tokens": 75000000,
            "gross_margin_percent": 45.2,
            "churn_rate": 2.5,
            "growth_rate_percent": 5.2
          }
    """
    service = ReportingService(db)
    dashboard = service.get_dashboard_metrics()

    return dashboard


# ==================== TRENDS ====================

@router.get("/trends/{metric}", status_code=status.HTTP_200_OK)
async def get_trend_data(
    metric: str,
    period_type: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    num_periods: int = Query(30, ge=7, le=365),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get trend data over time.

    **Authentication**: Required (API key)

    Shows metric trends and forecasts next period.

    Args:
        metric: Metric to analyze (api_calls, tokens, revenue)
        period_type: Time granularity (daily, weekly, monthly)
        num_periods: Number of periods to include

    Returns:
        Trend data with forecast

    Raises:
        401: Unauthorized

    Example:
        GET /reports/trends/api_calls?period_type=daily&num_periods=30
        Headers:
          X-API-Key: tenant-id
        Response:
          {
            "metric_name": "api_calls",
            "period_type": "daily",
            "data_points": [
              {"date": "2026-07-20", "value": 1200},
              {"date": "2026-07-21", "value": 1350},
              ...
            ],
            "trend_direction": "up",
            "trend_strength": 0.75,
            "forecast_next_period": 1450.5
          }
    """
    service = ReportingService(db)
    trend = service.get_trend_data(
        metric=metric,
        period_type=period_type,
        num_periods=num_periods,
    )

    return trend


# ==================== SAVED REPORTS ====================

@router.post("/saved", status_code=status.HTTP_201_CREATED)
async def create_saved_report(
    name: str = Query(...),
    report_type: str = Query(...),
    frequency: str = Query(...),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Create a saved report configuration.

    **Authentication**: Required (API key)

    Sets up a recurring report to be generated automatically.

    Args:
        name: Report name
        report_type: Type (usage_analytics, revenue_analysis, cost_breakdown, etc)
        frequency: Frequency (daily, weekly, monthly, quarterly, annual)

    Returns:
        Created report configuration

    Raises:
        401: Unauthorized
        400: Invalid type or frequency

    Example:
        POST /reports/saved?name=Monthly%20Revenue&report_type=revenue_analysis&frequency=monthly
        Headers:
          X-API-Key: tenant-id
        Response (201):
          {
            "id": "report_123",
            "name": "Monthly Revenue",
            "report_type": "revenue_analysis",
            "frequency": "monthly",
            "is_active": true,
            "created_at": "2026-08-19T10:30:00"
          }
    """
    try:
        report_type_enum = ReportType(report_type)
        frequency_enum = ReportFrequency(frequency)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid report_type or frequency",
        )

    service = ReportingService(db)
    report = service.create_saved_report(
        name=name,
        report_type=report_type_enum,
        frequency=frequency_enum,
        tenant_id=current_tenant.id,
    )

    return SavedReportResponse.model_validate(report)


@router.get("/saved", status_code=status.HTTP_200_OK)
async def list_saved_reports(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    List saved reports for tenant.

    **Authentication**: Required (API key)

    Returns:
        List of saved report configurations

    Raises:
        401: Unauthorized

    Example:
        GET /reports/saved
        Headers:
          X-API-Key: tenant-id
    """
    service = ReportingService(db)
    reports = service.list_saved_reports(tenant_id=current_tenant.id)

    return ReportListResponse(
        reports=[SavedReportResponse.model_validate(r) for r in reports],
        total_count=len(reports),
    )


@router.get("/saved/{report_id}", status_code=status.HTTP_200_OK)
async def get_saved_report(
    report_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get saved report details.

    **Authentication**: Required (API key)

    Args:
        report_id: Report ID

    Returns:
        Report configuration

    Raises:
        401: Unauthorized
        404: Report not found

    Example:
        GET /reports/saved/report_123
        Headers:
          X-API-Key: tenant-id
    """
    service = ReportingService(db)
    report = service.get_saved_report(report_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    if report.tenant_id and report.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return SavedReportResponse.model_validate(report)


@router.delete("/saved/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_report(
    report_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Delete saved report.

    **Authentication**: Required (API key)

    Args:
        report_id: Report ID

    Returns:
        No content

    Raises:
        401: Unauthorized
        404: Report not found

    Example:
        DELETE /reports/saved/report_123
        Headers:
          X-API-Key: tenant-id
    """
    service = ReportingService(db)
    report = service.get_saved_report(report_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    if report.tenant_id and report.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    service.delete_saved_report(report_id)
    return None


# ==================== REPORT RUNS ====================

@router.post("/run", status_code=status.HTTP_201_CREATED)
async def run_report(
    report_type: str = Query(...),
    days: int = Query(30, ge=1, le=365),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Execute a report immediately.

    **Authentication**: Required (API key)

    Generates and returns a report in the response.

    Args:
        report_type: Type of report to run
        days: Number of days to include

    Returns:
        Report execution result

    Raises:
        401: Unauthorized
        400: Invalid report type

    Example:
        POST /reports/run?report_type=usage_analytics&days=30
        Headers:
          X-API-Key: tenant-id
    """
    try:
        report_type_enum = ReportType(report_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid report_type",
        )

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    service = ReportingService(db)
    run = service.run_report(
        report_type=report_type_enum,
        start_date=start_date,
        end_date=end_date,
    )

    return ReportRunResponse.model_validate(run)


@router.get("/runs/{run_id}", status_code=status.HTTP_200_OK)
async def get_report_run(
    run_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get report run result.

    **Authentication**: Required (API key)

    Args:
        run_id: Run ID

    Returns:
        Report execution result

    Raises:
        401: Unauthorized
        404: Run not found

    Example:
        GET /reports/runs/run_123
        Headers:
          X-API-Key: tenant-id
    """
    service = ReportingService(db)
    run = service.get_report_run(run_id)

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report run not found",
        )

    return ReportRunResponse.model_validate(run)


@router.get("/runs/recent", status_code=status.HTTP_200_OK)
async def list_recent_runs(
    limit: int = Query(10, ge=1, le=50),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    List recent report runs.

    **Authentication**: Required (API key)

    Args:
        limit: Maximum results

    Returns:
        List of recent runs

    Raises:
        401: Unauthorized

    Example:
        GET /reports/runs/recent?limit=10
        Headers:
          X-API-Key: tenant-id
    """
    service = ReportingService(db)
    runs = service.list_recent_runs(limit=limit)

    return {
        "runs": [ReportRunResponse.model_validate(r) for r in runs],
        "total_count": len(runs),
    }
