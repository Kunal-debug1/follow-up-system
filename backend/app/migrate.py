"""Idempotent schema bootstrap for a new Supabase PostgreSQL database."""
from .database import Base, engine
from . import models  # noqa: F401


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine, checkfirst=True)
