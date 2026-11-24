"""Windows active-window tracker, local screenshot saver, and distraction detector."""

from __future__ import annotations

import ctypes
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

import mss
import psutil
from PIL import Image, ImageGrab

from app.config import SCREENSHOTS_DIR, SimiConfig

logger = logging.getLogger("simi.screen")


def get_active_window_info() -> Tuple[str, str]:
    """Return (window_title, process_name) for the current foreground Windows window."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ("Unknown", "unknown")
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip() or "Desktop"

        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc_name = "unknown"
        if pid.value:
            try:
                proc_name = psutil.Process(pid.value).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return (title, proc_name)
    except Exception as exc:
        logger.debug("Active window lookup failed: %s", exc)
        return ("Unknown", "unknown")


def classify_window(title: str, process_name: str, cfg: SimiConfig) -> str:
    """Classify current activity as 'productive', 'distracted', or 'neutral'."""
    haystack = f"{title} {process_name}".lower()
    if any(kw.lower() in haystack for kw in cfg.distraction_keywords):
        return "distracted"
    if any(kw.lower() in haystack for kw in cfg.productive_keywords):
        return "productive"
    return "neutral"


def capture_screen_thumbnail(max_width: int = 1280) -> str:
    """Capture primary monitor to data/screenshots/ as compressed JPEG and return path string."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = SCREENSHOTS_DIR / f"screen_{ts}.jpg"
    try:
        try:
            with mss.MSS() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                raw = sct.grab(monitor)
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        except Exception:
            img = ImageGrab.grab()
        if img.width > max_width:
            ratio = max_width / float(img.width)
            img = img.resize((max_width, int(img.height * ratio)), Image.Resampling.LANCZOS)
        img.save(out_path, "JPEG", quality=70, optimize=True)
        return str(out_path)
    except Exception as exc:
        logger.debug("Screen capture skipped (locked/protected desktop): %s", exc)
        return ""


def cleanup_old_screenshots(retention_hours: int) -> int:
    """Delete local screenshots older than retention_hours."""
    if not SCREENSHOTS_DIR.exists():
        return 0
    cutoff = time.time() - (retention_hours * 3600)
    removed = 0
    for f in SCREENSHOTS_DIR.glob("screen_*.jpg"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            pass
    return removed
