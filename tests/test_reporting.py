"""Tests for reporting, analytics, trends, and dashboards."""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models_reporting import SavedReport, ReportRun, ReportType, ReportFrequency
from app.services.reporting_service import ReportingService


class TestUsageAnalytics:
    """Test usage analytics reporting."""

    def test_get_usage_analytics_default_period(
        self, db: Session, create_tenant, create_subscription, create_usage_event
    ):
        """Test usage analytics with default period."""
        tenant = create_tenant()
        plan = self.create_plan(db)
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create usage events
        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1000)
        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=500)
        create_usage_event(tenant_id=tenant.id, usage_type="ai_tokens", quantity=100000)

        service = ReportingService(db)
        analytics = service.get_usage_analytics(tenant_id=tenant.id)

        assert analytics["api_calls_total"] == 1500
        assert analytics["tokens_total"] == 100000
        assert "trend" in analytics
        assert "trend_percent" in analytics

        print(f"✅ Analytics: Total API calls {analytics['api_calls_total']}")

    def test_api_calls_average_daily(
        self, db: Session, create_tenant, create_subscription, create_usage_event
    ):
        """Test API call daily average calculation."""
        tenant = create_tenant()
        plan = self.create_plan(db)
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create 30 days of usage
        for i in range(30):
            date = datetime.utcnow() - timedelta(days=30-i)
            event = create_usage_event(
                tenant_id=tenant.id,
                usage_type="api_calls",
                quantity=1000,
            )
            event.created_at = date
            db.commit()

        service = ReportingService(db)
        analytics = service.get_usage_analytics(
            tenant_id=tenant.id,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )

        assert analytics["api_calls_average_daily"] > 0
        print(f"✅ Analytics: Average daily {analytics['api_calls_average_daily']}")

    def test_peak_usage_detection(
        self, db: Session, create_tenant, create_subscription, create_usage_event
    ):
        """Test peak usage detection."""
        tenant = create_tenant()
        plan = self.create_plan(db)
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create varying usage
        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=100)
        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=5000)  # Peak
        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=200)

        service = ReportingService(db)
        analytics = service.get_usage_analytics(tenant_id=tenant.id)

        assert analytics["peak_usage_value"] >= 5000
        print(f"✅ Analytics: Peak usage {analytics['peak_usage_value']}")

    def test_trend_detection_up(
        self, db: Session, create_tenant, create_subscription, create_usage_event
    ):
        """Test upward trend detection."""
        tenant = create_tenant()
        plan = self.create_plan(db)
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create increasing usage
        start = datetime.utcnow() - timedelta(days=30)
        for i in range(30):
            date = start + timedelta(days=i)
            event = create_usage_event(
                tenant_id=tenant.id,
                usage_type="api_calls",
                quantity=1000 + (i * 100),  # Increasing
            )
            event.created_at = date
            db.commit()

        service = ReportingService(db)
        analytics = service.get_usage_analytics(
            tenant_id=tenant.id,
            start_date=start,
            end_date=datetime.utcnow(),
        )

        assert analytics["trend"] == "up"
        print(f"✅ Analytics: Upward trend {analytics['trend_percent']}%")

    def test_trend_detection_down(
        self, db: Session, create_tenant, create_subscription, create_usage_event
    ):
        """Test downward trend detection."""
        tenant = create_tenant()
        plan = self.create_plan(db)
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create decreasing usage
        start = datetime.utcnow() - timedelta(days=30)
        for i in range(30):
            date = start + timedelta(days=i)
            event = create_usage_event(
                tenant_id=tenant.id,
                usage_type="api_calls",
                quantity=5000 - (i * 100),  # Decreasing
            )
            event.created_at = date
            db.commit()

        service = ReportingService(db)
        analytics = service.get_usage_analytics(
            tenant_id=tenant.id,
            start_date=start,
            end_date=datetime.utcnow(),
        )

        assert analytics["trend"] == "down"
        print(f"✅ Analytics: Downward trend {analytics['trend_percent']}%")

    @staticmethod
    def create_plan(db: Session):
        """Helper to create a plan."""
        from app.models import Plan
        plan = Plan(
            id="plan_test",
            name="Test Plan",
            api_calls_limit=10000,
            ai_tokens_limit=1000000,
        )
        db.add(plan)
        db.commit()
        return plan


