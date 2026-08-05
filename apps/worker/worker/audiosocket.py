"""
Minimal Asterisk AudioSocket server (slin / 8k PCM).

Protocol (Asterisk AudioSocket):
  After TCP accept, Asterisk sends UUID as type 0x01 with 16-byte BINARY uuid.
  Frames: 1-byte type + 2-byte big-endian length + payload
  type 0x00 = hangup, 0x01 = UUID, 0x10 = 16-bit PCM (usually 8kHz)

Asterisk app_audiosocket disconnects after ~2s with no activity on either
side — send silence keepalive while TTS/STT/API work runs.
"""
from __future__ import annotations

import asyncio
import logging
import struct
import tempfile
import uuid
import wave
from pathlib import Path

logger = logging.getLogger("aibots.audiosocket")

TYPE_HANGUP = 0x00
TYPE_UUID = 0x01
TYPE_DTMF = 0x03
TYPE_AUDIO = 0x10
TYPE_ERROR = 0xFF

# 20ms of silence @ 8kHz 16-bit mono
SILENCE_20MS = b"\x00" * 320


def decode_uuid_payload(payload: bytes) -> str:
    """Asterisk sends 16-byte binary UUID; accept string form as fallback."""
    if len(payload) >= 16:
        try:
            return str(uuid.UUID(bytes=payload[:16]))
        except ValueError:
            pass
    text = payload.decode("utf-8", errors="ignore").strip().rstrip("\x00")
    if text:
        try:
            return str(uuid.UUID(text))
        except ValueError:
            return text
    return ""


async def read_frame(reader: asyncio.StreamReader) -> tuple[int, bytes] | None:
    header = await reader.readexactly(3)
    ftype = header[0]
    length = struct.unpack(">H", header[1:3])[0]
    payload = b""
    if length:
        payload = await reader.readexactly(length)
    return ftype, payload


async def write_audio(writer: asyncio.StreamWriter, pcm: bytes) -> None:
    # Chunk to ~20ms @ 8kHz 16-bit mono = 320 bytes
    chunk = 320
    for i in range(0, len(pcm), chunk):
        part = pcm[i : i + chunk]
        writer.write(bytes([TYPE_AUDIO]) + struct.pack(">H", len(part)) + part)
        await writer.drain()
        await asyncio.sleep(0.02)


async def write_silence(writer: asyncio.StreamWriter, duration_ms: int = 200) -> None:
    """Keep AudioSocket alive (Asterisk ~2s idle timeout)."""
    frames = max(1, duration_ms // 20)
    for _ in range(frames):
        writer.write(bytes([TYPE_AUDIO]) + struct.pack(">H", len(SILENCE_20MS)) + SILENCE_20MS)
        await writer.drain()
        await asyncio.sleep(0.02)


def wav_to_pcm8k(path: str) -> bytes:
    """Convert WAV to 8kHz mono 16-bit PCM (best-effort)."""
    import audioop
    import subprocess

    out = tempfile.mktemp(suffix=".raw")
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-i", path,
                "-ac", "1", "-ar", "8000", "-f", "s16le", out,
            ],
            capture_output=True,
            timeout=30,
        )
        if proc.returncode == 0 and Path(out).exists():
            data = Path(out).read_bytes()
            Path(out).unlink(missing_ok=True)
            return data
    except Exception:
        pass

    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        sw = w.getsampwidth()
        ch = w.getnchannels()
        frames = w.readframes(w.getnframes())
    if ch == 2:
        frames = audioop.tomono(frames, sw, 0.5, 0.5)
    if sw != 2:
        frames = audioop.lin2lin(frames, sw, 2)
    if rate != 8000:
        frames, _ = audioop.ratecv(frames, 2, 1, rate, 8000, None)
    return frames


def pcm8k_to_wav(pcm: bytes, path: str) -> str:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(pcm)
    return path


class CallAudioBridge:
    """Collect inbound PCM until silence/timeout, play outbound WAV."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.uuid = ""
        self._closed = False

    async def keepalive(self, duration_ms: int = 200) -> None:
        if not self._closed:
            await write_silence(self.writer, duration_ms)

    async def play_wav(self, wav_path: str) -> None:
        pcm = await asyncio.to_thread(wav_to_pcm8k, wav_path)
        if not pcm:
            logger.warning("Empty PCM for %s — playing brief silence", wav_path)
            await self.keepalive(400)
            return
        await write_audio(self.writer, pcm)

    async def listen(
        self,
        silence_ms: int = 1200,
        max_ms: int = 8000,
        energy_threshold: int = 400,
    ) -> bytes:
        """Record until silence after speech or max duration."""
        buf = bytearray()
        spoke = False
        silent_ms = 0
        elapsed = 0
        frame_ms = 20

        while elapsed < max_ms and not self._closed:
            try:
                frame = await asyncio.wait_for(read_frame(self.reader), timeout=0.5)
            except asyncio.TimeoutError:
                elapsed += 500
                # Nudge Asterisk so idle timeout does not tear down the socket
                await self.keepalive(40)
                if spoke and silent_ms >= silence_ms:
                    break
                continue
            except asyncio.IncompleteReadError:
                self._closed = True
                break

            if frame is None:
                break
            ftype, payload = frame
            if ftype == TYPE_HANGUP or ftype == TYPE_ERROR:
                self._closed = True
                break
            if ftype == TYPE_UUID:
                self.uuid = decode_uuid_payload(payload)
                continue
            if ftype != TYPE_AUDIO or not payload:
                continue

            buf.extend(payload)
            energy = sum(
                abs(int.from_bytes(payload[i : i + 2], "little", signed=True))
                for i in range(0, len(payload) - 1, 2)
            ) / max(1, len(payload) // 2)
            if energy > energy_threshold:
                spoke = True
                silent_ms = 0
            elif spoke:
                silent_ms += frame_ms
            elapsed += frame_ms
            if spoke and silent_ms >= silence_ms:
                break

        return bytes(buf)
