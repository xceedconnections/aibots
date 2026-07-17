"""Speech-to-text via Faster-Whisper."""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from worker.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@lru_cache
def get_whisper():
    try:
        from faster_whisper import WhisperModel

        logger.info(
            "Loading Whisper model=%s device=%s",
            settings.whisper_model,
            settings.whisper_device,
        )
        return WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    except Exception as exc:
        logger.error("Failed to load Whisper: %s", exc)
        return None


def transcribe_file(audio_path: str) -> str:
    model = get_whisper()
    if model is None:
        logger.warning("Whisper unavailable — returning empty transcript")
        return ""
    segments, _info = model.transcribe(audio_path, beam_size=1, language="en")
    text = " ".join(seg.text.strip() for seg in segments).strip()
    logger.info("STT: %s", text[:200])
    return text


def transcribe_bytes(pcm_or_wav: bytes, suffix: str = ".wav") -> str:
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(pcm_or_wav)
        path = f.name
    try:
        return transcribe_file(path)
    finally:
        Path(path).unlink(missing_ok=True)
