"""Indian English female voice output for Simi using edge-tts + Windows MCI, with pyttsx3 fallback."""

from __future__ import annotations

import asyncio
import ctypes
import logging
import queue
import threading
import uuid
from pathlib import Path
from typing import Optional

from app.config import AUDIO_CACHE_DIR, SimiConfig, load_config

logger = logging.getLogger("simi.voice")


def _play_mp3_windows(mp3_path: Path) -> None:
    """Play an MP3 file synchronously using Windows built-in winmm MCI (no external player)."""
    alias = f"simi_{uuid.uuid4().hex[:8]}"
    winmm = ctypes.windll.winmm
    buf = ctypes.create_unicode_buffer(256)
    path_str = str(mp3_path.resolve())
    err = winmm.mciSendStringW(f'open "{path_str}" type mpegvideo alias {alias}', buf, 255, 0)
    if err != 0:
        raise RuntimeError(f"MCI open failed with code {err}")
    try:
        winmm.mciSendStringW(f"play {alias} wait", buf, 255, 0)
    finally:
        winmm.mciSendStringW(f"close {alias}", buf, 255, 0)


async def _synthesize_edge_tts(text: str, out_path: Path, cfg: SimiConfig) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(
        text=text,
        voice=cfg.voice_name,
        rate=cfg.voice_rate,
        pitch=cfg.voice_pitch,
    )
    await communicate.save(str(out_path))


def _speak_pyttsx3(text: str) -> None:
    import pyttsx3

    engine = pyttsx3.init()
    voices = engine.getProperty("voices")
    # Prefer any Indian / female Windows SAPI5 voice if available
    for v in voices:
        name_lower = (v.name or "").lower()
        if "india" in name_lower or "heera" in name_lower or "kalpana" in name_lower:
            engine.setProperty("voice", v.id)
            break
    else:
        for v in voices:
            if "zira" in (v.name or "").lower() or "female" in (v.name or "").lower():
                engine.setProperty("voice", v.id)
                break
    engine.setProperty("rate", 172)
    engine.say(text)
    engine.runAndWait()


class VoiceEngine:
    """Non-blocking queued speech engine so Simi never talks over herself."""

    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_speaking = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="SimiVoice")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._queue.put("")

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def speak(self, text: str) -> None:
        clean = " ".join((text or "").split()).strip()
        if not clean:
            return
        cfg = load_config()
        if not cfg.voice_enabled:
            return
        if not self._thread or not self._thread.is_alive():
            self.start()
        self._queue.put(clean)

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if not text or self._stop_event.is_set():
                continue
            self._is_speaking = True
            try:
                self._speak_now(text)
            except Exception as exc:
                logger.warning("Voice playback error: %s", exc)
            finally:
                self._is_speaking = False

    def _speak_now(self, text: str) -> None:
        cfg = load_config()
        AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        out_path = AUDIO_CACHE_DIR / f"speech_{uuid.uuid4().hex[:8]}.mp3"
        try:
            asyncio.run(_synthesize_edge_tts(text, out_path, cfg))
            _play_mp3_windows(out_path)
        except Exception as exc:
            logger.info("edge-tts unavailable (%s), falling back to SAPI5 pyttsx3", exc)
            try:
                _speak_pyttsx3(text)
            except Exception as exc2:
                logger.warning("pyttsx3 fallback also failed: %s", exc2)
        finally:
            try:
                if out_path.exists():
                    out_path.unlink()
            except OSError:
                pass


voice_engine = VoiceEngine()
