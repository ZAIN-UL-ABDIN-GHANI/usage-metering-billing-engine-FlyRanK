"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_all_tables
from app.schemas import ErrorResponse, ValidationError

# ✅ FIX: Explicitly import models so Base.metadata populates before create_all_tables()
import app.models  # noqa: F401

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting FlyRank Metering & Billing Engine")
    create_all_tables()
    logger.info("Database tables initialized")
    yield
    # Shutdown
    logger.info("Shutting down FlyRank Metering & Billing Engine")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Production-ready usage metering and billing engine with Stripe integration",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Exception Handlers
# ============================================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "status": 422,
            "message": "Validation error",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": 500,
            "message": "Internal server error",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )


# ============================================================================
# Health Check Endpoint
# ============================================================================


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env,
    }


@app.get("/ready", tags=["health"])
async def readiness_check():
    """Readiness check endpoint."""
    return {
        "status": "ready",
        "app": settings.app_name,
    }


# ============================================================================
# Root Endpoint
# ============================================================================


@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


# Include Routers
from app.routes import (  # noqa: E402
    alerts,
    invoices,
    overages,
    plan_changes,
    reconciliation,
    reporting,
    stripe,
    tenants,
    usage,
)

for r in [
    alerts.router,
    invoices.router,
    overages.router,
    plan_changes.router,
    reconciliation.router,
    reporting.router,
    stripe.router,
    tenants.router,
    usage.router,
    usage.generate_router,
    stripe.webhook_router,
]:
    app.include_router(r, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers,
    )