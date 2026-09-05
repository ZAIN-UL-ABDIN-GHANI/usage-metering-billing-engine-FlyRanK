"""Dependency injection for authentication and tenant context."""

from fastapi import Depends, HTTPException, status, Header
import jwt
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Tenant, User
from app.config import settings


async def get_tenant_from_api_key(
    x_api_key: Optional[str] = Header(None),
    x_tenant_id: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Tenant:
    """
    Extract and verify API key from headers, return authenticated tenant.
    
    Args:
        x_api_key: API key from X-API-Key header
        db: Database session
        
    Returns:
        Tenant object if API key is valid
        
    Raises:
        HTTPException 401: If API key missing or invalid
    """
    api_key = x_api_key or x_tenant_id
    if not api_key and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
        try:
            claims = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            api_key = claims.get("tenant_id")
        except (jwt.InvalidTokenError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # In production, API keys would be hashed/stored in database
    # For now, we use tenant ID as API key (demo only)
    # In Module 5+, implement proper API key management
    
    tenant = db.query(Tenant).filter_by(id=api_key).first()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if tenant.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant account is {tenant.status}",
        )
    
    return tenant


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Decode the bearer token and return its active user."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]
    try:
        claims = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        user_id = claims.get("sub")
    except (jwt.InvalidTokenError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter_by(id=user_id, is_active=True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_tenant(
    tenant: Tenant = Depends(get_tenant_from_api_key),
) -> Tenant:
    """
    Get current authenticated tenant.
    
    This is a convenience dependency that extracts the tenant
    from the API key verification step.
    
    Args:
        tenant: Authenticated tenant from get_tenant_from_api_key
        
    Returns:
        Tenant object
    """
    return tenant
