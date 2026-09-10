"""Internal-gateway voice transcription for Visual Tutor."""
from __future__ import annotations

import os
import tempfile
import asyncio
import io
import wave

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api.core.visual_tutor_gateway_auth import (
    emit_visual_tutor_audit_event,
    require_visual_tutor_gateway,
)
from api.services.stt_service import get_stt_service
from api.services.tts_service import get_tts_service

router = APIRouter(prefix="/api/v1/visual_tutor", tags=["Visual Tutor"])

_MAX_AUDIO_BYTES = 12 * 1024 * 1024
_MIN_AUDIO_SECONDS = .2
_MAX_AUDIO_SECONDS = 180
_STT_TIMEOUT_SECONDS = 35


class VisualTutorSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="en", max_length=16)


_ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/mpeg",   # MP3
    "audio/mp4",    # M4A
    "audio/m4a",
    "audio/ogg",
    "audio/webm",
    "audio/aac",
}

_AUDIO_EXTENSIONS = {
    "audio/wav": ".wav",
    "audio/wave": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
    "audio/aac": ".aac",
}


def _validate_audio(audio: bytes, content_type: str) -> str:
    """Validate audio bytes and return the file extension to use."""
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized not in _ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            413,
            "Use WAV, MP3, M4A, OGG, WebM, or AAC audio",
        )
    if len(audio) < 100:
        raise HTTPException(413, "Recording is too short")
    if len(audio) > _MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording is too large (max 12 MB)")
    # WAV-specific duration check for uncompressed audio only
    if normalized in {"audio/wav", "audio/wave", "audio/x-wav"}:
        if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
            raise HTTPException(422, "This recording is not valid WAV audio")
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav:
                duration = wav.getnframes() / wav.getframerate()
                if wav.getnchannels() not in {1, 2} or wav.getframerate() <= 0:
                    raise wave.Error("unsupported WAV parameters")
        except (wave.Error, EOFError, ZeroDivisionError) as exc:
            raise HTTPException(422, "This recording is not valid WAV audio") from exc
        if duration < _MIN_AUDIO_SECONDS or duration > _MAX_AUDIO_SECONDS:
            raise HTTPException(422, "Recording must be between 0.2 seconds and 3 minutes")
    return _AUDIO_EXTENSIONS.get(normalized, ".wav")


def _validate_wav(audio: bytes) -> None:
    """Compatibility wrapper for WAV-only callers and focused validation tests.

    The production endpoint supports several safe audio containers via
    :func:`_validate_audio`; this helper intentionally keeps the same strict
    WAV checks rather than creating a second validation path.
    """
    _validate_audio(audio, "audio/wav")


@router.post("/transcribe")
async def transcribe_visual_tutor_voice(
    request: Request,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
):
    user_id = require_visual_tutor_gateway(x_visual_tutor_internal_token, x_visual_tutor_user_id)
    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    audio = await request.body()
    extension = _validate_audio(audio, content_type)
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as file:
            file.write(audio)
            path = file.name
        try:
            result = await asyncio.wait_for(
                get_stt_service().transcribe_file(path), timeout=_STT_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError as exc:
            raise HTTPException(504, "Transcription timed out. Please try again.") from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, "Voice transcription is temporarily unavailable. Please try again.") from exc
        text = str(result.get("text") or "").strip()
        if not text:
            raise HTTPException(422, "We could not hear a question. Try again in a quieter place.")
        # Never log or persist raw audio/transcript in this transport endpoint.
        emit_visual_tutor_audit_event(
            "visual_tutor_stt_completed", user_id=user_id, bytes=len(audio)
        )
        return {"transcript": text, "metadata": {"audio_stored": False}}
    finally:
        if path:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


@router.post("/synthesize")
async def synthesize_visual_tutor_voice(
    body: VisualTutorSpeechRequest,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
) -> Response:
    user_id = require_visual_tutor_gateway(x_visual_tutor_internal_token, x_visual_tutor_user_id)
    try:
        audio = await asyncio.wait_for(
            asyncio.to_thread(get_tts_service().synthesize, body.text.strip()), timeout=30
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, "Tutor speech timed out. Please try again.") from exc
    except Exception as exc:
        raise HTTPException(503, "Tutor speech is temporarily unavailable.") from exc
    if not audio:
        raise HTTPException(503, "Tutor speech is temporarily unavailable.")
    emit_visual_tutor_audit_event("visual_tutor_tts_completed", user_id=user_id, characters=len(body.text))
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
