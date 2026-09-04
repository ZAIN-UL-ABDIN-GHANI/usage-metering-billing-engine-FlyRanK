
from fastapi import APIRouter, Depends, HTTPException, Response, status, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant
from app.models import Plan
from app.services.usage_service import UsageService
from pydantic import BaseModel, Field
from typing import Optional


class UsageRecordRequest(BaseModel):
    """Request schema for recording usage."""
    usage_type: str = Field(..., pattern="^(api_calls|ai_tokens)$")
    quantity: int = Field(..., gt=0)
    cost_cents: Optional[int] = None


class GenerateRequest(BaseModel):
    prompt: str
    idempotency_key: str

router = APIRouter(
    prefix="/usage",
    tags=["usage"],
)
generate_router = APIRouter(tags=["usage"])


@generate_router.post("/generate")
async def generate(
    request: GenerateRequest,
    response: Response,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Compatibility endpoint for metered generation requests."""
    service = UsageService(db)
    subscription = current_tenant.subscriptions[0] if current_tenant.subscriptions else None
    if subscription and subscription.status in ("past_due", "canceled"):
        raise HTTPException(status_code=402, detail="Payment required or upgrade plan")

    if db.query(Plan).filter_by(id=current_tenant.plan_id).first():
        quota = service.check_quota(current_tenant.id, "api_calls", 1)
        if not quota["allowed"]:
            raise HTTPException(
                status_code=429,
                detail="Usage limit exceeded",
                headers={"Retry-After": "3600"},
            )

    event, _ = service.record_usage(
        tenant_id=current_tenant.id,
        usage_type="api_calls",
        quantity=1,
        idempotency_key=request.idempotency_key,
        cost_cents=1,
    )
    return {
        "id": event.id,
        "prompt": request.prompt,
        "usage_event_id": event.id,
        "cost_cents": event.cost_cents,
    }


@router.post("/record", status_code=status.HTTP_201_CREATED)
async def record_usage(
    usage_data: UsageRecordRequest,
    idempotency_key: str = Header(...),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Record a usage event (idempotent).

    **Authentication**: Required (API key)
    **Idempotency**: Guaranteed via Idempotency-Key header

    Sending same request twice with same Idempotency-Key returns same result
    without creating duplicate usage event.

    Args:
        usage_data: Usage data (usage_type, quantity, billing_period)
        idempotency_key: Idempotency-Key header (required)
        current_tenant: Authenticated tenant

    Returns:
        Usage event details

    Raises:
        400: Invalid usage type or quantity
        401: Unauthorized (missing/invalid API key)
        404: Tenant not found

    Example:
        POST /usage/record
        Headers:
          X-API-Key: tenant-id
          Idempotency-Key: unique-request-id
        Body:
          {
            "usage_type": "api_calls",
            "quantity": 42
          }
    """
    service = UsageService(db)

    try:
        # Record usage with idempotency guarantee
        event, is_duplicate = service.record_usage(
            tenant_id=current_tenant.id,
            usage_type=usage_data.usage_type,
            quantity=usage_data.quantity,
            idempotency_key=idempotency_key,
            cost_cents=usage_data.cost_cents,
        )

        return {
            "id": event.id,
            "tenant_id": event.tenant_id,
            "usage_type": event.usage_type,
            "quantity": event.quantity,
            "cost_cents": event.cost_cents,
            "billing_period": event.billing_period,
            "created_at": event.created_at.isoformat(),
            "is_duplicate": is_duplicate,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/check-quota", status_code=status.HTTP_200_OK)
async def check_quota(
    usage_type: str,
    quantity: int,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Check if tenant can use requested quantity against their quota.

    **Authentication**: Required (API key)

    Returns quota status without consuming usage.

    Args:
        usage_type: Type of usage ('api_calls' or 'ai_tokens')
        quantity: Quantity to check

    Returns:
        Quota check result with allowed/denied status

    Raises:
        400: Invalid usage type or quantity
        401: Unauthorized (missing/invalid API key)
        404: Tenant or plan not found

    Example:
        POST /usage/check-quota?usage_type=api_calls&quantity=100
        Headers:
          X-API-Key: tenant-id
    """
    service = UsageService(db)

    try:
        result = service.check_quota(
            tenant_id=current_tenant.id,
            usage_type=usage_type,
            requested_quantity=quantity,
        )
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/summary")
async def get_usage_summary(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get usage summary for current billing period.

    **Authentication**: Required (API key)

    Returns current usage, limits, remaining quota, and cost for all usage types.

    Returns:
        Usage summary with all metrics

    Raises:
        401: Unauthorized (missing/invalid API key)
        404: Tenant or plan not found

    Example:
        GET /usage/summary
        Headers:
          X-API-Key: tenant-id

        Response:
        {
          "billing_period": "2024-01",
          "plan": {
            "id": "free",
            "name": "Free",
            "monthly_cost_cents": 0
          },
          "api_calls": {
            "used": 250,
            "limit": 1000,
            "remaining": 750,
            "percent_used": 25.0
          },
          "ai_tokens": {
            "used": 50000,
            "limit": 100000,
            "remaining": 50000,
            "percent_used": 50.0
          },
          "cost": {
            "total_cents": 0,
            "total_dollars": 0.0
          }
        }
    """
    service = UsageService(db)

    try:
        summary = service.get_usage_summary(current_tenant.id)
        summary["total_cost_cents"] = summary["cost"]["total_cents"]
        summary["current_cost"] = summary["cost"]["total_cents"]
        return summary

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("")
async def get_usage_summary_compat(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    summary = UsageService(db).get_usage_summary(current_tenant.id)
    summary["total_cost_cents"] = summary["cost"]["total_cents"]
    summary["current_cost"] = summary["cost"]["total_cents"]
    return summary


@router.get("/events")
async def get_usage_events(
    limit: int = 50,
    offset: int = 0,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get usage events for current billing period (paginated).

    **Authentication**: Required (API key)

    Returns list of usage events in reverse chronological order.

    Args:
        limit: Max number of results (default: 50)
        offset: Number of results to skip (default: 0)

    Returns:
        List of usage events with pagination info

    Raises:
        401: Unauthorized (missing/invalid API key)
        404: Tenant not found

    Example:
        GET /usage/events?limit=10&offset=0
        Headers:
          X-API-Key: tenant-id
    """
    service = UsageService(db)

    try:
        return service.get_usage_events(
            tenant_id=current_tenant.id,
            limit=limit,
            offset=offset,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/status")
async def get_usage_status(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get current usage status and quota information.

    **Authentication**: Required (API key)

    Returns simplified status view showing which quotas are critical.

    Returns:
        Status object with quota warnings

    Raises:
        401: Unauthorized (missing/invalid API key)
        404: Tenant or plan not found

    Example:
        GET /usage/status
        Headers:
          X-API-Key: tenant-id
    """
    service = UsageService(db)

    try:
        summary = service.get_usage_summary(current_tenant.id)

        # Determine status
        api_calls_critical = summary["api_calls"]["percent_used"] >= 90
        tokens_critical = summary["ai_tokens"]["percent_used"] >= 90

        status_msg = "ok"
        if api_calls_critical or tokens_critical:
            status_msg = "warning"

        return {
            "status": status_msg,
            "billing_period": summary["billing_period"],
            "quotas": {
                "api_calls": {
                    "used": summary["api_calls"]["used"],
                    "limit": summary["api_calls"]["limit"],
                    "percent": summary["api_calls"]["percent_used"],
                    "critical": api_calls_critical,
                },
                "ai_tokens": {
                    "used": summary["ai_tokens"]["used"],
                    "limit": summary["ai_tokens"]["limit"],
                    "percent": summary["ai_tokens"]["percent_used"],
                    "critical": tokens_critical,
                },
            },
            "cost": summary["cost"],
            "plan": summary["plan"],
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
