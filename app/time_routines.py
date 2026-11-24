"""Clock-aware 24/7 Autonomous Routine Engine so Simi sees exact timings and acts naturally."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Set


@dataclass
class RoutineDecision:
    slot_key: str
    event_type: str
    expression: str
    move_mode: str   # "walk", "run", "stay"
    prompt_hint: str
    fallback_text: str


class TimeRoutineEngine:
    """Tracks real wall-clock timings and autonomously decides meal, water, break, and sleep check-ins."""

    def __init__(self) -> None:
        self._fired_day: str = ""
        self._fired_slots: Set[str] = set()

    def _reset_if_new_day(self, now: datetime) -> None:
        day = now.date().isoformat()
        if day != self._fired_day:
            self._fired_day = day
            self._fired_slots.clear()

    def describe_time_context(self, now: Optional[datetime] = None) -> str:
        now = now or datetime.now()
        hour = now.hour
        time_str = now.strftime("%I:%M %p").lstrip("0")
        day_name = now.strftime("%A")

        if 5 <= hour < 9:
            phase = "Early Morning (fresh start, breakfast & daily plan time)"
        elif 9 <= hour < 12:
            phase = "Morning Focus Hours (prime deep work)"
        elif 12 <= hour < 15:
            phase = "Lunch Time (check if they ate lunch & hydrated)"
        elif 15 <= hour < 18:
            phase = "Afternoon Work & Chai Break (keep energy up)"
        elif 18 <= hour < 21:
            phase = "Evening Wind-Down & Dinner Prep (celebrate today's wins)"
        elif 21 <= hour < 23:
            phase = "Night Wind-Down (dinner check & preparing for rest)"
        else:
            phase = "Late Night / Past Midnight (gently remind them to rest eyes & sleep soon)"

        return f"{day_name}, {time_str} — {phase}"

    def next_autonomous_routine(
        self, summary: Dict[str, Any], user_name: str, now: Optional[datetime] = None
    ) -> Optional[RoutineDecision]:
        """Check current clock time & user logs to decide if Simi should proactively act right now."""
        now = now or datetime.now()
        self._reset_if_new_day(now)

        h = now.hour
        m = now.minute
        time_str = now.strftime("%I:%M %p").lstrip("0")
        meals = summary.get("meals", [])
        meal_types = {str(x.get("meal_type", "")).lower() for x in meals}
        water = summary.get("state", {}).get("water_count", 0)

        # 1. Morning Briefing (06:00 - 10:30)
        if 6 <= h <= 10 and summary.get("state", {}).get("morning_briefing_done", 0) == 0 and "morning" not in self._fired_slots:
            self._fired_slots.add("morning")
            return RoutineDecision(
                slot_key="morning",
                event_type="morning_briefing",
                expression="morning_hype",
                move_mode="run",
                prompt_hint=f"It's {time_str} morning! Give an energetic, loving morning greeting, remind about water & breakfast, and ask what today's winning plan is.",
                fallback_text=f"Good morning {user_name}! {time_str} ho gaya — naya din hai aur aaj jeetna hai! Paani piyo, breakfast karo aur batao aaj ka plan kya hai?",
            )

        # 2. Breakfast check (09:30 - 11:00) if not logged
        if (h == 9 and m >= 30) or h == 10:
            if "breakfast" not in meal_types and "breakfast_nudge" not in self._fired_slots:
                self._fired_slots.add("breakfast_nudge")
                return RoutineDecision(
                    slot_key="breakfast_nudge",
                    event_type="checkin",
                    expression="breakfast_reminder",
                    move_mode="walk",
                    prompt_hint=f"It's {time_str} and they haven't logged breakfast yet. Lovingly nudge them to eat breakfast.",
                    fallback_text=f"Suno {user_name}, {time_str} baj gaye! Breakfast kiya kya? Khali pet kaam mat karo please, kuch achha kha lo.",
                )

        # 3. Lunch check (13:00 - 14:30) if not logged
        if (h == 13 or (h == 14 and m <= 30)) and "lunch" not in meal_types and "lunch_nudge" not in self._fired_slots:
            self._fired_slots.add("lunch_nudge")
            return RoutineDecision(
                slot_key="lunch_nudge",
                event_type="checkin",
                expression="lunch_time",
                move_mode="run",
                prompt_hint=f"It's {time_str} lunch time and no lunch is logged yet! Run over playfully and remind them to take a real lunch break.",
                fallback_text=f"Arey {user_name}, {time_str} ho gaya — lunch time! Screen se 15 minute break lo aur pet bhar ke lunch karo.",
            )

        # 4. Afternoon Chai / Stretch Break (16:30 - 17:45)
        if ((h == 16 and m >= 30) or (h == 17 and m <= 45)) and "chai_break" not in self._fired_slots:
            self._fired_slots.add("chai_break")
            return RoutineDecision(
                slot_key="chai_break",
                event_type="checkin",
                expression="chai_break",
                move_mode="walk",
                prompt_hint=f"It's {time_str} afternoon chai/snack time! Suggest a quick stretch, water/chai break, and check how their plan is going.",
                fallback_text=f"Suno {user_name}, {time_str} ho gaye — chai break aur 2 minute stretch banta hai! Mind fresh lag raha hai?",
            )

        # 5. Dinner check (20:30 - 22:00) if not logged
        if ((h == 20 and m >= 30) or h == 21) and "dinner" not in meal_types and "dinner_nudge" not in self._fired_slots:
            self._fired_slots.add("dinner_nudge")
            return RoutineDecision(
                slot_key="dinner_nudge",
                event_type="checkin",
                expression="dinner_time",
                move_mode="walk",
                prompt_hint=f"It's {time_str} evening dinner time and no dinner is logged yet. Warmly ask if they ate dinner and how their day went.",
                fallback_text=f"Hey {user_name}, {time_str} baj gaye! Dinner kar liya kya? Aur aaj ka din kaisa raha, mujhe batao!",
            )

        # 6. Late Night / Sleep Care (23:30 - 05:00, once per hour)
        if h >= 23 or h < 5:
            slot = f"late_night_{h}"
            if slot not in self._fired_slots:
                self._fired_slots.add(slot)
                return RoutineDecision(
                    slot_key=slot,
                    event_type="checkin",
                    expression="go_to_sleep_please" if h >= 1 else "cozy_night",
                    move_mode="walk",
                    prompt_hint=f"It's late night ({time_str})! You're a little sleepy and worried about their health — lovingly remind them of the exact time, ask if they're wrapping up soon, and tell them to rest their eyes and drink water.",
                    fallback_text=f"Arey {user_name}, dekho toh {time_str} baj gaye hain! Main bhi thodi sleepy ho rahi hoon... thoda paani piyo aur jaldi wrap up karke so jao please.",
                )

        # 7. Periodic Hydration Check (every 2 hours between 10 AM and 8 PM if water is low)
        if 10 <= h <= 20 and h % 2 == 0:
            slot = f"water_{h}"
            if slot not in self._fired_slots and water < (h - 8) // 2:
                self._fired_slots.add(slot)
                return RoutineDecision(
                    slot_key=slot,
                    event_type="checkin",
                    expression="hydration_nudge",
                    move_mode="walk",
                    prompt_hint=f"It's {time_str} and they've only logged {water} glasses of water today. Give a cute 1-2 sentence hydration nudge.",
                    fallback_text=f"Suno {user_name}, {time_str} ho gaya aur abhi sirf {water} glass paani! Chalo ek glass paani pi lo mere liye.",
                )

        return None


routine_engine = TimeRoutineEngine()
