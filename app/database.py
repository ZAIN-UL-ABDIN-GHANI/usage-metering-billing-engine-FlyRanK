"""Database initialization and session management."""

from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

load_dotenv(override=True)

from app.config import settings


# Use the DATABASE_URL directly from .env
db_url = settings.database_url


engine = create_engine(
    db_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=settings.debug,
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency injection for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables() -> None:
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)


def drop_all_tables() -> None:
    """Drop all tables from the database."""
    Base.metadata.drop_all(bind=engine)