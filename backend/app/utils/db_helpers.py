"""Database helper functions."""

from datetime import datetime, timedelta
from typing import Type, TypeVar, Optional, Any
import uuid

from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")


def generate_id() -> str:
    """Generate a UUID string ID."""
    return str(uuid.uuid4())


def get_current_billing_period() -> str:
    """Get current billing period in YYYY-MM format."""
    now = datetime.utcnow()
    return now.strftime("%Y-%m")


def get_next_billing_date(current_date: datetime = None) -> datetime:
    """Get the first day of next month."""
    if current_date is None:
        current_date = datetime.utcnow()
    
    # First day of next month
    if current_date.month == 12:
        return current_date.replace(year=current_date.year + 1, month=1, day=1)
    else:
        return current_date.replace(month=current_date.month + 1, day=1)


def get_billing_period_start(period: str) -> datetime:
    """Get the start datetime of a billing period (YYYY-MM)."""
    year, month = period.split("-")
    return datetime(int(year), int(month), 1, 0, 0, 0)


def get_billing_period_end(period: str) -> datetime:
    """Get the end datetime of a billing period (YYYY-MM)."""
    start = get_billing_period_start(period)
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1) - timedelta(seconds=1)
    else:
        return start.replace(month=start.month + 1) - timedelta(seconds=1)


def get_or_create(
    db: Session,
    model: Type[ModelType],
    defaults: dict = None,
    **filters: Any,
) -> tuple[ModelType, bool]:
    """Get or create a record.
    
    Returns:
        (instance, created) - instance is the object, created is bool
    """
    instance = db.query(model).filter_by(**filters).first()
    
    if instance:
        return instance, False
    
    defaults = defaults or {}
    params = {**filters, **defaults}
    instance = model(**params)
    db.add(instance)
    db.commit()
    db.refresh(instance)
    
    return instance, True


def bulk_create(
    db: Session,
    model: Type[ModelType],
    objects: list[dict],
) -> list[ModelType]:
    """Create multiple records at once."""
    instances = [model(**obj) for obj in objects]
    db.bulk_save_objects(instances)
    db.commit()
    return instances
