"""Alert routes - API endpoints for usage notifications."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant
from app.models_alert import AlertResponse, AlertListResponse, AlertPreferenceResponse, AlertPreferenceUpdate, AlertAcknowledge
from app.services.alert_service import AlertService

router = APIRouter(
    prefix="/alerts",
    tags=["alerts"],
)


@router.post("/check", status_code=status.HTTP_200_OK)
async def check_usage_alerts(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Check current usage against quotas and create alerts.

    **Authentication**: Required (API key)

    Scans current usage and creates alerts if usage exceeds thresholds (80%, 100%).

    Returns:
        List of alerts created (if any)

    Raises:
        401: Unauthorized

    Example:
        POST /alerts/check
        Headers:
          X-API-Key: tenant-id
        Response (200 OK):
          {
            "alerts_created": [
              {
                "id": "alert_123",
                "alert_type": "threshold_80",
                "usage_type": "api_calls",
                "usage_percent": 85.5,
                "status": "pending"
              }
            ],
            "total_created": 1
          }
    """
    service = AlertService(db)
    alerts = service.check_usage_and_create_alerts(tenant_id=current_tenant.id)

    return {
        "alerts_created": [AlertResponse.model_validate(a) for a in alerts],
        "total_created": len(alerts),
    }


@router.get("")
async def list_alerts(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    List alerts for tenant (paginated).

    **Authentication**: Required (API key)

    Returns alerts with optional filtering by status.

    Args:
        status: Optional filter (pending, sent, acknowledged, resolved)
        limit: Max results per page
        offset: Results to skip

    Returns:
        Paginated list of alerts

    Raises:
        401: Unauthorized

    Example:
        GET /alerts?status=pending&limit=10
        Headers:
          X-API-Key: tenant-id
    """
    service = AlertService(db)
    alerts, total_count = service.get_tenant_alerts(
        tenant_id=current_tenant.id,
        status=status,
        limit=limit,
        offset=offset,
    )

    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 0

    return AlertListResponse(
        alerts=[AlertResponse.model_validate(a) for a in alerts],
        total_count=total_count,
        page=offset // limit + 1,
        page_size=limit,
        total_pages=total_pages,
    )


@router.get("/{alert_id}")
async def get_alert(
    alert_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get alert details.

    **Authentication**: Required (API key)

    Args:
        alert_id: Alert ID

    Returns:
        Alert details

    Raises:
        401: Unauthorized
        403: Access denied
        404: Alert not found

    Example:
        GET /alerts/alert_123
        Headers:
          X-API-Key: tenant-id
    """
    service = AlertService(db)
    alert = service.get_alert(alert_id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    if alert.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/acknowledge", status_code=status.HTTP_200_OK)
async def acknowledge_alert(
    alert_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Acknowledge an alert (mark as acknowledged).

    **Authentication**: Required (API key)

    Args:
        alert_id: Alert ID

    Returns:
        Updated alert

    Raises:
        401: Unauthorized
        403: Access denied
        404: Alert not found

    Example:
        POST /alerts/alert_123/acknowledge
        Headers:
          X-API-Key: tenant-id
    """
    service = AlertService(db)
    alert = service.get_alert(alert_id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    if alert.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    try:
        alert = service.acknowledge_alert(alert_id)
        return AlertResponse.model_validate(alert)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{alert_id}/resolve", status_code=status.HTTP_200_OK)
async def resolve_alert(
    alert_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Resolve an alert (mark as resolved).

    **Authentication**: Required (API key)

    Args:
        alert_id: Alert ID

    Returns:
        Updated alert

    Raises:
        401: Unauthorized
        403: Access denied
        404: Alert not found

    Example:
        POST /alerts/alert_123/resolve
        Headers:
          X-API-Key: tenant-id
    """
    service = AlertService(db)
    alert = service.get_alert(alert_id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    if alert.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    try:
        alert = service.resolve_alert(alert_id)
        return AlertResponse.model_validate(alert)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/status/summary")
async def get_alert_summary(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get alert summary for tenant.

    **Authentication**: Required (API key)

    Shows count of alerts by status (pending, sent, acknowledged, resolved).

    Returns:
        Alert summary with status breakdown

    Raises:
        401: Unauthorized

    Example:
        GET /alerts/status/summary
        Headers:
          X-API-Key: tenant-id
        Response:
          {
            "tenant_id": "tenant-id",
            "total_alerts": 5,
            "pending": 1,
            "sent": 2,
            "acknowledged": 1,
            "resolved": 1
          }
    """
    service = AlertService(db)
    summary = service.get_alert_summary(current_tenant.id)

    return summary


@router.get("/preferences")
async def get_alert_preferences(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get alert notification preferences.

    **Authentication**: Required (API key)

    Returns current alert notification settings for tenant.

    Returns:
        Alert preferences

    Raises:
        401: Unauthorized

    Example:
        GET /alerts/preferences
        Headers:
          X-API-Key: tenant-id
    """
    service = AlertService(db)
    prefs = service.get_or_create_alert_preference(current_tenant.id)

    return AlertPreferenceResponse.model_validate(prefs)


@router.put("/preferences", status_code=status.HTTP_200_OK)
async def update_alert_preferences(
    request: AlertPreferenceUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Update alert notification preferences.

    **Authentication**: Required (API key)

    Updates tenant's alert notification settings.

    Args:
        email_address: Email for notifications
        email_on_80_percent: Alert at 80% usage
        email_on_100_percent: Alert at 100% usage
        email_on_overage: Alert on overage
        notify_daily_summary: Daily usage summary

    Returns:
        Updated preferences

    Raises:
        401: Unauthorized

    Example:
        PUT /alerts/preferences
        Headers:
          X-API-Key: tenant-id
        Body:
          {
            "email_address": "admin@example.com",
            "email_on_80_percent": true,
            "email_on_100_percent": true,
            "email_on_overage": true,
            "notify_daily_summary": false
          }
    """
    service = AlertService(db)
    prefs = service.update_alert_preference(
        tenant_id=current_tenant.id,
        email_address=request.email_address,
        email_on_80_percent=request.email_on_80_percent,
        email_on_100_percent=request.email_on_100_percent,
        email_on_overage=request.email_on_overage,
        notify_daily_summary=request.notify_daily_summary,
    )

    return AlertPreferenceResponse.model_validate(prefs)


@router.get("/active")
async def get_active_alerts(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get all active (unresolved) alerts for tenant.

    **Authentication**: Required (API key)

    Returns alerts that haven't been resolved yet.

    Returns:
        List of active alerts

    Raises:
        401: Unauthorized

    Example:
        GET /alerts/active
        Headers:
          X-API-Key: tenant-id
    """
    service = AlertService(db)
    alerts = service.get_active_alerts(current_tenant.id)

    return {
        "active_alerts": [AlertResponse.model_validate(a) for a in alerts],
        "count": len(alerts),
    }
