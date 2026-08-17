"""Health check and basic API endpoint tests."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_endpoint(self, client: TestClient):
        """Test /health endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app" in data
        assert "environment" in data

    def test_ready_endpoint(self, client: TestClient):
        """Test /ready endpoint."""
        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "app" in data

    def test_root_endpoint(self, client: TestClient):
        """Test / root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"


class TestAPIDocumentation:
    """Test API documentation endpoints."""

    def test_swagger_docs_available(self, client: TestClient):
        """Test that Swagger UI docs are available."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema_available(self, client: TestClient):
        """Test that OpenAPI schema is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
