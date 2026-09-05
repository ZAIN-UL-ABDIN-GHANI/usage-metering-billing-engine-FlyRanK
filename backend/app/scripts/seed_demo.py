"""Seed database with demo data for testing."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base

# Force import of all model definitions to register relationships (Alert, User, Tenant, etc.)
import app.models
from app.models import Tenant, Plan, Subscription, User
from app.config import settings
from app.utils.security import hash_password


def seed_database():
    """Create demo data for testing."""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Create all registered tables
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created")

        # Check if plans already exist to avoid duplicate key errors
        if not session.query(Plan).filter_by(id="free").first():
            free_plan = Plan(
                id="free",
                name="Free",
                api_calls_limit=1000,
                ai_tokens_limit=100000,
                monthly_cost_cents=0,
            )
            pro_plan = Plan(
                id="pro",
                name="Pro",
                api_calls_limit=100000,
                ai_tokens_limit=10000000,
                monthly_cost_cents=2999,
            )
            session.add_all([free_plan, pro_plan])
            session.commit()
            print("✅ Plans created")

        # Check if tenants already exist
        tenant1 = session.query(Tenant).filter_by(id="tenant-1").first()
        if not tenant1:
            tenant1 = Tenant(id="tenant-1", name="Demo Company", email="tenant1@example.com")
            tenant2 = Tenant(id="tenant-2", name="Another Org", email="tenant2@example.com")
            session.add_all([tenant1, tenant2])
            session.commit()
            print("✅ Tenants created")

        # Check if users already exist
        if not session.query(User).filter_by(email="tenant1@example.com").first():
            hashed_pwd = hash_password("password123")

            user1 = User(
                id="user-1",
                tenant_id="tenant-1",
                email="tenant1@example.com",
                hashed_password=hashed_pwd,
                is_active=True,
            )
            user2 = User(
                id="user-2",
                tenant_id="tenant-2",
                email="tenant2@example.com",
                hashed_password=hashed_pwd,
                is_active=True,
            )
            session.add_all([user1, user2])
            session.commit()
            print("✅ Users created")

        # Check if subscriptions already exist
        if not session.query(Subscription).filter_by(id="sub-1").first():
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
        print("Credentials:\n  Email: tenant1@example.com\n  Password: password123")

    except Exception as e:
        session.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()