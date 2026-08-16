"""
Customers router — customer CRUD and dashboard statistics.

All endpoints require authentication (applied at the router level in main.py).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Customer
from ..schemas import (
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    DashboardStats,
    PaginatedCustomers,
)
from ..services.customer_service import (
    DuplicateError,
    create_customer as service_create_customer,
    get_dashboard_stats,
    update_customer as service_update_customer,
)

router = APIRouter(tags=["Customers"])

# Maximum allowed page size — prevents accidentally loading the entire table
_MAX_PAGE_SIZE = 200


# ---------------------------------------------------------------------------
# Customer list
# ---------------------------------------------------------------------------

@router.get("/api/customers", response_model=PaginatedCustomers)
def list_customers(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=_MAX_PAGE_SIZE),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    """
    Return a paginated, searchable list of customers.

    Search matches against: name, phone, email, consumer_number.
    All filtering, sorting, and pagination is performed at the database level.
    """
    query = db.query(Customer)

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
    """Return a single customer by ID."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


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
    Supported fields: status, priority, notes, service, address,
    region, zone, circle, division, subdivision, business_unit.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    data = payload.model_dump(exclude_unset=True)
    return service_update_customer(db, customer, data)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    """Return aggregated CRM statistics computed at the database level."""
    return get_dashboard_stats(db)
