from __future__ import annotations

import asyncio
import io
import wave

import pytest
from fastapi import HTTPException

from api.routes import visual_tutor_voice


def _wav_bytes(seconds: float = 1.0) -> bytes:
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(b"\0\0" * int(seconds * 16_000))
    return stream.getvalue()


def test_validates_wav_container_and_duration() -> None:
    visual_tutor_voice._validate_wav(_wav_bytes())
    with pytest.raises(HTTPException) as malformed:
        visual_tutor_voice._validate_wav(b"not-a-wav" * 20)
    assert malformed.value.status_code == 422
    with pytest.raises(HTTPException) as too_short:
        visual_tutor_voice._validate_wav(_wav_bytes(.1))
    assert too_short.value.status_code == 422


@pytest.mark.asyncio
async def test_stt_timeout_returns_a_recoverable_error_and_cleans_temp_file(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "test-token")
    monkeypatch.setattr(visual_tutor_voice, "_STT_TIMEOUT_SECONDS", .001)

    class _Service:
        async def transcribe_file(self, _path: str):
            await asyncio.sleep(.02)
            return {"text": "ignored"}

    monkeypatch.setattr(visual_tutor_voice, "get_stt_service", lambda: _Service())

    class _Request:
        headers = {"content-type": "audio/wav"}

        async def body(self):
            return _wav_bytes()

    with pytest.raises(HTTPException) as timed_out:
        await visual_tutor_voice.transcribe_visual_tutor_voice(
            _Request(),
            x_visual_tutor_user_id="student-1",
            x_visual_tutor_internal_token="test-token",
        )
    assert timed_out.value.status_code == 504


@pytest.mark.asyncio
async def test_tts_unavailable_is_a_safe_recoverable_error(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "test-token")

    class _Tts:
        def synthesize(self, _text: str) -> bytes:
            raise RuntimeError("piper unavailable")

    monkeypatch.setattr(visual_tutor_voice, "get_tts_service", lambda: _Tts())
    with pytest.raises(HTTPException) as unavailable:
        await visual_tutor_voice.synthesize_visual_tutor_voice(
            visual_tutor_voice.VisualTutorSpeechRequest(text="Try subtracting five."),
            x_visual_tutor_user_id="student-1",
            x_visual_tutor_internal_token="test-token",
        )
    assert unavailable.value.status_code == 503
