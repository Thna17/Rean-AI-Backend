from __future__ import annotations

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from fastapi import HTTPException

from api.routes import visual_tutor_scan


def _png_bytes(width: int = 320, height: int = 320) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_scan_rejects_unsupported_type_and_small_images() -> None:
    with pytest.raises(HTTPException) as unsupported:
        visual_tutor_scan._validate_image(_png_bytes(), "application/pdf")
    assert unsupported.value.status_code == 415

    with pytest.raises(HTTPException) as too_small:
        visual_tutor_scan._validate_image(_png_bytes(100, 100), "image/png")
    assert too_small.value.status_code == 422

    with pytest.raises(HTTPException) as too_large:
        visual_tutor_scan._validate_image(_png_bytes(4000, 4000), "image/png")
    assert too_large.value.status_code == 413


def test_scan_rejects_empty_and_unreadable_image_bytes() -> None:
    with pytest.raises(HTTPException) as empty:
        visual_tutor_scan._validate_image(b"", "image/png")
    assert empty.value.status_code == 413

    with pytest.raises(HTTPException) as unreadable:
        visual_tutor_scan._validate_image(b"not-a-real-image", "image/png")
    assert unreadable.value.status_code == 415


def test_scan_rejects_an_image_that_does_not_match_its_declared_mime_type() -> None:
    with pytest.raises(HTTPException) as mismatch:
        visual_tutor_scan._validate_image(_png_bytes(), "image/jpeg")
    assert mismatch.value.status_code == 415


def test_scan_requires_a_configured_internal_gateway_token(monkeypatch) -> None:
    monkeypatch.delenv("VISUAL_TUTOR_INTERNAL_TOKEN", raising=False)
    with pytest.raises(HTTPException) as missing:
        visual_tutor_scan._verify_gateway_token(None)
    assert missing.value.status_code == 503

    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "internal-secret")
    with pytest.raises(HTTPException) as invalid:
        visual_tutor_scan._verify_gateway_token("wrong")
    assert invalid.value.status_code == 403


def test_scan_endpoint_uses_gateway_identity_and_returns_only_ocr_text(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(visual_tutor_scan.router)
    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "internal-secret")
    monkeypatch.setattr(
        visual_tutor_scan,
        "_extract_with_gemini",
        lambda _image: visual_tutor_scan.VisualTutorScanResult(
            detected_text="សមីការ 2x + 5 = 15",
            confidence=0.9,
            language="mixed",
            math_expression_candidates=["2x + 5 = 15"],
        ),
    )

    with TestClient(app) as client:
        forbidden = client.post("/api/v1/visual_tutor/scan", content=_png_bytes(), headers={"content-type": "image/png"})
        accepted = client.post(
            "/api/v1/visual_tutor/scan",
            content=_png_bytes(),
            headers={
                "content-type": "image/png",
                "x-visual-tutor-internal-token": "internal-secret",
                "x-visual-tutor-user-id": "firebase-student-1",
            },
        )

    assert forbidden.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json()["detected_text"] == "សមីការ 2x + 5 = 15"
    assert accepted.json()["math_expression_candidates"] == ["2x + 5 = 15"]


def test_scan_extracts_exact_text_from_real_ocr_provider_response(monkeypatch) -> None:
    class _Response:
        text = '{"detected_text":"ដោះស្រាយ 2x + 5 = 15", "confidence":0.91, "language":"mixed"}'

    class _Models:
        def generate_content(self, **_kwargs):
            return _Response()

    class _Client:
        models = _Models()

    monkeypatch.setenv("GEMINI_API_KEY", "configured-for-test")
    monkeypatch.setattr(visual_tutor_scan.genai, "Client", lambda **_kwargs: _Client())

    image = visual_tutor_scan._validate_image(_png_bytes(), "image/png")
    result = visual_tutor_scan._extract_with_gemini(image)

    # The service returns provider text verbatim for student confirmation; it
    # does not fabricate or solve an equation itself.
    assert result.detected_text == "ដោះស្រាយ 2x + 5 = 15"
    assert result.language == "mixed"
    assert result.confidence == 0.91


def test_scan_does_not_complete_or_normalize_ocr_math(monkeypatch) -> None:
    class _Response:
        text = '{"detected_text":"2x + 5 =", "confidence":0.8, "language":"en"}'

    class _Models:
        def generate_content(self, **_kwargs):
            return _Response()

    class _Client:
        models = _Models()

    monkeypatch.setenv("GEMINI_API_KEY", "configured-for-test")
    monkeypatch.setattr(visual_tutor_scan.genai, "Client", lambda **_kwargs: _Client())

    result = visual_tutor_scan._extract_with_gemini(
        visual_tutor_scan._validate_image(_png_bytes(), "image/png")
    )
    assert result.detected_text == "2x + 5 ="
    assert result.math_expression_candidates == ["2x + 5 ="]


def test_scan_maps_provider_failure_to_retryable_ocr_error(monkeypatch) -> None:
    class _Models:
        def generate_content(self, **_kwargs):
            raise RuntimeError("provider unavailable")

    class _Client:
        models = _Models()

    monkeypatch.setenv("GEMINI_API_KEY", "configured-for-test")
    monkeypatch.setattr(visual_tutor_scan.genai, "Client", lambda **_kwargs: _Client())
    with pytest.raises(HTTPException) as failed:
        visual_tutor_scan._extract_with_gemini(
            visual_tutor_scan._validate_image(_png_bytes(), "image/png")
        )
    assert failed.value.status_code == 503
