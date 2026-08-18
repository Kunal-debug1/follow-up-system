"""
Customer service — business logic for customer CRUD, archive/restore,
permanent deletion, and dashboard statistics.

Duplicate detection rules (business rule — do not change without explicit approval):
    1. If consumer_number is provided: reject if any existing customer has the same consumer_number.
    2. If phone is provided: reject if any existing customer has the same phone.
    Rule 1 takes priority over Rule 2.

Archive rules:
    - Archived customers are excluded from normal list queries but remain in the DB.
    - Archived customers retain all call logs and follow-ups.
    - Restore simply clears the archive fields.

Permanent delete rules:
    - Admin-only action (enforced at router level).
    - Cascades to call_logs and followups via FK constraints.
    - Caller must pass explicit confirm=True to prevent accidental mass deletion.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import CallLog, Customer, Followup
from ..utils.normalization import normalize_consumer_number, normalize_email, normalize_phone
from ..utils.timezone import business_start_of_day, business_end_of_day, business_today


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DuplicateError(Exception):
    """Raised when a customer with the same unique contact info already exists."""

    def __init__(self, message: str, field: str = "") -> None:
        self.message = message
        self.field = field
        super().__init__(message)


class AlreadyArchivedError(Exception):
    """Raised when trying to archive a customer that is already archived."""


class NotArchivedError(Exception):
    """Raised when trying to restore a customer that is not archived."""


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

    now = datetime.now(timezone.utc)
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
        is_archived=False,
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

    Supports full edit including name, phone, email, consumer_number.
    Duplicate check is performed for phone and consumer_number when they change.

    Raises:
        ValueError: for invalid field values.
        DuplicateError: if the new phone/consumer_number already belongs to another customer.
    """
    # Sensitive fields that require duplicate checks
    if "name" in data and data["name"] is not None:
        name = data["name"].strip()
        if not name:
            raise ValueError("Customer name cannot be empty")
        customer.name = name

    if "phone" in data:
        new_phone = normalize_phone(data["phone"])
        if new_phone and new_phone != customer.phone:
            existing = (
                db.query(Customer)
                .filter(Customer.phone == new_phone, Customer.id != customer.id)
                .first()
            )
            if existing:
                raise DuplicateError(
                    f"Another customer with phone {new_phone} already exists",
                    field="phone",
                )
        customer.phone = new_phone

    if "email" in data:
        customer.email = normalize_email(data["email"])

    if "consumer_number" in data:
        new_cn = normalize_consumer_number(data["consumer_number"])
        if new_cn and new_cn != customer.consumer_number:
            existing = (
                db.query(Customer)
                .filter(
                    Customer.consumer_number == new_cn,
                    Customer.id != customer.id,
                )
                .first()
            )
            if existing:
                raise DuplicateError(
                    f"Another customer with consumer number {new_cn} already exists",
                    field="consumer_number",
                )
        customer.consumer_number = new_cn

    # Non-sensitive editable fields
    simple_fields = {
        "status", "priority", "notes", "service", "address",
        "region", "zone", "circle", "division", "subdivision", "business_unit",
    }
    for field in simple_fields:
        if field in data and data[field] is not None:
            setattr(customer, field, data[field])

    customer.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(customer)
        return customer
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Customer archive / restore
# ---------------------------------------------------------------------------

def archive_customer(db: Session, customer: Customer, archived_by: str) -> Customer:
    """
    Soft-delete a customer by setting is_archived=True.

    Does NOT delete any data. Call logs and follow-ups are preserved.

    Raises:
        AlreadyArchivedError: if the customer is already archived.
    """
    if customer.is_archived:
        raise AlreadyArchivedError(
            f"Customer '{customer.name}' is already archived"
        )

    customer.is_archived = True
    customer.archived_at = datetime.now(timezone.utc)
    customer.archived_by = archived_by
    customer.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(customer)
        return customer
    except Exception:
        db.rollback()
        raise


def restore_customer(db: Session, customer: Customer) -> Customer:
    """
    Restore an archived customer by clearing is_archived.

    Does NOT create a duplicate — the same customer record is restored in place.

    Raises:
        NotArchivedError: if the customer is not archived.
    """
    if not customer.is_archived:
        raise NotArchivedError(
            f"Customer '{customer.name}' is not archived"
        )

    customer.is_archived = False
    customer.archived_at = None
    customer.archived_by = None
    customer.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(customer)
        return customer
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Customer permanent delete (admin only — enforced at router level)
# ---------------------------------------------------------------------------

def delete_customer_permanently(db: Session, customer: Customer) -> dict:
    """
    Permanently delete a customer and all associated data.

    Call logs and follow-ups cascade-delete via the FK constraints
    (ondelete='CASCADE') that already exist on both tables.

    This function must only be called from an admin-protected endpoint.
    """
    customer_id = customer.id
    customer_name = customer.name

    try:
        db.delete(customer)
        db.commit()
        return {
            "message": f"Customer '{customer_name}' permanently deleted",
            "id": customer_id,
        }
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Dashboard statistics
# ---------------------------------------------------------------------------

def get_dashboard_stats(db: Session) -> dict:
    """
    Return aggregated CRM statistics using database-level COUNT queries.

    Follow-up statistics are computed in a single combined query with conditional
    aggregation, reducing roundtrips.

    Archived customers are excluded from total_customers.
    """
    today = business_today()
    today_str = today.isoformat()
    # Business day boundaries in UTC — consistent with how timestamps are stored
    start_of_day = business_start_of_day()
    start_of_tomorrow = business_end_of_day()

    # 1. Total active customers count (indexed on is_archived)
    total_customers: int = db.query(func.count(Customer.id)).filter(
        Customer.is_archived == False  # noqa: E712
    ).scalar() or 0

    # 2. Combined follow-up counts for today, overdue, and upcoming in 1 query
    fu_row = (
        db.query(
            func.count(case((Followup.followup_date == today_str, Followup.id))),
            func.count(case((Followup.followup_date < today_str, Followup.id))),
            func.count(case((Followup.followup_date > today_str, Followup.id))),
        )
        .filter(Followup.status == "pending")
        .first()
    )

    today_followups: int = fu_row[0] if fu_row else 0
    overdue_followups: int = fu_row[1] if fu_row else 0
    upcoming_followups: int = fu_row[2] if fu_row else 0

    # 3. Calls today count (indexed on called_at)
    calls_today: int = db.query(func.count(CallLog.id)).filter(
        CallLog.called_at >= start_of_day,
        CallLog.called_at < start_of_tomorrow,
    ).scalar() or 0

    return {
        "total_customers": total_customers,
        "today_followups": today_followups,
        "overdue_followups": overdue_followups,
        "upcoming_followups": upcoming_followups,
        "calls_today": calls_today,
    }
