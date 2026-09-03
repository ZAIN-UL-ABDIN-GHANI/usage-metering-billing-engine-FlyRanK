"""Stripe routes - API endpoints for Stripe Checkout and webhook handling."""

from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant
from app.services.stripe_service import StripeService
from app.services.webhook_handler import WebhookEventHandler
from app.config import settings

router = APIRouter(
    prefix="/stripe",
    tags=["stripe"],
)


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
async def create_checkout_session(
    plan_id: str,
    success_url: str = None,
    cancel_url: str = None,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Create Stripe Checkout session.

    **Authentication**: Required (API key)

    User is redirected to Stripe Checkout to complete payment.
    On success, subscription is created via webhook.

    Args:
        plan_id: Plan ID to upgrade/downgrade to
        success_url: Optional URL to redirect on success
        cancel_url: Optional URL to redirect on cancel

    Returns:
        Checkout session details with redirect URL

    Raises:
        400: Invalid plan
        401: Unauthorized (missing/invalid API key)
        404: Tenant not found

    Example:
        POST /stripe/checkout?plan_id=pro
        Headers:
          X-API-Key: tenant-id
        Response:
          {
            "checkout_url": "https://checkout.stripe.com/...",
            "session_id": "cs_123456",
            "expires_at": 1234567890
          }
    """
    service = StripeService(db)

    try:
        # Use provided URLs or defaults
        if not success_url:
            success_url = f"{settings.app_base_url}/checkout/success"
        if not cancel_url:
            cancel_url = f"{settings.app_base_url}/checkout/cancel"

        # Create checkout session
        result = service.create_checkout_session(
            tenant_id=current_tenant.id,
            plan_id=plan_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )

        return {
            "checkout_url": result["checkout_url"],
            "session_id": result["session_id"],
            "expires_at": result["expires_at"],
            "plan_id": result["plan_id"],
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/webhooks/stripe", status_code=status.HTTP_200_OK)
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    Handle Stripe webhook events.

    **Authentication**: Stripe signature verification (not API key)

    Webhook events:
    - checkout.session.completed: User completed checkout
    - customer.subscription.updated: Subscription changed
    - customer.subscription.deleted: Subscription canceled

    Webhooks are deduplicated by Stripe event ID - same event
    processed multiple times will only have effect once.

    Args:
        request: HTTP request with raw body
        stripe_signature: Stripe-Signature header

    Returns:
        Success acknowledgment

    Raises:
        400: Invalid signature or processing error
        401: Missing signature header

    Example:
        POST /stripe/webhooks/stripe
        Headers:
          Stripe-Signature: t=123456,v1=abc123...
    """
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Stripe-Signature header",
        )

    # Get raw body
    body = await request.body()

    # Verify signature
    stripe_service = StripeService(db)
    if not stripe_service.verify_webhook_signature(body, stripe_signature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    # Parse event
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in webhook body",
        )

    # Extract required fields
    event_id = event.get("id")
    event_type = event.get("type")

    if not event_id or not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing event id or type",
        )

    # Process webhook
    handler = WebhookEventHandler(db)

    try:
        success, message = handler.process_webhook(
            event_type=event_type,
            stripe_event_id=event_id,
            event_data=event,
        )

        return {
            "received": True,
            "event_id": event_id,
            "event_type": event_type,
            "message": message,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/subscription")
async def get_subscription(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get current subscription details.

    **Authentication**: Required (API key)

    Returns subscription information for authenticated tenant.

    Returns:
        Subscription details or None if no active subscription

    Raises:
        401: Unauthorized (missing/invalid API key)

    Example:
        GET /stripe/subscription
        Headers:
          X-API-Key: tenant-id
    """
    from app.models import Subscription

    subscription = (
        db.query(Subscription)
        .filter_by(tenant_id=current_tenant.id, status="active")
        .first()
    )

    if not subscription:
        return {"subscription": None}

    return {
        "subscription": {
            "id": subscription.id,
            "stripe_subscription_id": subscription.stripe_subscription_id,
            "stripe_customer_id": subscription.stripe_customer_id,
            "plan_id": subscription.plan_id,
            "status": subscription.status,
            "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            "created_at": subscription.created_at.isoformat(),
            "updated_at": subscription.updated_at.isoformat(),
        }
    }


@router.get("/webhooks/events")
async def get_webhook_events(
    status_filter: str = None,
    limit: int = 50,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get recent webhook events (admin only).

    **Authentication**: Required (API key)

    Returns recent webhook events for debugging.
    Useful for monitoring webhook processing.

    Args:
        status_filter: Filter by status (processing, processed, failed)
        limit: Max number of results (default: 50)

    Returns:
        List of webhook events

    Raises:
        401: Unauthorized

    Example:
        GET /stripe/webhooks/events?status=failed&limit=10
        Headers:
          X-API-Key: tenant-id
    """
    handler = WebhookEventHandler(db)

    if status_filter:
        events = handler.get_webhook_events_by_status(
            status=status_filter,
            limit=limit,
        )
    else:
        events = handler.get_recent_webhook_events(limit=limit)

    return {
        "events": [
            {
                "id": event.id,
                "stripe_event_id": event.stripe_event_id,
                "event_type": event.event_type,
                "status": event.status,
                "tenant_id": event.tenant_id,
                "subscription_id": event.subscription_id,
                "error": event.error,
                "created_at": event.created_at.isoformat(),
                "processed_at": event.processed_at.isoformat() if event.processed_at else None,
            }
            for event in events
        ],
        "count": len(events),
    }
