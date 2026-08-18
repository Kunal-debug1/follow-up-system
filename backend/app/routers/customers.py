"""
Customers router — customer CRUD, archive/restore, permanent delete,
timeline, and dashboard statistics.

All endpoints require authentication (applied at the router level in main.py).

Existing endpoints preserved with identical signatures:
    GET    /api/customers               — list (now supports ?archived= filter)
    POST   /api/customers               — create
    GET    /api/customers/{id}          — get by ID
    PATCH  /api/customers/{id}          — update (now supports name/phone/email/consumer_number)
    GET    /api/dashboard/stats         — dashboard statistics

New endpoints:
    POST   /api/customers/{id}/archive  — soft archive
    POST   /api/customers/{id}/restore  — restore from archive
    DELETE /api/customers/{id}          — permanent delete (admin only)
    GET    /api/customers/{id}/timeline — customer event timeline
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..database import get_db
from ..models import CallLog, Customer, Followup
from ..schemas import (
    CallLogWithCustomer,
    CustomerArchiveOut,
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    DashboardStats,
    PaginatedCustomers,
    TimelineEvent,
)
from ..services.customer_service import (
    AlreadyArchivedError,
    DuplicateError,
    NotArchivedError,
    archive_customer,
    create_customer as service_create_customer,
    delete_customer_permanently,
    get_dashboard_stats,
    restore_customer,
    update_customer as service_update_customer,
)

router = APIRouter(tags=["Customers"])

# Maximum allowed page size — prevents accidentally loading the entire table
_MAX_PAGE_SIZE = 200


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_customer_or_404(db: Session, customer_id: int) -> Customer:
    """Return the customer (active or archived) or raise HTTP 404."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def _is_admin(current_user: str) -> bool:
    """Return True if the authenticated user is the configured admin."""
    admin_username = os.getenv("CRM_ADMIN_USERNAME", "")
    return bool(admin_username) and current_user == admin_username


# ---------------------------------------------------------------------------
# Customer list
# ---------------------------------------------------------------------------

@router.get("/api/customers", response_model=PaginatedCustomers)
def list_customers(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=_MAX_PAGE_SIZE),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    archived: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """
    Return a paginated, searchable list of customers.

    By default only active (non-archived) customers are returned.
    Pass archived=true to list archived customers instead.

    Search matches against: name, phone, email, consumer_number.
    All filtering, sorting, and pagination is performed at the database level.

    BACKWARD COMPATIBLE: archived defaults to False, which preserves
    the same result set as the previous version of this endpoint.
    """
    query = db.query(Customer).filter(Customer.is_archived == archived)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            Customer.name.ilike(term)
            | Customer.phone.ilike(term)
            | Customer.email.ilike(term)
            | Customer.consumer_number.ilike(term)
        )

    if status_filter:
        query = query.filter(Customer.status == status_filter)

    total = query.count()
    pages = (total + limit - 1) // limit
    offset = (page - 1) * limit
    items = query.order_by(Customer.id.desc()).offset(offset).limit(limit).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


# ---------------------------------------------------------------------------
# Customer create
# ---------------------------------------------------------------------------

@router.post(
    "/api/customers",
    status_code=status.HTTP_201_CREATED,
    response_model=CustomerOut,
)
def create_new_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    """Create a new customer. Returns HTTP 409 if a duplicate is detected."""
    try:
        customer = service_create_customer(db, payload.model_dump())
        return customer
    except DuplicateError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e), "field": e.field},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------------------------------------------------------------------------
# Customer get
# ---------------------------------------------------------------------------

@router.get("/api/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    """Return a single customer by ID (active or archived)."""
    return _get_customer_or_404(db, customer_id)


# ---------------------------------------------------------------------------
# Customer update
# ---------------------------------------------------------------------------

@router.patch("/api/customers/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
):
    """
    Update editable fields on an existing customer.

    Only fields included in the request body are changed.
    Supported fields: name, phone, email, consumer_number, status, priority,
    notes, service, address, region, zone, circle, division, subdivision,
    business_unit.
    """
    customer = _get_customer_or_404(db, customer_id)
    data = payload.model_dump(exclude_unset=True)
    try:
        return service_update_customer(db, customer, data)
    except DuplicateError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e), "field": e.field},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------------------------------------------------------------------------
# Customer archive
# ---------------------------------------------------------------------------

@router.post("/api/customers/{customer_id}/archive", response_model=CustomerArchiveOut)
def archive(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
):
    """
    Soft-archive a customer.

    The customer is hidden from normal lists but is never deleted.
    All call logs and follow-ups are preserved and remain attached.
    The customer can be restored at any time via the /restore endpoint.
    """
    customer = _get_customer_or_404(db, customer_id)
    try:
        return archive_customer(db, customer, archived_by=current_user)
    except AlreadyArchivedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# ---------------------------------------------------------------------------
# Customer restore
# ---------------------------------------------------------------------------

@router.post("/api/customers/{customer_id}/restore", response_model=CustomerArchiveOut)
def restore(
    customer_id: int,
    db: Session = Depends(get_db),
    _current_user: str = Depends(require_auth),
):
    """
    Restore an archived customer to active status.

    The same customer record is reactivated in place.
    No duplicate is created. All history is retained.
    """
    customer = _get_customer_or_404(db, customer_id)
    try:
        return restore_customer(db, customer)
    except NotArchivedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# ---------------------------------------------------------------------------
# Customer permanent delete (admin only)
# ---------------------------------------------------------------------------

@router.delete("/api/customers/{customer_id}")
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
):
    """
    Permanently delete a customer and all associated data.

    ADMIN ONLY — returns HTTP 403 for non-admin users.

    This action is irreversible. All call logs and follow-ups belonging
    to this customer will also be permanently deleted (via CASCADE).
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permanent deletion requires administrator privileges",
        )

    customer = _get_customer_or_404(db, customer_id)
    return delete_customer_permanently(db, customer)


