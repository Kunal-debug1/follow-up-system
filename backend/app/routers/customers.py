from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Customer
from ..schemas import CustomerOut, CustomerCreate, PaginatedCustomers, DashboardStats
from ..services.customer_service import create_customer as service_create_customer, get_dashboard_stats, DuplicateError

router = APIRouter(tags=["Customers"])


@router.get("/api/customers", response_model=PaginatedCustomers)
def list_customers(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    query = db.query(Customer)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (Customer.name.ilike(term)) |
            (Customer.phone.ilike(term)) |
            (Customer.email.ilike(term)) |
            (Customer.consumer_number.ilike(term))
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
        "pages": pages
    }


@router.post("/api/customers", status_code=status.HTTP_201_CREATED, response_model=CustomerOut)
def create_new_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    try:
        customer = service_create_customer(db, payload.model_dump())
        return customer
    except DuplicateError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": str(e), "field": e.field})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/api/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/api/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    return get_dashboard_stats(db)
