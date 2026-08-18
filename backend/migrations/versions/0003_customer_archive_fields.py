"""
Add customer archive fields.

This migration is safe to run against databases where some or all
archive fields already exist.
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_customer_archive_fields"
down_revision = "0002_add_missing_indexes"
branch_labels = None
depends_on = None


def _existing_columns(table_name: str) -> set[str]:
    """Return the existing column names for a table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    return {
        column["name"]
        for column in inspector.get_columns(table_name)
    }


def upgrade() -> None:
    """Add customer archive columns only when they don't already exist."""

    existing = _existing_columns("customers")

    # ---------------------------------------------------------------
    # Soft-delete/archive flag
    # ---------------------------------------------------------------
    if "is_archived" not in existing:
        op.add_column(
            "customers",
            sa.Column(
                "is_archived",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    # ---------------------------------------------------------------
    # Date/time when customer was archived
    # ---------------------------------------------------------------
    if "archived_at" not in existing:
        op.add_column(
            "customers",
            sa.Column(
                "archived_at",
                sa.DateTime(),
                nullable=True,
            ),
        )

    # ---------------------------------------------------------------
    # User who archived the customer
    # ---------------------------------------------------------------
    if "archived_by" not in existing:
        op.add_column(
            "customers",
            sa.Column(
                "archived_by",
                sa.String(255),
                nullable=True,
            ),
        )

    # ---------------------------------------------------------------
    # Index for active/archived customer filtering
    # ---------------------------------------------------------------
    op.create_index(
        "idx_customers_is_archived",
        "customers",
        ["is_archived"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """Remove archive fields if they exist."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        column["name"]
        for column in inspector.get_columns("customers")
    }

    op.drop_index(
        "idx_customers_is_archived",
        table_name="customers",
        if_exists=True,
    )

    if "archived_by" in columns:
        op.drop_column("customers", "archived_by")

    if "archived_at" in columns:
        op.drop_column("customers", "archived_at")

    if "is_archived" in columns:
        op.drop_column("customers", "is_archived")