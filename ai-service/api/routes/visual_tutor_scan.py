"""Authenticated-gateway image intake for Visual Tutor problem scans.

The image is processed in memory and is never written to disk or stored with
the tutor session. The student must confirm the extracted text in Flutter.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
from typing import Literal

from google import genai
from google.genai import types
from fastapi import APIRouter, Header, HTTPException, Request, status
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from api.core.visual_tutor_gateway_auth import (
    emit_visual_tutor_audit_event,
    require_visual_tutor_gateway,
)


router = APIRouter(prefix="/api/v1/visual_tutor", tags=["Visual Tutor"])

_MAX_BYTES = 8 * 1024 * 1024
_MAX_PIXELS = 12_000_000
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
_OCR_TIMEOUT_SECONDS = 25


class VisualTutorScanResult(BaseModel):
    detected_text: str
    confidence: float
    language: Literal["en", "km", "mixed", "unknown"]
    math_expression_candidates: list[str] = []


def _verify_gateway_token(value: str | None) -> None:
    # Compatibility wrapper for internal callers; endpoint handlers additionally
    # require a gateway-bound user identity through require_visual_tutor_gateway.
    require_visual_tutor_gateway(value, "internal")


def _validate_image(image_bytes: bytes, content_type: str) -> Image.Image:
    if content_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Use a JPG, PNG, or WEBP image")
    if not image_bytes or len(image_bytes) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image must be smaller than 8 MB")
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()
        image = Image.open(io.BytesIO(image_bytes))
        expected_format = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[content_type]
        if image.format != expected_format:
            raise HTTPException(status_code=415, detail="Image file does not match its declared type")
        if image.width < 160 or image.height < 160:
            raise HTTPException(status_code=422, detail="Image is too small to read. Use a clearer photo.")
        if image.width * image.height > _MAX_PIXELS:
            raise HTTPException(status_code=413, detail="Image dimensions are too large")
        return image.convert("RGB")
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=415, detail="This file is not a readable image") from exc


def _extract_with_gemini(image: Image.Image) -> VisualTutorScanResult:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Image reading is not configured")
    client = genai.Client(api_key=api_key)
    prompt = """Read the student's worksheet image. Extract only the question/problem text exactly as visible.
Preserve Khmer and English. Do not solve, complete, infer, or correct the math.
Return strict JSON: {\"detected_text\": string, \"confidence\": number 0..1, \"language\": \"en\"|\"km\"|\"mixed\"|\"unknown\"}.
If unreadable, return an empty detected_text with confidence 0."""
    try:
        response = client.models.generate_content(
            model=os.getenv("VISUAL_TUTOR_OCR_MODEL", "gemini-2.0-flash"),
            contents=[prompt, image],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        raw = (response.text or "").strip()
        payload = json.loads(raw)
    except Exception as exc:
        # Do not mistake a provider failure for unreadable student content.
        raise HTTPException(status_code=503, detail="Image reading is temporarily unavailable. Please try again.") from exc
    text = str(payload.get("detected_text") or "").strip()
    confidence = payload.get("confidence", 0)
    language = str(payload.get("language") or "unknown").lower()
    if language not in {"en", "km", "mixed", "unknown"}:
        language = "unknown"
    if not text or len(text) > 4000:
        raise HTTPException(status_code=422, detail="We could not read a question. Use a sharper, well-lit image.")
    # Reject control-heavy model output; the student still edits every accepted result.
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    # Candidates are copied from OCR text only; they are never normalized or
    # completed by the model. The learner must still edit and confirm the text.
    candidates = [
        match.strip()
        for match in re.findall(r"[0-9a-zA-Z()\s+\-*/^=.]{3,}", text)
        if "=" in match and len(match.strip()) <= 240
    ][:5]
    return VisualTutorScanResult(
        detected_text=text,
        confidence=max(0.0, min(1.0, float(confidence))),
        language=language,
        math_expression_candidates=candidates,
    )


@router.post("/scan", response_model=VisualTutorScanResult)
async def scan_visual_tutor_problem(
    request: Request,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
) -> VisualTutorScanResult:
    # Only the authenticated TypeScript gateway supplies this header. Keep this
    # router private to the gateway in deployment; it never accepts user_id body/query input.
    user_id = require_visual_tutor_gateway(x_visual_tutor_internal_token, x_visual_tutor_user_id)
    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].lower()
    image_bytes = await request.body()
    image = _validate_image(image_bytes, content_type)
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_extract_with_gemini, image),
            timeout=_OCR_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Image reading timed out. Please try again.",
        ) from exc
    finally:
        # Intake is memory-only. Explicitly release decoded pixels on every
        # success, error, and timeout path.
        image.close()
    emit_visual_tutor_audit_event(
        "visual_tutor_scan_completed",
        user_id=user_id,
        content_type=content_type,
        bytes=len(image_bytes),
        language=result.language,
    )
    return result
