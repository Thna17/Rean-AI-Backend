from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.core.visual_tutor_gateway_auth import (
    enforce_gateway_user,
    require_visual_tutor_gateway,
)


def test_gateway_identity_requires_configured_secret_and_user(monkeypatch) -> None:
    monkeypatch.delenv("VISUAL_TUTOR_INTERNAL_TOKEN", raising=False)
    with pytest.raises(HTTPException) as missing:
        require_visual_tutor_gateway(None, "student-a")
    assert missing.value.status_code == 503

    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "gateway-secret")
    with pytest.raises(HTTPException) as missing_secret:
        require_visual_tutor_gateway(None, "student-a")
    assert missing_secret.value.status_code == 403

    with pytest.raises(HTTPException) as wrong_secret:
        require_visual_tutor_gateway("wrong", "student-a")
    assert wrong_secret.value.status_code == 403

    with pytest.raises(HTTPException) as no_user:
        require_visual_tutor_gateway("gateway-secret", None)
    assert no_user.value.status_code == 401


def test_gateway_identity_blocks_cross_user_body_query_and_path_scopes(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "gateway-secret")
    user_id = require_visual_tutor_gateway("gateway-secret", "student-a")
    assert enforce_gateway_user(user_id, "student-a") == "student-a"
    with pytest.raises(HTTPException) as cross_user:
        enforce_gateway_user(user_id, "student-b")
    assert cross_user.value.status_code == 403
