"""Tests for reconciliation service and Stripe sync auditing."""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from app.models_reconciliation import ReconciliationRun, ReconciliationIssue, ReconciliationType, ReconciliationStatus
from app.services.reconciliation_service import ReconciliationService


class TestReconciliationRunCreation:
    """Test reconciliation run creation and tracking."""

    def test_reconciliation_run_created(
        self, db: Session, create_tenant
    ):
        """Test that reconciliation run is created."""
        tenant = create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        assert run is not None
        assert run.id is not None
        assert run.run_type == "manual"
        assert run.started_at is not None

        print("✅ Reconciliation: Run created")

    def test_reconciliation_run_marks_completion(
        self, db: Session, create_tenant
    ):
        """Test that run marks completion time."""
        create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        assert run.completed_at is not None
        assert run.completed_at >= run.started_at

        print("✅ Reconciliation: Completion marked")

    def test_reconciliation_run_success_status(
        self, db: Session, create_tenant
    ):
        """Test that run success status is set."""
        create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        assert run.success is True
        assert run.error_message is None

        print("✅ Reconciliation: Success status set")

    def test_reconciliation_counts_tenants(
        self, db: Session, create_tenant
    ):
        """Test that run counts tenants checked."""
        create_tenant()
        create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        assert run.total_tenants_checked >= 2

        print(f"✅ Reconciliation: Checked {run.total_tenants_checked} tenants")

    def test_reconciliation_counts_subscriptions(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test that run counts subscriptions checked."""
        plan = create_plan()
        tenant = create_tenant()
        create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        assert run.total_subscriptions_checked >= 1

        print(f"✅ Reconciliation: Checked {run.total_subscriptions_checked} subscriptions")


class TestIssueDetection:
    """Test reconciliation issue detection."""

    def test_issue_creation_stores_details(
        self, db: Session, create_tenant
    ):
        """Test that issue creation stores all details."""
        tenant = create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        issue = service._create_issue(
            run_id=run.id,
            tenant_id=tenant.id,
            issue_type=ReconciliationType.SUBSCRIPTION_MISMATCH,
            message="Test mismatch",
            local_value="plan1",
            stripe_value="plan2",
        )

        assert issue.run_id == run.id
        assert issue.tenant_id == tenant.id
        assert issue.issue_type == ReconciliationType.SUBSCRIPTION_MISMATCH
        assert issue.local_value == "plan1"
        assert issue.stripe_value == "plan2"
        assert issue.status == ReconciliationStatus.PENDING

        print("✅ Issue: Created with details")

    def test_issue_types_created(
        self, db: Session, create_tenant
    ):
        """Test that different issue types can be created."""
        tenant = create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        # Create different types
        for issue_type in [
            ReconciliationType.SUBSCRIPTION_MISMATCH,
            ReconciliationType.PAYMENT_MISMATCH,
            ReconciliationType.WEBHOOK_MISSED,
        ]:
            issue = service._create_issue(
                run_id=run.id,
                tenant_id=tenant.id,
                issue_type=issue_type,
                message=f"Test {issue_type.value}",
            )
            assert issue.issue_type == issue_type

        print("✅ Issue: All types can be created")


class TestIssueRetrieval:
    """Test issue retrieval and querying."""

    def test_get_run_by_id(
        self, db: Session, create_tenant
    ):
        """Test getting run by ID."""
        create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        retrieved = service.get_run(run.id)

        assert retrieved is not None
        assert retrieved.id == run.id

        print("✅ Retrieval: Run retrieved by ID")

    def test_get_latest_runs(
        self, db: Session, create_tenant
    ):
        """Test getting latest runs."""
        create_tenant()

        service = ReconciliationService(db)
        run1 = service.run_reconciliation(run_type="manual")
        run2 = service.run_reconciliation(run_type="manual")

        latest = service.get_latest_runs(limit=10)

        assert len(latest) >= 2
        # Most recent first
        assert latest[0].created_at >= latest[1].created_at

        print(f"✅ Retrieval: Got {len(latest)} latest runs")

    def test_get_run_issues(
        self, db: Session, create_tenant
    ):
        """Test getting issues from specific run."""
        tenant = create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        # Create issues
        issue1 = service._create_issue(
            run_id=run.id,
            tenant_id=tenant.id,
            issue_type=ReconciliationType.SUBSCRIPTION_MISMATCH,
            message="Issue 1",
        )
        issue2 = service._create_issue(
            run_id=run.id,
            tenant_id=tenant.id,
            issue_type=ReconciliationType.PAYMENT_MISMATCH,
            message="Issue 2",
        )
        db.add(issue1)
        db.add(issue2)
        db.commit()

        issues = service.get_run_issues(run.id)

        assert len(issues) >= 2

        print(f"✅ Retrieval: Got {len(issues)} issues from run")

    def test_get_pending_issues(
        self, db: Session, create_tenant
    ):
        """Test getting pending issues."""
        tenant = create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        # Create pending issue
        issue = service._create_issue(
            run_id=run.id,
            tenant_id=tenant.id,
            issue_type=ReconciliationType.SUBSCRIPTION_MISMATCH,
            message="Pending issue",
        )
        db.add(issue)
        db.commit()

        pending = service.get_pending_issues()

        assert len(pending) > 0
        assert all(i.status == ReconciliationStatus.PENDING for i in pending)

        print(f"✅ Retrieval: Got {len(pending)} pending issues")


class TestIssueResolution:
    """Test issue resolution."""

    def test_resolve_issue(
        self, db: Session, create_tenant
    ):
        """Test resolving an issue."""
        tenant = create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        issue = service._create_issue(
            run_id=run.id,
            tenant_id=tenant.id,
            issue_type=ReconciliationType.SUBSCRIPTION_MISMATCH,
            message="Test issue",
        )
        db.add(issue)
        db.commit()

        resolved = service.resolve_issue(issue.id, "Manually synced")

        assert resolved.status == ReconciliationStatus.RESOLVED
        assert resolved.resolution_action == "Manually synced"
        assert resolved.resolved_at is not None

        print("✅ Resolution: Issue marked resolved")

    def test_resolve_invalid_issue_raises_error(
        self, db: Session
    ):
        """Test that resolving invalid issue raises error."""
        service = ReconciliationService(db)

        with pytest.raises(ValueError, match="not found"):
            service.resolve_issue("invalid-id", "Action")

        print("✅ Resolution: Invalid issue error handled")


class TestSummaryStatistics:
    """Test reconciliation summary and statistics."""

    def test_reconciliation_summary(
        self, db: Session, create_tenant
    ):
        """Test getting reconciliation summary."""
        create_tenant()

        service = ReconciliationService(db)
        service.run_reconciliation(run_type="manual")

        summary = service.get_reconciliation_summary()

        assert summary["total_runs"] > 0
        assert summary["last_run_id"] is not None
        assert "total_issues_found" in summary
        assert "total_pending_issues" in summary

        print("✅ Summary: Generated successfully")

    def test_summary_tracks_successful_runs(
        self, db: Session, create_tenant
    ):
        """Test that summary tracks successful runs."""
        create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")
        assert run.success is True

        summary = service.get_reconciliation_summary()

        assert summary["last_successful_run"] is not None

        print("✅ Summary: Tracks successful runs")

    def test_summary_includes_recent_issues(
        self, db: Session, create_tenant
    ):
        """Test that summary includes recent issues."""
        tenant = create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        issue = service._create_issue(
            run_id=run.id,
            tenant_id=tenant.id,
            issue_type=ReconciliationType.SUBSCRIPTION_MISMATCH,
            message="Recent issue",
        )
        db.add(issue)
        db.commit()

        summary = service.get_reconciliation_summary()

        assert len(summary["most_recent_issues"]) > 0

        print("✅ Summary: Includes recent issues")


class TestTenantSpecificReconciliation:
    """Test reconciliation for specific tenants."""

    def test_reconcile_specific_tenant(
        self, db: Session, create_tenant, create_plan, create_subscription
    ):
        """Test reconciling specific tenant."""
        plan = create_plan()
        tenant1 = create_tenant()
        tenant2 = create_tenant()
        
        create_subscription(tenant_id=tenant1.id, plan_id=plan.id)
        create_subscription(tenant_id=tenant2.id, plan_id=plan.id)

        service = ReconciliationService(db)
        run = service.run_reconciliation(tenant_id=tenant1.id, run_type="manual")

        assert run.success is True

        print("✅ Tenant Specific: Specific tenant reconciled")

    def test_get_pending_issues_for_tenant(
        self, db: Session, create_tenant
    ):
        """Test getting pending issues for specific tenant."""
        tenant1 = create_tenant()
        tenant2 = create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        # Create issues for both tenants
        issue1 = service._create_issue(
            run_id=run.id,
            tenant_id=tenant1.id,
            issue_type=ReconciliationType.SUBSCRIPTION_MISMATCH,
            message="Tenant 1 issue",
        )
        issue2 = service._create_issue(
            run_id=run.id,
            tenant_id=tenant2.id,
            issue_type=ReconciliationType.SUBSCRIPTION_MISMATCH,
            message="Tenant 2 issue",
        )
        db.add(issue1)
        db.add(issue2)
        db.commit()

        # Get pending for tenant1
        pending = service.get_pending_issues(tenant_id=tenant1.id)

        assert all(i.tenant_id == tenant1.id for i in pending)

        print("✅ Tenant Specific: Pending issues filtered by tenant")


class TestRunTypes:
    """Test different run types."""

    def test_scheduled_run_type(
        self, db: Session, create_tenant
    ):
        """Test creating scheduled run."""
        create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="scheduled")

        assert run.run_type == "scheduled"

        print("✅ Run Type: Scheduled run created")

    def test_manual_run_type(
        self, db: Session, create_tenant
    ):
        """Test creating manual run."""
        create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        assert run.run_type == "manual"

        print("✅ Run Type: Manual run created")


class TestAutoResolution:
    """Test auto-resolution of issues."""

    def test_resolve_issues_flag(
        self, db: Session, create_tenant
    ):
        """Test resolve_issues flag in reconciliation."""
        create_tenant()

        service = ReconciliationService(db)
        
        # Run with resolve_issues=True
        run = service.run_reconciliation(
            run_type="manual",
            resolve_issues=True,
        )

        # Run should complete successfully
        assert run.success is True

        print("✅ Auto Resolution: Flag processed")


class TestErrorHandling:
    """Test error handling in reconciliation."""

    def test_reconciliation_handles_stripe_error(
        self, db: Session, create_tenant
    ):
        """Test handling of Stripe API errors."""
        create_tenant()

        service = ReconciliationService(db)
        
        # Mock Stripe to fail
        with patch('app.services.reconciliation_service.stripe') as mock_stripe:
            mock_stripe.Subscription.list.side_effect = Exception("Stripe offline")
            
            run = service.run_reconciliation(run_type="manual")
            
            # Should complete but not be successful
            assert run.completed_at is not None

        print("✅ Error Handling: Stripe errors handled")

    def test_missing_stripe_customer_handled(
        self, db: Session, create_tenant
    ):
        """Test handling of tenants without Stripe customer."""
        tenant = create_tenant()
        # Tenant has no stripe_customer_id

        service = ReconciliationService(db)
        run = service.run_reconciliation(tenant_id=tenant.id, run_type="manual")

        # Should complete without error
        assert run.completed_at is not None

        print("✅ Error Handling: Missing Stripe customer handled")


class TestIssueMessages:
    """Test issue message clarity."""

    def test_issue_has_clear_message(
        self, db: Session, create_tenant
    ):
        """Test that issues have clear descriptive messages."""
        tenant = create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        issue = service._create_issue(
            run_id=run.id,
            tenant_id=tenant.id,
            issue_type=ReconciliationType.SUBSCRIPTION_MISMATCH,
            message="Subscription plan mismatch: local=free, stripe=pro",
        )

        assert len(issue.message) > 10
        assert "mismatch" in issue.message.lower()

        print("✅ Messages: Issues have clear messages")

    def test_issue_stores_local_and_stripe_values(
        self, db: Session, create_tenant
    ):
        """Test that issues store both local and Stripe values."""
        tenant = create_tenant()

        service = ReconciliationService(db)
        run = service.run_reconciliation(run_type="manual")

        issue = service._create_issue(
            run_id=run.id,
            tenant_id=tenant.id,
            issue_type=ReconciliationType.PAYMENT_MISMATCH,
            message="Status mismatch",
            local_value="active",
            stripe_value="inactive",
        )

        assert issue.local_value == "active"
        assert issue.stripe_value == "inactive"

        print("✅ Messages: Values stored for comparison")


class TestReconciliationIntegration:
    """Test integration of reconciliation system."""

    def test_full_reconciliation_workflow(
        self, db: Session, create_plan, create_tenant, create_subscription
    ):
        """Test complete reconciliation workflow."""
        plan = create_plan()
        tenant = create_tenant()
        sub = create_subscription(tenant_id=tenant.id, plan_id=plan.id)

        service = ReconciliationService(db)
        
        # Run reconciliation
        run = service.run_reconciliation(run_type="manual")
        assert run.success is True

        # Get run details
        retrieved_run = service.get_run(run.id)
        assert retrieved_run is not None

        # Get issues (if any)
        issues = service.get_run_issues(run.id)
        
        # If issues exist, resolve one
        if issues:
            resolved = service.resolve_issue(issues[0].id, "Manual sync")
            assert resolved.status == ReconciliationStatus.RESOLVED

        # Get summary
        summary = service.get_reconciliation_summary()
        assert summary["total_runs"] > 0

        print("✅ Integration: Full workflow completed")
