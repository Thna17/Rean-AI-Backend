"""The tutor must not pretend to speak a language its voice cannot say.

Two faults made the deployed tutor silent or worse, and both were invisible
because the service answered 200 either way.

The first: when no Piper model is installed, `synthesize` returned one second
of digital silence dressed up as speech. The client cannot tell that from a
real utterance, so its browser-speech fallback never engaged and the student
simply heard nothing.

The second: the route accepted a `language` and then dropped it, so every
language went through whatever single voice was loaded. Khmer text sent to an
English voice does not fail -- the phonemiser spells the characters out, and a
45-character Khmer sentence came back as 34 seconds of noise. That is worse
than silence: it is 34 seconds of nonsense the board now waits for.

Both should fail loudly instead, so the client falls back to browser speech,
which does have Khmer voices on some platforms.
"""

from __future__ import annotations

import pytest

from api.services.tts_service import TTSLanguageUnavailable, TTSUnavailable, TTSService


class _FakeChunk:
    sample_channels = 1
    sample_width = 2
    sample_rate = 22050
    audio_int16_bytes = b"\x01\x02" * 2205


class _FakeVoice:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def synthesize(self, text: str):
        self.spoken.append(text)
        return [_FakeChunk()]


@pytest.fixture()
def service() -> TTSService:
    tts = TTSService()
    tts._voice = _FakeVoice()  # noqa: SLF001 - substituting the model under test
    tts._voice_language = "en"  # noqa: SLF001
    return tts


def test_speaks_text_in_the_voice_s_own_language(service: TTSService) -> None:
    audio = service.synthesize("Cancel the common factor.", language="en")
    assert audio.startswith(b"RIFF")
    assert len(audio) > 44


def test_a_regional_tag_still_matches_the_voice(service: TTSService) -> None:
    # The client sends "en"; the voice is en_US. Those are the same language.
    assert service.synthesize("Substitute x equals two.", language="en_US")
    assert service.synthesize("Substitute x equals two.", language="en-GB")


def test_no_language_asked_for_is_left_to_the_voice(service: TTSService) -> None:
    # Older callers pass text only. They keep working.
    assert service.synthesize("Any text at all")


def test_khmer_is_refused_rather_than_spelled_out_in_english(
    service: TTSService,
) -> None:
    with pytest.raises(TTSLanguageUnavailable) as raised:
        service.synthesize("ជំនួសតម្លៃ", language="km")
    assert "km" in str(raised.value)
    # Nothing reached the English voice, so no 34 seconds of noise was produced.
    assert service._voice.spoken == []  # noqa: SLF001


def test_a_missing_model_fails_instead_of_returning_silence() -> None:
    tts = TTSService()
    # A machine with no model installed: _load_voice finds nothing.
    tts._load_voice = lambda: None  # type: ignore[method-assign]  # noqa: SLF001
    with pytest.raises(TTSUnavailable):
        tts.synthesize("Cancel the common factor.", language="en")


def test_silence_is_never_offered_as_speech() -> None:
    # The old fallback is gone: there is no code path that answers a request
    # for speech with a silent buffer.
    assert not hasattr(TTSService, "_generate_silent_wav")
