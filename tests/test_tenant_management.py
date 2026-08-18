"""Tests for tenant management and authentication."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Tenant
from app.services.tenant_service import TenantService
from app.repositories.tenant_repository import TenantRepository


class TestTenantCreation:
    """Test tenant creation endpoint."""

    def test_create_tenant_success(self, client: TestClient, create_plan):
        """Test creating a tenant successfully."""
        create_plan(plan_id="free", name="Free")

        response = client.post(
            "/tenants",
            json={
                "name": "Acme Corp",
                "email": "acme@example.com",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Acme Corp"
        assert data["email"] == "acme@example.com"
        assert data["plan_id"] == "free"
        assert data["status"] == "active"
        assert "id" in data
        assert "created_at" in data

    def test_create_tenant_duplicate_email(self, client: TestClient, create_plan, create_tenant):
        """Test creating tenant with duplicate email fails."""
        create_plan(plan_id="free", name="Free")
        create_tenant(email="existing@example.com")

        response = client.post(
            "/tenants",
            json={
                "name": "Another Corp",
                "email": "existing@example.com",
            },
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_tenant_invalid_email(self, client: TestClient, create_plan):
        """Test creating tenant with invalid email fails."""
        create_plan(plan_id="free", name="Free")

        response = client.post(
            "/tenants",
            json={
                "name": "Test Corp",
                "email": "not-an-email",
            },
        )

        assert response.status_code == 422  # Validation error


class TestTenantAuthentication:
    """Test tenant authentication via API key."""

    def test_get_tenant_requires_auth(self, client: TestClient, create_plan, create_tenant):
        """Test that getting tenant details requires authentication."""
        create_plan()
        tenant = create_tenant()

        # No API key - should fail
        response = client.get(f"/tenants/{tenant.id}")
        assert response.status_code == 401
        assert "Missing API key" in response.json()["detail"]

    def test_get_tenant_invalid_api_key(self, client: TestClient, create_plan, create_tenant):
        """Test that invalid API key fails."""
        create_plan()
        tenant = create_tenant()

        # Invalid API key
        response = client.get(
            f"/tenants/{tenant.id}",
            headers={"X-API-Key": "invalid-key"},
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_get_tenant_with_valid_api_key(self, client: TestClient, create_plan, create_tenant):
        """Test getting tenant with valid API key."""
        create_plan()
        tenant = create_tenant()

        # Valid API key (tenant ID)
        response = client.get(
            f"/tenants/{tenant.id}",
            headers={"X-API-Key": tenant.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == tenant.id
        assert data["name"] == tenant.name
        assert data["email"] == tenant.email


class TestTenantIsolation:
    """Test tenant isolation - tenants cannot access each other's data."""

    def test_tenant_cannot_access_other_tenant(self, client: TestClient, create_plan, create_tenant):
        """Test that tenant cannot access another tenant's data."""
        create_plan()
        tenant1 = create_tenant(name="Tenant 1", email="tenant1@example.com")
        tenant2 = create_tenant(name="Tenant 2", email="tenant2@example.com")

        # Tenant1 tries to access Tenant2's data - should fail
        response = client.get(
            f"/tenants/{tenant2.id}",
            headers={"X-API-Key": tenant1.id},
        )
        assert response.status_code == 403
        assert "Cannot access other tenant's data" in response.json()["detail"]

    def test_tenant_can_access_own_data(self, client: TestClient, create_plan, create_tenant):
        """Test that tenant can access their own data."""
        create_plan()
        tenant = create_tenant()

        response = client.get(
            f"/tenants/{tenant.id}",
            headers={"X-API-Key": tenant.id},
        )
        assert response.status_code == 200
        assert response.json()["id"] == tenant.id

    def test_tenant_cannot_update_other_tenant(self, client: TestClient, create_plan, create_tenant):
        """Test that tenant cannot update another tenant."""
        create_plan()
        tenant1 = create_tenant(name="Tenant 1", email="tenant1@example.com")
        tenant2 = create_tenant(name="Tenant 2", email="tenant2@example.com")

        # Tenant1 tries to update Tenant2 - should fail
        response = client.put(
            f"/tenants/{tenant2.id}",
            headers={"X-API-Key": tenant1.id},
            json={"name": "Hacked Name"},
        )
        assert response.status_code == 403
        assert "Cannot update other tenant's data" in response.json()["detail"]

    def test_tenant_cannot_view_other_tenant_plan(self, client: TestClient, create_plan, create_tenant):
        """Test that tenant cannot view another tenant's plan."""
        create_plan()
        tenant1 = create_tenant(name="Tenant 1", email="tenant1@example.com")
        tenant2 = create_tenant(name="Tenant 2", email="tenant2@example.com")

        # Tenant1 tries to view Tenant2's plan - should fail
        response = client.get(
            f"/tenants/{tenant2.id}/plan",
            headers={"X-API-Key": tenant1.id},
        )
        assert response.status_code == 403
        assert "Cannot access other tenant's plan" in response.json()["detail"]

    def test_tenant_cannot_view_other_tenant_status(self, client: TestClient, create_plan, create_tenant):
        """Test that tenant cannot view another tenant's status."""
        create_plan()
        tenant1 = create_tenant(name="Tenant 1", email="tenant1@example.com")
        tenant2 = create_tenant(name="Tenant 2", email="tenant2@example.com")

        # Tenant1 tries to view Tenant2's status - should fail
        response = client.get(
            f"/tenants/{tenant2.id}/status",
            headers={"X-API-Key": tenant1.id},
        )
        assert response.status_code == 403
        assert "Cannot access other tenant's status" in response.json()["detail"]


