"""Add pg_trgm extension and GIN trigram indexes for leading-wildcard search.

Normal B-tree indexes on name, phone, email, consumer_number do NOT speed up
ILIKE '%term%' queries (leading wildcard).  PostgreSQL's pg_trgm extension
provides the gin_trgm_ops operator class that makes such pattern searches
index-accelerated.

These indexes are additive — the existing B-tree indexes remain and continue
to serve exact-match / duplicate-detection lookups.

Available on Supabase PostgreSQL.  On SQLite (tests) the migration is a
no-op because create_all is used instead of alembic in tests.
"""
from alembic import op

revision = "0005_trgm_search_indexes"
down_revision = "0004_followup_new_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # pg_trgm and GIN indexes are PostgreSQL-specific.
        # Tests use SQLite with create_all; skip gracefully.
        return

    # Enable the pg_trgm extension (idempotent).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    _columns = ("name", "phone", "email", "consumer_number")
    for col in _columns:
        op.create_index(
            f"idx_customers_{col}_trgm",
            "customers",
            [col],
            postgresql_using="gin",
            postgresql_ops={col: "gin_trgm_ops"},
            if_not_exists=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    _columns = ("name", "phone", "email", "consumer_number")
    for col in reversed(_columns):
        op.drop_index(
            f"idx_customers_{col}_trgm",
            table_name="customers",
            if_exists=True,
        )
    op.execute("DROP EXTENSION IF EXISTS pg_trgm CASCADE")