# ---------------------------------------------------------------------------
# Customer timeline
# ---------------------------------------------------------------------------

@router.get("/api/customers/{customer_id}/timeline", response_model=list[TimelineEvent])
def customer_timeline(
    customer_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Return a chronological timeline of events for a customer.

    Events are derived from existing records:
        - Customer creation event (from Customer.created_at)
        - Call log entries
        - Follow-up entries

    No new database table is created — the timeline is computed on the fly.
    Events are returned newest-first.
    """
    customer = _get_customer_or_404(db, customer_id)

    events: list[TimelineEvent] = []

    # --- Customer created event ---
    events.append(TimelineEvent(
        event_type="created",
        timestamp=customer.created_at,
        title="Customer added",
        subtitle=f"Customer record created for {customer.name}",
        event_id=customer.id,
    ))

    # --- Call log events ---
    calls = (
        db.query(CallLog)
        .filter(CallLog.customer_id == customer_id)
        .order_by(CallLog.called_at.desc())
        .limit(limit)
        .all()
    )
    for call in calls:
        status_label = call.call_status.replace("_", " ").title()
        events.append(TimelineEvent(
            event_type="call",
            timestamp=call.called_at,
            title=f"Call — {status_label}",
            subtitle=call.notes,
            status=call.call_status,
            event_id=call.id,
        ))

    # --- Follow-up events ---
    followups = (
        db.query(Followup)
        .filter(Followup.customer_id == customer_id)
        .order_by(Followup.created_at.desc())
        .limit(limit)
        .all()
    )
    for fu in followups:
        # Use completed_at for completed follow-ups so the timeline is accurate
        timestamp = fu.completed_at if fu.completed_at else fu.created_at
        status_label = fu.status.title()
        title = f"Follow-up — {status_label}"

        subtitle_parts = []
        if fu.reason:
            subtitle_parts.append(fu.reason)
        scheduled = f"Scheduled: {fu.followup_date}"
        if fu.followup_time:
            scheduled += f" {fu.followup_time}"
        subtitle_parts.append(scheduled)

        events.append(TimelineEvent(
            event_type="followup",
            timestamp=timestamp,
            title=title,
            subtitle=" · ".join(subtitle_parts) if subtitle_parts else None,
            outcome=fu.outcome,
            status=fu.status,
            notes=fu.notes,
            event_id=fu.id,
        ))

    # Sort all events newest-first
    events.sort(key=lambda e: e.timestamp, reverse=True)

    return events[:limit]


# ---------------------------------------------------------------------------
# Recent calls (global view) — powers the Call History page
# ---------------------------------------------------------------------------

@router.get("/api/calls/recent", response_model=list[CallLogWithCustomer])
def recent_calls(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Return the most recent call logs across ALL customers, newest first.

    Each entry includes the customer name and phone so the Call History page
    can display meaningful information without extra requests.

    BUSINESS RULE: This endpoint returns only REAL call log records.
    It never returns customers that have no call history. Creating a customer
    NEVER creates a call log — so a brand-new customer will NOT appear here.
    """
    rows = (
        db.query(
            CallLog.id,
            CallLog.customer_id,
            Customer.name.label("customer_name"),
            Customer.phone.label("customer_phone"),
            CallLog.call_status,
            CallLog.notes,
            CallLog.called_at,
        )
        .join(Customer, CallLog.customer_id == Customer.id)
        .order_by(CallLog.called_at.desc())
        .limit(limit)
        .all()
    )

    return [
        CallLogWithCustomer(
            id=row.id,
            customer_id=row.customer_id,
            customer_name=row.customer_name,
            customer_phone=row.customer_phone,
            call_status=row.call_status,
            notes=row.notes,
            called_at=row.called_at,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    """Return aggregated CRM statistics computed at the database level."""
    return get_dashboard_stats(db)
