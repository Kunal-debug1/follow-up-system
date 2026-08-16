"""
Database engine, session factory, and readiness check.

The engine is created at module import time so that Alembic env.py can
import it directly. Pool settings are tuned for production on Render's
single-process web service.
"""
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ---------------------------------------------------------------------------
# Connection URL
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required. "
        "Use Supabase Project Settings → Database → Connection string (URI) "
        "with ?sslmode=require appended."
    )

# Supabase provides postgres:// or postgresql:// URLs; SQLAlchemy 2.x
# requires the psycopg dialect prefix.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# ---------------------------------------------------------------------------
# Engine
#
# pool_pre_ping: validate connections before use (handles Supabase idle drops)
# pool_recycle:  recycle connections after 5 minutes (Supabase closes ~10 min)
# pool_size:     5 persistent connections (suitable for Render starter tier)
# max_overflow:  10 extra connections under burst load
# ---------------------------------------------------------------------------

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_db():
    """Yield a database session and ensure it is closed on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def database_is_ready() -> bool:
    """Return True if the database is reachable, False otherwise."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
