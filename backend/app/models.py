from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ImportBatch(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    customers: Mapped[list["Customer"]] = relationship(
        back_populates="import_batch"
    )


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    service: Mapped[str | None] = mapped_column(String(255))
    consumer_number: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(255))
    zone: Mapped[str | None] = mapped_column(String(255))
    circle: Mapped[str | None] = mapped_column(String(255))
    division: Mapped[str | None] = mapped_column(String(255))
    subdivision: Mapped[str | None] = mapped_column(String(255))
    business_unit: Mapped[str | None] = mapped_column(String(255))
    priority: Mapped[str] = mapped_column(
        String(30), default="medium", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default="new", nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    import_id: Mapped[int | None] = mapped_column(
        ForeignKey("imports.id", ondelete="SET NULL")
    )
    source_file: Mapped[str | None] = mapped_column(String(255))
    source_row: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ---------------------------------------------------------------------------
    # Archive / soft-delete fields  (added in migration 0003)
    # ---------------------------------------------------------------------------
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    import_batch: Mapped[ImportBatch | None] = relationship(
        back_populates="customers"
    )


class Followup(Base):
    __tablename__ = "followups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    followup_date: Mapped[str] = mapped_column(String(20), nullable=False)
    followup_time: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # ---------------------------------------------------------------------------
    # New follow-up fields  (added in migration 0004)
    # ---------------------------------------------------------------------------
    # outcome — set when completing a follow-up (null on pending/missed/cancelled)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # priority — low / medium / high (mirrors customer priority)
    priority: Mapped[str] = mapped_column(
        String(20), default="medium", nullable=False
    )
    # completion audit fields
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    call_status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    called_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

Index("idx_customers_phone", Customer.phone)
Index("idx_customers_consumer_number", Customer.consumer_number)
Index("idx_customers_status", Customer.status)
Index("idx_customers_name", Customer.name)
Index("idx_customers_import_id", Customer.import_id)
Index("idx_customers_is_archived", Customer.is_archived)          # new (0003)
Index("idx_followups_date", Followup.followup_date)
Index(
    "idx_followups_status_date_time",
    Followup.status,
    Followup.followup_date,
    Followup.followup_time,
)
Index("idx_followups_customer_id", Followup.customer_id)
Index(
    "idx_followups_customer_status_datetime",
    Followup.customer_id,
    Followup.status,
    Followup.followup_date,
    Followup.followup_time,
)
Index("idx_followups_outcome", Followup.outcome)                   # new (0004)
Index("idx_followups_priority", Followup.priority)                 # new (0004)
Index("idx_call_logs_customer", CallLog.customer_id)
Index("idx_call_logs_called_at", CallLog.called_at)
