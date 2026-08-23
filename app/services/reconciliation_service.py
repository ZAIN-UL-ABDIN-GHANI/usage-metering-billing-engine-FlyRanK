"""Reconciliation service - audits Stripe sync and detects missed webhooks."""

from typing import Optional, Tuple, List
from datetime import datetime
from sqlalchemy.orm import Session
import stripe

from app.models_reconciliation import (
    ReconciliationRun, ReconciliationIssue, ReconciliationType, ReconciliationStatus
)
from app.models import Tenant, Subscription, Plan
from app.utils.db_helpers import generate_id
from app.config import settings


class ReconciliationService:
    """Service for reconciliation of local database with Stripe."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        # Configure Stripe
        stripe.api_key = settings.stripe_secret_key

    def run_reconciliation(
        self,
        tenant_id: Optional[str] = None,
        run_type: str = "scheduled",
        resolve_issues: bool = False,
    ) -> ReconciliationRun:
        """
        Run full reconciliation check.

        Compares local database with Stripe for all or specific tenant.

        Args:
            tenant_id: Optional specific tenant to reconcile
            run_type: "scheduled" or "manual"
            resolve_issues: Auto-resolve mismatches if possible

        Returns:
            ReconciliationRun with results
        """
        run = ReconciliationRun(
            id=generate_id(),
            run_type=run_type,
            started_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

        try:
            # Get tenants to check
            if tenant_id:
                tenants = self.db.query(Tenant).filter_by(id=tenant_id).all()
            else:
                tenants = self.db.query(Tenant).all()

            run.total_tenants_checked = len(tenants)

            # Check each tenant
            for tenant in tenants:
                self._reconcile_tenant(run, tenant, resolve_issues)

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

    def _reconcile_tenant(
        self,
        run: ReconciliationRun,
        tenant: Tenant,
        resolve_issues: bool,
    ) -> None:
        """
        Reconcile single tenant.

        Args:
            run: Reconciliation run to update
            tenant: Tenant to reconcile
            resolve_issues: Auto-resolve issues
        """
        # Get local subscriptions
        local_subs = (
            self.db.query(Subscription)
            .filter_by(tenant_id=tenant.id)
            .all()
        )

        run.total_subscriptions_checked += len(local_subs)

        # Get Stripe subscriptions for tenant
        try:
            stripe_subs = self._get_stripe_subscriptions(tenant)
        except stripe.error.StripeError as e:
            # Stripe offline - create issue
            issue = self._create_issue(
                run_id=run.id,
                tenant_id=tenant.id,
                issue_type=ReconciliationType.STRIPE_OFFLINE,
                message=f"Could not reach Stripe API: {str(e)}",
            )
            self.db.add(issue)
            run.total_mismatches_found += 1
            return

        # Compare local vs Stripe
        stripe_by_id = {sub.id: sub for sub in stripe_subs}

        for local_sub in local_subs:
            stripe_sub = stripe_by_id.get(local_sub.stripe_subscription_id)

            if not stripe_sub:
                # Stripe subscription not found - could be webhook miss
                issue = self._create_issue(
                    run_id=run.id,
                    tenant_id=tenant.id,
                    subscription_id=local_sub.id,
                    issue_type=ReconciliationType.WEBHOOK_MISSED,
                    local_value=f"Plan: {local_sub.plan_id}",
                    stripe_value="Not found in Stripe",
                    stripe_object_id=local_sub.stripe_subscription_id,
                    stripe_object_type="subscription",
                    message=f"Subscription exists locally but not in Stripe",
                )
                self.db.add(issue)
                run.total_mismatches_found += 1
                continue

            # Check plan mismatch
            if stripe_sub.plan.id != local_sub.plan_id:
                issue = self._create_issue(
                    run_id=run.id,
                    tenant_id=tenant.id,
                    subscription_id=local_sub.id,
                    issue_type=ReconciliationType.SUBSCRIPTION_MISMATCH,
                    local_value=f"Plan: {local_sub.plan_id}",
                    stripe_value=f"Plan: {stripe_sub.plan.id}",
                    stripe_object_id=stripe_sub.id,
                    stripe_object_type="subscription",
                    message=f"Plan mismatch: local={local_sub.plan_id}, stripe={stripe_sub.plan.id}",
                )
                self.db.add(issue)
                run.total_mismatches_found += 1

                if resolve_issues:
                    # Auto-resolve: update local to match Stripe
                    local_sub.plan_id = stripe_sub.plan.id
                    issue.status = ReconciliationStatus.RESOLVED
                    issue.resolution_action = "Updated local plan to match Stripe"
                    issue.resolved_at = datetime.utcnow()
                    run.total_issues_resolved += 1

            # Check payment status mismatch
            local_paid = local_sub.status == "active"
            stripe_paid = stripe_sub.status == "active"

            if local_paid != stripe_paid:
                issue = self._create_issue(
                    run_id=run.id,
                    tenant_id=tenant.id,
                    subscription_id=local_sub.id,
                    issue_type=ReconciliationType.PAYMENT_MISMATCH,
                    local_value=f"Status: {local_sub.status}",
                    stripe_value=f"Status: {stripe_sub.status}",
                    stripe_object_id=stripe_sub.id,
                    stripe_object_type="subscription",
                    message=f"Payment status mismatch: local={local_sub.status}, stripe={stripe_sub.status}",
                )
                self.db.add(issue)
                run.total_mismatches_found += 1

                if resolve_issues:
                    # Auto-resolve: update local to match Stripe
                    local_sub.status = stripe_sub.status
                    issue.status = ReconciliationStatus.RESOLVED
                    issue.resolution_action = "Updated local status to match Stripe"
                    issue.resolved_at = datetime.utcnow()
                    run.total_issues_resolved += 1

        self.db.commit()

    def _get_stripe_subscriptions(self, tenant: Tenant) -> List:
        """
        Get all Stripe subscriptions for tenant.

        Args:
            tenant: Tenant object

        Returns:
            List of Stripe subscription objects

        Raises:
            stripe.error.StripeError: If Stripe API call fails
        """
        stripe_subs = []

        try:
            # Get Stripe customer for tenant
            if not tenant.stripe_customer_id:
                return stripe_subs

            # List subscriptions for customer
            response = stripe.Subscription.list(
                customer=tenant.stripe_customer_id,
                limit=100,
            )

            stripe_subs = response.get("data", [])

        except stripe.error.StripeError as e:
            raise e

        return stripe_subs

    def _create_issue(
        self,
        run_id: str,
        tenant_id: str,
        issue_type: ReconciliationType,
        message: str,
        subscription_id: Optional[str] = None,
        local_value: Optional[str] = None,
        stripe_value: Optional[str] = None,
        stripe_object_id: Optional[str] = None,
        stripe_object_type: Optional[str] = None,
    ) -> ReconciliationIssue:
        """
        Create reconciliation issue record.

        Args:
            run_id: Run ID
            tenant_id: Tenant ID
            issue_type: Type of issue
            message: Issue description
            subscription_id: Optional subscription ID
            local_value: Local database value
            stripe_value: Stripe API value
            stripe_object_id: Stripe object ID
            stripe_object_type: Stripe object type

        Returns:
            Created ReconciliationIssue
        """
        issue = ReconciliationIssue(
            id=generate_id(),
            run_id=run_id,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            issue_type=issue_type,
            local_value=local_value,
            stripe_value=stripe_value,
            stripe_object_id=stripe_object_id,
            stripe_object_type=stripe_object_type,
            status=ReconciliationStatus.PENDING,
            message=message,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        return issue

    def get_run(self, run_id: str) -> Optional[ReconciliationRun]:
        """
        Get reconciliation run by ID.

        Args:
            run_id: Run ID

        Returns:
            ReconciliationRun or None
        """
        return self.db.query(ReconciliationRun).filter_by(id=run_id).first()

    def get_latest_runs(self, limit: int = 10) -> List[ReconciliationRun]:
        """
        Get latest reconciliation runs.

        Args:
            limit: Max runs to return

        Returns:
            List of runs
        """
        return (
            self.db.query(ReconciliationRun)
            .order_by(ReconciliationRun.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_run_issues(self, run_id: str) -> List[ReconciliationIssue]:
        """
        Get all issues from reconciliation run.

        Args:
            run_id: Run ID

        Returns:
            List of issues
        """
        return (
            self.db.query(ReconciliationIssue)
            .filter_by(run_id=run_id)
            .all()
        )

    def get_pending_issues(self, tenant_id: Optional[str] = None) -> List[ReconciliationIssue]:
        """
        Get pending (unresolved) issues.

        Args:
            tenant_id: Optional filter by tenant

        Returns:
            List of pending issues
        """
        query = self.db.query(ReconciliationIssue).filter_by(
            status=ReconciliationStatus.PENDING
        )

        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)

        return query.all()

    def resolve_issue(
        self,
        issue_id: str,
        resolution_action: str,
    ) -> ReconciliationIssue:
        """
        Mark issue as resolved.

        Args:
            issue_id: Issue ID
            resolution_action: What was done to fix it

        Returns:
            Updated ReconciliationIssue

        Raises:
            ValueError: If issue not found
        """
        issue = self.db.query(ReconciliationIssue).filter_by(id=issue_id).first()
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")

        issue.status = ReconciliationStatus.RESOLVED
        issue.resolution_action = resolution_action
        issue.resolved_at = datetime.utcnow()
        issue.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(issue)

        return issue

    def get_reconciliation_summary(self) -> dict:
        """
        Get summary of reconciliation status.

        Returns:
            Dictionary with summary statistics
        """
        runs = self.db.query(ReconciliationRun).all()
        issues = self.db.query(ReconciliationIssue).all()

        last_run = runs[0] if runs else None
        last_successful = next((r for r in runs if r.success), None)

        pending_issues = [i for i in issues if i.status == ReconciliationStatus.PENDING]

        return {
            "total_runs": len(runs),
            "last_run_id": last_run.id if last_run else None,
            "last_run_date": last_run.created_at if last_run else None,
            "last_successful_run": last_successful.created_at if last_successful else None,
            "total_issues_found": len(issues),
            "total_issues_resolved": len([i for i in issues if i.status == ReconciliationStatus.RESOLVED]),
            "total_pending_issues": len(pending_issues),
            "most_recent_issues": sorted(issues, key=lambda i: i.created_at, reverse=True)[:5],
        }
