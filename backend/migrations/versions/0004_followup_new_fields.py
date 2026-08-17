"""Add follow-up outcome, priority, completed_at, completed_by fields

Extends the followups table with:
    - outcome       VARCHAR(50) nullable — call outcome after completion
                    (interested, not_interested, call_back, no_answer, busy, converted)
    - priority      VARCHAR(20) NOT NULL DEFAULT 'medium'
                    (low, medium, high) — mirrors customer priority naming
    - completed_at  TIMESTAMP nullable — when the follow-up was marked complete
    - completed_by  VARCHAR(255) nullable — which admin marked it complete

This migration is fully backward-safe:
    - All existing follow-ups will have outcome=NULL (not yet set), priority='medium',
      completed_at=NULL, completed_by=NULL.
    - No existing follow-up data is modified or deleted.
    - The 'missed' status value requires no migration — the status column is
      VARCHAR(30) with no DB-level enum constraint.

Revision ID: 0004_followup_new_fields
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_followup_new_fields"
down_revision = "0003_customer_archive_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Outcome — null until a follow-up is completed with an outcome
    op.add_column(
        "followups",
        sa.Column("outcome", sa.String(50), nullable=True),
    )

    # Priority — defaults to 'medium' for all existing and new follow-ups
    op.add_column(
        "followups",
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default="medium",
        ),
    )

    # Completion timestamp
    op.add_column(
        "followups",
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    # Which user completed the follow-up
    op.add_column(
        "followups",
        sa.Column("completed_by", sa.String(255), nullable=True),
    )

    # Index to support outcome-based filtering (e.g. all "converted" follow-ups)
    op.create_index(
        "idx_followups_outcome",
        "followups",
        ["outcome"],
        if_not_exists=True,
    )

    # Index for priority-based ordering within the followup list
    op.create_index(
        "idx_followups_priority",
        "followups",
        ["priority"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_followups_priority", table_name="followups", if_exists=True)
    op.drop_index("idx_followups_outcome", table_name="followups", if_exists=True)
    op.drop_column("followups", "completed_by")
    op.drop_column("followups", "completed_at")
    op.drop_column("followups", "priority")
    op.drop_column("followups", "outcome")
