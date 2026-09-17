"""Fail-closed deployment configuration tests for the Visual Tutor."""

import pytest
from pydantic import ValidationError
from fastapi import HTTPException

from api.core.config import Settings
from api.core import visual_tutor_gateway_auth
from api.routes import visual_tutor


def _production_settings(**overrides):
    values = {
        "ENVIRONMENT": "production",
        "APP_ENV": "production",
        "DEBUG": False,
        "SECRET_KEY": "s" * 32,
        "MONGODB_URI": "mongodb+srv://user:password@cluster.example.net/ai_tutor",
        "MONGODB_DATABASE": "ai_tutor",
        "ALLOWED_ORIGINS": ["https://app.example.com"],
        "VISUAL_TUTOR_INTERNAL_TOKEN": "t" * 32,
        "VISUAL_TUTOR_LLM_PROVIDER": "openrouter",
        "OPENROUTER_API_KEY": "test-openrouter-key",
        "GEMINI_API_KEY": "test-gemini-key",
        "STT_MODEL_NAME": "base.en",
        "TTS_MODEL_PATH": "models/piper/voice.onnx",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_visual_tutor_configuration_is_accepted_only_when_complete():
    settings = _production_settings()

    assert settings.VISUAL_TUTOR_LLM_PROVIDER == "openrouter"
    assert settings.VISUAL_TUTOR_INTERNAL_TOKEN == "t" * 32


def test_production_allows_deepseek_without_an_openrouter_key():
    settings = _production_settings(
        VISUAL_TUTOR_LLM_PROVIDER="deepseek",
        DEEPSEEK_API_KEY="test-deepseek-key",
        OPENROUTER_API_KEY="",
    )

    assert settings.VISUAL_TUTOR_LLM_PROVIDER == "deepseek"


def test_production_rejects_deepseek_without_a_real_key():
    with pytest.raises(ValidationError):
        _production_settings(
            VISUAL_TUTOR_LLM_PROVIDER="deepseek",
            DEEPSEEK_API_KEY="",
            OPENROUTER_API_KEY="",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("VISUAL_TUTOR_INTERNAL_TOKEN", "short"),
        ("MONGODB_URI", "mongodb://localhost:27017"),
        ("OPENROUTER_API_KEY", ""),
        ("GEMINI_API_KEY", ""),
        ("ALLOWED_ORIGINS", ["*"]),
    ],
)
def test_production_visual_tutor_configuration_rejects_missing_or_unsafe_values(field, value):
    with pytest.raises(ValidationError):
        _production_settings(**{field: value})


def test_staging_uses_the_same_fail_closed_visual_tutor_rules():
    with pytest.raises(ValidationError):
        _production_settings(ENVIRONMENT="staging", VISUAL_TUTOR_INTERNAL_TOKEN="")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("APP_ENV", "development"),
        ("ALLOW_DEVELOPMENT_FALLBACKS", True),
        ("VISUAL_TUTOR_LLM_PROVIDER", "ollama"),
        ("VISUAL_TUTOR_LLM_PROVIDER", "codex_cli"),
        ("VISUAL_TUTOR_LLM_PROVIDER", "auto"),
        ("OPENROUTER_API_KEY", "your_api_key"),
    ],
)
def test_production_rejects_development_or_ambiguous_visual_tutor_configuration(field, value):
    with pytest.raises(ValidationError):
        _production_settings(**{field: value})


def test_private_readiness_rejects_missing_or_wrong_gateway_token(monkeypatch):
    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "t" * 32)

    with pytest.raises(HTTPException) as missing:
        visual_tutor_gateway_auth.require_visual_tutor_service(None)
    assert missing.value.status_code == 403

    with pytest.raises(HTTPException) as wrong:
        visual_tutor_gateway_auth.require_visual_tutor_service("wrong")
    assert wrong.value.status_code == 403


@pytest.mark.asyncio
async def test_private_readiness_never_reports_healthy_without_mongo_or_ai(monkeypatch):
    class BrokenAdmin:
        async def command(self, _name):
            raise RuntimeError("Mongo unavailable")

    class BrokenClient:
        admin = BrokenAdmin()

    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "t" * 32)
    monkeypatch.setattr(visual_tutor.mongodb_manager, "_client", BrokenClient())
    monkeypatch.setattr(visual_tutor.settings, "VISUAL_TUTOR_LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(visual_tutor.settings, "OPENROUTER_API_KEY", "")

    response = await visual_tutor.visual_tutor_readiness("t" * 32)

    assert response.status_code == 503
    assert b'"status":"unavailable"' in response.body


@pytest.mark.asyncio
async def test_private_readiness_reports_degraded_for_optional_ocr_dependency(monkeypatch):
    class HealthyAdmin:
        async def command(self, _name):
            return {"ok": 1}

    class HealthyClient:
        admin = HealthyAdmin()

    async def provider_ready():
        return True

    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "t" * 32)
    monkeypatch.setattr(visual_tutor.mongodb_manager, "_client", HealthyClient())
    monkeypatch.setattr(visual_tutor, "_llm_provider_ready", provider_ready)
    monkeypatch.setattr(visual_tutor.settings, "VISUAL_TUTOR_OCR_ENABLED", False)

    response = await visual_tutor.visual_tutor_readiness("t" * 32)

    assert response.status_code == 200
    assert b'"status":"degraded"' in response.body


@pytest.mark.asyncio
async def test_public_health_reports_degraded_without_exposing_configuration(monkeypatch):
    # Import after the pure Settings validation tests: api.main loads the
    # developer dotenv file as part of normal application boot.
    from api import main as ai_main

    class HealthyAdmin:
        async def command(self, _name):
            return {"ok": 1}

    class HealthyClient:
        admin = HealthyAdmin()

    async def provider_ready():
        return True

    monkeypatch.setattr(ai_main.mongodb_manager, "_client", HealthyClient())
    monkeypatch.setattr(visual_tutor, "_llm_provider_ready", provider_ready)
    monkeypatch.setattr(ai_main.settings, "VISUAL_TUTOR_OCR_ENABLED", False)
    monkeypatch.setattr(ai_main.settings, "OPENROUTER_API_KEY", "do-not-expose-me")

    payload = await ai_main.health_check()

    assert payload["status"] == "degraded"
    assert payload["dependencies"]["visual_tutor_ai"] == "healthy"
    assert "do-not-expose-me" not in str(payload)
