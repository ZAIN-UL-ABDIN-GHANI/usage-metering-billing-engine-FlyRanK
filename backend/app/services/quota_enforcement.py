"""Quota enforcement service - validates and enforces usage quotas."""

from typing import Dict, Optional
from enum import Enum

from sqlalchemy.orm import Session

from app.models import Tenant, Plan
from app.repositories.usage_repository import UsageRepository


class QuotaStatus(str, Enum):
    """Quota status enumeration."""

    ALLOWED = "allowed"
    QUOTA_EXCEEDED = "quota_exceeded"
    PLAN_SUSPENDED = "plan_suspended"
    PAYMENT_REQUIRED = "payment_required"


class QuotaEnforcementService:
    """Service for enforcing usage quotas and returning proper HTTP codes."""

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.repo = UsageRepository(db)

    def check_and_enforce_quota(
        self,
        tenant_id: str,
        usage_type: str,
        requested_quantity: int,
    ) -> Dict:
        """
        Check quota and determine if request should be allowed or rejected.

        Returns proper HTTP status code information for different rejection scenarios:
        - 429 Too Many Requests: Usage quota exceeded
        - 402 Payment Required: Subscription/payment issue

        Args:
            tenant_id: Tenant ID
            usage_type: Type of usage ('api_calls' or 'ai_tokens')
            requested_quantity: Quantity requested

        Returns:
            Dict with:
            - status: QuotaStatus enum
            - allowed: bool
            - http_status: int (200, 429, or 402)
            - message: str (human-readable explanation)
            - quota_info: dict (current, limit, remaining, etc.)

        Raises:
            ValueError: If tenant not found
        """
        # Get tenant
        tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Check tenant status
        if tenant.status == "suspended":
            return {
                "status": QuotaStatus.PLAN_SUSPENDED,
                "allowed": False,
                "http_status": 402,
                "message": "Tenant account is suspended. Upgrade or contact support.",
                "quota_info": None,
            }

        if tenant.status == "deleted":
            return {
                "status": QuotaStatus.PLAN_SUSPENDED,
                "allowed": False,
                "http_status": 402,
                "message": "Tenant account is deleted.",
                "quota_info": None,
            }

        # Get plan
        plan = self.db.query(Plan).filter_by(id=tenant.plan_id).first()
        if not plan:
            return {
                "status": QuotaStatus.PAYMENT_REQUIRED,
                "allowed": False,
                "http_status": 402,
                "message": "Plan not found. Update billing information.",
                "quota_info": None,
            }

        # Get limit from plan
        if usage_type == "api_calls":
            limit = plan.api_calls_limit
        elif usage_type == "ai_tokens":
            limit = plan.ai_tokens_limit
        else:
            return {
                "status": QuotaStatus.QUOTA_EXCEEDED,
                "allowed": False,
                "http_status": 429,
                "message": f"Invalid usage type: {usage_type}",
                "quota_info": None,
            }

        # Get current usage
        current = self.repo.get_current_period_usage(tenant_id, usage_type)

        # Check quota
        total_if_allowed = current + requested_quantity
        allowed = total_if_allowed <= limit

        # Calculate metrics
        remaining = max(0, limit - current)
        percent_used = (current / limit * 100) if limit > 0 else 0

        # Build quota info
        quota_info = {
            "current": current,
            "limit": limit,
            "remaining": remaining,
            "requested": requested_quantity,
            "total_if_allowed": total_if_allowed,
            "percent_used": round(percent_used, 2),
            "usage_type": usage_type,
            "billing_period": self._get_current_period(),
        }

        # Return result
        if allowed:
            return {
                "status": QuotaStatus.ALLOWED,
                "allowed": True,
                "http_status": 200,
                "message": "Request allowed",
                "quota_info": quota_info,
            }
        else:
            # Quota exceeded
            message = (
                f"Usage quota exceeded for {usage_type}. "
                f"Current: {current}, Limit: {limit}, Requested: {requested_quantity}. "
                f"Upgrade your plan or wait for billing period reset."
            )
            return {
                "status": QuotaStatus.QUOTA_EXCEEDED,
                "allowed": False,
                "http_status": 429,
                "message": message,
                "quota_info": quota_info,
            }

    def get_quota_status(
        self,
        tenant_id: str,
        usage_type: str,
    ) -> Dict:
        """
        Get current quota status without attempting a request.

        Args:
            tenant_id: Tenant ID
            usage_type: Type of usage ('api_calls' or 'ai_tokens')

        Returns:
            Dict with quota status information

        Raises:
            ValueError: If tenant not found
        """
        # Get tenant
        tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Get plan
        plan = self.db.query(Plan).filter_by(id=tenant.plan_id).first()
        if not plan:
            raise ValueError(f"Plan {tenant.plan_id} not found")

        # Get limit
        if usage_type == "api_calls":
            limit = plan.api_calls_limit
        elif usage_type == "ai_tokens":
            limit = plan.ai_tokens_limit
        else:
            raise ValueError(f"Invalid usage type: {usage_type}")

        # Get current usage
        current = self.repo.get_current_period_usage(tenant_id, usage_type)

        # Calculate metrics
        remaining = max(0, limit - current)
        percent_used = (current / limit * 100) if limit > 0 else 0
        at_limit = current >= limit
        critical = percent_used >= 90

        return {
            "usage_type": usage_type,
            "current": current,
            "limit": limit,
            "remaining": remaining,
            "percent_used": round(percent_used, 2),
            "at_limit": at_limit,
            "critical": critical,
            "billing_period": self._get_current_period(),
        }

    def would_exceed_quota(
        self,
        tenant_id: str,
        usage_type: str,
        requested_quantity: int,
    ) -> bool:
        """
        Check if request would exceed quota (boolean only).

        Args:
            tenant_id: Tenant ID
            usage_type: Type of usage
            requested_quantity: Quantity requested

        Returns:
            True if would exceed quota, False otherwise
        """
        result = self.check_and_enforce_quota(
            tenant_id,
            usage_type,
            requested_quantity,
        )
        return not result["allowed"]

    def get_quota_percentage(
        self,
        tenant_id: str,
        usage_type: str,
    ) -> float:
        """
        Get usage percentage for quota type (0-100).

        Args:
            tenant_id: Tenant ID
            usage_type: Type of usage

        Returns:
            Percentage of quota used (0-100)
        """
        status = self.get_quota_status(tenant_id, usage_type)
        return status["percent_used"]

    def is_quota_critical(
        self,
        tenant_id: str,
        usage_type: str,
    ) -> bool:
        """
        Check if quota is at critical level (90%+).

        Args:
            tenant_id: Tenant ID
            usage_type: Type of usage

        Returns:
            True if 90% or more of quota used
        """
        status = self.get_quota_status(tenant_id, usage_type)
        return status["critical"]

    def _get_current_period(self) -> str:
        """Get current billing period (YYYY-MM)."""
        from app.utils.db_helpers import get_current_billing_period
        return get_current_billing_period()
