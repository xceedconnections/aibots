"""Text-to-speech via Piper (local). Falls back to writing a silent placeholder."""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from worker.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def synthesize(text: str, out_path: str | None = None, voice: str | None = None) -> str:
    """
    Synthesize speech to a WAV file. Returns path to WAV.
    Prefers `piper` CLI if installed; otherwise tries piper Python API;
    otherwise writes a tiny silent wav so the pipeline can continue.
    """
    if out_path is None:
        out_path = tempfile.mktemp(suffix=".wav")

    model = settings.piper_model_path
    config = settings.piper_config_path

    piper_bin = shutil.which("piper")
    if piper_bin and Path(model).exists():
        try:
            proc = subprocess.run(
                [
                    piper_bin,
                    "--model", model,
                    "--config", config,
                    "--output_file", out_path,
                ],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=60,
                check=False,
            )
            if proc.returncode == 0 and Path(out_path).exists():
                logger.info("TTS Piper OK -> %s (%d chars)", out_path, len(text))
                return out_path
            logger.warning("Piper CLI failed: %s", proc.stderr.decode(errors="ignore")[:300])
        except Exception as exc:
            logger.warning("Piper CLI error: %s", exc)

    # Python piper-tts fallback
    try:
        from piper import PiperVoice
        import wave

        if Path(model).exists():
            voice_obj = PiperVoice.load(model, config_path=config if Path(config).exists() else None)
            with wave.open(out_path, "wb") as wav_file:
                voice_obj.synthesize(text, wav_file)
            logger.info("TTS Piper Python OK -> %s", out_path)
            return out_path
    except Exception as exc:
        logger.warning("Piper Python fallback failed: %s", exc)

    # Silent placeholder so call loop does not crash before models are downloaded
    _write_silent_wav(out_path, duration_sec=0.4)
    logger.warning("TTS placeholder silent WAV (install Piper model). Text was: %s", text[:80])
    return out_path


def _write_silent_wav(path: str, duration_sec: float = 0.4, rate: int = 16000):
    import struct
    import wave

    n_frames = int(rate * duration_sec)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<" + "h" * n_frames, *([0] * n_frames)))
