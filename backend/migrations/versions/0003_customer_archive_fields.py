"""Add customer archive fields

Adds soft-delete / archive support to the customers table:
    - is_archived   BOOLEAN NOT NULL DEFAULT false
    - archived_at   TIMESTAMP (nullable)
    - archived_by   VARCHAR(255) (nullable)
    - idx_customers_is_archived (index for fast active/archived filtering)

This migration is fully backward-safe:
    - All existing customers will have is_archived = false (the default).
    - No existing customer data is modified, moved, or deleted.
    - The customer list endpoint adds is_archived=false as its default filter,
      which produces exactly the same result set as before this migration.

Revision ID: 0003_customer_archive_fields
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_customer_archive_fields"
down_revision = "0002_add_missing_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_archived with a server-side default so existing rows are set to false
    op.add_column(
        "customers",
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # archived_at is nullable — NULL means the customer is active
    op.add_column(
        "customers",
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )

    # archived_by records which admin performed the archive
    op.add_column(
        "customers",
        sa.Column("archived_by", sa.String(255), nullable=True),
    )

    # Index to efficiently separate active vs archived customers in all queries
    op.create_index(
        "idx_customers_is_archived",
        "customers",
        ["is_archived"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_customers_is_archived", table_name="customers", if_exists=True)
    op.drop_column("customers", "archived_by")
    op.drop_column("customers", "archived_at")
    op.drop_column("customers", "is_archived")