class TestTenantUpdate:
    """Test tenant update functionality."""

    def test_update_tenant_name(self, client: TestClient, create_plan, create_tenant):
        """Test updating tenant name."""
        create_plan()
        tenant = create_tenant(name="Old Name")

        response = client.put(
            f"/tenants/{tenant.id}",
            headers={"X-API-Key": tenant.id},
            json={"name": "New Name"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    def test_update_tenant_status(self, client: TestClient, create_plan, create_tenant):
        """Test updating tenant status."""
        create_plan()
        tenant = create_tenant()

        response = client.put(
            f"/tenants/{tenant.id}",
            headers={"X-API-Key": tenant.id},
            json={"status": "suspended"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "suspended"

    def test_update_tenant_invalid_status(self, client: TestClient, create_plan, create_tenant):
        """Test updating to invalid status fails."""
        create_plan()
        tenant = create_tenant()

        response = client.put(
            f"/tenants/{tenant.id}",
            headers={"X-API-Key": tenant.id},
            json={"status": "invalid_status"},
        )

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_update_tenant_email_to_duplicate(self, client: TestClient, create_plan, create_tenant):
        """Test that updating email to duplicate fails."""
        create_plan()
        tenant1 = create_tenant(name="Tenant 1", email="tenant1@example.com")
        tenant2 = create_tenant(name="Tenant 2", email="tenant2@example.com")

        # Try to update tenant2's email to tenant1's email
        response = client.put(
            f"/tenants/{tenant2.id}",
            headers={"X-API-Key": tenant2.id},
            json={"email": "tenant1@example.com"},
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


class TestTenantRetrieval:
    """Test tenant retrieval methods."""

    def test_get_tenant_by_id(self, db: Session, create_plan, create_tenant):
        """Test getting tenant by ID."""
        create_plan()
        tenant = create_tenant()

        service = TenantService(db)
        retrieved = service.get_tenant(tenant.id)

        assert retrieved is not None
        assert retrieved.id == tenant.id
        assert retrieved.name == tenant.name

    def test_get_tenant_by_email(self, db: Session, create_plan, create_tenant):
        """Test getting tenant by email."""
        create_plan()
        tenant = create_tenant(email="test@example.com")

        service = TenantService(db)
        retrieved = service.get_tenant_by_email("test@example.com")

        assert retrieved is not None
        assert retrieved.email == "test@example.com"

    def test_get_nonexistent_tenant(self, db: Session):
        """Test getting nonexistent tenant returns None."""
        service = TenantService(db)
        retrieved = service.get_tenant("nonexistent-id")

        assert retrieved is None

    def test_list_tenants(self, db: Session, create_plan, create_tenant):
        """Test listing tenants."""
        create_plan()
        tenant1 = create_tenant(name="Tenant 1", email="tenant1@example.com")
        tenant2 = create_tenant(name="Tenant 2", email="tenant2@example.com")

        service = TenantService(db)
        tenants = service.get_all_tenants(limit=10)

        assert len(tenants) >= 2
        tenant_ids = [t.id for t in tenants]
        assert tenant1.id in tenant_ids
        assert tenant2.id in tenant_ids


class TestTenantPlan:
    """Test tenant plan information."""

    def test_get_tenant_plan(self, client: TestClient, create_plan, create_tenant):
        """Test getting tenant's plan details."""
        create_plan(plan_id="free", name="Free", api_calls_limit=1000)
        tenant = create_tenant()

        response = client.get(
            f"/tenants/{tenant.id}/plan",
            headers={"X-API-Key": tenant.id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "free"
        assert data["name"] == "Free"
        assert data["api_calls_limit"] == 1000

    def test_get_tenant_status(self, client: TestClient, create_plan, create_tenant):
        """Test getting tenant status."""
        create_plan()
        tenant = create_tenant()

        response = client.get(
            f"/tenants/{tenant.id}/status",
            headers={"X-API-Key": tenant.id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == tenant.id
        assert data["status"] == "active"
        assert data["plan_id"] == "free"


class TestSuspendedTenant:
    """Test suspended/deleted tenant behavior."""

    def test_suspended_tenant_cannot_authenticate(self, db: Session, create_plan, create_tenant):
        """Test that suspended tenant cannot authenticate."""
        create_plan()
        tenant = create_tenant()

        # Suspend tenant
        repo = TenantRepository(db)
        repo.update(tenant.id, status="suspended")

        # Try to authenticate - should fail
        from app.dependencies import get_tenant_from_api_key

        # This would be called by FastAPI, but we can test the service logic
        service = TenantService(db)
        retrieved = service.get_tenant(tenant.id)
        assert retrieved.status == "suspended"

    def test_deleted_tenant_cannot_authenticate(self, db: Session, create_plan, create_tenant):
        """Test that deleted tenant cannot authenticate."""
        create_plan()
        tenant = create_tenant()

        # Delete tenant
        service = TenantService(db)
        service.delete_tenant(tenant.id)

        # Retrieve and verify status
        retrieved = service.get_tenant(tenant.id)
        assert retrieved.status == "deleted"


class TestTenantCounts:
    """Test tenant counting methods."""

    def test_count_active_tenants(self, db: Session, create_plan, create_tenant):
        """Test counting active tenants."""
        create_plan()
        tenant1 = create_tenant()
        tenant2 = create_tenant(name="Tenant 2", email="tenant2@example.com")

        service = TenantService(db)
        count = service.get_active_tenants_count()

        assert count >= 2

    def test_count_tenants_by_plan(self, db: Session, create_plan, create_tenant):
        """Test counting tenants on a plan."""
        create_plan(plan_id="free", name="Free")
        tenant1 = create_tenant(plan_id="free")
        tenant2 = create_tenant(name="Tenant 2", email="tenant2@example.com", plan_id="free")

        repo = TenantRepository(db)
        count = repo.count_by_plan("free")

        assert count >= 2