class TestRevenueAnalytics:
    """Test revenue analytics reporting."""

    def test_get_revenue_analytics(
        self, db: Session, create_invoice
    ):
        """Test revenue analytics calculation."""
        # Create invoices for period
        create_invoice(total_cents=50000)
        create_invoice(total_cents=75000)

        service = ReportingService(db)
        analytics = service.get_revenue_analytics(
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )

        assert analytics["total_revenue_cents"] > 0
        assert analytics["total_revenue_dollars"] > 0
        assert "revenue_by_plan" in analytics

        print(f"✅ Revenue: Total ${analytics['total_revenue_dollars']:.2f}")

    def test_revenue_by_type_breakdown(
        self, db: Session, create_invoice
    ):
        """Test revenue breakdown by type."""
        create_invoice(total_cents=100000)

        service = ReportingService(db)
        analytics = service.get_revenue_analytics(
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )

        assert "base_plan" in analytics["revenue_by_type"]
        assert "overages" in analytics["revenue_by_type"]
        print("✅ Revenue: Breakdown by type")

    def test_average_revenue_per_tenant(
        self, db: Session, create_tenant, create_invoice
    ):
        """Test average revenue per tenant."""
        create_tenant()
        create_tenant()
        create_invoice(total_cents=100000)

        service = ReportingService(db)
        analytics = service.get_revenue_analytics(
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )

        assert analytics["average_revenue_per_tenant"] > 0
        print(f"✅ Revenue: Avg per tenant ${analytics['average_revenue_per_tenant']:.2f}")


class TestCostBreakdown:
    """Test cost breakdown reporting."""

    def test_get_cost_breakdown(
        self, db: Session, create_invoice
    ):
        """Test cost breakdown calculation."""
        create_invoice(total_cents=100000)

        service = ReportingService(db)
        breakdown = service.get_cost_breakdown(
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )

        assert breakdown["total_cost_cents"] > 0
        assert breakdown["total_cost_dollars"] > 0
        assert "cost_by_usage_type" in breakdown

        print(f"✅ Costs: Total ${breakdown['total_cost_dollars']:.2f}")

    def test_cost_by_component(
        self, db: Session, create_invoice
    ):
        """Test cost breakdown by component."""
        create_invoice(total_cents=100000)

        service = ReportingService(db)
        breakdown = service.get_cost_breakdown(
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )

        assert "metering" in breakdown["cost_by_component"]
        assert "storage" in breakdown["cost_by_component"]
        assert "processing" in breakdown["cost_by_component"]
        print("✅ Costs: Breakdown by component")


class TestTenantMetrics:
    """Test tenant-specific metrics."""

    def test_get_tenant_metrics(
        self, db: Session, create_tenant, create_subscription, create_usage_event, create_invoice, create_plan
    ):
        """Test tenant metrics calculation."""
        tenant = create_tenant()
        plan = create_plan()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1000)
        create_usage_event(tenant_id=tenant.id, usage_type="ai_tokens", quantity=100000)
        create_invoice(tenant_id=tenant.id, total_cents=50000)

        service = ReportingService(db)
        metrics = service.get_tenant_metrics(
            tenant_id=tenant.id,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )

        assert metrics["usage_api_calls"] >= 1000
        assert metrics["usage_tokens"] >= 100000
        assert metrics["revenue_generated_cents"] > 0

        print(f"✅ Tenant: Metrics collected")

    def test_churn_risk_assessment(
        self, db: Session, create_tenant, create_subscription, create_usage_event, create_plan
    ):
        """Test churn risk assessment."""
        tenant = create_tenant()
        plan = create_plan()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Minimal usage = high churn risk
        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=10)

        service = ReportingService(db)
        metrics = service.get_tenant_metrics(
            tenant_id=tenant.id,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )

        assert metrics["churn_risk"] in ["low", "medium", "high"]
        print(f"✅ Tenant: Churn risk {metrics['churn_risk']}")

    def test_active_days_calculation(
        self, db: Session, create_tenant, create_subscription, create_usage_event, create_plan
    ):
        """Test active days calculation."""
        tenant = create_tenant()
        plan = create_plan()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create usage on different days
        start = datetime.utcnow() - timedelta(days=30)
        for i in [0, 5, 10, 15, 20]:
            event = create_usage_event(
                tenant_id=tenant.id,
                usage_type="api_calls",
                quantity=100,
            )
            event.created_at = start + timedelta(days=i)
            db.commit()

        service = ReportingService(db)
        metrics = service.get_tenant_metrics(
            tenant_id=tenant.id,
            start_date=start,
            end_date=datetime.utcnow(),
        )

        assert metrics["active_days"] >= 1
        print(f"✅ Tenant: Active days {metrics['active_days']}")


