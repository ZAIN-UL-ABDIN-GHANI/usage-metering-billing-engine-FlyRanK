"""Tenant service - business logic for tenant operations."""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Tenant, Plan
from app.repositories.tenant_repository import TenantRepository
from app.schemas import TenantCreate, TenantUpdate, TenantResponse


class TenantService:
    """Business logic for tenant operations."""

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.repo = TenantRepository(db)

    def create_tenant(self, tenant_create: TenantCreate) -> TenantResponse:
        """
        Create a new tenant with validation.

        Args:
            tenant_create: Tenant creation schema

        Returns:
            TenantResponse with created tenant data

        Raises:
            ValueError: If email already exists or plan doesn't exist
        """
        # Check if email already exists
        if self.repo.exists_by_email(tenant_create.email):
            raise ValueError(f"Email {tenant_create.email} already exists")

        # Verify plan exists
        plan = self.db.query(Plan).filter_by(id="free").first()
        if not plan:
            raise ValueError("Default 'free' plan does not exist")

        # Create tenant
        tenant = self.repo.create(
            name=tenant_create.name,
            email=tenant_create.email,
            plan_id="free",  # Always start with free plan
            status="active",
        )

        return TenantResponse.from_orm(tenant)

    def get_tenant(self, tenant_id: str) -> Optional[TenantResponse]:
        """
        Get tenant by ID.

        Args:
            tenant_id: Tenant ID

        Returns:
            TenantResponse or None if not found
        """
        tenant = self.repo.get_by_id(tenant_id)
        if not tenant:
            return None
        return TenantResponse.from_orm(tenant)

    def get_tenant_by_email(self, email: str) -> Optional[TenantResponse]:
        """
        Get tenant by email.

        Args:
            email: Tenant email

        Returns:
            TenantResponse or None if not found
        """
        tenant = self.repo.get_by_email(email)
        if not tenant:
            return None
        return TenantResponse.from_orm(tenant)

    def get_all_tenants(self, limit: int = 100, offset: int = 0) -> List[TenantResponse]:
        """
        Get all tenants with pagination.

        Args:
            limit: Max number of results
            offset: Number of results to skip

        Returns:
            List of TenantResponse objects
        """
        tenants = self.repo.get_all(limit=limit, offset=offset)
        return [TenantResponse.from_orm(t) for t in tenants]

    def update_tenant(
        self,
        tenant_id: str,
        tenant_update: TenantUpdate,
    ) -> Optional[TenantResponse]:
        """
        Update a tenant with validation.

        Args:
            tenant_id: Tenant ID
            tenant_update: Tenant update schema

        Returns:
            Updated TenantResponse or None if not found

        Raises:
            ValueError: If email already exists for another tenant
        """
        tenant = self.repo.get_by_id(tenant_id)
        if not tenant:
            return None

        # Check email uniqueness if changing email
        if tenant_update.email and tenant_update.email != tenant.email:
            if self.repo.exists_by_email(tenant_update.email):
                raise ValueError(f"Email {tenant_update.email} already exists")

        # Verify plan exists if changing plan
        if tenant_update.status and tenant_update.status not in ["active", "suspended", "deleted"]:
            raise ValueError(f"Invalid status: {tenant_update.status}")

        # Update tenant
        updated_tenant = self.repo.update(
            tenant_id,
            name=tenant_update.name,
            email=tenant_update.email,
            status=tenant_update.status,
        )

        if not updated_tenant:
            return None

        return TenantResponse.from_orm(updated_tenant)

    def delete_tenant(self, tenant_id: str) -> bool:
        """
        Delete a tenant (soft delete).

        Args:
            tenant_id: Tenant ID

        Returns:
            True if deleted, False if not found
        """
        return self.repo.delete(tenant_id)

    def get_tenant_plan(self, tenant_id: str) -> Optional[dict]:
        """
        Get the plan details for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Dict with plan details or None if not found
        """
        tenant = self.repo.get_by_id(tenant_id)
        if not tenant:
            return None

        plan = self.db.query(Plan).filter_by(id=tenant.plan_id).first()
        if not plan:
            return None

        return {
            "id": plan.id,
            "name": plan.name,
            "api_calls_limit": plan.api_calls_limit,
            "ai_tokens_limit": plan.ai_tokens_limit,
            "monthly_cost_cents": plan.monthly_cost_cents,
        }

    def tenant_has_active_subscription(self, tenant_id: str) -> bool:
        """
        Check if tenant has an active subscription.

        Args:
            tenant_id: Tenant ID

        Returns:
            True if tenant has active subscription, False otherwise
        """
        from app.models import Subscription

        subscription = (
            self.db.query(Subscription)
            .filter_by(tenant_id=tenant_id, status="active")
            .first()
        )
        return subscription is not None

    def get_active_tenants_count(self) -> int:
        """
        Get count of active tenants.

        Returns:
            Number of active tenants
        """
        from sqlalchemy import func

        return self.db.query(func.count(Tenant.id)).filter_by(status="active").scalar()

    def get_tenants_by_plan(self, plan_id: str) -> List[TenantResponse]:
        """
        Get all tenants on a specific plan.

        Args:
            plan_id: Plan ID

        Returns:
            List of TenantResponse objects on plan
        """
        tenants = self.db.query(Tenant).filter_by(plan_id=plan_id).all()
        return [TenantResponse.from_orm(t) for t in tenants]
