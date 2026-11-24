"""Configuration management for Simi Wellness & Productivity Companion."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
AUDIO_CACHE_DIR = DATA_DIR / "audio_cache"
CONFIG_PATH = DATA_DIR / "config.json"
DB_PATH = DATA_DIR / "simi.db"


@dataclass
class SimiConfig:
    assistant_name: str = "Simi"
    user_name: str = "Partner"
    voice_name: str = "en-IN-NeerjaNeural"
    voice_rate: str = "+2%"
    voice_pitch: str = "+2Hz"
    voice_enabled: bool = True

    # AI provider: "auto", "gemini", "groq", "openai_compat", "ollama", "builtin"
    ai_provider: str = "auto"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openai_base_url: str = "http://127.0.0.1:8080/v1"
    openai_api_key: str = ""
    openai_model: str = "local-model"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    screen_monitor_enabled: bool = True
    screen_capture_interval_sec: int = 30
    save_screenshots: bool = True
    screenshot_retention_hours: int = 24
    checkin_interval_min: int = 45
    morning_briefing_hour: int = 8
    webcam_emotion_enabled: bool = False
    webcam_check_interval_sec: int = 10
    distraction_threshold_sec: int = 90
    distraction_keywords: List[str] = field(
        default_factory=lambda: [
            "youtube",
            "instagram",
            "facebook",
            "twitter",
            "x.com",
            "reddit",
            "netflix",
            "twitch",
            "reels",
            "shorts",
            "steam",
            "prime video",
            "hotstar",
        ]
    )
    productive_keywords: List[str] = field(
        default_factory=lambda: [
            "visual studio code",
            "vscode",
            "code",
            "pycharm",
            "powershell",
            "terminal",
            "cmd",
            "github",
            "gitlab",
            "notion",
            "obsidian",
            "figma",
            "excel",
            "word",
            "docs",
            "antigravity",
            "localhost",
        ]
    )


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> SimiConfig:
    ensure_dirs()
    if not CONFIG_PATH.exists():
        cfg = SimiConfig()
        save_config(cfg)
        return cfg
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        valid_fields = {f for f in SimiConfig.__dataclass_fields__}
        filtered = {k: v for k, v in raw.items() if k in valid_fields}
        return SimiConfig(**filtered)
    except Exception:
        cfg = SimiConfig()
        save_config(cfg)
        return cfg


def save_config(cfg: SimiConfig) -> None:
    ensure_dirs()
    CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
