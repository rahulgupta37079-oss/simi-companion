"""Natural-language memory extraction so Simi remembers meals, plans, water & mood from normal chat."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict

from app import db


def _guess_meal_type() -> str:
    hour = datetime.now().hour
    if hour < 11:
        return "Breakfast"
    if hour < 16:
        return "Lunch"
    if hour < 19:
        return "Snack"
    return "Dinner"


def capture_from_chat(user_text: str) -> Dict[str, object]:
    """Extract and store meals, water, plans, or emotional state naturally from chat text."""
    text = user_text.strip()
    low = text.lower()
    recorded: Dict[str, object] = {}

    # 1. Water tracking
    if re.search(
        r"(?:drank|had|piya|drinking)\s+(?:\d+\s+(?:glass|glasses|bottle|bottles)\s+(?:of\s+)?)?(?:water|paani|pani)|hydrated",
        low,
    ):
        glasses = 1
        m = re.search(r"(\d+)\s*(?:glass|glasses|bottle|bottles)", low)
        if m:
            glasses = max(1, min(6, int(m.group(1))))
        total = db.add_water(glasses)
        recorded["water"] = total

    # 2. Meal tracking
    meal_match = re.search(
        r"(?:i\s+(?:just\s+)?(?:ate|had|eaten)|khaya|breakfast\s+was|lunch\s+was|dinner\s+was)\s+(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if meal_match and not any(w in low for w in ["headache", "bad day", "fever"]):
        desc = re.split(r"\band\s+(?:drank|had\s+\d*\s*(?:glass|water))", meal_match.group(1), flags=re.IGNORECASE)[0]
        desc = desc.strip(" .!?")[:120]
        if len(desc) >= 2 and desc.lower() not in {"water", "paani", "pani"}:
            mtype = _guess_meal_type()
            for explicit in ("Breakfast", "Lunch", "Dinner", "Snack"):
                if explicit.lower() in low:
                    mtype = explicit
                    break
            db.add_meal(mtype, desc)
            recorded["meal"] = f"{mtype}: {desc}"

    # 3. Plan / Goal tracking
    plan_match = re.search(
        r"(?:my\s+plan\s+(?:is|today\s+is)|working\s+on|today\s+i(?:'ll| will)\s+(?:do|finish|build|study|work on)|goal\s+is)\s+(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if plan_match:
        title = plan_match.group(1).strip(" .!?")[:120]
        if len(title) >= 3:
            db.add_plan(title, priority="high")
            recorded["plan"] = title

    # Mark top active plan complete
    if any(w in low for w in ["finished my plan", "completed my goal", "done with my task", "ho gaya kaam", "task done"]):
        plans = [p for p in db.get_today_plans() if p["status"] == "active"]
        if plans:
            db.update_plan_status(plans[0]["id"], "done")
            recorded["plan_done"] = plans[0]["title"]

    # 4. Emotional state detection
    if any(w in low for w in ["crying", "cry", "rona", "ro raha", "ro rahi", "heartbroken", "breaking down"]):
        db.add_checkin("Crying", energy=2, note=text[:140], source="chat")
        recorded["mood"] = "crying"
    elif any(w in low for w in ["sad", "depressed", "anxious", "stressed", "overwhelmed", "lonely", "tired", "exhausted"]):
        db.add_checkin("Stressed", energy=3, note=text[:140], source="chat")
        recorded["mood"] = "distressed"
    elif any(w in low for w in ["happy", "great", "awesome", "excited", "motivated", "energized", "feeling good"]):
        db.add_checkin("Energized", energy=9, note=text[:140], source="chat")
        recorded["mood"] = "happy"

    return recorded
