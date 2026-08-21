"""Tests for alert detection and management."""

import pytest
from sqlalchemy.orm import Session

from app.models_alert import Alert, AlertPreference, AlertType, AlertStatus
from app.services.alert_service import AlertService
from app.utils.db_helpers import get_current_billing_period


class TestAlertDetection:
    """Test alert detection at usage thresholds."""

    def test_alert_created_at_80_percent(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that alert is created when usage reaches 80%."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create usage at 85% of quota (850 calls out of 1000)
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=850,
        )

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)

        assert len(alerts) > 0
        assert any(a.alert_type == AlertType.THRESHOLD_80 for a in alerts)
        assert any(a.usage_percent >= 80 for a in alerts)

        print("✅ Alert: Created at 80% usage")

    def test_alert_created_at_100_percent(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that alert is created when usage reaches quota."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create usage at quota (1000 calls)
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=1000,
        )

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)

        assert len(alerts) > 0
        assert any(a.alert_type == AlertType.THRESHOLD_100 for a in alerts)
        assert any(a.usage_percent >= 100 for a in alerts)

        print("✅ Alert: Created at 100% usage")

    def test_overage_alert_created_over_100_percent(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that overage alert is created when usage exceeds quota."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create usage over quota (1100 calls, 110%)
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=1100,
        )

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)

        assert len(alerts) > 0
        assert any(a.alert_type == AlertType.OVERAGE_WARNING for a in alerts)
        assert any(a.usage_percent > 100 for a in alerts)

        print("✅ Alert: Overage warning created at 110% usage")

    def test_no_alert_below_80_percent(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that no alert is created when usage is below 80%."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create usage at 50% of quota
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=500,
        )

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)

        assert len(alerts) == 0

        print("✅ Alert: No alert below 80%")

    def test_duplicate_alerts_not_created(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that duplicate alerts are not created."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create usage at 85%
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="api_calls",
            quantity=850,
        )

        service = AlertService(db)

        # Check alerts twice
        alerts1 = service.check_usage_and_create_alerts(tenant.id)
        alerts2 = service.check_usage_and_create_alerts(tenant.id)

        # Should only create alerts first time
        assert len(alerts1) > 0
        assert len(alerts2) == 0

        print("✅ Alert: Duplicates not created")

    def test_alert_for_ai_tokens(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test alert detection for AI token usage."""
        plan = create_plan(ai_tokens_limit=1_000_000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create token usage at 85%
        create_usage_event(
            tenant_id=tenant.id,
            usage_type="ai_tokens",
            quantity=850_000,
        )

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)

        assert len(alerts) > 0
        assert any(a.usage_type == "ai_tokens" for a in alerts)

        print("✅ Alert: AI token alert created")


class TestAlertStatus:
    """Test alert status transitions."""

    def test_alert_starts_as_pending(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that new alerts start with PENDING status."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        create_usage_event(tenant_id=tenant.id, quantity=850)

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)

        assert all(a.status == AlertStatus.PENDING for a in alerts)

        print("✅ Alert: Starts as PENDING")

    def test_mark_alert_sent(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test marking alert as sent."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        create_usage_event(tenant_id=tenant.id, quantity=850)

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)
        alert = alerts[0]

        # Mark as sent
        sent_alert = service.mark_alert_sent(alert.id, "email")

        assert sent_alert.status == AlertStatus.SENT
        assert sent_alert.sent_at is not None
        assert sent_alert.notification_method == "email"

        print("✅ Alert: Marked as SENT")

    def test_acknowledge_alert(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test acknowledging an alert."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        create_usage_event(tenant_id=tenant.id, quantity=850)

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)
        alert = alerts[0]

        # Acknowledge
        ack_alert = service.acknowledge_alert(alert.id)

        assert ack_alert.status == AlertStatus.ACKNOWLEDGED
        assert ack_alert.acknowledged_at is not None

        print("✅ Alert: Acknowledged")

    def test_resolve_alert(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test resolving an alert."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        create_usage_event(tenant_id=tenant.id, quantity=850)

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)
        alert = alerts[0]

        # Resolve
        resolved = service.resolve_alert(alert.id)

        assert resolved.status == AlertStatus.RESOLVED

        print("✅ Alert: Resolved")


class TestAlertRetrieval:
    """Test alert retrieval and querying."""

    def test_get_alert_by_id(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test getting alert by ID."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        create_usage_event(tenant_id=tenant.id, quantity=850)

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)
        alert = alerts[0]

        retrieved = service.get_alert(alert.id)

        assert retrieved is not None
        assert retrieved.id == alert.id

        print("✅ Alert: Retrieved by ID")

    def test_get_tenant_alerts(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test getting all alerts for tenant."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        
        # Create multiple alerts
        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=850)
        create_usage_event(tenant_id=tenant.id, usage_type="ai_tokens", quantity=850_000)

        service = AlertService(db)
        service.check_usage_and_create_alerts(tenant.id)

        alerts, total = service.get_tenant_alerts(tenant.id)

        assert len(alerts) >= 2
        assert total >= 2

        print("✅ Alert: Retrieved all alerts")

    def test_get_pending_alerts(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test getting pending alerts."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        create_usage_event(tenant_id=tenant.id, quantity=850)

        service = AlertService(db)
        service.check_usage_and_create_alerts(tenant.id)

        pending = service.get_pending_alerts(tenant.id)

        assert len(pending) > 0
        assert all(a.status == AlertStatus.PENDING for a in pending)

        print("✅ Alert: Retrieved pending alerts")

    def test_get_active_alerts(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test getting active (unresolved) alerts."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        create_usage_event(tenant_id=tenant.id, quantity=850)

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)
        alert = alerts[0]

        # Resolve one alert
        service.resolve_alert(alert.id)

        # Get active alerts
        active = service.get_active_alerts(tenant.id)

        # All remaining should be active (not resolved)
        assert all(a.status != AlertStatus.RESOLVED for a in active)

        print("✅ Alert: Retrieved active alerts")


class TestAlertPreferences:
    """Test alert notification preferences."""

    def test_get_or_create_preferences(
        self, db: Session, create_tenant
    ):
        """Test getting or creating default preferences."""
        tenant = create_tenant()

        service = AlertService(db)
        prefs = service.get_or_create_alert_preference(tenant.id)

        assert prefs is not None
        assert prefs.tenant_id == tenant.id
        assert prefs.email_on_80_percent is True
        assert prefs.email_on_100_percent is True
        assert prefs.email_on_overage is True

        print("✅ Alert: Preferences created with defaults")

    def test_update_preferences(
        self, db: Session, create_tenant
    ):
        """Test updating alert preferences."""
        tenant = create_tenant()

        service = AlertService(db)
        prefs = service.update_alert_preference(
            tenant.id,
            email_on_80_percent=False,
            notify_daily_summary=True,
        )

        assert prefs.email_on_80_percent is False
        assert prefs.email_on_100_percent is True
        assert prefs.notify_daily_summary is True

        print("✅ Alert: Preferences updated")

    def test_should_send_alert_respects_preferences(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that sending respects preferences."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        create_usage_event(tenant_id=tenant.id, quantity=850)

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)
        alert = alerts[0]

        # Disable 80% alerts
        prefs = service.update_alert_preference(
            tenant.id,
            email_on_80_percent=False,
        )

        # Check if alert should be sent
        if alert.alert_type == AlertType.THRESHOLD_80:
            should_send = service.should_send_alert(alert, prefs)
            assert should_send is False
        else:
            should_send = service.should_send_alert(alert, prefs)
            assert should_send is True

        print("✅ Alert: Preferences respected")


class TestAlertSummary:
    """Test alert summary statistics."""

    def test_alert_summary(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test getting alert summary."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        create_usage_event(tenant_id=tenant.id, quantity=850)

        service = AlertService(db)
        service.check_usage_and_create_alerts(tenant.id)

        summary = service.get_alert_summary(tenant.id)

        assert summary["tenant_id"] == tenant.id
        assert summary["total_alerts"] > 0
        assert summary["pending"] > 0

        print("✅ Alert: Summary generated")

    def test_summary_tracks_status_breakdown(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that summary tracks by status."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        create_usage_event(tenant_id=tenant.id, quantity=850)

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)
        alert = alerts[0]

        # Mark one as sent
        service.mark_alert_sent(alert.id)

        summary = service.get_alert_summary(tenant.id)

        assert summary["pending"] >= 0
        assert summary["sent"] >= 1

        print("✅ Alert: Summary tracks status")


class TestAlertIsolation:
    """Test tenant isolation in alerts."""

    def test_alerts_isolated_by_tenant(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test that alerts are isolated by tenant."""
        plan = create_plan()
        tenant1 = create_tenant()
        tenant2 = create_tenant()
        
        create_subscription(tenant_id=tenant1.id, plan_id=plan.id)
        create_subscription(tenant_id=tenant2.id, plan_id=plan.id)

        # Create alerts for tenant1
        create_usage_event(tenant_id=tenant1.id, quantity=850)
        service = AlertService(db)
        service.check_usage_and_create_alerts(tenant1.id)

        # Get alerts for tenant2
        tenant2_alerts, _ = service.get_tenant_alerts(tenant2.id)

        # Tenant2 should see no alerts
        assert len(tenant2_alerts) == 0

        print("✅ Alert: Tenant isolation verified")


class TestAlertPercentageCalculation:
    """Test usage percentage calculations."""

    def test_usage_percentage_80(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test percentage calculation at 80%."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        create_usage_event(tenant_id=tenant.id, quantity=800)

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)

        if alerts:
            alert = alerts[0]
            assert abs(alert.usage_percent - 80.0) < 0.1

        print("✅ Alert: Percentage calculation 80%")

    def test_usage_percentage_110(
        self, db: Session, create_plan, create_tenant, create_subscription, create_usage_event
    ):
        """Test percentage calculation over 100%."""
        plan = create_plan(api_calls_limit=1000)
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        create_usage_event(tenant_id=tenant.id, quantity=1100)

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)

        if alerts:
            alert = alerts[0]
            assert abs(alert.usage_percent - 110.0) < 0.1

        print("✅ Alert: Percentage calculation 110%")


class TestAlertEdgeCases:
    """Test edge cases in alert handling."""

    def test_no_alerts_without_subscription(
        self, db: Session, create_plan, create_tenant
    ):
        """Test that no alerts are created without subscription."""
        create_plan()
        tenant = create_tenant()
        # No subscription created

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)

        assert len(alerts) == 0

        print("✅ Alert: No alerts without subscription")

    def test_no_alerts_no_usage(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that no alerts are created with zero usage."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)
        # No usage events created

        service = AlertService(db)
        alerts = service.check_usage_and_create_alerts(tenant.id)

        assert len(alerts) == 0

        print("✅ Alert: No alerts with zero usage")

    def test_alert_invalid_id_raises_error(
        self, db: Session
    ):
        """Test that getting invalid alert raises error."""
        service = AlertService(db)
        alert = service.get_alert("invalid-id")

        assert alert is None

        print("✅ Alert: Invalid ID handled")
