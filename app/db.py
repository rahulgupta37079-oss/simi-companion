"""Local SQLite storage for Simi's memory: plans, meals, mood, screen logs, and chat."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from app.config import DB_PATH, ensure_dirs


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today_str() -> str:
    return date.today().isoformat()


@contextmanager
def get_conn(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    ensure_dirs()
    conn = sqlite3.connect(str(db_path or DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                priority TEXT NOT NULL DEFAULT 'high',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                description TEXT NOT NULL,
                water_glasses INTEGER NOT NULL DEFAULT 0,
                logged_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                mood TEXT NOT NULL,
                energy INTEGER NOT NULL DEFAULT 7,
                note TEXT DEFAULT '',
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS screen_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                window_title TEXT NOT NULL,
                process_name TEXT NOT NULL,
                category TEXT NOT NULL,
                screenshot_path TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                event_type TEXT NOT NULL DEFAULT 'chat',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_state (
                day TEXT PRIMARY KEY,
                morning_briefing_done INTEGER NOT NULL DEFAULT 0,
                water_count INTEGER NOT NULL DEFAULT 0,
                distraction_count INTEGER NOT NULL DEFAULT 0,
                focus_minutes INTEGER NOT NULL DEFAULT 0
            );
            """
        )


def _ensure_daily_state(conn: sqlite3.Connection, day: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO daily_state (day) VALUES (?)",
        (day,),
    )


def add_plan(title: str, priority: str = "high", db_path: Optional[Path] = None) -> int:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO plans (day, title, status, priority, created_at) VALUES (?, ?, 'active', ?, ?)",
            (_today_str(), title.strip(), priority, _now_iso()),
        )
        return int(cur.lastrowid)


def update_plan_status(plan_id: int, status: str, db_path: Optional[Path] = None) -> None:
    with get_conn(db_path) as conn:
        conn.execute("UPDATE plans SET status = ? WHERE id = ?", (status, plan_id))


def get_today_plans(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM plans WHERE day = ? ORDER BY id DESC", (_today_str(),)
        ).fetchall()
        return [dict(r) for r in rows]


def add_meal(
    meal_type: str, description: str, water_glasses: int = 0, db_path: Optional[Path] = None
) -> int:
    day = _today_str()
    with get_conn(db_path) as conn:
        _ensure_daily_state(conn, day)
        cur = conn.execute(
            "INSERT INTO meals (day, meal_type, description, water_glasses, logged_at) VALUES (?, ?, ?, ?, ?)",
            (day, meal_type, description.strip(), water_glasses, _now_iso()),
        )
        if water_glasses > 0:
            conn.execute(
                "UPDATE daily_state SET water_count = water_count + ? WHERE day = ?",
                (water_glasses, day),
            )
        return int(cur.lastrowid)


def add_water(glasses: int = 1, db_path: Optional[Path] = None) -> int:
    day = _today_str()
    with get_conn(db_path) as conn:
        _ensure_daily_state(conn, day)
        conn.execute(
            "UPDATE daily_state SET water_count = MAX(0, water_count + ?) WHERE day = ?",
            (glasses, day),
        )
        row = conn.execute(
            "SELECT water_count FROM daily_state WHERE day = ?", (day,)
        ).fetchone()
        return int(row["water_count"]) if row else 0


def get_today_meals(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM meals WHERE day = ? ORDER BY id DESC", (_today_str(),)
        ).fetchall()
        return [dict(r) for r in rows]


def add_checkin(
    mood: str,
    energy: int = 7,
    note: str = "",
    source: str = "manual",
    db_path: Optional[Path] = None,
) -> int:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO checkins (day, mood, energy, note, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (_today_str(), mood, energy, note.strip(), source, _now_iso()),
        )
        return int(cur.lastrowid)


def get_today_checkins(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM checkins WHERE day = ? ORDER BY id DESC", (_today_str(),)
        ).fetchall()
        return [dict(r) for r in rows]


def log_screen_event(
    window_title: str,
    process_name: str,
    category: str,
    screenshot_path: str = "",
    db_path: Optional[Path] = None,
) -> int:
    day = _today_str()
    with get_conn(db_path) as conn:
        _ensure_daily_state(conn, day)
        cur = conn.execute(
            """
            INSERT INTO screen_events (day, window_title, process_name, category, screenshot_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (day, window_title, process_name, category, screenshot_path, _now_iso()),
        )
        return int(cur.lastrowid)


def increment_distraction_count(db_path: Optional[Path] = None) -> None:
    day = _today_str()
    with get_conn(db_path) as conn:
        _ensure_daily_state(conn, day)
        conn.execute(
            "UPDATE daily_state SET distraction_count = distraction_count + 1 WHERE day = ?",
            (day,),
        )


def get_recent_screen_events(
    limit: int = 15, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM screen_events WHERE day = ? ORDER BY id DESC LIMIT ?",
            (_today_str(), limit),
        ).fetchall()
        return [dict(r) for r in rows]


def add_message(
    role: str, content: str, event_type: str = "chat", db_path: Optional[Path] = None
) -> int:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO messages (role, content, event_type, created_at) VALUES (?, ?, ?, ?)",
            (role, content, event_type, _now_iso()),
        )
        return int(cur.lastrowid)


def get_recent_messages(limit: int = 30, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_daily_summary(db_path: Optional[Path] = None) -> Dict[str, Any]:
    day = _today_str()
    with get_conn(db_path) as conn:
        _ensure_daily_state(conn, day)
        state = dict(
            conn.execute("SELECT * FROM daily_state WHERE day = ?", (day,)).fetchone()
        )
        plans = get_today_plans(db_path)
        meals = get_today_meals(db_path)
        checkins = get_today_checkins(db_path)
        screen_events = get_recent_screen_events(10, db_path)
        return {
            "day": day,
            "state": state,
            "plans": plans,
            "meals": meals,
            "checkins": checkins,
            "recent_screen": screen_events,
        }


def mark_morning_briefing_done(db_path: Optional[Path] = None) -> None:
    day = _today_str()
    with get_conn(db_path) as conn:
        _ensure_daily_state(conn, day)
        conn.execute(
            "UPDATE daily_state SET morning_briefing_done = 1 WHERE day = ?", (day,)
        )