class TestDashboard:
    """Test dashboard metrics."""

    def test_get_dashboard_metrics(
        self, db: Session, create_tenant, create_subscription, create_usage_event, create_invoice, create_plan
    ):
        """Test dashboard metrics."""
        tenant = create_tenant()
        plan = create_plan()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1000)
        create_invoice(tenant_id=tenant.id, total_cents=50000)

        service = ReportingService(db)
        dashboard = service.get_dashboard_metrics()

        assert dashboard["total_active_tenants"] >= 1
        assert dashboard["total_active_subscriptions"] >= 1
        assert dashboard["total_revenue_cents"] >= 0
        assert "gross_margin_percent" in dashboard

        print(f"✅ Dashboard: {dashboard['total_active_tenants']} tenants")

    def test_dashboard_margin_calculation(
        self, db: Session, create_invoice
    ):
        """Test gross margin calculation."""
        create_invoice(total_cents=100000)

        service = ReportingService(db)
        dashboard = service.get_dashboard_metrics()

        assert dashboard["gross_margin_percent"] >= 0
        assert dashboard["total_cost_dollars"] >= 0
        print(f"✅ Dashboard: Margin {dashboard['gross_margin_percent']}%")


class TestTrendAnalysis:
    """Test trend analysis and forecasting."""

    def test_get_trend_data_api_calls(
        self, db: Session, create_usage_event, create_tenant, create_subscription, create_plan
    ):
        """Test API call trend data."""
        tenant = create_tenant()
        plan = create_plan()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        # Create 30 days of data
        start = datetime.utcnow() - timedelta(days=30)
        for i in range(30):
            event = create_usage_event(
                tenant_id=tenant.id,
                usage_type="api_calls",
                quantity=1000 + (i * 50),  # Trending up
            )
            event.created_at = start + timedelta(days=i)
            db.commit()

        service = ReportingService(db)
        trend = service.get_trend_data(metric="api_calls", num_periods=30)

        assert len(trend["data_points"]) > 0
        assert "trend_direction" in trend
        assert "trend_strength" in trend
        print(f"✅ Trend: {len(trend['data_points'])} data points")

    def test_trend_forecast_calculation(
        self, db: Session, create_usage_event, create_tenant, create_subscription, create_plan
    ):
        """Test trend forecast calculation."""
        tenant = create_tenant()
        plan = create_plan()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        start = datetime.utcnow() - timedelta(days=30)
        for i in range(30):
            event = create_usage_event(
                tenant_id=tenant.id,
                usage_type="api_calls",
                quantity=1000,
            )
            event.created_at = start + timedelta(days=i)
            db.commit()

        service = ReportingService(db)
        trend = service.get_trend_data(metric="api_calls", num_periods=30)

        assert trend["forecast_next_period"] is not None
        print(f"✅ Forecast: {trend['forecast_next_period']}")

    def test_revenue_trends(
        self, db: Session, create_invoice
    ):
        """Test revenue trend analysis."""
        # Create invoices over time
        for i in range(10):
            invoice = create_invoice(total_cents=10000 + (i * 1000))
            invoice.created_at = datetime.utcnow() - timedelta(days=10-i)
            db.commit()

        service = ReportingService(db)
        trend = service.get_trend_data(metric="revenue", num_periods=10)

        assert len(trend["data_points"]) > 0
        assert "trend_direction" in trend
        print(f"✅ Revenue Trend: {trend['trend_direction']}")


