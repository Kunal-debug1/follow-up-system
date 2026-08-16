"""Dependency-free authentication for the self-hosted CRM."""

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


security = HTTPBearer(auto_error=False)


def _setting(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise HTTPException(
            status_code=503,
            detail=f"Server is missing {name}.",
        )
    return value


def _sign(payload: str) -> str:
    return hmac.new(
        _setting("CRM_AUTH_SECRET").encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def create_token(username: str) -> str:
    payload = json.dumps(
        {
            "sub": username,
            "exp": int(time.time()) + 43200,
        },
        separators=(",", ":"),
    )

    encoded = (
        base64.urlsafe_b64encode(payload.encode())
        .decode()
        .rstrip("=")
    )

    return f"{encoded}.{_sign(encoded)}"


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication required",
        )

    authorization = credentials.credentials

    try:
        encoded, signature = authorization.split(".", 1)

        if not hmac.compare_digest(
            signature,
            _sign(encoded),
        ):
            raise ValueError("Invalid signature")

        payload = base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        )

        user = json.loads(payload)

        if user["exp"] < time.time():
            raise ValueError("Expired token")

        return str(user["sub"])

    except (
        ValueError,
        KeyError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
