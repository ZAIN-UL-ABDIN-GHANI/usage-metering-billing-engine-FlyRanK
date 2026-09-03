"""Invoice routes - API endpoints for invoice management."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant
from app.models_invoice import InvoiceCreate, InvoiceUpdate, InvoiceResponse, InvoiceDetailedResponse, InvoiceListResponse
from app.services.invoice_service import InvoiceService

router = APIRouter(
    prefix="/invoices",
    tags=["invoices"],
)


@router.post("", status_code=status.HTTP_201_CREATED)
async def generate_invoice(
    request: InvoiceCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Generate invoice for a billing period.

    **Authentication**: Required (API key)

    Creates invoice from usage events for the specified billing period.

    Args:
        billing_period: Billing period (YYYY-MM format)
        notes: Optional invoice notes

    Returns:
        Generated Invoice

    Raises:
        400: Invoice already exists for period or no usage found
        401: Unauthorized

    Example:
        POST /invoices
        Headers:
          X-API-Key: tenant-id
        Body:
          {
            "billing_period": "2024-01",
            "notes": "January 2024 usage"
          }
        Response (201 Created):
          {
            "id": "inv_...",
            "invoice_number": "INV-2024-01-0001",
            "billing_period": "2024-01",
            "subtotal_cents": 15250,
            "total_cents": 15250,
            "status": "draft",
            ...
          }
    """
    service = InvoiceService(db)

    try:
        invoice = service.generate_invoice(
            tenant_id=current_tenant.id,
            billing_period=request.billing_period,
            notes=request.notes,
        )

        return InvoiceResponse.model_validate(invoice)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get invoice details with line items.

    **Authentication**: Required (API key)

    Returns complete invoice with usage line items.

    Args:
        invoice_id: Invoice ID

    Returns:
        Detailed Invoice with line items

    Raises:
        401: Unauthorized
        403: Access denied (invoice belongs to different tenant)
        404: Invoice not found

    Example:
        GET /invoices/inv_123456
        Headers:
          X-API-Key: tenant-id
    """
    service = InvoiceService(db)
    invoice = service.get_invoice(invoice_id)

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    # Check tenant isolation
    if invoice.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Get line items
    line_items = service.get_invoice_line_items(invoice_id)
    response = InvoiceDetailedResponse.model_validate(invoice)
    response.line_items = [
        InvoiceDetailedResponse.model_validate(item) for item in line_items
    ]

    return response


@router.get("")
async def list_invoices(
    billing_period: Optional[str] = Query(None, description="Filter by billing period"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    List invoices for tenant (paginated).

    **Authentication**: Required (API key)

    Returns invoices with pagination.

    Args:
        billing_period: Optional filter by billing period
        status: Optional filter by status
        limit: Max results per page
        offset: Number of results to skip

    Returns:
        List of Invoices with pagination info

    Raises:
        401: Unauthorized

    Example:
        GET /invoices?limit=10&offset=0
        Headers:
          X-API-Key: tenant-id
    """
    service = InvoiceService(db)
    invoices, total_count = service.get_tenant_invoices(
        tenant_id=current_tenant.id,
        limit=limit,
        offset=offset,
    )

    # Apply optional filters
    if billing_period:
        invoices = [i for i in invoices if i.billing_period == billing_period]
    if status:
        invoices = [i for i in invoices if i.status.value == status]

    total_pages = (len(invoices) + limit - 1) // limit if invoices else 0

    return InvoiceListResponse(
        invoices=[InvoiceResponse.model_validate(i) for i in invoices],
        total_count=len(invoices),
        page=offset // limit + 1,
        page_size=limit,
        total_pages=total_pages,
    )


@router.post("/{invoice_id}/issue", status_code=status.HTTP_200_OK)
async def issue_invoice(
    invoice_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Issue an invoice (change status from draft to issued).

    **Authentication**: Required (API key)

    Finalizes invoice for customer delivery.

    Args:
        invoice_id: Invoice ID

    Returns:
        Updated Invoice

    Raises:
        400: Invoice already issued or in invalid state
        401: Unauthorized
        403: Access denied
        404: Invoice not found

    Example:
        POST /invoices/inv_123456/issue
        Headers:
          X-API-Key: tenant-id
    """
    service = InvoiceService(db)
    invoice = service.get_invoice(invoice_id)

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    if invoice.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    try:
        invoice = service.issue_invoice(invoice_id)
        return InvoiceResponse.model_validate(invoice)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{invoice_id}/mark-paid", status_code=status.HTTP_200_OK)
async def mark_invoice_paid(
    invoice_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Mark invoice as paid.

    **Authentication**: Required (API key)

    Records payment receipt.

    Args:
        invoice_id: Invoice ID

    Returns:
        Updated Invoice

    Raises:
        401: Unauthorized
        403: Access denied
        404: Invoice not found

    Example:
        POST /invoices/inv_123456/mark-paid
        Headers:
          X-API-Key: tenant-id
    """
    service = InvoiceService(db)
    invoice = service.get_invoice(invoice_id)

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    if invoice.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    try:
        invoice = service.mark_paid(invoice_id)
        return InvoiceResponse.model_validate(invoice)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{invoice_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_invoice(
    invoice_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Cancel an invoice.

    **Authentication**: Required (API key)

    Voids invoice (cannot cancel paid invoices).

    Args:
        invoice_id: Invoice ID

    Returns:
        Updated Invoice

    Raises:
        400: Cannot cancel (e.g., already paid)
        401: Unauthorized
        403: Access denied
        404: Invoice not found

    Example:
        POST /invoices/inv_123456/cancel
        Headers:
          X-API-Key: tenant-id
    """
    service = InvoiceService(db)
    invoice = service.get_invoice(invoice_id)

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    if invoice.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    try:
        invoice = service.cancel_invoice(invoice_id)
        return InvoiceResponse.model_validate(invoice)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{invoice_id}/html")
async def get_invoice_html(
    invoice_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get HTML representation of invoice.

    **Authentication**: Required (API key)

    Returns HTML suitable for email, PDF, or viewing.

    Args:
        invoice_id: Invoice ID

    Returns:
        HTML string

    Raises:
        401: Unauthorized
        403: Access denied
        404: Invoice not found

    Example:
        GET /invoices/inv_123456/html
        Headers:
          X-API-Key: tenant-id
        Response: text/html
    """
    service = InvoiceService(db)
    invoice = service.get_invoice(invoice_id)

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    if invoice.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    try:
        html = service.get_invoice_html(invoice_id)
        return {"html": html}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{tenant_id}/summary")
async def get_invoice_summary(
    tenant_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get invoice summary for tenant.

    **Authentication**: Required (API key)

    Shows total billed, paid, outstanding, etc.

    Args:
        tenant_id: Tenant ID to summarize

    Returns:
        Invoice summary with statistics

    Raises:
        401: Unauthorized
        403: Access denied

    Example:
        GET /invoices/tenant-id/summary
        Headers:
          X-API-Key: tenant-id
    """
    # Check authorization
    if tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    service = InvoiceService(db)
    summary = service.get_tenant_invoice_summary(tenant_id)

    return summary
