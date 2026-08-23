"""Reconciliation routes - API endpoints for Stripe reconciliation."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant
from app.models_reconciliation import (
    ManualReconciliationRequest, ReconciliationRunResponse, 
    ReconciliationRunDetailResponse, ReconciliationSummaryResponse,
    ReconciliationIssueResponse
)
from app.services.reconciliation_service import ReconciliationService

router = APIRouter(
    prefix="/reconciliation",
    tags=["reconciliation"],
)


@router.post("/run", status_code=status.HTTP_200_OK)
async def run_manual_reconciliation(
    request: ManualReconciliationRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Run manual reconciliation check.

    **Authentication**: Required (API key)

    Compares local database with Stripe and detects mismatches.
    Can optionally auto-resolve issues if possible.

    Args:
        tenant_id: Optional specific tenant to reconcile (default: current tenant)
        resolve_issues: Auto-resolve mismatches if possible (default: false)

    Returns:
        Reconciliation run with results

    Raises:
        401: Unauthorized
        500: Stripe API error

    Example:
        POST /reconciliation/run
        Headers:
          X-API-Key: tenant-id
        Body:
          {
            "tenant_id": null,
            "resolve_issues": false
          }
        Response (200 OK):
          {
            "id": "run_123",
            "run_type": "manual",
            "started_at": "2026-08-19T12:00:00",
            "completed_at": "2026-08-19T12:00:15",
            "total_tenants_checked": 1,
            "total_subscriptions_checked": 5,
            "total_mismatches_found": 1,
            "total_issues_resolved": 0,
            "success": true
          }
    """
    service = ReconciliationService(db)

    # Use specific tenant or current tenant
    tenant_id_to_check = request.tenant_id or current_tenant.id

    try:
        run = service.run_reconciliation(
            tenant_id=tenant_id_to_check,
            run_type="manual",
            resolve_issues=request.resolve_issues,
        )

        return ReconciliationRunResponse.model_validate(run)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation failed: {str(e)}",
        )


@router.get("/run/{run_id}", status_code=status.HTTP_200_OK)
async def get_run_details(
    run_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get reconciliation run details with all issues.

    **Authentication**: Required (API key)

    Args:
        run_id: Reconciliation run ID

    Returns:
        Run details with associated issues

    Raises:
        401: Unauthorized
        404: Run not found

    Example:
        GET /reconciliation/run/run_123
        Headers:
          X-API-Key: tenant-id
    """
    service = ReconciliationService(db)
    run = service.get_run(run_id)

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    issues = service.get_run_issues(run_id)

    return ReconciliationRunDetailResponse(
        run=ReconciliationRunResponse.model_validate(run),
        issues=[ReconciliationIssueResponse.model_validate(i) for i in issues],
        unresolved_count=len([i for i in issues if i.status == "pending"]),
    )


@router.get("/runs/latest", status_code=status.HTTP_200_OK)
async def get_latest_runs(
    limit: int = Query(10, ge=1, le=100),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get latest reconciliation runs.

    **Authentication**: Required (API key)

    Args:
        limit: Max runs to return

    Returns:
        List of recent runs

    Raises:
        401: Unauthorized

    Example:
        GET /reconciliation/runs/latest?limit=5
        Headers:
          X-API-Key: tenant-id
    """
    service = ReconciliationService(db)
    runs = service.get_latest_runs(limit=limit)

    return {
        "runs": [ReconciliationRunResponse.model_validate(r) for r in runs],
        "count": len(runs),
    }


@router.get("/issues/pending", status_code=status.HTTP_200_OK)
async def get_pending_issues(
    tenant_id: Optional[str] = Query(None),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get pending (unresolved) reconciliation issues.

    **Authentication**: Required (API key)

    Args:
        tenant_id: Optional filter by tenant (default: current tenant)

    Returns:
        List of pending issues

    Raises:
        401: Unauthorized

    Example:
        GET /reconciliation/issues/pending
        Headers:
          X-API-Key: tenant-id
    """
    service = ReconciliationService(db)

    # Use specific tenant or current tenant
    filter_tenant = tenant_id or current_tenant.id
    issues = service.get_pending_issues(tenant_id=filter_tenant)

    return {
        "issues": [ReconciliationIssueResponse.model_validate(i) for i in issues],
        "count": len(issues),
    }


@router.post("/issues/{issue_id}/resolve", status_code=status.HTTP_200_OK)
async def resolve_issue(
    issue_id: str,
    resolution_action: str = Query(..., description="What was done to resolve it"),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Mark reconciliation issue as resolved.

    **Authentication**: Required (API key)

    Args:
        issue_id: Issue ID
        resolution_action: Description of resolution

    Returns:
        Updated issue

    Raises:
        401: Unauthorized
        404: Issue not found

    Example:
        POST /reconciliation/issues/issue_123/resolve?resolution_action=Manual%20sync%20completed
        Headers:
          X-API-Key: tenant-id
    """
    service = ReconciliationService(db)

    try:
        issue = service.resolve_issue(issue_id, resolution_action)
        return ReconciliationIssueResponse.model_validate(issue)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/summary", status_code=status.HTTP_200_OK)
async def get_reconciliation_summary(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get reconciliation status summary.

    **Authentication**: Required (API key)

    Shows total runs, issues found/resolved, and pending items.

    Returns:
        Reconciliation summary

    Raises:
        401: Unauthorized

    Example:
        GET /reconciliation/summary
        Headers:
          X-API-Key: tenant-id
        Response:
          {
            "total_runs": 5,
            "last_run_date": "2026-08-19T12:00:00",
            "last_successful_run": "2026-08-19T11:00:00",
            "total_issues_found": 3,
            "total_issues_resolved": 2,
            "total_pending_issues": 1
          }
    """
    service = ReconciliationService(db)
    summary = service.get_reconciliation_summary()

    return {
        "total_runs": summary["total_runs"],
        "last_run_date": summary["last_run_date"],
        "last_successful_run": summary["last_successful_run"],
        "total_issues_found": summary["total_issues_found"],
        "total_issues_resolved": summary["total_issues_resolved"],
        "total_pending_issues": summary["total_pending_issues"],
        "recent_issues": [
            ReconciliationIssueResponse.model_validate(i) 
            for i in summary["most_recent_issues"]
        ],
    }
