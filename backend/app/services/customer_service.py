"""
Customer service — business logic for customer creation and dashboard statistics.

Duplicate detection rules (business rule — do not change without explicit approval):
    1. If consumer_number is provided: reject if any existing customer has the same consumer_number.
    2. If phone is provided: reject if any existing customer has the same phone.
    Rule 1 takes priority over Rule 2.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import CallLog, Customer, Followup
from ..utils.normalization import normalize_consumer_number, normalize_email, normalize_phone


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DuplicateError(Exception):
    """Raised when a customer with the same unique contact info already exists."""

    def __init__(self, message: str, field: str = "") -> None:
        self.message = message
        self.field = field
        super().__init__(message)


# ---------------------------------------------------------------------------
# Customer creation
# ---------------------------------------------------------------------------

def create_customer(db: Session, data: dict) -> Customer:
    """
    Create a new customer with validation and duplicate checking.

    Raises:
        ValueError: if required fields are missing.
        DuplicateError: if a duplicate consumer_number or phone already exists.
    """
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Customer name is required")

    phone = normalize_phone(data.get("phone"))
    email = normalize_email(data.get("email"))
    consumer_number = normalize_consumer_number(data.get("consumer_number"))

    if not phone and not consumer_number:
        raise ValueError("Either phone or consumer number is required")

    # Duplicate checks — use indexed columns for O(log n) lookups
    if consumer_number:
        existing = (
            db.query(Customer)
            .filter(Customer.consumer_number == consumer_number)
            .first()
        )
        if existing:
            raise DuplicateError(
                f"Customer with consumer number {consumer_number} already exists",
                field="consumer_number",
            )

    if phone:
        existing = (
            db.query(Customer)
            .filter(Customer.phone == phone)
            .first()
        )
        if existing:
            raise DuplicateError(
                f"Customer with phone {phone} already exists",
                field="phone",
            )

    now = datetime.utcnow()
    customer = Customer(
        name=name,
        phone=phone,
        email=email,
        service=(data.get("service") or "").strip() or None,
        consumer_number=consumer_number,
        address=(data.get("address") or "").strip() or None,
        region=(data.get("region") or "").strip() or None,
        zone=(data.get("zone") or "").strip() or None,
        circle=(data.get("circle") or "").strip() or None,
        division=(data.get("division") or "").strip() or None,
        subdivision=(data.get("subdivision") or "").strip() or None,
        business_unit=(data.get("business_unit") or "").strip() or None,
        priority=data.get("priority", "medium"),
        status=data.get("status", "new"),
        notes=(data.get("notes") or "").strip() or None,
        created_at=now,
        updated_at=now,
    )

    try:
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateError(
            "A customer with the same unique contact information already exists"
        ) from exc


# ---------------------------------------------------------------------------
# Customer update
# ---------------------------------------------------------------------------

def update_customer(db: Session, customer: Customer, data: dict) -> Customer:
    """
    Update editable fields on an existing customer.

    Only the fields present in `data` are modified — absent keys are skipped.
    Raises ValueError for invalid field values.
    """
    editable_fields = {
        "status", "priority", "notes", "service", "address",
        "region", "zone", "circle", "division", "subdivision", "business_unit",
    }

    for field in editable_fields:
        if field in data and data[field] is not None:
            setattr(customer, field, data[field])

    customer.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(customer)
        return customer
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Dashboard statistics
# ---------------------------------------------------------------------------

def get_dashboard_stats(db: Session) -> dict:
    """
    Return aggregated CRM statistics using database-level COUNT queries.

    All counts are computed in a single round-trip per query — no Python-side
    filtering or aggregation is performed.
    """
    today = date.today()
    today_str = today.isoformat()
    start_of_day = datetime.combine(today, time.min)
    start_of_tomorrow = start_of_day + timedelta(days=1)

    total_customers: int = db.query(func.count(Customer.id)).scalar()

    today_followups: int = db.query(func.count(Followup.id)).filter(
        Followup.followup_date == today_str,
        Followup.status == "pending",
    ).scalar()

    overdue_followups: int = db.query(func.count(Followup.id)).filter(
        Followup.followup_date < today_str,
        Followup.status == "pending",
    ).scalar()

    # upcoming = strictly after today (today is counted separately above)
    upcoming_followups: int = db.query(func.count(Followup.id)).filter(
        Followup.followup_date > today_str,
        Followup.status == "pending",
    ).scalar()

    calls_today: int = db.query(func.count(CallLog.id)).filter(
        CallLog.called_at >= start_of_day,
        CallLog.called_at < start_of_tomorrow,
    ).scalar()

    return {
        "total_customers": total_customers,
        "today_followups": today_followups,
        "overdue_followups": overdue_followups,
        "upcoming_followups": upcoming_followups,
        "calls_today": calls_today,
    }
