"""
CRM Follow-Up API — FastAPI application entry point.

Render deployment:
    Build:      pip install -r requirements.txt
    Pre-deploy: alembic upgrade head
    Start:      uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers

Health checks:
    GET /health        — liveness (always 200 if process is alive)
    GET /health/ready  — readiness (200 only when database is reachable)
"""
import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .auth import create_token, require_auth
from .core.config import get_cors_origins
from .database import database_is_ready
from .routers import customers, followups, imports
from .schemas import LoginRequest
import os

# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "level": logging.INFO,
        "handlers": ["console"],
    },
})

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("CRM API starting up")
    yield
    logger.info("CRM API shutting down")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CRM Follow-Up API",
    version="1.0.0",
    description="Production CRM for managing customers, follow-ups, and call logs.",
    lifespan=lifespan,
    # Never expose internal error details in API responses
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@app.post("/api/auth/login", tags=["Auth"])
def login(payload: LoginRequest):
    """
    Exchange admin credentials for a session token.

    The token is an HMAC-signed payload — no external JWT library is used.
    Tokens expire after 12 hours.
    """
    expected_username = os.getenv("CRM_ADMIN_USERNAME", "")
    expected_password = os.getenv("CRM_ADMIN_PASSWORD", "")

    if not expected_username or not expected_password:
        raise HTTPException(
            status_code=503,
            detail="Server login credentials are not configured.",
        )

    import hmac
    credentials_valid = (
        hmac.compare_digest(payload.username, expected_username)
        and hmac.compare_digest(payload.password, expected_password)
    )
    if not credentials_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Note: username is intentionally NOT logged (even though it is not a secret
    # on its own) to keep the login flow free of PII in production logs.
    return {"token": create_token(expected_username), "username": expected_username}


# ---------------------------------------------------------------------------
# Protected routers
# ---------------------------------------------------------------------------

app.include_router(customers.router, dependencies=[Depends(require_auth)])
app.include_router(followups.router, dependencies=[Depends(require_auth)])
app.include_router(imports.router, dependencies=[Depends(require_auth)])

# ---------------------------------------------------------------------------
# Health check endpoints (no auth required)
# ---------------------------------------------------------------------------

@app.get("/health", include_in_schema=False)
def health():
    """Liveness check — returns 200 while the process is alive."""
    return {"status": "ok", "service": "crm-api"}


@app.get("/health/ready", include_in_schema=False)
def readiness():
    """Readiness check — returns 200 only when the database is reachable."""
    if not database_is_ready():
        raise HTTPException(status_code=503, detail="Database is unavailable")
    return {"status": "ready"}


@app.get("/api/health", include_in_schema=False)
def legacy_health():
    """Legacy alias for /health — preserved for backward compatibility."""
    return health()
