"""Authentication routes for dashboard users."""

from datetime import datetime, timedelta, timezone
import logging

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.utils.security import verify_password


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "Demo123!"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
async def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    email = str(credentials.email)
    is_demo_login = (
        settings.app_env.upper() == "DEVELOPMENT"
        and email == DEMO_EMAIL
        and credentials.password == DEMO_PASSWORD
    )

    try:
        if is_demo_login:
            user = (
                db.query(User)
                .filter(User.is_active.is_(True))
                .order_by(User.id)
                .first()
            )
        else:
            user = db.query(User).filter_by(email=email).first()
    except SQLAlchemyError:
        logger.exception("Authentication query failed for email %s", email)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )

    if not user or not user.is_active or (
        not is_demo_login
        and not verify_password(credentials.password, user.hashed_password)
    ):
        logger.warning("Login failed: invalid credentials for email %s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    token = jwt.encode(
        {"sub": user.id, "tenant_id": user.tenant_id, "exp": expires_at},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "tenant_id": user.tenant_id,
        "expires_in": settings.access_token_expire_minutes * 60,
    }