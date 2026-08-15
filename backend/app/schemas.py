from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

CustomerStatus = Literal["new", "contacted", "interested", "not_interested", "converted"]
Priority = Literal["low", "medium", "high"]
FollowupStatus = Literal["pending", "completed", "cancelled"]

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)

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
    created_at: datetime
    updated_at: datetime

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

class PaginatedCustomers(BaseModel):
    items: list[CustomerOut]
    total: int
    page: int
    limit: int
    pages: int

class DashboardStats(BaseModel):
    total_customers: int
    today_followups: int
    overdue_followups: int
    upcoming_followups: int
    calls_today: int

class CallLogCreate(BaseModel):
    call_status: str = Field(min_length=1, max_length=50, pattern=r"^\S(?:.*\S)?$")
    notes: Optional[str] = None

class CallLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    call_status: str
    notes: Optional[str]
    called_at: datetime

class FollowupCreate(BaseModel):
    followup_date: date
    followup_time: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    reason: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None

class FollowupUpdate(BaseModel):
    followup_date: Optional[date] = None
    followup_time: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    status: Optional[FollowupStatus] = None
    reason: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None

class FollowupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    followup_date: str
    followup_time: Optional[str]
    status: str
    reason: Optional[str]
    notes: Optional[str]
    created_at: datetime
