"""initial PostgreSQL schema

Revision ID: 0001_initial_schema
"""
from alembic import op
from app.database import Base
from app import models  # noqa: F401

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=True)
