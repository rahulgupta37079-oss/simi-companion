"""Microphone voice listener for Simi: smart VAD recording + native Gemini Hinglish audio understanding."""

from __future__ import annotations

import base64
import io
import logging
import time
import wave
from typing import Callable, Optional, Tuple

import httpx
import numpy as np

from app.config import SimiConfig, load_config
from app.voice import voice_engine

logger = logging.getLogger("simi.listener")

SAMPLE_RATE = 16000
BLOCK_MS = 80
BLOCK_SAMPLES = int(SAMPLE_RATE * BLOCK_MS / 1000)


def _pcm_to_wav_bytes(pcm: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Normalize quiet mic audio safely (without clipping) and encode mono 16-bit WAV bytes."""
    arr = pcm.astype(np.float32)
    peak = float(np.max(np.abs(arr))) if arr.size else 0.0
    if 150.0 < peak < 24000.0:
        gain = min(6.0, 24000.0 / peak)
        arr = np.clip(arr * gain, -32767.0, 32767.0)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(arr.astype(np.int16).tobytes())
    return buf.getvalue()


def list_microphones() -> list[Tuple[int, str]]:
    try:
        import sounddevice as sd

        seen = set()
        out = []
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                name = str(d["name"]).strip()
                if name and name not in seen and "Mapper" not in name and "Primary" not in name:
                    seen.add(name)
                    out.append((i, name))
        return out
    except Exception:
        return []


def probe_mic_level(device_index: int = -1, duration_sec: float = 1.2) -> Tuple[bool, float, float]:
    """Quick 1.2s mic level check returning (ok, rms, peak)."""
    try:
        import sounddevice as sd

        dev = None if device_index < 0 else device_index
        rec = sd.rec(int(SAMPLE_RATE * duration_sec), samplerate=SAMPLE_RATE, channels=1, dtype="int16", device=dev)
        sd.wait()
        arr = rec[:, 0].astype(np.float32)
        return True, float(np.sqrt(np.mean(arr * arr))), float(np.max(np.abs(arr)))
    except Exception as exc:
        logger.warning("Mic probe failed: %s", exc)
        return False, 0.0, 0.0


def record_utterance(
    max_duration_sec: float = 11.0,
    start_timeout_sec: float = 6.0,
    silence_stop_sec: float = 1.25,
    device_index: int = -1,
    abort_check: Optional[Callable[[], bool]] = None,
) -> Optional[bytes]:
    """Record a single spoken utterance using adaptive ambient-noise VAD; returns WAV bytes or None."""
    try:
        import sounddevice as sd
    except Exception as exc:
        logger.warning("sounddevice unavailable: %s", exc)
        return None

    device = None if device_index < 0 else device_index
    blocks: list[np.ndarray] = []
    pre_roll: list[np.ndarray] = []

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=BLOCK_SAMPLES,
            device=device,
        ) as stream:
            # 1. Brief 0.32s ambient noise floor calibration
            cal_rms = []
            for _ in range(4):
                data, _ = stream.read(BLOCK_SAMPLES)
                arr = data[:, 0].astype(np.float32)
                cal_rms.append(float(np.sqrt(np.mean(arr * arr))) + 1.0)
            noise_floor = float(np.median(cal_rms))
            # Tuned for both close headsets and laptop/webcam mics across the desk
            speech_thresh = max(180.0, noise_floor * 1.9 + 75.0)

            started = False
            speech_blocks = 0
            silence_blocks = 0
            start_t = time.time()
            rec_start_t = start_t
            max_silence_blocks = max(5, int(silence_stop_sec * 1000 / BLOCK_MS))

            while True:
                if abort_check and abort_check():
                    return None
                if voice_engine.is_speaking:
                    return None

                data, _ = stream.read(BLOCK_SAMPLES)
                chunk = data[:, 0].copy()
                arr = chunk.astype(np.float32)
                rms = float(np.sqrt(np.mean(arr * arr)))
                now = time.time()

                if not started:
                    pre_roll.append(chunk)
                    if len(pre_roll) > 4:
                        pre_roll.pop(0)
                    if rms > speech_thresh:
                        started = True
                        rec_start_t = now
                        blocks.extend(pre_roll)
                        speech_blocks = 1
                        silence_blocks = 0
                    elif (now - start_t) >= start_timeout_sec:
                        return None
                else:
                    blocks.append(chunk)
                    if rms > speech_thresh * 0.72:
                        speech_blocks += 1
                        silence_blocks = 0
                    else:
                        silence_blocks += 1

                    if silence_blocks >= max_silence_blocks:
                        break
                    if (now - rec_start_t) >= max_duration_sec:
                        break

            # Ignore tiny accidental clicks/coughs (< ~0.4s speech)
            if speech_blocks < 4 or not blocks:
                return None

            pcm = np.concatenate(blocks)
            return _pcm_to_wav_bytes(pcm)
    except Exception as exc:
        logger.warning("Microphone recording error: %s", exc)
        return None


def transcribe_audio_sync(wav_bytes: bytes, cfg: Optional[SimiConfig] = None) -> Tuple[str, str]:
    """Transcribe Hinglish/English/Hindi speech via Gemini native audio; returns (transcript, vocal_mood)."""
    cfg = cfg or load_config()
    api_key = cfg.gemini_api_key.strip()
    if not api_key:
        return "", ""

    model = cfg.gemini_model.strip() or "gemini-flash-lite-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    b64 = base64.b64encode(wav_bytes).decode("ascii")

    prompt = (
        "Listen carefully to this short microphone clip from an Indian speaker speaking English, Hindi, or Hinglish. "
        "If there is only silence, background fan/keyboard noise, or unintelligible mumble, reply with exactly: SILENCE\n"
        "Otherwise output TWO lines only:\n"
        "MOOD: one word from [neutral, happy, tired, stressed, sad, crying]\n"
        "TEXT: exact natural transcription (use Roman/English script for Hinglish words so it reads cleanly)."
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "audio/wav", "data": b64}},
                    {"text": prompt},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 140},
    }
    try:
        with httpx.Client(timeout=18.0) as client:
            resp = client.post(
                url,
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                json=payload,
            )
            if resp.status_code != 200:
                logger.warning("Gemini audio HTTP %s: %s", resp.status_code, resp.text[:140])
                return "", ""
            parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            raw = "".join(p.get("text", "") for p in parts).strip()
            if not raw or raw.upper().startswith("SILENCE"):
                return "", ""

            mood = "neutral"
            text = raw
            for line in raw.splitlines():
                ln = line.strip()
                if ln.upper().startswith("MOOD:"):
                    mood = ln.split(":", 1)[1].strip().lower()
                elif ln.upper().startswith("TEXT:"):
                    text = ln.split(":", 1)[1].strip()
            if not text or text.upper() == "SILENCE":
                return "", ""
            return text, mood
    except Exception as exc:
        logger.warning("Gemini audio transcription failed: %s", exc)
        return "", ""
