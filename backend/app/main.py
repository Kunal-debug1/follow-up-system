from __future__ import annotations

"""
CRM Follow-Up API
-----------------

Main FastAPI application.

Responsibilities:
    - Create the FastAPI application
    - Configure CORS
    - Handle administrator login
    - Register protected CRM routers
    - Provide health/readiness endpoints

Production:
    Backend:
        https://follow-up-system.onrender.com

    Frontend:
        https://follow-up-system-1.onrender.com
"""

import hmac
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .auth import create_token, require_auth
from .database import database_is_ready
from .routers import customers, followups, imports
from .schemas import LoginRequest


# ============================================================
# APPLICATION SETTINGS
# ============================================================

APP_TITLE = "CRM Follow-Up API"
APP_VERSION = "1.0.0"

# Production frontend.
PRODUCTION_FRONTEND = "https://follow-up-system-1.onrender.com"

# Local development frontends.
LOCAL_FRONTENDS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


# ============================================================
# CORS
# ============================================================

def get_cors_origins() -> list[str]:
    """
    Return the allowed frontend origins.

    Render environment variable:

        CORS_ORIGINS=https://follow-up-system-1.onrender.com

    Multiple origins can be separated by commas.

    Example:

        CORS_ORIGINS=https://follow-up-system-1.onrender.com,http://localhost:5173
    """

    # Always allow the known production frontend.
    origins = set(LOCAL_FRONTENDS)
    origins.add(PRODUCTION_FRONTEND)

    # Optional Render environment variable.
    configured_origins = os.getenv(
        "CORS_ORIGINS",
        "",
    ).strip()

    if configured_origins:
        for origin in configured_origins.split(","):
            origin = origin.strip().rstrip("/")

            if origin:
                origins.add(origin)

    return sorted(origins)


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Application startup/shutdown lifecycle.

    Keep this lightweight because the application runs on
    Render's free instance.
    """

    # Startup
    yield

    # Shutdown
    # No persistent resources need to be closed here currently.


# ============================================================
# CREATE FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    lifespan=lifespan,
)


# ============================================================
# CORS MIDDLEWARE
# ============================================================

app.add_middleware(
    CORSMiddleware,

    # Explicitly allow the CRM frontend.
    allow_origins=get_cors_origins(),

    # Required for authenticated browser requests.
    allow_credentials=True,

    # Allow GET, POST, PATCH, DELETE, OPTIONS, etc.
    allow_methods=["*"],

    # Allow Authorization, Content-Type, and multipart headers.
    allow_headers=["*"],
)


# ============================================================
# AUTHENTICATION
# ============================================================

@app.post(
    "/api/auth/login",
    tags=["Authentication"],
)
def login(payload: LoginRequest):
    """
    Authenticate the CRM administrator.

    Credentials are stored as Render environment variables:

        CRM_ADMIN_USERNAME
        CRM_ADMIN_PASSWORD

    A signed token is returned after successful authentication.
    """

    expected_username = os.getenv(
        "CRM_ADMIN_USERNAME",
        "",
    )

    expected_password = os.getenv(
        "CRM_ADMIN_PASSWORD",
        "",
    )

    # --------------------------------------------------------
    # Check server configuration
    # --------------------------------------------------------

    if not expected_username or not expected_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Server login credentials are not configured."
            ),
        )

    # --------------------------------------------------------
    # Compare credentials securely
    # --------------------------------------------------------

    username_valid = hmac.compare_digest(
        payload.username,
        expected_username,
    )

    password_valid = hmac.compare_digest(
        payload.password,
        expected_password,
    )

    if not (username_valid and password_valid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # --------------------------------------------------------
    # Create authentication token
    # --------------------------------------------------------

    token = create_token(
        expected_username,
    )

    return {
        "token": token,
        "username": expected_username,
    }


# ============================================================
# PROTECTED CRM ROUTERS
# ============================================================

# Every endpoint inside these routers requires:
#
# Authorization: Bearer <token>
#
# Login remains public because users need to authenticate first.

app.include_router(
    customers.router,
    dependencies=[Depends(require_auth)],
)

app.include_router(
    followups.router,
    dependencies=[Depends(require_auth)],
)

app.include_router(
    imports.router,
    dependencies=[Depends(require_auth)],
)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get(
    "/health",
    include_in_schema=False,
)
def health():
    """
    Basic health check.

    Used by Render to verify that the application is running.

    This endpoint intentionally does not require authentication.
    """

    return {
        "status": "ok",
        "service": "crm-api",
    }


# ============================================================
# DATABASE READINESS CHECK
# ============================================================

@app.get(
    "/health/ready",
    include_in_schema=False,
)
def readiness():
    """
    Check whether the API and PostgreSQL database are ready.

    Returns:
        200 -> database available
        503 -> database unavailable
    """

    if not database_is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        )

    return {
        "status": "ready",
        "database": "connected",
    }


# ============================================================
# LEGACY API HEALTH ENDPOINT
# ============================================================

@app.get(
    "/api/health",
    include_in_schema=False,
)
def legacy_health():
    """
    Backward-compatible health endpoint.

    Some older frontend code may still call:

        /api/health
    """

    return health()
