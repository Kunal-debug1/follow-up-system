"""ensure indexes used by production CRM queries

Revision ID: 0002_ensure_query_indexes
Revises: 0001_initial_schema
"""

from alembic import op


revision = "0002_ensure_query_indexes"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers (phone)",
    "CREATE INDEX IF NOT EXISTS idx_customers_consumer_number ON customers (consumer_number)",
    "CREATE INDEX IF NOT EXISTS idx_customers_status ON customers (status)",
    "CREATE INDEX IF NOT EXISTS idx_customers_import_id ON customers (import_id)",
    "CREATE INDEX IF NOT EXISTS idx_followups_status_date_time ON followups (status, followup_date, followup_time)",
    "CREATE INDEX IF NOT EXISTS idx_followups_customer_status_datetime ON followups (customer_id, status, followup_date, followup_time)",
    "CREATE INDEX IF NOT EXISTS idx_call_logs_customer ON call_logs (customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_call_logs_called_at ON call_logs (called_at)",
)


def upgrade():
    for statement in INDEXES:
        op.execute(statement)


def downgrade():
    for name in (
        "idx_call_logs_called_at", "idx_call_logs_customer", "idx_followups_customer_status_datetime",
        "idx_followups_status_date_time", "idx_customers_import_id", "idx_customers_status",
        "idx_customers_consumer_number", "idx_customers_phone",
    ):
        op.execute(f"DROP INDEX IF EXISTS {name}")
