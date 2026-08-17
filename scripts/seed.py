"""Seed script for initial data (plans, demo tenants)."""

import sys
from datetime import datetime, timedelta

sys.path.insert(0, "/app")

from app.models import Plan, Tenant, Subscription
from app.database import SessionLocal, engine, Base
from app.utils.db_helpers import generate_id

# Ensure tables exist
Base.metadata.create_all(bind=engine)


def seed_plans(db):
    """Create default plans."""
    plans = [
        {
            "id": "free",
            "name": "Free",
            "stripe_price_id": None,
            "monthly_cost_cents": 0,
            "api_calls_limit": 1000,
            "ai_tokens_limit": 100000,
        },
        {
            "id": "pro",
            "name": "Pro",
            "stripe_price_id": "price_pro_test",
            "monthly_cost_cents": 9900,  # $99/month
            "api_calls_limit": 100000,
            "ai_tokens_limit": 10000000,
        },
    ]

    for plan_data in plans:
        existing = db.query(Plan).filter_by(id=plan_data["id"]).first()
        if not existing:
            plan = Plan(**plan_data, created_at=datetime.utcnow())
            db.add(plan)
            print(f"✅ Created plan: {plan.name}")
        else:
            print(f"⏭️  Plan already exists: {plan.name}")

    db.commit()


def seed_demo_tenant(db):
    """Create a demo tenant with Free plan subscription."""
    # Check if demo tenant exists
    existing = db.query(Tenant).filter_by(email="demo@example.com").first()
    if existing:
        print(f"⏭️  Demo tenant already exists: {existing.name}")
        return

    # Create demo tenant
    tenant_id = generate_id()
    tenant = Tenant(
        id=tenant_id,
        name="Demo Company",
        email="demo@example.com",
        plan_id="free",
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(tenant)
    db.flush()  # Flush to get tenant in session

    # Create subscription
    now = datetime.utcnow()
    month_end = now.replace(day=1) + timedelta(days=32)
    month_end = month_end.replace(day=1) - timedelta(seconds=1)

    subscription = Subscription(
        id=generate_id(),
        tenant_id=tenant_id,
        stripe_subscription_id=None,
        plan_id="free",
        status="active",
        current_period_start=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        current_period_end=month_end,
        created_at=now,
        updated_at=now,
    )
    db.add(subscription)
    db.commit()

    print(f"✅ Created demo tenant: {tenant.name} (ID: {tenant.id})")
    print(f"   Email: {tenant.email}")
    print(f"   Plan: Free")
    print(f"   Subscription ID: {subscription.id}")


def main():
    """Run seeding."""
    db = SessionLocal()

    try:
        print("\n🌱 Seeding database...\n")
        
        seed_plans(db)
        print()
        seed_demo_tenant(db)

        print("\n✅ Database seeding complete!\n")

    except Exception as e:
        print(f"\n❌ Error during seeding: {e}\n")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
