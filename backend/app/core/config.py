"""Centralised application configuration loaded from environment variables."""
from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    """Read an integer environment variable with a fallback default."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def get_cors_origins() -> list[str]:
    """
    Return the list of allowed CORS origins.

    Set CORS_ORIGINS to a comma-separated list of full URLs in production:
        CORS_ORIGINS=https://your-frontend.onrender.com
    """
    configured = os.getenv("CORS_ORIGINS", "")
    if not configured:
        return _DEFAULT_CORS_ORIGINS
    return [o.strip() for o in configured.split(",") if o.strip()]


# ---------------------------------------------------------------------------
# Import limits (all configurable via environment variables)
# ---------------------------------------------------------------------------

IMPORT_BATCH_SIZE: int = _int_env("IMPORT_BATCH_SIZE", 250)
MAX_UPLOAD_BYTES: int = _int_env("MAX_UPLOAD_BYTES", 12 * 1024 * 1024)
MAX_WORKSHEET_ROWS: int = _int_env("MAX_WORKSHEET_ROWS", 50_000)

# ---------------------------------------------------------------------------
# Auth (read-only references — secrets are accessed in auth.py only)
# ---------------------------------------------------------------------------

# These keys are listed here for documentation purposes only.
# The actual values are read directly in auth.py using os.getenv().
# Never expose them via the config module to avoid accidental logging.
_AUTH_ENV_KEYS = ("CRM_AUTH_SECRET", "CRM_ADMIN_USERNAME", "CRM_ADMIN_PASSWORD")
