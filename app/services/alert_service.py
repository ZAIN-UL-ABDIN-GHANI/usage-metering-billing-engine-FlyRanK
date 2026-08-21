"""Alert service - detects and tracks usage threshold alerts."""

from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models_alert import Alert, AlertPreference, AlertType, AlertStatus
from app.models import Tenant, Subscription, Plan, UsageEvent
from app.utils.db_helpers import generate_id, get_current_billing_period


class AlertService:
    """Service for alert detection and management."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def check_usage_and_create_alerts(
        self,
        tenant_id: str,
        billing_period: Optional[str] = None,
    ) -> List[Alert]:
        """
        Check tenant usage against quotas and create alerts as needed.

        Checks for 80% and 100% thresholds.

        Args:
            tenant_id: Tenant ID
            billing_period: Billing period (default: current)

        Returns:
            List of alerts created
        """
        if not billing_period:
            billing_period = get_current_billing_period()

        alerts = []

        # Get tenant and active subscription
        tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            return alerts

        # Get active subscription
        subscription = (
            self.db.query(Subscription)
            .filter_by(tenant_id=tenant_id)
            .first()
        )
        if not subscription:
            return alerts

        # Get plan
        plan = self.db.query(Plan).filter_by(id=subscription.plan_id).first()
        if not plan:
            return alerts

        # Get current usage for period
        api_call_usage = (
            self.db.query(UsageEvent)
            .filter_by(
                tenant_id=tenant_id,
                usage_type="api_calls",
                billing_period=billing_period,
            )
            .with_entities(UsageEvent.quantity)
        )
        api_call_total = sum(q[0] for q in api_call_usage) or 0

        token_usage = (
            self.db.query(UsageEvent)
            .filter_by(
                tenant_id=tenant_id,
                usage_type="ai_tokens",
                billing_period=billing_period,
            )
            .with_entities(UsageEvent.quantity)
        )
        token_total = sum(q[0] for q in token_usage) or 0

        # Check API call quota
        api_percent = (api_call_total / plan.api_calls_limit * 100) if plan.api_calls_limit > 0 else 0
        api_alerts = self._check_and_create_alerts(
            tenant_id=tenant_id,
            billing_period=billing_period,
            usage_type="api_calls",
            current_usage=api_call_total,
            quota_limit=plan.api_calls_limit,
            usage_percent=api_percent,
        )
        alerts.extend(api_alerts)

        # Check token quota
        token_percent = (token_total / plan.ai_tokens_limit * 100) if plan.ai_tokens_limit > 0 else 0
        token_alerts = self._check_and_create_alerts(
            tenant_id=tenant_id,
            billing_period=billing_period,
            usage_type="ai_tokens",
            current_usage=token_total,
            quota_limit=plan.ai_tokens_limit,
            usage_percent=token_percent,
        )
        alerts.extend(token_alerts)

        return alerts

    def _check_and_create_alerts(
        self,
        tenant_id: str,
        billing_period: str,
        usage_type: str,
        current_usage: int,
        quota_limit: int,
        usage_percent: float,
    ) -> List[Alert]:
        """
        Check thresholds and create alerts.

        Internal method called by check_usage_and_create_alerts.

        Args:
            tenant_id: Tenant ID
            billing_period: Billing period
            usage_type: Type of usage
            current_usage: Current usage quantity
            quota_limit: Plan quota limit
            usage_percent: Percentage of quota

        Returns:
            List of alerts created
        """
        alerts = []

        # Check if 80% alert already exists
        alert_80 = (
            self.db.query(Alert)
            .filter_by(
                tenant_id=tenant_id,
                billing_period=billing_period,
                usage_type=usage_type,
                alert_type=AlertType.THRESHOLD_80,
            )
            .first()
        )

        # Create 80% alert if usage crosses threshold and no alert exists
        if usage_percent >= 80 and usage_percent < 100 and not alert_80:
            alert = self._create_alert(
                tenant_id=tenant_id,
                alert_type=AlertType.THRESHOLD_80,
                billing_period=billing_period,
                usage_type=usage_type,
                current_usage=current_usage,
                quota_limit=quota_limit,
                usage_percent=usage_percent,
                threshold_percent=80,
                message=f"Usage is at {usage_percent:.0f}% of {usage_type} quota",
            )
            alerts.append(alert)

        # Check if 100% alert already exists
        alert_100 = (
            self.db.query(Alert)
            .filter_by(
                tenant_id=tenant_id,
                billing_period=billing_period,
                usage_type=usage_type,
                alert_type=AlertType.THRESHOLD_100,
            )
            .first()
        )

        # Create 100% alert if usage meets or exceeds limit
        if usage_percent >= 100 and not alert_100:
            alert_type = AlertType.OVERAGE_WARNING if usage_percent > 100 else AlertType.THRESHOLD_100
            alert = self._create_alert(
                tenant_id=tenant_id,
                alert_type=alert_type,
                billing_period=billing_period,
                usage_type=usage_type,
                current_usage=current_usage,
                quota_limit=quota_limit,
                usage_percent=usage_percent,
                threshold_percent=100,
                message=f"Usage has reached {usage_percent:.0f}% of {usage_type} quota",
            )
            alerts.append(alert)

        return alerts

    def _create_alert(
        self,
        tenant_id: str,
        alert_type: AlertType,
        billing_period: str,
        usage_type: str,
        current_usage: int,
        quota_limit: int,
        usage_percent: float,
        threshold_percent: int,
        message: str,
    ) -> Alert:
        """
        Create alert record in database.

        Args:
            tenant_id: Tenant ID
            alert_type: Type of alert
            billing_period: Billing period
            usage_type: Type of usage
            current_usage: Current usage quantity
            quota_limit: Plan quota limit
            usage_percent: Percentage of quota
            threshold_percent: Threshold that triggered alert
            message: Alert message

        Returns:
            Created Alert object
        """
        alert = Alert(
            id=generate_id(),
            tenant_id=tenant_id,
            alert_type=alert_type,
            billing_period=billing_period,
            usage_type=usage_type,
            current_usage=current_usage,
            quota_limit=quota_limit,
            usage_percent=usage_percent,
            threshold_percent=threshold_percent,
            status=AlertStatus.PENDING,
            message=message,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)

        return alert

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """
        Get alert by ID.

        Args:
            alert_id: Alert ID

        Returns:
            Alert object or None
        """
        return self.db.query(Alert).filter_by(id=alert_id).first()

    def get_tenant_alerts(
        self,
        tenant_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Alert], int]:
        """
        Get alerts for a tenant (paginated).

        Args:
            tenant_id: Tenant ID
            status: Optional filter by status
            limit: Max results
            offset: Results to skip

        Returns:
            Tuple of (alerts list, total count)
        """
        query = self.db.query(Alert).filter_by(tenant_id=tenant_id)

        if status:
            query = query.filter_by(status=status)

        total_count = query.count()

        alerts = (
            query
            .order_by(desc(Alert.created_at))
            .limit(limit)
            .offset(offset)
            .all()
        )

        return alerts, total_count

    def get_pending_alerts(self, tenant_id: str) -> List[Alert]:
        """
        Get all pending (unnotified) alerts for tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of pending alerts
        """
        return (
            self.db.query(Alert)
            .filter_by(tenant_id=tenant_id, status=AlertStatus.PENDING)
            .all()
        )

    def mark_alert_sent(self, alert_id: str, notification_method: str = "email") -> Alert:
        """
        Mark alert as sent (notification sent to customer).

        Args:
            alert_id: Alert ID
            notification_method: How it was sent (email, webhook, etc)

        Returns:
            Updated Alert object

        Raises:
            ValueError: If alert not found
        """
        alert = self.get_alert(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.status = AlertStatus.SENT
        alert.sent_at = datetime.utcnow()
        alert.notification_method = notification_method
        alert.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(alert)

        return alert

    def acknowledge_alert(self, alert_id: str) -> Alert:
        """
        Mark alert as acknowledged by customer.

        Args:
            alert_id: Alert ID

        Returns:
            Updated Alert object

        Raises:
            ValueError: If alert not found
        """
        alert = self.get_alert(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(alert)

        return alert

    def resolve_alert(self, alert_id: str) -> Alert:
        """
        Mark alert as resolved (usage returned below threshold).

        Args:
            alert_id: Alert ID

        Returns:
            Updated Alert object

        Raises:
            ValueError: If alert not found
        """
        alert = self.get_alert(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.status = AlertStatus.RESOLVED
        alert.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(alert)

        return alert

    def get_or_create_alert_preference(self, tenant_id: str) -> AlertPreference:
        """
        Get or create alert preferences for tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            AlertPreference object
        """
        from app.models_alert import AlertPreference

        prefs = (
            self.db.query(AlertPreference)
            .filter_by(tenant_id=tenant_id)
            .first()
        )

        if not prefs:
            # Get tenant email (from tenant object if available)
            tenant = self.db.query(Tenant).filter_by(id=tenant_id).first()
            email = tenant.email if tenant and hasattr(tenant, 'email') else f"admin@{tenant_id}.local"

            prefs = AlertPreference(
                id=generate_id(),
                tenant_id=tenant_id,
                email_address=email,
                email_on_80_percent=True,
                email_on_100_percent=True,
                email_on_overage=True,
                notify_daily_summary=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            self.db.add(prefs)
            self.db.commit()
            self.db.refresh(prefs)

        return prefs

    def update_alert_preference(
        self,
        tenant_id: str,
        email_address: Optional[str] = None,
        email_on_80_percent: Optional[bool] = None,
        email_on_100_percent: Optional[bool] = None,
        email_on_overage: Optional[bool] = None,
        notify_daily_summary: Optional[bool] = None,
    ) -> AlertPreference:
        """
        Update alert preferences for tenant.

        Args:
            tenant_id: Tenant ID
            email_address: New email address
            email_on_80_percent: Alert at 80%
            email_on_100_percent: Alert at 100%
            email_on_overage: Alert on overage
            notify_daily_summary: Daily summary

        Returns:
            Updated AlertPreference object
        """
        prefs = self.get_or_create_alert_preference(tenant_id)

        if email_address:
            prefs.email_address = email_address
        if email_on_80_percent is not None:
            prefs.email_on_80_percent = email_on_80_percent
        if email_on_100_percent is not None:
            prefs.email_on_100_percent = email_on_100_percent
        if email_on_overage is not None:
            prefs.email_on_overage = email_on_overage
        if notify_daily_summary is not None:
            prefs.notify_daily_summary = notify_daily_summary

        prefs.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(prefs)

        return prefs

    def should_send_alert(
        self,
        alert: Alert,
        preferences: AlertPreference,
    ) -> bool:
        """
        Determine if alert should be sent based on preferences.

        Args:
            alert: Alert object
            preferences: Alert preference object

        Returns:
            True if alert should be sent
        """
        if alert.alert_type == AlertType.THRESHOLD_80:
            return preferences.email_on_80_percent
        elif alert.alert_type == AlertType.THRESHOLD_100:
            return preferences.email_on_100_percent
        elif alert.alert_type == AlertType.OVERAGE_WARNING:
            return preferences.email_on_overage

        return True

    def get_active_alerts(self, tenant_id: str) -> List[Alert]:
        """
        Get all active (not resolved) alerts for tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of active alerts
        """
        return (
            self.db.query(Alert)
            .filter_by(tenant_id=tenant_id)
            .filter(Alert.status != AlertStatus.RESOLVED)
            .all()
        )

    def get_alert_summary(self, tenant_id: str) -> dict:
        """
        Get alert summary for tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Dictionary with alert statistics
        """
        alerts = self.db.query(Alert).filter_by(tenant_id=tenant_id).all()

        pending = len([a for a in alerts if a.status == AlertStatus.PENDING])
        sent = len([a for a in alerts if a.status == AlertStatus.SENT])
        acknowledged = len([a for a in alerts if a.status == AlertStatus.ACKNOWLEDGED])
        resolved = len([a for a in alerts if a.status == AlertStatus.RESOLVED])

        return {
            "tenant_id": tenant_id,
            "total_alerts": len(alerts),
            "pending": pending,
            "sent": sent,
            "acknowledged": acknowledged,
            "resolved": resolved,
        }
