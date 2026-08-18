"""
Pydantic schemas for request validation and response serialisation.

All schemas use Pydantic v2 syntax (model_config, ConfigDict, etc.).

Timezone strategy:
    All datetime fields in response schemas are serialised with UTC offset
    (e.g. "2026-08-18T05:00:00+00:00"). JavaScript Date() will parse these
    correctly as UTC and convert to the browser's local timezone (IST) for
    display. Never manually add/subtract hours.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

CustomerStatus = Literal["new", "contacted", "interested", "not_interested", "converted"]
Priority = Literal["low", "medium", "high"]
# 'missed' added — existing pending/completed/cancelled values are unchanged
FollowupStatus = Literal["pending", "completed", "missed", "cancelled"]
FollowupOutcome = Literal[
    "interested",
    "not_interested",
    "call_back",
    "no_answer",
    "busy",
    "converted",
]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str | None = None
    email: str | None = None
    consumer_number: str | None = None
    service: str | None = None
    address: str | None = None
    region: str | None = None
    zone: str | None = None
    circle: str | None = None
    division: str | None = None
    subdivision: str | None = None
    business_unit: str | None = None
    status: CustomerStatus
    priority: Priority
    notes: str | None = None
    # Archive fields
    is_archived: bool = False
    archived_at: datetime | None = None
    archived_by: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at", "archived_at")
    def serialize_dt(self, v: Optional[datetime]) -> Optional[str]:
        """Ensure all datetimes are serialised as UTC ISO-8601 with +00:00."""
        if v is None:
            return None
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = None
    email: str | None = None
    consumer_number: str | None = None
    service: str | None = None
    address: str | None = None
    region: str | None = None
    zone: str | None = None
    circle: str | None = None
    division: str | None = None
    subdivision: str | None = None
    business_unit: str | None = None
    priority: Priority = "medium"
    status: CustomerStatus = "new"
    notes: str | None = None


class CustomerUpdate(BaseModel):
    """Partial update schema — all fields are optional.

    Includes name, phone, email, consumer_number for full edit support.
    Duplicate detection for phone/consumer_number is enforced in the service layer.
    """
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    consumer_number: Optional[str] = Field(default=None, max_length=100)
    status: Optional[CustomerStatus] = None
    priority: Optional[Priority] = None
    notes: Optional[str] = None
    service: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = None
    region: Optional[str] = Field(default=None, max_length=255)
    zone: Optional[str] = Field(default=None, max_length=255)
    circle: Optional[str] = Field(default=None, max_length=255)
    division: Optional[str] = Field(default=None, max_length=255)
    subdivision: Optional[str] = Field(default=None, max_length=255)
    business_unit: Optional[str] = Field(default=None, max_length=255)


class CustomerArchiveOut(BaseModel):
    """Response after archiving or restoring a customer."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_archived: bool
    archived_at: datetime | None = None
    archived_by: str | None = None


class PaginatedCustomers(BaseModel):
    items: list[CustomerOut]
    total: int
    page: int
    limit: int
    pages: int


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

class TimelineEvent(BaseModel):
    """A single event in the customer timeline (call, follow-up, or creation)."""
    event_type: str          # 'created', 'call', 'followup'
    timestamp: datetime
    title: str
    subtitle: str | None = None
    outcome: str | None = None
    status: str | None = None
    notes: str | None = None
    event_id: int | None = None  # the id of the underlying call/followup record

    @field_serializer("timestamp")
    def serialize_timestamp(self, v: datetime) -> str:
        """Ensure timestamp is serialised as UTC ISO-8601 with +00:00."""
        if v is None:
            return None
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardStats(BaseModel):
    total_customers: int
    today_followups: int
    overdue_followups: int
    upcoming_followups: int
    calls_today: int


# ---------------------------------------------------------------------------
# Call log
# ---------------------------------------------------------------------------

class CallLogCreate(BaseModel):
    call_status: str = Field(
        min_length=1,
        max_length=50,
        pattern=r"^\S(?:.*\S)?$",
    )
    notes: Optional[str] = None


class CallLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    call_status: str
    notes: Optional[str]
    called_at: datetime

    @field_serializer("called_at")
    def serialize_called_at(self, v: datetime) -> str:
        """Ensure called_at is serialised as UTC ISO-8601 with Z suffix."""
        if v is None:
            return None
        if v.tzinfo is None:
            # Stored as naive UTC — attach UTC tzinfo before serialising
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()


class CallLogWithCustomer(BaseModel):
    """Extended call log that includes the customer name and phone — used by
    the /api/calls/recent endpoint so CallsPage can display meaningful info."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    customer_name: str
    customer_phone: Optional[str] = None
    call_status: str
    notes: Optional[str]
    called_at: datetime

    @field_serializer("called_at")
    def serialize_called_at(self, v: datetime) -> str:
        """Ensure called_at is serialised as UTC ISO-8601 with Z suffix."""
        if v is None:
            return None
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()


# ---------------------------------------------------------------------------
# Follow-up
# ---------------------------------------------------------------------------

class FollowupCreate(BaseModel):
    followup_date: date
    followup_time: Optional[str] = Field(
        default=None,
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
    )
    reason: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None
    priority: Priority = "medium"


class FollowupUpdate(BaseModel):
    followup_date: Optional[date] = None
    followup_time: Optional[str] = Field(
        default=None,
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
    )
    status: Optional[FollowupStatus] = None
    reason: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None
    outcome: Optional[FollowupOutcome] = None
    priority: Optional[Priority] = None


class CompleteFollowupRequest(BaseModel):
    """Request body for the POST /api/followups/{id}/complete endpoint."""
    outcome: FollowupOutcome
    notes: Optional[str] = None
    # If True, a new follow-up is scheduled for this customer
    create_next: bool = False
    next_date: Optional[date] = None
    next_time: Optional[str] = Field(
        default=None,
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
    )
    next_reason: Optional[str] = Field(default=None, max_length=255)


class FollowupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    # customer_name is populated by JOIN queries in the router layer;
    # it is absent from direct ORM results so we default to None.
    customer_name: Optional[str] = None
    followup_date: str
    followup_time: Optional[str]
    status: str
    reason: Optional[str]
    notes: Optional[str]
    outcome: Optional[str] = None
    priority: str = "medium"
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    created_at: datetime

    @field_serializer("completed_at", "created_at")
    def serialize_dt(self, v: Optional[datetime]) -> Optional[str]:
        """Ensure all datetimes are serialised as UTC ISO-8601 with +00:00."""
        if v is None:
            return None
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()


class CompleteFollowupOut(BaseModel):
    """Response after completing a follow-up (may include a new follow-up)."""
    completed: FollowupOut
    next_followup: Optional[FollowupOut] = None
