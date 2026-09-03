"""Tenant routes - API endpoints for tenant management."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant
from app.schemas import TenantCreate, TenantUpdate, TenantResponse
from app.services.tenant_service import TenantService

router = APIRouter(
    prefix="/tenants",
    tags=["tenants"],
)


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_create: TenantCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new tenant.

    **Authentication**: Not required (public endpoint for signup)

    Args:
        tenant_create: Tenant creation data

    Returns:
        Created tenant details

    Raises:
        400: Email already exists
    """
    service = TenantService(db)

    try:
        return service.create_tenant(tenant_create)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get tenant details by ID.

    **Authentication**: Required (API key)

    **Tenant Isolation**: Tenants can only view their own details.

    Args:
        tenant_id: Tenant ID to retrieve
        current_tenant: Authenticated tenant from API key

    Returns:
        Tenant details

    Raises:
        401: Unauthorized (missing/invalid API key)
        403: Forbidden (tenant trying to access another tenant's data)
        404: Tenant not found
    """
    # Enforce tenant isolation
    if tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other tenant's data",
        )

    service = TenantService(db)
    tenant = service.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return tenant


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    tenant_update: TenantUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Update tenant details.

    **Authentication**: Required (API key)

    **Tenant Isolation**: Tenants can only update their own details.

    Args:
        tenant_id: Tenant ID to update
        tenant_update: Updated tenant data
        current_tenant: Authenticated tenant from API key

    Returns:
        Updated tenant details

    Raises:
        401: Unauthorized (missing/invalid API key)
        403: Forbidden (tenant trying to update another tenant's data)
        404: Tenant not found
        400: Invalid data (e.g., duplicate email)
    """
    # Enforce tenant isolation
    if tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update other tenant's data",
        )

    service = TenantService(db)

    try:
        tenant = service.update_tenant(tenant_id, tenant_update)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )
        return tenant
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=List[TenantResponse])
async def list_tenants(
    limit: int = 100,
    offset: int = 0,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    List all tenants (admin only).

    **Authentication**: Required (API key)

    **Tenant Isolation**: Returns only current tenant's data.

    Args:
        limit: Maximum number of results
        offset: Number of results to skip
        current_tenant: Authenticated tenant from API key

    Returns:
        List of tenant details

    Raises:
        401: Unauthorized (missing/invalid API key)
    """
    # For now, return only current tenant
    # In production, implement admin role check
    service = TenantService(db)
    tenant = service.get_tenant(current_tenant.id)

    if not tenant:
        return []

    return [tenant]


@router.get("/{tenant_id}/plan")
async def get_tenant_plan(
    tenant_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get tenant's current plan details.

    **Authentication**: Required (API key)

    **Tenant Isolation**: Tenants can only view their own plan.

    Args:
        tenant_id: Tenant ID
        current_tenant: Authenticated tenant from API key

    Returns:
        Plan details with limits and pricing

    Raises:
        401: Unauthorized (missing/invalid API key)
        403: Forbidden (tenant trying to access another tenant's plan)
        404: Tenant or plan not found
    """
    # Enforce tenant isolation
    if tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other tenant's plan",
        )

    service = TenantService(db)
    plan = service.get_tenant_plan(tenant_id)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant or plan not found",
        )

    return plan


@router.get("/{tenant_id}/status")
async def get_tenant_status(
    tenant_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get tenant account status.

    **Authentication**: Required (API key)

    **Tenant Isolation**: Tenants can only view their own status.

    Args:
        tenant_id: Tenant ID
        current_tenant: Authenticated tenant from API key

    Returns:
        Status details (active/suspended/deleted)

    Raises:
        401: Unauthorized (missing/invalid API key)
        403: Forbidden (tenant trying to access another tenant's status)
        404: Tenant not found
    """
    # Enforce tenant isolation
    if tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other tenant's status",
        )

    service = TenantService(db)
    tenant = service.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return {
        "tenant_id": tenant.id,
        "status": tenant.status,
        "name": tenant.name,
        "email": tenant.email,
        "plan_id": tenant.plan_id,
    }
