"""
Add follow-up outcome, priority and completion fields.

This migration is safe to run when some fields already exist.
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_followup_new_fields"
down_revision = "0003_customer_archive_fields"
branch_labels = None
depends_on = None


def _existing_columns(table_name: str) -> set[str]:
    """Return existing columns for a table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    return {
        column["name"]
        for column in inspector.get_columns(table_name)
    }


def upgrade() -> None:
    """Add follow-up fields only when missing."""

    existing = _existing_columns("followups")

    # ---------------------------------------------------------------
    # Follow-up outcome
    # ---------------------------------------------------------------
    if "outcome" not in existing:
        op.add_column(
            "followups",
            sa.Column(
                "outcome",
                sa.String(50),
                nullable=True,
            ),
        )

    # ---------------------------------------------------------------
    # Follow-up priority
    # ---------------------------------------------------------------
    if "priority" not in existing:
        op.add_column(
            "followups",
            sa.Column(
                "priority",
                sa.String(20),
                nullable=False,
                server_default="medium",
            ),
        )

    # ---------------------------------------------------------------
    # Completion timestamp
    # ---------------------------------------------------------------
    if "completed_at" not in existing:
        op.add_column(
            "followups",
            sa.Column(
                "completed_at",
                sa.DateTime(),
                nullable=True,
            ),
        )

    # ---------------------------------------------------------------
    # User who completed the follow-up
    # ---------------------------------------------------------------
    if "completed_by" not in existing:
        op.add_column(
            "followups",
            sa.Column(
                "completed_by",
                sa.String(255),
                nullable=True,
            ),
        )

    # ---------------------------------------------------------------
    # Performance indexes
    # ---------------------------------------------------------------
    op.create_index(
        "idx_followups_outcome",
        "followups",
        ["outcome"],
        if_not_exists=True,
    )

    op.create_index(
        "idx_followups_priority",
        "followups",
        ["priority"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """Remove follow-up fields and indexes."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        column["name"]
        for column in inspector.get_columns("followups")
    }

    op.drop_index(
        "idx_followups_priority",
        table_name="followups",
        if_exists=True,
    )

    op.drop_index(
        "idx_followups_outcome",
        table_name="followups",
        if_exists=True,
    )

    if "completed_by" in columns:
        op.drop_column("followups", "completed_by")

    if "completed_at" in columns:
        op.drop_column("followups", "completed_at")

    if "priority" in columns:
        op.drop_column("followups", "priority")

    if "outcome" in columns:
        op.drop_column("followups", "outcome")