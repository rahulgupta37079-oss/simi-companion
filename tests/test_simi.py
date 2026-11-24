"""Automated tests for Floating Simi Companion (108 expressions, walk/run, lip-sync, clock routines)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from PIL import Image

from app import ai_engine, db, natural_memory
from app.config import BASE_DIR, SimiConfig
from app.expression_engine import (
    EXPRESSIONS,
    bake_mouth_frame,
    pick_expression_for_context,
)
from app.floating_companion import FloatingSimiApp
from app.screen_monitor import classify_window
from app.time_routines import TimeRoutineEngine


def test_all_10_sprites_exist_and_transparent():
    assets = BASE_DIR / "assets"
    expected = (
        "simi_idle.png",
        "simi_talk.png",
        "simi_focus.png",
        "simi_care.png",
        "simi_walk_1.png",
        "simi_walk_2.png",
        "simi_run_1.png",
        "simi_run_2.png",
        "simi_sleepy.png",
        "simi_laugh.png",
    )
    for name in expected:
        p = assets / name
        assert p.exists(), f"Missing sprite: {p}"
        img = Image.open(p)
        assert img.mode == "RGBA"
        assert img.getpixel((0, 0))[3] == 0


def test_108_expressions_and_lip_sync():
    assert len(EXPRESSIONS) >= 100
    assert pick_expression_for_context("I am crying", "emotional_support", 14).name == "crying_comfort"
    assert pick_expression_for_context("Reels band karo", "distraction_nudge", 15).name == "no_reels_allowed"
    assert pick_expression_for_context("So jao please", "checkin", 2).name == "go_to_sleep_please"

    base = Image.open(BASE_DIR / "assets" / "simi_talk.png").convert("RGBA")
    for state in ("closed", "small", "mid", "wide", "o", "pout", "yawn"):
        frame = bake_mouth_frame(base, state, blush=0.7)
        assert frame.size == base.size
        assert frame.mode == "RGBA"


def test_clock_aware_routines():
    eng = TimeRoutineEngine()
    empty_summary = {"state": {"morning_briefing_done": 0, "water_count": 0}, "meals": []}

    d_morning = eng.next_autonomous_routine(empty_summary, "Boss", now=datetime(2026, 11, 25, 8, 15))
    assert d_morning is not None and d_morning.slot_key == "morning" and d_morning.move_mode == "run"

    d_lunch = eng.next_autonomous_routine(empty_summary, "Boss", now=datetime(2026, 11, 25, 13, 20))
    assert d_lunch is not None and d_lunch.slot_key == "lunch_nudge"

    d_chai = eng.next_autonomous_routine(empty_summary, "Boss", now=datetime(2026, 11, 25, 17, 0))
    assert d_chai is not None and d_chai.slot_key == "chai_break"

    d_dinner = eng.next_autonomous_routine(empty_summary, "Boss", now=datetime(2026, 11, 25, 21, 5))
    assert d_dinner is not None and d_dinner.slot_key == "dinner_nudge"

    d_night = eng.next_autonomous_routine(empty_summary, "Boss", now=datetime(2026, 11, 25, 2, 30))
    assert d_night is not None and d_night.slot_key == "late_night_2"


def test_natural_memory_capture(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "nat_simi.db"
    db.init_db(db_file)
    monkeypatch.setattr(db, "DB_PATH", db_file)

    r1 = natural_memory.capture_from_chat("I just ate masala dosa and drank 2 glasses of water")
    assert "meal" in r1
    assert r1["water"] == 2

    r2 = natural_memory.capture_from_chat("My plan today is building my startup MVP")
    assert r2["plan"] == "building my startup MVP"

    r3 = natural_memory.capture_from_chat("I'm feeling really sad and crying right now")
    assert r3["mood"] == "crying"


def test_screen_classification():
    cfg = SimiConfig()
    assert classify_window("main.py - Visual Studio Code", "Code.exe", cfg) == "productive"
    assert classify_window("Funny Reels - Instagram", "chrome.exe", cfg) == "distracted"
    assert classify_window("Calculator", "calc.exe", cfg) == "neutral"


def test_ai_fallback_replies():
    cfg = SimiConfig(user_name="Aarav", ai_provider="builtin")
    summary = {
        "day": "2026-11-25",
        "state": {"water_count": 2, "distraction_count": 1},
        "plans": [{"title": "Ship release", "status": "active"}],
        "meals": [{"meal_type": "Lunch", "description": "Dal chawal"}],
        "checkins": [{"mood": "Focused"}],
        "recent_screen": [{"window_title": "VS Code"}],
    }
    reply = asyncio.run(ai_engine.generate_chat_reply("I am feeling sad and want to cry", [], cfg, summary))
    assert "Aarav" in reply
    assert "main hoon" in reply.lower()


def test_floating_companion_walk_run_lipsync():
    app = FloatingSimiApp()
    try:
        assert "walk_1" in app.base_images and "run_1" in app.base_images
        app._roam_now("walk")
        assert app.is_moving and app.move_mode == "walk"
        app.root.update()

        app._roam_now("run")
        assert app.is_moving and app.move_mode == "run"
        app.root.update()

        app.show_bubble("Testing live mouth animation and 108 expressions!", expr_name="radiant_joy", duration_sec=2.0)
        app.root.update()
    finally:
        app.quit()
