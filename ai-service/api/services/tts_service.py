"""Text-to-Speech (TTS) service using Piper."""

from __future__ import annotations

import io
import logging
import os
import wave
from pathlib import Path
from typing import Optional

from api.core.config import settings

# Absolute path to the ai-service root (2 levels up from api/services/)
_SERVICE_ROOT = Path(__file__).resolve().parent.parent.parent

logger = logging.getLogger(__name__)


class TTSUnavailable(RuntimeError):
    """No voice could be loaded, so nothing can be spoken."""


class TTSLanguageUnavailable(TTSUnavailable):
    """The loaded voice does not speak the language that was asked for."""


def _language_of(tag: str | None) -> str | None:
    """The bare language of a tag: en_US, en-GB and en all reduce to "en"."""
    if not tag:
        return None
    return tag.strip().replace("-", "_").split("_")[0].lower() or None


class TTSService:
    def __init__(self) -> None:
        self._voice = None
        self._voice_language: Optional[str] = None

    def _load_voice(self):
        if self._voice is not None:
            return self._voice

        try:
            from piper import PiperVoice  # type: ignore
        except Exception as exc:  # pragma: no cover - runtime dependency
            logger.warning(
                "Piper TTS is not installed. TTS is disabled. "
                "Add 'piper-tts' to requirements to enable voice."
            )
            return None

        model_path = settings.TTS_MODEL_PATH
        config_path = settings.TTS_CONFIG_PATH

        # Support both absolute model paths and voice IDs like "en_US-lessac-medium".
        # Use _SERVICE_ROOT (absolute) so paths resolve correctly regardless of CWD.
        model_candidates = [
            model_path,
            f"{model_path}.onnx",
            str(_SERVICE_ROOT / "models" / "piper" / model_path),
            str(_SERVICE_ROOT / "models" / "piper" / f"{model_path}.onnx"),
            os.path.join("models", "piper", model_path),
            os.path.join("models", "piper", f"{model_path}.onnx"),
        ]

        resolved_model_path = next(
            (candidate for candidate in model_candidates if candidate and os.path.exists(candidate)),
            model_path,
        )

        resolved_config_path: Optional[str] = None
        if config_path:
            resolved_config_path = config_path
        else:
            json_candidates = [
                f"{resolved_model_path}.json",
                resolved_model_path.replace(".onnx", ".onnx.json"),
                str(_SERVICE_ROOT / "models" / "piper" / f"{Path(model_path).stem}.onnx.json"),
            ]
            resolved_config_path = next(
                (candidate for candidate in json_candidates if os.path.exists(candidate)),
                None,
            )

        logger.info(f"Loading TTS model: {resolved_model_path}")
        if not os.path.exists(resolved_model_path):
            logger.warning(
                f"TTS model file not found at {resolved_model_path}. "
                "TTS is disabled. Please download the model files to models/piper/."
            )
            return None

        self._voice = PiperVoice.load(
            resolved_model_path,
            config_path=resolved_config_path,
        )
        self._voice_language = self._language_from_config(resolved_config_path) or _language_of(
            settings.TTS_VOICE
        )
        logger.info("TTS voice loaded, speaking %s", self._voice_language or "an unknown language")
        return self._voice

    @staticmethod
    def _language_from_config(config_path: Optional[str]) -> Optional[str]:
        """The language a Piper voice actually speaks, per its own config."""
        if not config_path or not os.path.exists(config_path):
            return None
        try:
            import json

            with open(config_path, encoding="utf-8") as handle:
                config = json.load(handle)
        except Exception:  # pragma: no cover - a malformed config is not fatal
            return None
        language = config.get("language")
        if isinstance(language, dict):
            return _language_of(language.get("code") or language.get("family"))
        return _language_of(language if isinstance(language, str) else None)

    def synthesize(self, text: str, language: str | None = None) -> bytes:
        """Speak `text`, or raise if this service cannot speak it.

        It deliberately does not fall back to a silent buffer. A caller cannot
        distinguish silence from speech, so returning it hides a broken
        install and, in the student app, suppresses the browser-speech
        fallback that would otherwise have said something.
        """
        voice = self._load_voice()
        if voice is None:
            raise TTSUnavailable(
                "No TTS voice is installed. Add a Piper model under models/piper/."
            )

        wanted = _language_of(language)
        speaks = _language_of(self._voice_language)
        if wanted and speaks and wanted != speaks:
            # Piper does not fail on foreign script: the phonemiser spells it
            # out, so Khmer through an English voice returns minutes of noise
            # rather than an error. Refusing here is what lets the client fall
            # back to a browser voice that may actually speak the language.
            raise TTSLanguageUnavailable(
                f"The installed voice speaks {speaks}, not {wanted}."
            )

        # Newer piper-tts versions return AudioChunk iterables.
        chunks = list(voice.synthesize(text))
        if chunks:
            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wav_file:
                wav_file.setnchannels(chunks[0].sample_channels)
                wav_file.setsampwidth(chunks[0].sample_width)
                wav_file.setframerate(chunks[0].sample_rate)
                for chunk in chunks:
                    wav_file.writeframes(chunk.audio_int16_bytes)
            return wav_io.getvalue()

        # Keep compatibility with older piper APIs that write into a buffer.
        wav_io = io.BytesIO()
        try:
            voice.synthesize(text, wav_io, speaker_id=settings.TTS_SPEAKER_ID)
        except TypeError:
            voice.synthesize(text, wav_io)
        return wav_io.getvalue()


_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service
