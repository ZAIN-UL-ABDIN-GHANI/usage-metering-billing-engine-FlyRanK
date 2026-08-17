"""Pytest configuration and shared fixtures."""

import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Use test database
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite:///./test.db"
)

# Create test engine
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {},
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create test database tables before running tests."""
    from app.models import Base
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Session:
    """Provide a database session for each test."""
    from app.models import Base
    
    # Create tables for this test
    Base.metadata.create_all(bind=engine)
    
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> TestClient:
    """Provide a test client with database session."""
    from app.main import app
    from app.database import get_db

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def create_plan(db: Session):
    """Factory to create plans."""
    from app.models import Plan

    def _create_plan(
        plan_id: str = "test-plan",
        name: str = "Test Plan",
        api_calls_limit: int = 1000,
        ai_tokens_limit: int = 100000,
        monthly_cost_cents: int = 0,
    ) -> Plan:
        plan = Plan(
            id=plan_id,
            name=name,
            api_calls_limit=api_calls_limit,
            ai_tokens_limit=ai_tokens_limit,
            monthly_cost_cents=monthly_cost_cents,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    return _create_plan


@pytest.fixture
def create_tenant(db: Session, create_plan):
    """Factory to create tenants."""
    from app.models import Tenant
    from app.utils.db_helpers import generate_id

    # Ensure default plan exists
    create_plan(plan_id="free", name="Free")

    def _create_tenant(
        tenant_id: str = None,
        name: str = "Test Tenant",
        email: str = "test@example.com",
        plan_id: str = "free",
        status: str = "active",
    ) -> Tenant:
        if tenant_id is None:
            tenant_id = generate_id()

        tenant = Tenant(
            id=tenant_id,
            name=name,
            email=email,
            plan_id=plan_id,
            status=status,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        return tenant

    return _create_tenant


@pytest.fixture
def create_subscription(db: Session):
    """Factory to create subscriptions."""
    from app.models import Subscription
    from app.utils.db_helpers import generate_id

    def _create_subscription(
        tenant_id: str,
        plan_id: str = "free",
        status: str = "active",
        period_start: datetime = None,
        period_end: datetime = None,
    ) -> Subscription:
        if period_start is None:
            period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        if period_end is None:
            # End of current month
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1)
            period_end = period_end - timedelta(seconds=1)

        subscription = Subscription(
            id=generate_id(),
            tenant_id=tenant_id,
            plan_id=plan_id,
            status=status,
            current_period_start=period_start,
            current_period_end=period_end,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        return subscription

    return _create_subscription


@pytest.fixture
def create_usage_event(db: Session):
    """Factory to create usage events."""
    from app.models import UsageEvent
    from app.utils.db_helpers import generate_id, get_current_billing_period

    def _create_usage_event(
        tenant_id: str,
        usage_type: str = "api_calls",
        quantity: int = 100,
        idempotency_key: str = None,
        billing_period: str = None,
        cost_cents: int = None,
    ) -> UsageEvent:
        if idempotency_key is None:
            idempotency_key = generate_id()
        
        if billing_period is None:
            billing_period = get_current_billing_period()

        event = UsageEvent(
            id=generate_id(),
            tenant_id=tenant_id,
            usage_type=usage_type,
            quantity=quantity,
            idempotency_key=idempotency_key,
            cost_cents=cost_cents,
            billing_period=billing_period,
            created_at=datetime.utcnow(),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    return _create_usage_event
