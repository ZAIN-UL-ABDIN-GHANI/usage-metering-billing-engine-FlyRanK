"""Reporting service - analytics, trends, dashboards, and custom reports."""

from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
import json

from app.models_reporting import SavedReport, ReportRun, ReportType, ReportFrequency
from app.models import Tenant, Subscription, Plan, UsageEvent, Invoice
from app.models_overage import OverageCharge
from app.utils.db_helpers import generate_id, get_current_billing_period


class ReportingService:
    """Service for analytics, reporting, and trend analysis."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    # ==================== USAGE ANALYTICS ====================

    def get_usage_analytics(
        self,
        tenant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """
        Get usage analytics for period.

        Args:
            tenant_id: Optional tenant filter
            start_date: Period start (default: 30 days ago)
            end_date: Period end (default: now)

        Returns:
            Dictionary with usage metrics
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        query = self.db.query(UsageEvent).filter(
            UsageEvent.created_at >= start_date,
            UsageEvent.created_at <= end_date,
        )

        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)

        # Get API calls
        api_calls = query.filter_by(usage_type="api_calls").all()
        api_total = sum(e.quantity for e in api_calls)
        api_avg = api_total / max(1, (end_date - start_date).days)

        # Get tokens
        tokens = query.filter_by(usage_type="ai_tokens").all()
        token_total = sum(e.quantity for e in tokens)
        token_avg = token_total / max(1, (end_date - start_date).days)

        # Find peak usage
        peak_date = None
        peak_value = 0
        if api_calls:
            daily_usage = {}
            for event in api_calls:
                date_key = event.created_at.date()
                daily_usage[date_key] = daily_usage.get(date_key, 0) + event.quantity
            if daily_usage:
                peak_date, peak_value = max(daily_usage.items(), key=lambda x: x[1])

        # Calculate trend
        mid_point = start_date + (end_date - start_date) / 2
        first_half = sum(
            e.quantity for e in api_calls
            if e.created_at < mid_point
        )
        second_half = sum(
            e.quantity for e in api_calls
            if e.created_at >= mid_point
        )

        trend = "flat"
        trend_percent = 0
        if first_half > 0:
            trend_percent = ((second_half - first_half) / first_half) * 100
            if trend_percent > 5:
                trend = "up"
            elif trend_percent < -5:
                trend = "down"

        return {
            "period": f"{start_date.date()} to {end_date.date()}",
            "api_calls_total": api_total,
            "api_calls_average_daily": round(api_avg, 2),
            "tokens_total": token_total,
            "tokens_average_daily": round(token_avg, 2),
            "peak_usage_date": str(peak_date) if peak_date else None,
            "peak_usage_value": peak_value,
            "trend": trend,
            "trend_percent": round(trend_percent, 2),
        }

    # ==================== REVENUE ANALYTICS ====================

    def get_revenue_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """
        Get revenue analytics for period.

        Args:
            start_date: Period start
            end_date: Period end

        Returns:
            Dictionary with revenue metrics
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        # Get invoices for period
        invoices = self.db.query(Invoice).filter(
            Invoice.created_at >= start_date,
            Invoice.created_at <= end_date,
        ).all()

        total_revenue = sum(i.total_cents for i in invoices)

        # Revenue by plan
        revenue_by_plan = {}
        for invoice in invoices:
            # Get plan from subscription
            plan_name = "Unknown"
            # Would need to join through subscription
            revenue_by_plan[plan_name] = revenue_by_plan.get(plan_name, 0) + invoice.total_cents

        # Estimate revenue by type (would need invoice line items for accuracy)
        total_tenants = self.db.query(Tenant).count()
        avg_revenue = total_revenue / max(1, total_tenants)

        return {
            "period": f"{start_date.date()} to {end_date.date()}",
            "total_revenue_cents": total_revenue,
            "total_revenue_dollars": round(total_revenue / 100, 2),
            "revenue_by_plan": {k: round(v / 100, 2) for k, v in revenue_by_plan.items()},
            "revenue_by_type": {
                "base_plan": round(total_revenue * 0.7 / 100, 2),
                "overages": round(total_revenue * 0.3 / 100, 2),
            },
            "average_revenue_per_tenant": round(avg_revenue / 100, 2),
            "month_over_month_growth": 0.0,  # Would need historical data
        }

    # ==================== COST BREAKDOWN ====================

    def get_cost_breakdown(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """
        Get cost breakdown for period.

        Args:
            start_date: Period start
            end_date: Period end

        Returns:
            Dictionary with cost analysis
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        # Get invoices
        invoices = self.db.query(Invoice).filter(
            Invoice.created_at >= start_date,
            Invoice.created_at <= end_date,
        ).all()

        total_cost = sum(i.total_cents for i in invoices)

        # Estimate breakdown (in real system, use detailed line items)
        api_call_cost = total_cost * 0.4
        token_cost = total_cost * 0.5
        overage_cost = total_cost * 0.1

        return {
            "period": f"{start_date.date()} to {end_date.date()}",
            "total_cost_cents": total_cost,
            "total_cost_dollars": round(total_cost / 100, 2),
            "cost_by_usage_type": {
                "api_calls": round(api_call_cost / 100, 2),
                "tokens": round(token_cost / 100, 2),
                "overages": round(overage_cost / 100, 2),
            },
            "cost_by_component": {
                "metering": round(total_cost * 0.2 / 100, 2),
                "storage": round(total_cost * 0.3 / 100, 2),
                "processing": round(total_cost * 0.5 / 100, 2),
            },
            "cost_variance_percent": 0.0,
        }

    # ==================== TENANT METRICS ====================

    def get_tenant_metrics(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """
        Get tenant-specific metrics.

        Args:
            tenant_id: Tenant ID
            start_date: Period start
            end_date: Period end

        Returns:
            Dictionary with tenant metrics
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        # Get usage
        api_calls = self.db.query(func.sum(UsageEvent.quantity)).filter_by(
            tenant_id=tenant_id,
            usage_type="api_calls",
        ).filter(
            UsageEvent.created_at >= start_date,
            UsageEvent.created_at <= end_date,
        ).scalar() or 0

        tokens = self.db.query(func.sum(UsageEvent.quantity)).filter_by(
            tenant_id=tenant_id,
            usage_type="ai_tokens",
        ).filter(
            UsageEvent.created_at >= start_date,
            UsageEvent.created_at <= end_date,
        ).scalar() or 0

        # Get revenue
        invoices = self.db.query(func.sum(Invoice.total_cents)).filter_by(
            tenant_id=tenant_id,
        ).filter(
            Invoice.created_at >= start_date,
            Invoice.created_at <= end_date,
        ).scalar() or 0

        # Calculate active days
        active_days = self.db.query(
            func.count(func.distinct(func.date(UsageEvent.created_at)))
        ).filter_by(tenant_id=tenant_id).filter(
            UsageEvent.created_at >= start_date,
            UsageEvent.created_at <= end_date,
        ).scalar() or 0

        # Estimate churn risk (would use ML in production)
        churn_risk = "low"
        if invoices < 1000:  # Less than $10
            churn_risk = "high"
        elif invoices < 5000:  # Less than $50
            churn_risk = "medium"

        return {
            "tenant_id": tenant_id,
            "period": f"{start_date.date()} to {end_date.date()}",
            "usage_api_calls": api_calls,
            "usage_tokens": tokens,
            "revenue_generated_cents": invoices,
            "revenue_generated_dollars": round(invoices / 100, 2),
            "active_days": active_days,
            "churn_risk": churn_risk,
        }

    # ==================== DASHBOARD METRICS ====================

    def get_dashboard_metrics(self) -> dict:
        """
        Get high-level dashboard overview.

        Returns:
            Dictionary with dashboard metrics
        """
        # Current period
        period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = datetime.utcnow()

        # Count metrics
        active_tenants = self.db.query(Tenant).count()
        active_subscriptions = self.db.query(Subscription).filter_by(
            status="active"
        ).count()

        # Revenue
        invoices = self.db.query(func.sum(Invoice.total_cents)).filter(
            Invoice.created_at >= period_start,
            Invoice.created_at <= period_end,
        ).scalar() or 0

        # Usage
        api_total = self.db.query(func.sum(UsageEvent.quantity)).filter_by(
            usage_type="api_calls"
        ).filter(
            UsageEvent.created_at >= period_start,
            UsageEvent.created_at <= period_end,
        ).scalar() or 0

        token_total = self.db.query(func.sum(UsageEvent.quantity)).filter_by(
            usage_type="ai_tokens"
        ).filter(
            UsageEvent.created_at >= period_start,
            UsageEvent.created_at <= period_end,
        ).scalar() or 0

        # Cost (estimated)
        cost = invoices * 0.4  # Assume 40% cost ratio

        # Calculate metrics
        margin = invoices - cost if invoices > 0 else 0
        margin_percent = (margin / invoices * 100) if invoices > 0 else 0

        return {
            "current_period": period_start.strftime("%Y-%m"),
            "total_active_tenants": active_tenants,
            "total_active_subscriptions": active_subscriptions,
            "total_revenue_cents": invoices,
            "total_revenue_dollars": round(invoices / 100, 2),
            "total_usage_api_calls": api_total,
            "total_usage_tokens": token_total,
            "total_cost_cents": int(cost),
            "total_cost_dollars": round(cost / 100, 2),
            "gross_margin_percent": round(margin_percent, 2),
            "churn_rate": 2.5,  # Placeholder
            "growth_rate_percent": 5.2,  # Placeholder
        }

    # ==================== TREND ANALYSIS ====================

    def get_trend_data(
        self,
        metric: str,  # api_calls, tokens, revenue
        period_type: str = "daily",  # daily, weekly, monthly
        num_periods: int = 30,
    ) -> dict:
        """
        Get trend data over time.

        Args:
            metric: Metric to analyze
            period_type: Time period granularity
            num_periods: Number of periods to include

        Returns:
            Dictionary with trend data
        """
        data_points = []

        if metric == "api_calls":
            # Get daily API call usage
            query = self.db.query(
                func.date(UsageEvent.created_at).label("date"),
                func.sum(UsageEvent.quantity).label("total"),
            ).filter_by(usage_type="api_calls").group_by(
                func.date(UsageEvent.created_at)
            ).order_by(
                func.date(UsageEvent.created_at).desc()
            ).limit(num_periods).all()

            for row in reversed(query):
                data_points.append({
                    "date": str(row.date),
                    "value": row.total or 0,
                })

        elif metric == "revenue":
            # Get daily revenue
            query = self.db.query(
                func.date(Invoice.created_at).label("date"),
                func.sum(Invoice.total_cents).label("total"),
            ).group_by(
                func.date(Invoice.created_at)
            ).order_by(
                func.date(Invoice.created_at).desc()
            ).limit(num_periods).all()

            for row in reversed(query):
                data_points.append({
                    "date": str(row.date),
                    "value": round((row.total or 0) / 100, 2),
                })

        # Analyze trend
        trend_direction = "flat"
        trend_strength = 0.0

        if len(data_points) >= 2:
            first_half = sum(p["value"] for p in data_points[:len(data_points)//2])
            second_half = sum(p["value"] for p in data_points[len(data_points)//2:])

            if first_half > 0:
                change = (second_half - first_half) / first_half
                trend_strength = min(1.0, abs(change))
                if change > 0.05:
                    trend_direction = "up"
                elif change < -0.05:
                    trend_direction = "down"

        # Forecast next period
        forecast = None
        if len(data_points) >= 7:
            recent_avg = sum(p["value"] for p in data_points[-7:]) / 7
            forecast = recent_avg * (1 + trend_strength * (1 if trend_direction == "up" else -1))

        return {
            "metric_name": metric,
            "period_type": period_type,
            "data_points": data_points,
            "trend_direction": trend_direction,
            "trend_strength": round(trend_strength, 2),
            "forecast_next_period": round(forecast, 2) if forecast else None,
        }

    # ==================== SAVED REPORTS ====================

    def create_saved_report(
        self,
        name: str,
        report_type: ReportType,
        frequency: ReportFrequency,
        tenant_id: Optional[str] = None,
        parameters: Optional[dict] = None,
    ) -> SavedReport:
        """
        Create a saved report configuration.

        Args:
            name: Report name
            report_type: Type of report
            frequency: Generation frequency
            tenant_id: Optional tenant filter
            parameters: Optional report parameters

        Returns:
            Created SavedReport
        """
        report = SavedReport(
            id=generate_id(),
            tenant_id=tenant_id,
            name=name,
            report_type=report_type,
            frequency=frequency,
            include_charts=True,
            include_summary=True,
            include_trends=True,
            parameters=json.dumps(parameters) if parameters else None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        return report

    def get_saved_report(self, report_id: str) -> Optional[SavedReport]:
        """Get saved report by ID."""
        return self.db.query(SavedReport).filter_by(id=report_id).first()

    def list_saved_reports(self, tenant_id: Optional[str] = None) -> List[SavedReport]:
        """List saved reports."""
        query = self.db.query(SavedReport).filter_by(is_active=True)
        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)
        return query.all()

    def delete_saved_report(self, report_id: str) -> None:
        """Delete (deactivate) saved report."""
        report = self.get_saved_report(report_id)
        if report:
            report.is_active = False
            self.db.commit()

    def run_report(
        self,
        report_type: ReportType,
        start_date: datetime,
        end_date: datetime,
        saved_report_id: Optional[str] = None,
    ) -> ReportRun:
        """
        Execute a report and store results.

        Args:
            report_type: Type of report to run
            start_date: Report period start
            end_date: Report period end
            saved_report_id: Optional associated saved report

        Returns:
            ReportRun with results
        """
        run = ReportRun(
            id=generate_id(),
            saved_report_id=saved_report_id,
            report_type=report_type,
            date_range_start=start_date,
            date_range_end=end_date,
            started_at=datetime.utcnow(),
        )

        try:
            # Generate report data based on type
            if report_type == ReportType.USAGE_ANALYTICS:
                data = self.get_usage_analytics(start_date=start_date, end_date=end_date)
            elif report_type == ReportType.REVENUE_ANALYSIS:
                data = self.get_revenue_analytics(start_date=start_date, end_date=end_date)
            elif report_type == ReportType.COST_BREAKDOWN:
                data = self.get_cost_breakdown(start_date=start_date, end_date=end_date)
            else:
                data = {}

            run.summary_data = json.dumps(data)
            run.total_records = 1
            run.success = True
            run.completed_at = datetime.utcnow()

        except Exception as e:
            run.success = False
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()

        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        return run

    def get_report_run(self, run_id: str) -> Optional[ReportRun]:
        """Get report run by ID."""
        return self.db.query(ReportRun).filter_by(id=run_id).first()

    def list_recent_runs(self, limit: int = 10) -> List[ReportRun]:
        """List recent report runs."""
        return (
            self.db.query(ReportRun)
            .order_by(ReportRun.created_at.desc())
            .limit(limit)
            .all()
        )
