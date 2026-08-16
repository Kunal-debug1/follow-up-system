"""Add missing performance indexes

Adds indexes that are not created by the initial 0001 migration:
    - idx_customers_email        — search and duplicate detection on email
    - idx_customers_priority     — future filtering by priority
    - idx_customers_created_at   — ordering by most recently added
    - idx_followups_status       — standalone status filter queries

Note: The following indexes already exist from models.py / 0001 migration
and are NOT re-created here:
    idx_customers_phone, idx_customers_consumer_number, idx_customers_status,
    idx_customers_name, idx_customers_import_id, idx_followups_date,
    idx_followups_status_date_time, idx_followups_customer_id,
    idx_followups_customer_status_datetime, idx_call_logs_customer,
    idx_call_logs_called_at

Revision ID: 0002_add_missing_indexes
"""
from alembic import op

revision = "0002_add_missing_indexes"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Email index — supports ilike search and future duplicate detection
    op.create_index(
        "idx_customers_email",
        "customers",
        ["email"],
        if_not_exists=True,
    )

    # Priority index — supports future priority-based filtering
    op.create_index(
        "idx_customers_priority",
        "customers",
        ["priority"],
        if_not_exists=True,
    )

    # Created-at index — supports ordering dashboard/recent customer lists
    op.create_index(
        "idx_customers_created_at",
        "customers",
        ["created_at"],
        if_not_exists=True,
    )

    # Standalone followup status index — supports queries filtering only by status
    # (the composite idx_followups_status_date_time covers multi-column queries)
    op.create_index(
        "idx_followups_status",
        "followups",
        ["status"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_followups_status", table_name="followups", if_exists=True)
    op.drop_index("idx_customers_created_at", table_name="customers", if_exists=True)
    op.drop_index("idx_customers_priority", table_name="customers", if_exists=True)
    op.drop_index("idx_customers_email", table_name="customers", if_exists=True)
