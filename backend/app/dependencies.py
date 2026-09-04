"""Dependency injection for authentication and tenant context."""

from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Tenant


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
        api_key = authorization[7:]

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
