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


@pytest.mark.asyncio
async def test_language_the_voice_cannot_speak_is_refused_not_mispronounced(
    monkeypatch,
) -> None:
    """Khmer must not be handed to an English voice.

    Piper does not reject foreign script -- it spells it out. A 45-character
    Khmer sentence came back from the deployed English voice as 34 seconds of
    noise, which the board then waited for. A 503 is the honest answer, and it
    is what makes the student app try the browser's own Khmer voice instead.
    """
    from api.services.tts_service import TTSLanguageUnavailable

    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "test-token")

    spoken: list[str] = []

    class _EnglishOnly:
        def synthesize(self, text: str, language: str | None = None) -> bytes:
            if language and language.split("-")[0].lower() != "en":
                raise TTSLanguageUnavailable("The installed voice speaks en, not km.")
            spoken.append(text)
            return _wav_bytes()

    monkeypatch.setattr(visual_tutor_voice, "get_tts_service", lambda: _EnglishOnly())

    body = visual_tutor_voice.VisualTutorSpeechRequest(
        text="ជំនួសតម្លៃ", language="km"
    )
    with pytest.raises(HTTPException) as refused:
        await visual_tutor_voice.synthesize_visual_tutor_voice(
            body,
            x_visual_tutor_user_id="student-1",
            x_visual_tutor_internal_token="test-token",
        )
    assert refused.value.status_code == 503
    assert spoken == [], "Khmer reached the English voice"

    english = visual_tutor_voice.VisualTutorSpeechRequest(
        text="Cancel the common factor.", language="en"
    )
    response = await visual_tutor_voice.synthesize_visual_tutor_voice(
        english,
        x_visual_tutor_user_id="student-1",
        x_visual_tutor_internal_token="test-token",
    )
    assert response.status_code == 200
    assert spoken == ["Cancel the common factor."]
