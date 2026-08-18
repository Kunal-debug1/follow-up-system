"""
Database configuration for the CRM Follow-Up API.

Responsibilities:
- Read DATABASE_URL from environment variables
- Configure SQLAlchemy + psycopg
- Create the database engine
- Provide FastAPI database sessions
- Provide a lightweight database readiness check

Production target:
- FastAPI
- SQLAlchemy 2.x
- PostgreSQL / Supabase
- Render
"""

from __future__ import annotations

import os
from typing import Any, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


# ============================================================================
# DATABASE URL
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required.\n"
        "Configure it in Render → Environment Variables.\n"
        "For Supabase, use the PostgreSQL connection URI."
    )


# ============================================================================
# SQLALCHEMY / PSYCOPG URL NORMALIZATION
# ============================================================================

# Supabase may provide:
#
#   postgres://...
#   postgresql://...
#
# SQLAlchemy should use the psycopg driver explicitly:
#
#   postgresql+psycopg://...
#
# Do not modify an already-correct URL.

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql+psycopg://",
        1,
    )

elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )


# ============================================================================
# DATABASE ENGINE
# ============================================================================

is_sqlite = DATABASE_URL.startswith("sqlite")

engine_kwargs: dict[str, Any] = {
    "pool_pre_ping": True,
}

if not is_sqlite:
    engine_kwargs.update({
        # Recycle connections periodically to reduce stale connection problems.
        "pool_recycle": 300,
        # Keep the connection pool reasonably small for Render + Supabase limits.
        "pool_size": 5,
        # Allow temporary burst traffic.
        "max_overflow": 10,
        # Do not block indefinitely while waiting for a connection.
        "pool_timeout": 30,
        # PostgreSQL connection timeout.
        "connect_args": {
            "connect_timeout": 10,
        },
    })
else:
    engine_kwargs["connect_args"] = {
        "check_same_thread": False,
    }

engine = create_engine(
    DATABASE_URL,
    **engine_kwargs,
)


# ============================================================================
# SESSION FACTORY
# ============================================================================

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# ============================================================================
# SQLALCHEMY BASE CLASS
# ============================================================================

class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    Example:

        class Customer(Base):
            __tablename__ = "customers"
            ...
    """

    pass


# ============================================================================
# FASTAPI DATABASE DEPENDENCY
# ============================================================================

def get_db() -> Generator[Session, None, None]:
    """
    Create a database session for a request.

    The session is always closed after the request finishes.
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# ============================================================================
# DATABASE READINESS CHECK
# ============================================================================

def database_is_ready() -> bool:
    """
    Check whether PostgreSQL is reachable.

    This only verifies database connectivity.

    It does NOT verify that migrations/tables exist.
    """

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return True

    except Exception:
        return False


# ============================================================================
# DATABASE SCHEMA CHECK
# ============================================================================

def database_schema_is_ready() -> bool:
    """
    Check whether the main CRM table exists.

    This is useful for detecting situations where:
    - PostgreSQL is reachable
    - but Alembic migrations were not executed
    - or the application is connected to the wrong database
    """

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'customers'
                    )
                    """
                )
            )

            return bool(result.scalar())

    except Exception:
        return False