class TestSavedReports:
    """Test saved report management."""

    def test_create_saved_report(
        self, db: Session
    ):
        """Test creating a saved report."""
        service = ReportingService(db)
        report = service.create_saved_report(
            name="Monthly Usage",
            report_type=ReportType.USAGE_ANALYTICS,
            frequency=ReportFrequency.MONTHLY,
        )

        assert report is not None
        assert report.name == "Monthly Usage"
        assert report.is_active is True
        print("✅ Saved Report: Created")

    def test_list_saved_reports(
        self, db: Session
    ):
        """Test listing saved reports."""
        service = ReportingService(db)

        service.create_saved_report(
            name="Report 1",
            report_type=ReportType.USAGE_ANALYTICS,
            frequency=ReportFrequency.DAILY,
        )
        service.create_saved_report(
            name="Report 2",
            report_type=ReportType.REVENUE_ANALYSIS,
            frequency=ReportFrequency.WEEKLY,
        )

        reports = service.list_saved_reports()

        assert len(reports) >= 2
        print(f"✅ Saved Report: Listed {len(reports)} reports")

    def test_delete_saved_report(
        self, db: Session
    ):
        """Test deleting a saved report."""
        service = ReportingService(db)

        report = service.create_saved_report(
            name="Report to Delete",
            report_type=ReportType.USAGE_ANALYTICS,
            frequency=ReportFrequency.ONCE,
        )

        service.delete_saved_report(report.id)

        deleted = service.get_saved_report(report.id)
        assert deleted.is_active is False

        print("✅ Saved Report: Deleted")

    def test_update_report_after_generation(
        self, db: Session
    ):
        """Test updating report after generation."""
        service = ReportingService(db)

        report = service.create_saved_report(
            name="Auto Report",
            report_type=ReportType.USAGE_ANALYTICS,
            frequency=ReportFrequency.DAILY,
        )

        # Simulate update
        report.last_generated_at = datetime.utcnow()
        db.commit()
        db.refresh(report)

        assert report.last_generated_at is not None
        print("✅ Saved Report: Updated after generation")


class TestReportRuns:
    """Test report execution."""

    def test_run_report_usage_analytics(
        self, db: Session
    ):
        """Test running usage analytics report."""
        service = ReportingService(db)

        start = datetime.utcnow() - timedelta(days=30)
        end = datetime.utcnow()

        run = service.run_report(
            report_type=ReportType.USAGE_ANALYTICS,
            start_date=start,
            end_date=end,
        )

        assert run.success is True
        assert run.completed_at is not None
        assert run.summary_data is not None
        print("✅ Report Run: Usage analytics executed")

    def test_run_report_revenue_analysis(
        self, db: Session
    ):
        """Test running revenue analysis report."""
        service = ReportingService(db)

        start = datetime.utcnow() - timedelta(days=30)
        end = datetime.utcnow()

        run = service.run_report(
            report_type=ReportType.REVENUE_ANALYSIS,
            start_date=start,
            end_date=end,
        )

        assert run.success is True
        print("✅ Report Run: Revenue analysis executed")

    def test_list_recent_runs(
        self, db: Session
    ):
        """Test listing recent report runs."""
        service = ReportingService(db)

        # Create multiple runs
        for i in range(3):
            service.run_report(
                report_type=ReportType.USAGE_ANALYTICS,
                start_date=datetime.utcnow() - timedelta(days=30),
                end_date=datetime.utcnow(),
            )

        runs = service.list_recent_runs(limit=10)

        assert len(runs) >= 3
        print(f"✅ Report Run: Listed {len(runs)} recent runs")

    def test_get_report_run_by_id(
        self, db: Session
    ):
        """Test retrieving report run by ID."""
        service = ReportingService(db)

        run = service.run_report(
            report_type=ReportType.USAGE_ANALYTICS,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )

        retrieved = service.get_report_run(run.id)

        assert retrieved is not None
        assert retrieved.id == run.id
        print("✅ Report Run: Retrieved by ID")


class TestReportingEdgeCases:
    """Test edge cases in reporting."""

    def test_analytics_no_data(
        self, db: Session, create_tenant
    ):
        """Test analytics with no data."""
        tenant = create_tenant()

        service = ReportingService(db)
        analytics = service.get_usage_analytics(tenant_id=tenant.id)

        assert analytics["api_calls_total"] == 0
        assert analytics["tokens_total"] == 0
        print("✅ Edge Case: Analytics with no data")

    def test_trend_with_single_point(
        self, db: Session, create_usage_event, create_tenant, create_subscription, create_plan
    ):
        """Test trend with single data point."""
        tenant = create_tenant()
        plan = create_plan()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        create_usage_event(tenant_id=tenant.id, usage_type="api_calls", quantity=1000)

        service = ReportingService(db)
        trend = service.get_trend_data(metric="api_calls", num_periods=30)

        assert "trend_direction" in trend
        print("✅ Edge Case: Trend with single point")

    def test_zero_cost_breakdown(
        self, db: Session
    ):
        """Test cost breakdown with zero cost."""
        service = ReportingService(db)
        breakdown = service.get_cost_breakdown(
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )

        assert breakdown["total_cost_cents"] >= 0
        print("✅ Edge Case: Zero cost breakdown")
