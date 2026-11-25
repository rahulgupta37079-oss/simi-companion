"""100+ Expression Engine & Real-Time Animated Lip-Sync Mouth Composer for Simi."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw


@dataclass(frozen=True)
class ExpressionSpec:
    name: str
    pose: str                 # idle, talk, focus, care, laugh, sleepy, think, eat, walk_1, run_1
    emote: str                # floating icon/badge next to head: "", "heart", "hearts", "sparkle", "star", "zzz", "anger", "question", "exclaim", "idea", "water", "chai", "music", "sweat", "fire", "sun", "moon", "trophy", "hug", "blush_dots"
    blush: float              # 0.0 to 1.0 soft rosy cheek glow
    mouth_rest: str           # "default", "smile", "o", "pout", "yawn", "happy_open"
    bob_speed: float = 2.6
    bob_amp: float = 5.5
    energy: str = "normal"    # "calm", "normal", "high", "sleepy"


def _build_108_expressions() -> Dict[str, ExpressionSpec]:
    """Generate 108 distinct named human-like expressions across moods, routines, and reactions."""
    specs: List[ExpressionSpec] = [
        # --- Happy / Warm / Affectionate (1-20) ---
        ExpressionSpec("happy_wave", "idle", "sparkle", 0.2, "default", 2.6, 5.5, "normal"),
        ExpressionSpec("warm_smile", "idle", "", 0.15, "default", 2.2, 4.5, "calm"),
        ExpressionSpec("radiant_joy", "laugh", "sparkle", 0.45, "happy_open", 3.4, 7.5, "high"),
        ExpressionSpec("bright_cheer", "laugh", "star", 0.35, "happy_open", 3.6, 8.0, "high"),
        ExpressionSpec("sweet_affection", "care", "heart", 0.55, "smile", 2.0, 4.5, "calm"),
        ExpressionSpec("deep_love", "care", "hearts", 0.75, "smile", 2.1, 5.0, "calm"),
        ExpressionSpec("shy_blush", "idle", "blush_dots", 0.85, "smile", 2.0, 4.0, "calm"),
        ExpressionSpec("super_shy", "think", "blush_dots", 0.95, "o", 1.8, 3.5, "calm"),
        ExpressionSpec("giggling", "laugh", "music", 0.5, "happy_open", 3.8, 7.0, "high"),
        ExpressionSpec("laughing_out_loud", "laugh", "hearts", 0.6, "happy_open", 4.2, 8.5, "high"),
        ExpressionSpec("proud_smile", "idle", "star", 0.3, "default", 2.5, 5.5, "normal"),
        ExpressionSpec("super_proud", "laugh", "trophy", 0.5, "happy_open", 3.5, 8.0, "high"),
        ExpressionSpec("excited_bounce", "laugh", "exclaim", 0.4, "happy_open", 4.4, 9.0, "high"),
        ExpressionSpec("starry_eyed", "talk", "star", 0.4, "happy_open", 3.2, 6.5, "high"),
        ExpressionSpec("admiring_you", "care", "sparkle", 0.5, "smile", 2.0, 4.5, "calm"),
        ExpressionSpec("cozy_content", "idle", "music", 0.25, "smile", 1.8, 4.0, "calm"),
        ExpressionSpec("grateful_warmth", "care", "heart", 0.45, "smile", 2.1, 4.5, "calm"),
        ExpressionSpec("cheerful_chat", "talk", "sparkle", 0.25, "default", 2.9, 6.0, "normal"),
        ExpressionSpec("enthusiastic_story", "talk", "exclaim", 0.35, "happy_open", 3.3, 6.8, "high"),
        ExpressionSpec("loving_listen", "think", "heart", 0.35, "smile", 2.0, 4.0, "calm"),

        # --- Playful / Teasing / Scolding / Focus (21-40) ---
        ExpressionSpec("playful_tease", "focus", "sparkle", 0.3, "default", 2.8, 5.5, "normal"),
        ExpressionSpec("caught_you", "focus", "exclaim", 0.2, "default", 3.5, 6.5, "high"),
        ExpressionSpec("playful_scold", "focus", "anger", 0.35, "pout", 3.4, 6.0, "high"),
        ExpressionSpec("strict_boss", "focus", "anger", 0.15, "pout", 2.6, 4.0, "normal"),
        ExpressionSpec("gentle_nudge", "focus", "exclaim", 0.2, "default", 2.7, 5.0, "normal"),
        ExpressionSpec("back_to_work", "focus", "fire", 0.25, "default", 3.6, 7.0, "high"),
        ExpressionSpec("no_reels_allowed", "focus", "anger", 0.4, "pout", 3.8, 6.5, "high"),
        ExpressionSpec("determined_win", "focus", "fire", 0.2, "default", 3.2, 6.5, "high"),
        ExpressionSpec("hype_coach", "laugh", "fire", 0.35, "happy_open", 4.0, 8.5, "high"),
        ExpressionSpec("pouty_cute", "focus", "blush_dots", 0.65, "pout", 2.2, 4.5, "normal"),
        ExpressionSpec("mock_offended", "focus", "sweat", 0.5, "pout", 2.5, 4.5, "normal"),
        ExpressionSpec("smug_victory", "focus", "trophy", 0.3, "smile", 2.9, 6.0, "high"),
        ExpressionSpec("challenge_mode", "focus", "star", 0.2, "default", 3.3, 6.5, "high"),
        ExpressionSpec("timer_watch", "think", "exclaim", 0.1, "default", 2.6, 5.0, "normal"),
        ExpressionSpec("deadline_sprint", "run_1", "fire", 0.3, "happy_open", 4.5, 8.0, "high"),
        ExpressionSpec("focus_cheer", "idle", "fire", 0.25, "smile", 3.0, 6.0, "high"),
        ExpressionSpec("quiet_supervising", "think", "", 0.1, "smile", 1.9, 3.8, "calm"),
        ExpressionSpec("impressed_nod", "talk", "star", 0.3, "smile", 2.7, 5.5, "normal"),
        ExpressionSpec("silly_tease", "laugh", "blush_dots", 0.55, "happy_open", 3.4, 7.0, "high"),
        ExpressionSpec("sassy_partner", "focus", "heart", 0.4, "default", 2.9, 5.5, "normal"),

        # --- Deep Empathy / Emotional Care / Crying Support (41-60) ---
        ExpressionSpec("crying_comfort", "care", "hug", 0.45, "smile", 1.6, 3.5, "calm"),
        ExpressionSpec("heart_hold", "care", "hearts", 0.5, "smile", 1.7, 3.8, "calm"),
        ExpressionSpec("gentle_reassure", "care", "heart", 0.35, "smile", 1.8, 4.0, "calm"),
        ExpressionSpec("worried_for_you", "care", "sweat", 0.25, "o", 1.9, 3.5, "calm"),
        ExpressionSpec("soft_empathy", "care", "sparkle", 0.3, "smile", 1.7, 3.5, "calm"),
        ExpressionSpec("breathe_with_me", "care", "water", 0.25, "o", 1.4, 5.0, "calm"),
        ExpressionSpec("calm_anchor", "care", "", 0.2, "smile", 1.5, 3.5, "calm"),
        ExpressionSpec("protective_care", "care", "fire", 0.3, "default", 2.2, 4.5, "normal"),
        ExpressionSpec("missing_you", "care", "heart", 0.6, "pout", 1.9, 4.0, "calm"),
        ExpressionSpec("proud_of_your_strength", "care", "star", 0.4, "smile", 2.1, 4.5, "calm"),
        ExpressionSpec("stress_relief", "care", "music", 0.3, "smile", 1.6, 4.0, "calm"),
        ExpressionSpec("overwhelmed_hug", "care", "hug", 0.55, "smile", 1.5, 3.5, "calm"),
        ExpressionSpec("quiet_company", "care", "", 0.2, "smile", 1.4, 3.0, "calm"),
        ExpressionSpec("healing_warmth", "care", "sun", 0.4, "smile", 1.8, 4.0, "calm"),
        ExpressionSpec("wipe_tears", "care", "hearts", 0.5, "smile", 1.6, 3.5, "calm"),
        ExpressionSpec("burnout_stop", "focus", "heart", 0.3, "pout", 2.0, 4.0, "calm"),
        ExpressionSpec("gentle_check_in", "talk", "heart", 0.3, "smile", 2.2, 4.5, "calm"),
        ExpressionSpec("mental_reset", "care", "sparkle", 0.25, "smile", 1.6, 4.0, "calm"),
        ExpressionSpec("lonely_companion", "care", "hug", 0.6, "smile", 1.7, 3.8, "calm"),
        ExpressionSpec("always_here", "care", "hearts", 0.65, "smile", 1.8, 4.2, "calm"),

        # --- Time-of-Day / Meals / Hydration / Sleep (61-84) ---
        ExpressionSpec("morning_sunrise", "idle", "sun", 0.35, "happy_open", 3.1, 6.5, "high"),
        ExpressionSpec("morning_hype", "laugh", "sun", 0.45, "happy_open", 3.8, 8.0, "high"),
        ExpressionSpec("breakfast_reminder", "eat", "sun", 0.3, "smile", 2.6, 5.5, "normal"),
        ExpressionSpec("morning_chai", "eat", "chai", 0.35, "smile", 2.4, 5.0, "normal"),
        ExpressionSpec("hydration_nudge", "eat", "water", 0.25, "default", 2.8, 5.5, "normal"),
        ExpressionSpec("water_celebrate", "laugh", "water", 0.35, "happy_open", 3.3, 7.0, "high"),
        ExpressionSpec("lunch_time", "eat", "chai", 0.3, "happy_open", 2.9, 6.0, "normal"),
        ExpressionSpec("lunch_scold", "focus", "chai", 0.35, "pout", 3.1, 5.5, "normal"),
        ExpressionSpec("afternoon_boost", "talk", "sparkle", 0.25, "default", 2.8, 5.5, "normal"),
        ExpressionSpec("chai_break", "eat", "chai", 0.45, "smile", 2.5, 5.5, "normal"),
        ExpressionSpec("snack_check", "eat", "heart", 0.35, "smile", 2.4, 5.0, "normal"),
        ExpressionSpec("evening_glow", "idle", "sparkle", 0.3, "smile", 2.2, 4.8, "calm"),
        ExpressionSpec("evening_review", "think", "star", 0.25, "default", 2.3, 4.5, "normal"),
        ExpressionSpec("dinner_time", "eat", "heart", 0.35, "smile", 2.5, 5.0, "normal"),
        ExpressionSpec("dinner_nudge", "eat", "exclaim", 0.3, "pout", 2.8, 5.5, "normal"),
        ExpressionSpec("cozy_night", "sleepy", "moon", 0.25, "smile", 1.6, 3.8, "sleepy"),
        ExpressionSpec("sleepy_yawn", "sleepy", "zzz", 0.2, "yawn", 1.3, 3.2, "sleepy"),
        ExpressionSpec("drowsy_blink", "sleepy", "zzz", 0.15, "o", 1.2, 3.0, "sleepy"),
        ExpressionSpec("midnight_care", "sleepy", "moon", 0.35, "pout", 1.5, 3.5, "sleepy"),
        ExpressionSpec("late_night_scold", "focus", "moon", 0.3, "pout", 2.4, 4.5, "normal"),
        ExpressionSpec("go_to_sleep_please", "sleepy", "heart", 0.4, "pout", 1.5, 3.5, "sleepy"),
        ExpressionSpec("eye_rest_reminder", "sleepy", "sparkle", 0.2, "smile", 1.6, 3.5, "sleepy"),
        ExpressionSpec("night_owl_company", "care", "moon", 0.35, "smile", 1.6, 3.8, "calm"),
        ExpressionSpec("sweet_dreams", "sleepy", "hearts", 0.45, "smile", 1.3, 3.2, "sleepy"),

        # --- Thinking / Curious / Surprised / Movement & Play (85-108) ---
        ExpressionSpec("curious_tilt", "think", "question", 0.2, "default", 2.3, 4.5, "normal"),
        ExpressionSpec("deep_thinking", "think", "question", 0.1, "o", 1.8, 3.8, "calm"),
        ExpressionSpec("lightbulb_idea", "talk", "idea", 0.35, "happy_open", 3.3, 7.0, "high"),
        ExpressionSpec("aha_moment", "laugh", "idea", 0.4, "happy_open", 3.6, 7.5, "high"),
        ExpressionSpec("confused_cute", "think", "question", 0.3, "o", 2.1, 4.2, "normal"),
        ExpressionSpec("surprised_gasp", "talk", "exclaim", 0.35, "o", 3.5, 7.0, "high"),
        ExpressionSpec("shocked_wide", "think", "exclaim", 0.25, "o", 3.8, 7.5, "high"),
        ExpressionSpec("nervous_sweat", "think", "sweat", 0.35, "o", 2.7, 5.0, "normal"),
        ExpressionSpec("relieved_sigh", "idle", "sweat", 0.3, "smile", 1.9, 4.0, "calm"),
        ExpressionSpec("listening_intently", "think", "sparkle", 0.2, "default", 2.1, 4.0, "calm"),
        ExpressionSpec("peeking_curious", "idle", "question", 0.25, "smile", 2.4, 4.5, "normal"),
        ExpressionSpec("music_vibing", "idle", "music", 0.35, "smile", 3.6, 7.2, "high"),
        ExpressionSpec("dancing_happy", "laugh", "music", 0.45, "happy_open", 4.5, 9.0, "high"),
        ExpressionSpec("celebration_trophy", "laugh", "trophy", 0.5, "happy_open", 4.0, 8.5, "high"),
        ExpressionSpec("cheerleader_hype", "laugh", "star", 0.45, "happy_open", 4.1, 8.5, "high"),
        ExpressionSpec("casual_stroll", "walk_1", "", 0.15, "default", 3.0, 4.0, "normal"),
        ExpressionSpec("happy_walk", "walk_1", "music", 0.25, "smile", 3.2, 4.5, "normal"),
        ExpressionSpec("patrol_walk", "walk_1", "sparkle", 0.15, "default", 3.0, 4.0, "normal"),
        ExpressionSpec("excited_run", "run_1", "sparkle", 0.35, "happy_open", 4.5, 6.0, "high"),
        ExpressionSpec("distraction_sprint", "run_1", "exclaim", 0.3, "default", 4.8, 6.5, "high"),
        ExpressionSpec("rescue_run", "run_1", "heart", 0.4, "o", 4.6, 6.0, "high"),
        ExpressionSpec("picked_up_giggle", "laugh", "hearts", 0.6, "happy_open", 4.0, 7.5, "high"),
        ExpressionSpec("welcome_back", "idle", "hearts", 0.45, "happy_open", 3.2, 6.5, "high"),
        ExpressionSpec("proud_partner", "care", "trophy", 0.5, "smile", 2.5, 5.2, "normal"),
    ]
    return {s.name: s for s in specs}


EXPRESSIONS: Dict[str, ExpressionSpec] = _build_108_expressions()


def pick_expression_for_context(
    text: str = "",
    event_type: str = "chat",
    hour: int = 12,
    mood: str = "",
) -> ExpressionSpec:
    """Pick the most fitting expression from all 108 expressions for the current moment."""
    low = (text or "").lower()

    if event_type == "emotional_support" or mood in {"crying", "distressed"} or any(
        w in low for w in ["cry", "rona", "upset", "alone", "breathe", "hug", "mat ro", "main hoon na"]
    ):
        if "breathe" in low or "saans" in low:
            return EXPRESSIONS["breathe_with_me"]
        if "hug" in low or "gale" in low:
            return EXPRESSIONS["overwhelmed_hug"]
        return EXPRESSIONS["crying_comfort"]

    if event_type == "distraction_nudge" or any(
        w in low for w in ["reels", "youtube", "instagram", "distract", "pakde", "wapas", "band karo"]
    ):
        if "reels" in low or "instagram" in low:
            return EXPRESSIONS["no_reels_allowed"]
        return EXPRESSIONS["playful_scold"]

    if event_type == "morning_briefing":
        return EXPRESSIONS["morning_hype"]

    if event_type == "celebration" or any(w in low for w in ["shabash", "proud", "jeet", "awesome", "win", "amazing"]):
        if "proud" in low:
            return EXPRESSIONS["super_proud"]
        return EXPRESSIONS["celebration_trophy"]

    if any(w in low for w in ["chai", "tea", "coffee"]):
        return EXPRESSIONS["chai_break"]
    if any(w in low for w in ["lunch", "breakfast", "dinner", "khana", "khaya", "eat", "meal"]):
        return EXPRESSIONS["lunch_time"]
    if any(w in low for w in ["water", "paani", "pani", "hydrat"]):
        return EXPRESSIONS["hydration_nudge"]
    if any(w in low for w in ["sleep", "so jao", "late", "neend", "rest", "goodnight"]):
        if hour >= 23 or hour < 5:
            return EXPRESSIONS["go_to_sleep_please"]
        return EXPRESSIONS["sleepy_yawn"]
    if any(w in low for w in ["haha", "hehe", "funny", "lol", "laugh"]):
        return EXPRESSIONS["giggling"]
    if any(w in low for w in ["idea", "plan", "goal", "focus"]):
        return EXPRESSIONS["lightbulb_idea"]
    if any(w in low for w in ["love", "jaan", "sweet", "miss", "cute", "darling"]):
        return EXPRESSIONS["shy_blush"]
    if "?" in low:
        return EXPRESSIONS["curious_tilt"]

    # Default time-of-day mood
    if hour >= 23 or hour < 5:
        return EXPRESSIONS["cozy_night"]
    if 5 <= hour < 10:
        return EXPRESSIONS["morning_sunrise"]
    if 16 <= hour < 18:
        return EXPRESSIONS["chai_break"]
    return EXPRESSIONS["cheerful_chat"]


def _detect_mouth_anchor(img: Image.Image) -> Tuple[int, int, Tuple[int, int, int]]:
    """Locate exact (cx, cy, skin_rgb) of the mouth for realistic ~6.5-head human proportions."""
    w, h = img.size
    px = img.load()

    # In realistic full-body proportions, face sits in top y=0.05..0.145
    y0, y1 = int(h * 0.085), int(h * 0.145)
    skin_xs = []
    skin_rgbs = []
    for y in range(y0, y1):
        for x in range(int(w * 0.25), int(w * 0.75)):
            r, g, b, a = px[x, y]
            if a < 220:
                continue
            if 130 <= r <= 235 and 80 <= g <= 185 and 50 <= b <= 145 and (r - b) > 25:
                skin_xs.append(x)
                skin_rgbs.append((r, g, b))

    face_cx = (sum(skin_xs) // len(skin_xs)) if skin_xs else int(w * 0.50)
    if skin_rgbs:
        skin_rgb = (
            sum(c[0] for c in skin_rgbs) // len(skin_rgbs),
            sum(c[1] for c in skin_rgbs) // len(skin_rgbs),
            sum(c[2] for c in skin_rgbs) // len(skin_rgbs),
        )
    else:
        skin_rgb = (195, 138, 102)

    return face_cx, int(h * 0.116), skin_rgb


def bake_mouth_frame(base_img: Image.Image, mouth_state: str, blush: float = 0.0) -> Image.Image:
    """Apply ultra-subtle realistic lip-sync micro-motion & soft cheek glow without cartoon overlays."""
    if mouth_state == "default" and blush <= 0.15:
        return base_img.copy()

    img = base_img.copy()
    w, h = img.size
    cx, cy, _ = _detect_mouth_anchor(img)

    # Very subtle soft rosy warmth on cheeks for high-blush moods
    if blush > 0.35:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        alpha = int(min(38, blush * 36))
        r_chk = max(3, int(h * 0.014))
        dx_chk = max(5, int(h * 0.025))
        for dx in (-dx_chk, dx_chk):
            odraw.ellipse((cx + dx - r_chk, cy - r_chk - 2, cx + dx + r_chk, cy + 1), fill=(255, 110, 140, alpha))
        opx = overlay.load()
        bpx = base_img.load()
        for y in range(max(0, cy - r_chk - 4), min(h, cy + 4)):
            for x in range(max(0, cx - dx_chk - r_chk - 2), min(w, cx + dx_chk + r_chk + 2)):
                if bpx[x, y][3] < 200:
                    opx[x, y] = (0, 0, 0, 0)
        img = Image.alpha_composite(img, overlay)

    # Subtle realistic mouth opening (proportional to realistic face size — never oversized cartoon!)
    if mouth_state in {"small", "mid", "wide", "o", "yawn"}:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        rx = max(2, int(h * (0.012 if mouth_state in {"mid", "wide"} else 0.008)))
        ry = max(1, int(h * (0.007 if mouth_state in {"wide", "yawn"} else 0.0045)))
        odraw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(115, 38, 48, 175))
        img = Image.alpha_composite(img, overlay)

    return img
