"""Tenant repository for database operations."""

from typing import List, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Tenant, Plan
from app.utils.db_helpers import generate_id


class TenantRepository:
    """Data access layer for tenant operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def create(
        self,
        name: str,
        email: str,
        plan_id: str = "free",
        status: str = "active",
    ) -> Tenant:
        """
        Create a new tenant.

        Args:
            name: Tenant name
            email: Tenant email (unique)
            plan_id: Plan ID (default: "free")
            status: Tenant status (default: "active")

        Returns:
            Created Tenant object

        Raises:
            IntegrityError: If email already exists
        """
        tenant = Tenant(
            id=generate_id(),
            name=name,
            email=email,
            plan_id=plan_id,
            status=status,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def get_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """
        Get tenant by ID.

        Args:
            tenant_id: Tenant ID

        Returns:
            Tenant object or None if not found
        """
        return self.db.query(Tenant).filter_by(id=tenant_id).first()

    def get_by_email(self, email: str) -> Optional[Tenant]:
        """
        Get tenant by email.

        Args:
            email: Tenant email

        Returns:
            Tenant object or None if not found
        """
        return self.db.query(Tenant).filter_by(email=email).first()

    def get_by_stripe_customer_id(self, stripe_customer_id: str) -> Optional[Tenant]:
        """
        Get tenant by Stripe customer ID.

        Args:
            stripe_customer_id: Stripe customer ID

        Returns:
            Tenant object or None if not found
        """
        return (
            self.db.query(Tenant)
            .filter_by(stripe_customer_id=stripe_customer_id)
            .first()
        )

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Tenant]:
        """
        Get all tenants with pagination.

        Args:
            limit: Max number of results
            offset: Number of results to skip

        Returns:
            List of Tenant objects
        """
        return (
            self.db.query(Tenant)
            .order_by(Tenant.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def update(
        self,
        tenant_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        plan_id: Optional[str] = None,
        status: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
    ) -> Optional[Tenant]:
        """
        Update a tenant.

        Args:
            tenant_id: Tenant ID
            name: New tenant name
            email: New email
            plan_id: New plan ID
            status: New status
            stripe_customer_id: Stripe customer ID

        Returns:
            Updated Tenant object or None if not found
        """
        tenant = self.get_by_id(tenant_id)
        if not tenant:
            return None

        if name is not None:
            tenant.name = name
        if email is not None:
            tenant.email = email
        if plan_id is not None:
            tenant.plan_id = plan_id
        if status is not None:
            tenant.status = status
        if stripe_customer_id is not None:
            tenant.stripe_customer_id = stripe_customer_id

        tenant.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def delete(self, tenant_id: str) -> bool:
        """
        Delete a tenant (soft delete via status).

        Args:
            tenant_id: Tenant ID

        Returns:
            True if deleted, False if not found
        """
        tenant = self.get_by_id(tenant_id)
        if not tenant:
            return False

        # Soft delete: mark as deleted
        tenant.status = "deleted"
        tenant.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def get_active_tenants(self, limit: int = 100) -> List[Tenant]:
        """
        Get all active tenants.

        Args:
            limit: Max number of results

        Returns:
            List of active Tenant objects
        """
        return (
            self.db.query(Tenant)
            .filter_by(status="active")
            .order_by(Tenant.created_at.desc())
            .limit(limit)
            .all()
        )

    def count_by_plan(self, plan_id: str) -> int:
        """
        Count tenants on a specific plan.

        Args:
            plan_id: Plan ID

        Returns:
            Number of tenants on plan
        """
        return self.db.query(Tenant).filter_by(plan_id=plan_id).count()

    def exists_by_email(self, email: str) -> bool:
        """
        Check if tenant with email exists.

        Args:
            email: Email to check

        Returns:
            True if exists, False otherwise
        """
        return self.db.query(Tenant).filter_by(email=email).first() is not None
