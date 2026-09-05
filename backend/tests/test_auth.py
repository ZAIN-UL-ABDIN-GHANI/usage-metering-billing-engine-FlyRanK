"""Tests for dashboard authentication."""

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.config import settings
from app.models import Plan, Tenant, User
from app.utils.security import hash_password


def add_active_user(db: Session) -> None:
    db.add(Tenant(id="tenant-auth", name="Auth Tenant", email="auth@example.com"))
    db.add(
        User(
            id="user-auth",
            tenant_id="tenant-auth",
            email="auth@example.com",
            hashed_password="unused-for-demo-login",
            is_active=True,
        )
    )
    db.commit()


def test_development_demo_credentials_login(
    client: TestClient, db: Session, monkeypatch
):
    add_active_user(db)
    monkeypatch.setattr(settings, "app_env", "DEVELOPMENT")

    response = client.post(
        "/api/auth/login",
        json={"email": "demo@example.com", "password": "Demo123!"},
    )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-auth"


def test_demo_credentials_rejected_outside_development(
    client: TestClient, db: Session, monkeypatch
):
    add_active_user(db)
    monkeypatch.setattr(settings, "app_env", "PRODUCTION")

    response = client.post(
        "/api/auth/login",
        json={"email": "demo@example.com", "password": "Demo123!"},
    )

    assert response.status_code == 401


def test_seeded_credentials_login(client: TestClient, db: Session, monkeypatch):
    db.add(Tenant(id="tenant-seeded", name="Seeded Tenant", email="tenant1@example.com"))
    db.add(
        User(
            id="user-seeded",
            tenant_id="tenant-seeded",
            email="tenant1@example.com",
            hashed_password=hash_password("password123"),
            is_active=True,
        )
    )
    db.commit()
    monkeypatch.setattr(settings, "app_env", "PRODUCTION")

    response = client.post(
        "/api/auth/login",
        json={"email": "tenant1@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-seeded"


def test_usage_accepts_login_token(client: TestClient, db: Session, monkeypatch):
    db.add(Plan(id="free", name="Free", api_calls_limit=1000, ai_tokens_limit=100000))
    db.add(Tenant(id="tenant-usage", name="Usage Tenant", email="usage@example.com"))
    db.add(
        User(
            id="user-usage",
            tenant_id="tenant-usage",
            email="usage@example.com",
            hashed_password=hash_password("usage-password"),
            is_active=True,
        )
    )
    db.commit()
    monkeypatch.setattr(settings, "app_env", "PRODUCTION")

    login_response = client.post(
        "/api/auth/login",
        json={"email": "usage@example.com", "password": "usage-password"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/usage",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200