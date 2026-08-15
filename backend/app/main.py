import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .routers import customers, followups, imports
from .database import database_is_ready
from .auth import create_token, require_auth
from .schemas import LoginRequest

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def get_cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS", "")
    if not configured_origins:
        return DEFAULT_CORS_ORIGINS
    return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield

app = FastAPI(
    title="CRM Follow-Up API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/auth/login")
def login(payload: LoginRequest):
    expected_username = os.getenv("CRM_ADMIN_USERNAME", "")
    expected_password = os.getenv("CRM_ADMIN_PASSWORD", "")
    if not expected_username or not expected_password:
        raise HTTPException(status_code=503, detail="Server login credentials are not configured.")
    if not (__import__("hmac").compare_digest(payload.username, expected_username) and __import__("hmac").compare_digest(payload.password, expected_password)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    return {"token": create_token(expected_username), "username": expected_username}


app.include_router(customers.router, dependencies=[Depends(require_auth)])
app.include_router(followups.router, dependencies=[Depends(require_auth)])
app.include_router(imports.router, dependencies=[Depends(require_auth)])

@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "service": "crm-api"}


@app.get("/health/ready", include_in_schema=False)
def readiness():
    if not database_is_ready():
        raise HTTPException(status_code=503, detail="Database is unavailable")
    return {"status": "ready"}


@app.get("/api/health", include_in_schema=False)
def legacy_health():
    return health()
