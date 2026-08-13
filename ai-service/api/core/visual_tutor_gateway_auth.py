"""Authentication boundary for Visual Tutor calls from the TypeScript gateway."""

from __future__ import annotations

import hmac
import json
import logging
import os
from typing import Any

from fastapi import HTTPException, status


logger = logging.getLogger(__name__)


def require_visual_tutor_service(internal_token: str | None) -> None:
    """Authenticate a non-user Visual Tutor gateway operation, such as readiness."""
    expected = os.getenv("VISUAL_TUTOR_INTERNAL_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Visual Tutor gateway is not configured")
    if not internal_token or not hmac.compare_digest(internal_token, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def require_visual_tutor_gateway(
    internal_token: str | None,
    gateway_user_id: str | None,
) -> str:
    """Return the authenticated gateway user identity or reject the request.

    Firebase tokens are verified by the public TypeScript gateway. The AI service
    is deliberately not a second public API: a shared, environment-only internal
    credential authenticates the gateway and the gateway supplies its verified UID.
    """
    require_visual_tutor_service(internal_token)
    user_id = (gateway_user_id or "").strip()
    if not user_id or len(user_id) > 256:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user_id


def enforce_gateway_user(gateway_user_id: str, requested_user_id: str | None) -> str:
    """Reject body/query/path identities that differ from gateway-authenticated UID."""
    if requested_user_id and requested_user_id.strip() != gateway_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: user scope mismatch")
    return gateway_user_id


def emit_visual_tutor_audit_event(
    event: str,
    *,
    user_id: str | None = None,
    request_id: str | None = None,
    **metadata: Any,
) -> None:
    """Emit structured, content-free security telemetry for tutor operations."""
    safe_metadata = {
        key: value
        for key, value in metadata.items()
        if isinstance(value, (str, int, float, bool)) or value is None
    }
    logger.info(
        "visual_tutor_audit %s",
        json.dumps(
            {
                "audit_event": event,
                "user_id": user_id,
                "request_id": request_id,
                **safe_metadata,
            },
            sort_keys=True,
        ),
    )
