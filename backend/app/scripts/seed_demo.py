"""Seed database with demo data for testing."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Tenant, Plan, Subscription, User
from app.config import settings


def seed_database():
    """Create demo data for testing."""
    # Create engine and session
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Create tables
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created")

        # Create plans
        free_plan = Plan(
            id="free",
            name="Free",
            description="Free plan with basic limits",
            api_calls_limit=1000,
            ai_tokens_limit=100000,
            price_cents=0,
        )
        
        pro_plan = Plan(
            id="pro",
            name="Pro",
            description="Professional plan with higher limits",
            api_calls_limit=100000,
            ai_tokens_limit=10000000,
            price_cents=2999,  # $29.99/month
        )
        
        session.add_all([free_plan, pro_plan])
        session.commit()
        print("✅ Plans created")

        # Create demo tenants
        tenant1 = Tenant(
            id="tenant-1",
            name="Demo Company",
            email="tenant1@example.com",
        )
        
        tenant2 = Tenant(
            id="tenant-2",
            name="Another Org",
            email="tenant2@example.com",
        )
        
        session.add_all([tenant1, tenant2])
        session.commit()
        print("✅ Tenants created")

        # Create demo users (for login)
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        user1 = User(
            id="user-1",
            tenant_id="tenant-1",
            email="tenant1@example.com",
            hashed_password=pwd_context.hash("password123"),
            is_active=True,
        )
        
        user2 = User(
            id="user-2",
            tenant_id="tenant-2",
            email="tenant2@example.com",
            hashed_password=pwd_context.hash("password123"),
            is_active=True,
        )
        
        session.add_all([user1, user2])
        session.commit()
        print("✅ Users created")

        # Create subscriptions
        sub1 = Subscription(
            id="sub-1",
            tenant_id="tenant-1",
            plan_id="free",
            status="active",
            stripe_subscription_id="sub_demo_1",
        )
        
        sub2 = Subscription(
            id="sub-2",
            tenant_id="tenant-2",
            plan_id="free",
            status="active",
            stripe_subscription_id="sub_demo_2",
        )
        
        session.add_all([sub1, sub2])
        session.commit()
        print("✅ Subscriptions created")

        print("\n✅ Demo data seeded successfully!")
        print("\nDemo Credentials:")
        print("  Email: tenant1@example.com")
        print("  Password: password123")
        print("\n  Email: tenant2@example.com")
        print("  Password: password123")

    except Exception as e:
        session.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
