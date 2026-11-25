"""Simi — Autonomous Floating/Walking/Running Animated Companion with 108 Expressions, Lip-Sync & Clock Awareness."""

from __future__ import annotations

import asyncio
import logging
import math
import queue
import random
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import ttk
from typing import Dict, Optional, Tuple

from PIL import Image, ImageTk

from app import ai_engine, db, natural_memory
from app.config import BASE_DIR, load_config, save_config
from app.emotion_monitor import emotion_detector
from app.expression_engine import (
    EXPRESSIONS,
    ExpressionSpec,
    bake_mouth_frame,
    pick_expression_for_context,
)
from app.screen_monitor import (
    capture_screen_thumbnail,
    classify_window,
    cleanup_old_screenshots,
    get_active_window_info,
)
from app.time_routines import routine_engine
from app.voice import voice_engine
from app.voice_listener import record_utterance, transcribe_audio_sync

logger = logging.getLogger("simi.companion")

ASSETS_DIR = BASE_DIR / "assets"
TRANSPARENT_KEY = "#010203"

# Natural syllable-like lip-sync sequence (~11 Hz while speaking)
LIP_SYNC_SEQ = ("closed", "small", "mid", "wide", "mid", "o", "small", "mid", "closed", "small", "wide", "o")

EMOTE_GLYPHS: Dict[str, Tuple[str, str]] = {
    "heart": ("♥", "#fb7185"),
    "hearts": ("♥ ♥", "#f43f5e"),
    "hug": ("♡♥♡", "#ec4899"),
    "sparkle": ("✦✧", "#fbbf24"),
    "star": ("★", "#facc15"),
    "zzz": ("Zzz", "#93c5fd"),
    "anger": ("💢", "#ef4444"),
    "question": ("?", "#38bdf8"),
    "exclaim": ("!", "#f97316"),
    "idea": ("💡", "#fde047"),
    "water": ("💧", "#38bdf8"),
    "chai": ("☕", "#f59e0b"),
    "music": ("♪ ♫", "#c084fc"),
    "sweat": ("💦", "#60a5fa"),
    "fire": ("🔥", "#f97316"),
    "sun": ("☀", "#fbbf24"),
    "moon": ("☾", "#a5b4fc"),
    "trophy": ("🏆", "#facc15"),
    "blush_dots": ("〃", "#fb7185"),
}


@dataclass
class CompanionEvent:
    kind: str  # "speak", "expression", "move"
    text: str = ""
    expression: str = "happy_wave"
    move_mode: str = "walk"  # "walk", "run", "float", "stay"
    duration_sec: float = 8.0


def _ease_in_out(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


class FloatingSimiApp:
    """Autonomous animated girl companion: walks, runs, floats, lip-syncs, 108 expressions & clock-aware."""

    def __init__(self) -> None:
        db.init_db()
        voice_engine.start()

        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self.root = tk.Tk()
        self.root.title("Simi")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT_KEY)
        self.root.configure(bg=TRANSPARENT_KEY)

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        # Load base PIL sprites and lazily cache baked mouth/blush PhotoImages
        self.base_images: Dict[str, Image.Image] = {}
        self._photo_cache: Dict[Tuple[str, str, str, int], ImageTk.PhotoImage] = {}
        self.sprite_w = 150
        self.sprite_h = 185
        self._load_base_sprites()

        self.canvas_w = self.sprite_w + 56
        self.canvas_h = self.sprite_h + 46
        self.canvas = tk.Canvas(
            self.root,
            width=self.canvas_w,
            height=self.canvas_h,
            bg=TRANSPARENT_KEY,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()

        # Starting position: standing cheerfully above taskbar near bottom-right
        self.floor_y = float(self.screen_h - self.sprite_h - 74)
        self.x = float(self.screen_w - self.sprite_w - 80)
        self.y = self.floor_y
        self.target_x = self.x
        self.target_y = self.y
        self.move_start_x = self.x
        self.move_start_y = self.y
        self.move_start_t = 0.0
        self.move_duration = 1.0
        self.is_moving = False
        self.move_mode = "walk"  # "walk", "run", "float"
        self.facing = "left"
        self.free_roam = True
        self.meeting_paused = False
        self.next_roam_at = time.time() + random.uniform(6.0, 12.0)
        self.next_micro_expr_at = time.time() + random.uniform(14.0, 25.0)

        # Expression & lip-sync state
        self.current_expr: ExpressionSpec = self._default_time_expression()
        self.expr_until = 0.0
        self.lip_sync_until = 0.0
        self._lip_idx = 0
        self._last_lip_t = 0.0

        # Drag state
        self._dragging = False
        self._drag_moved = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._drag_start_x = 0.0
        self._drag_start_y = 0.0

        # Canvas items: character sprite + floating emote glyph
        self._img_item = self.canvas.create_image(
            self.canvas_w // 2,
            self.canvas_h // 2 + 6,
            image=self._get_photo(self.current_expr.pose, self.facing, "default", self.current_expr.blush),
        )
        self._emote_shadow = self.canvas.create_text(
            self.canvas_w - 22,
            24,
            text="",
            fill="#111827",
            font=("Segoe UI Emoji", 14, "bold"),
        )
        self._emote_item = self.canvas.create_text(
            self.canvas_w - 23,
            23,
            text="",
            fill="#fbbf24",
            font=("Segoe UI Emoji", 14, "bold"),
        )

        # Mouse bindings
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Double-Button-1>", lambda _e: self.open_chat_popup())

        # Floating speech bubble
        self.bubble_win = tk.Toplevel(self.root)
        self.bubble_win.overrideredirect(True)
        self.bubble_win.attributes("-topmost", True)
        self.bubble_win.attributes("-transparentcolor", TRANSPARENT_KEY)
        self.bubble_win.configure(bg=TRANSPARENT_KEY)
        self.bubble_frame = tk.Frame(
            self.bubble_win,
            bg="#fff7f3",
            highlightbackground="#f472b6",
            highlightthickness=2,
            padx=12,
            pady=8,
        )
        self.bubble_frame.pack()
        self.bubble_label = tk.Label(
            self.bubble_frame,
            text="",
            bg="#fff7f3",
            fg="#1f2937",
            font=("Segoe UI", 10),
            wraplength=265,
            justify="left",
        )
        self.bubble_label.pack()
        self.bubble_label.bind("<Button-1>", lambda _e: self.open_chat_popup())
        self.bubble_win.withdraw()
        self.bubble_hide_at = 0.0

        self.chat_win: Optional[tk.Toplevel] = None
        self.chat_entry: Optional[tk.Entry] = None
        self.settings_win: Optional[tk.Toplevel] = None

        # Autonomous brain thread
        self.events: queue.Queue[CompanionEvent] = queue.Queue()
        self._stop_event = threading.Event()
        self._distracted_since: Optional[float] = None
        self._last_nudge_at = 0.0
        self._last_checkin_at = time.time()
        self._last_emotion_at = 0.0
        self._last_emotion_alert_at = 0.0
        self._last_cleanup_at = 0.0
        self._last_praise_at = time.time()

        self._brain_thread = threading.Thread(
            target=self._autonomous_brain_loop, daemon=True, name="SimiBrain"
        )
        self._brain_thread.start()

        self._is_listening_once = False
        self._last_voice_chat_at = 0.0
        self._mic_thread = threading.Thread(
            target=self._hands_free_mic_loop, daemon=True, name="SimiMic"
        )
        self._mic_thread.start()

        self._schedule_startup_greeting()
        self._update_geometry()
        self.root.after(33, self._tick)

    def _load_base_sprites(self) -> None:
        files = {
            "idle": ASSETS_DIR / "simi_idle.png",
            "talk": ASSETS_DIR / "simi_talk.png",
            "focus": ASSETS_DIR / "simi_focus.png",
            "care": ASSETS_DIR / "simi_care.png",
            "walk_1": ASSETS_DIR / "simi_walk_1.png",
            "walk_2": ASSETS_DIR / "simi_walk_2.png",
            "run_1": ASSETS_DIR / "simi_run_1.png",
            "run_2": ASSETS_DIR / "simi_run_2.png",
            "sleepy": ASSETS_DIR / "simi_sleepy.png",
            "laugh": ASSETS_DIR / "simi_laugh.png",
        }
        fallback = files["idle"]
        for key, path in files.items():
            src = path if path.exists() else fallback
            if src.exists():
                img = Image.open(src).convert("RGBA")
                self.base_images[key] = img
                if key == "idle":
                    self.sprite_w, self.sprite_h = img.size
            else:
                self.base_images[key] = Image.new("RGBA", (120, 150), (244, 114, 182, 255))

        # Aliases for expression specs
        self.base_images["think"] = self.base_images.get("idle", self.base_images["idle"])
        self.base_images["eat"] = self.base_images.get("talk", self.base_images["idle"])

    def _get_photo(
        self, pose: str, facing: str, mouth_state: str = "default", blush: float = 0.0
    ) -> ImageTk.PhotoImage:
        blush_bucket = 0 if blush < 0.25 else (1 if blush < 0.6 else 2)
        pose_key = pose if pose in self.base_images else "idle"
        cache_key = (pose_key, facing, mouth_state, blush_bucket)
        cached = self._photo_cache.get(cache_key)
        if cached is not None:
            return cached

        base = self.base_images[pose_key]
        baked = bake_mouth_frame(base, mouth_state, blush=blush_bucket * 0.42)
        # Note: our generated walk/run/idle sprites naturally face right; flip when moving left
        if facing == "left":
            baked = baked.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        photo = ImageTk.PhotoImage(baked)
        # Cap cache size conservatively
        if len(self._photo_cache) > 320:
            self._photo_cache.clear()
        self._photo_cache[cache_key] = photo
        return photo

    def _default_time_expression(self) -> ExpressionSpec:
        h = datetime.now().hour
        if h >= 23 or h < 5:
            return EXPRESSIONS["cozy_night"]
        if 5 <= h < 10:
            return EXPRESSIONS["morning_sunrise"]
        if 16 <= h < 18:
            return EXPRESSIONS["chai_break"]
        return EXPRESSIONS["happy_wave"]

    def _schedule_startup_greeting(self) -> None:
        def _greet():
            time.sleep(1.0)
            cfg = load_config()
            summary = db.get_daily_summary()
            h = datetime.now().hour
            time_str = datetime.now().strftime("%I:%M %p").lstrip("0")

            if 5 <= h <= 10 and summary["state"].get("morning_briefing_done", 0) == 0:
                msg = asyncio.run(ai_engine.generate_morning_briefing(cfg, summary))
                db.mark_morning_briefing_done()
                expr = "morning_hype"
                mode = "run"
            elif h >= 23 or h < 5:
                msg = (
                    f"Suno na, dekho {time_str} baj gaye hain — main aa gayi hoon tumhare saath. "
                    f"Jaldi kaam wrap up karke thoda rest bhi lena, okay?"
                )
                expr = "cozy_night"
                mode = "walk"
            else:
                msg = (
                    f"Hey suno na! {time_str} ho gaya — main aa gayi hoon. "
                    f"Batao abhi kya kar rahe ho, aaj kaam saath mein finish karte hain!"
                )
                expr = "happy_wave"
                mode = "run"

            db.add_message("assistant", msg, event_type="greeting")
            self.events.put(
                CompanionEvent("move", expression=expr, move_mode=mode, duration_sec=9.0)
            )
            self.events.put(
                CompanionEvent("speak", text=msg, expression=expr, duration_sec=9.5)
            )
            voice_engine.speak(msg)

        threading.Thread(target=_greet, daemon=True).start()

    # ---------------- Mouse & Interaction ----------------

    def _on_press(self, event: tk.Event) -> None:
        self._dragging = True
        self._drag_moved = False
        self.is_moving = False
        self._drag_offset_x = event.x
        self._drag_offset_y = event.y
        self._drag_start_x = self.x
        self._drag_start_y = self.y

    def _on_drag(self, event: tk.Event) -> None:
        if not self._dragging:
            return
        nx = self.root.winfo_pointerx() - self._drag_offset_x
        ny = self.root.winfo_pointery() - self._drag_offset_y
        nx = max(10, min(self.screen_w - self.canvas_w - 10, nx))
        ny = max(10, min(self.screen_h - self.canvas_h - 35, ny))
        if abs(nx - self._drag_start_x) > 8 or abs(ny - self._drag_start_y) > 8:
            self._drag_moved = True
        self.facing = "right" if nx >= self.x else "left"
        self.x, self.y = float(nx), float(ny)
        self._update_geometry()

    def _on_release(self, _event: tk.Event) -> None:
        was_moved = self._drag_moved
        self._dragging = False
        self._drag_moved = False
        if not was_moved:
            self.open_chat_popup()
        else:
            self.next_roam_at = time.time() + random.uniform(12.0, 22.0)
            if random.random() < 0.55:
                quips = [
                    "Hehe, okay okay I'll stay right here with you!",
                    "Arey wah, nice spot! Main yahin se dekhti hoon.",
                    "Wheee! Chalo yahan se saath kaam karte hain!",
                ]
                self.show_bubble(random.choice(quips), expr_name="picked_up_giggle", duration_sec=4.5)

    def _on_right_click(self, event: tk.Event) -> None:
        cfg = load_config()
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Talk to Simi (Type)", command=self.open_chat_popup)
        menu.add_command(label="Listen to Me Now (Mic)", command=self.trigger_listen_once)
        menu.add_command(
            label=f"Hands-Free 'Simi' Mic: {'ON' if cfg.hands_free_listening else 'OFF'}",
            command=lambda: self._toggle_cfg("hands_free_listening"),
        )
        menu.add_command(label="I'm feeling low / need comfort", command=self._trigger_comfort)
        menu.add_command(label="Morning Check-in", command=self._trigger_morning)
        menu.add_separator()
        menu.add_command(
            label=f"Interview & Study Prep Mode: {'ON' if cfg.interview_prep_mode else 'OFF'}",
            command=self._toggle_interview_prep,
        )
        menu.add_command(
            label="Meeting / Screen-Share Pause (Hide to Tray)",
            command=self.toggle_meeting_pause,
        )
        menu.add_separator()
        menu.add_command(label="Walk Around Now", command=lambda: self._roam_now("walk"))
        menu.add_command(label="Run Around Excitedly!", command=lambda: self._roam_now("run"))
        menu.add_command(label=f"Show Random Expression ({len(EXPRESSIONS)} total)", command=self._trigger_random_expression)
        menu.add_separator()
        menu.add_command(
            label=f"Free Roaming: {'ON' if self.free_roam else 'OFF'}",
            command=self._toggle_roam,
        )
        menu.add_command(
            label=f"Voice: {'ON' if cfg.voice_enabled else 'OFF'}",
            command=lambda: self._toggle_cfg("voice_enabled"),
        )
        menu.add_command(
            label=f"Screen Watching: {'ON' if cfg.screen_monitor_enabled else 'OFF'}",
            command=lambda: self._toggle_cfg("screen_monitor_enabled"),
        )
        menu.add_command(
            label=f"Webcam Emotion Care: {'ON' if cfg.webcam_emotion_enabled else 'OFF'}",
            command=lambda: self._toggle_cfg("webcam_emotion_enabled"),
        )
        menu.add_separator()
        menu.add_command(label="Open 3D Character Studio", command=self._open_3d_studio)
        menu.add_command(label="AI Brain & Name Settings...", command=self.open_settings_dialog)
        menu.add_command(label="Quit Simi", command=self.quit)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _open_3d_studio(self) -> None:
        import webbrowser
        webbrowser.open("https://rahulgupta37079-oss.github.io/simi-companion/3d-studio.html")

    def _roam_now(self, mode: str) -> None:
        tx, ty = self._pick_autonomous_spot(mode)
        self._start_move_to(tx, ty, mode=mode)

    def _trigger_random_expression(self) -> None:
        spec = random.choice(list(EXPRESSIONS.values()))
        self.set_expression(spec.name, duration_sec=6.0)
        label = spec.name.replace("_", " ").title()
        self.show_bubble(f"Expression: {label}!", expr_name=spec.name, duration_sec=4.0, animate_mouth=True)

    def _toggle_interview_prep(self) -> None:
        cfg = load_config()
        cfg.interview_prep_mode = not cfg.interview_prep_mode
        save_config(cfg)
        if cfg.interview_prep_mode:
            msg = "Chalo! Interview and Study Prep mode ON hai. Mujhe batao kis topic ya role ke liye practice karni hai, main mock questions puchhungi!"
            self.show_bubble(msg, expr_name="lightbulb_idea", duration_sec=8.0)
            voice_engine.speak(msg)
        else:
            msg = "Prep mode off kar diya! Wapas normal hangout mode mein aa gaye."
            self.show_bubble(msg, expr_name="warm_smile", duration_sec=4.5)

    def toggle_meeting_pause(self) -> None:
        """Cleanly pause and hide Simi during screen-sharing or meetings, and restore from tray anytime."""
        self.meeting_paused = not self.meeting_paused
        if self.meeting_paused:
            self.bubble_win.withdraw()
            if self.chat_win and self.chat_win.winfo_exists():
                self.chat_win.destroy()
            self.root.withdraw()
        else:
            self.root.deiconify()
            self.root.lift()
            self.show_bubble("Suno na, main wapas aa gayi! Meeting kaisi rahi?", expr_name="welcome_back", duration_sec=6.0)

    def _toggle_roam(self) -> None:
        self.free_roam = not self.free_roam
        state = "Yay! I'll walk & run around freely!" if self.free_roam else "Okay, staying right beside you here."
        self.show_bubble(state, expr_name="happy_wave" if self.free_roam else "warm_smile", duration_sec=4.0)

    def _toggle_cfg(self, key: str) -> None:
        cfg = load_config()
        val = not getattr(cfg, key)
        setattr(cfg, key, val)
        save_config(cfg)
        label = key.replace("_", " ").title()
        self.show_bubble(f"{label}: {'ON' if val else 'OFF'}", expr_name="proud_smile", duration_sec=3.5)

    def _trigger_comfort(self) -> None:
        def _work():
            cfg = load_config()
            db.add_checkin("Crying", energy=2, note="Requested comfort", source="manual")
            summary = db.get_daily_summary()
            msg = asyncio.run(ai_engine.generate_crying_support(cfg, summary))
            db.add_message("assistant", msg, event_type="emotional_support")
            self.events.put(CompanionEvent("move", expression="crying_comfort", move_mode="run"))
            self.events.put(CompanionEvent("speak", text=msg, expression="crying_comfort", duration_sec=12.0))
            voice_engine.speak(msg)

        threading.Thread(target=_work, daemon=True).start()

    def _trigger_morning(self) -> None:
        def _work():
            cfg = load_config()
            summary = db.get_daily_summary()
            msg = asyncio.run(ai_engine.generate_morning_briefing(cfg, summary))
            db.mark_morning_briefing_done()
            db.add_message("assistant", msg, event_type="morning_briefing")
            self.events.put(CompanionEvent("move", expression="morning_hype", move_mode="run"))
            self.events.put(CompanionEvent("speak", text=msg, expression="morning_hype", duration_sec=10.0))
            voice_engine.speak(msg)

        threading.Thread(target=_work, daemon=True).start()

    # ---------------- Expressions, Bubble & Whisper Chat ----------------

    def set_expression(self, expr_name: str, duration_sec: float = 8.0) -> None:
        self.current_expr = EXPRESSIONS.get(expr_name) or self._default_time_expression()
        self.expr_until = time.time() + max(3.0, duration_sec)

    def show_bubble(
        self,
        text: str,
        expr_name: str = "cheerful_chat",
        duration_sec: float = 8.0,
        animate_mouth: bool = True,
    ) -> None:
        self.set_expression(expr_name, duration_sec=max(duration_sec, 4.5))
        if animate_mouth:
            # Animate working mouth for estimated spoken reading time even if TTS is muted
            est_talk = max(2.2, min(11.0, len(text) * 0.055))
            self.lip_sync_until = time.time() + est_talk
        self.bubble_label.configure(text=text)
        self.bubble_win.deiconify()
        self.bubble_win.update_idletasks()
        self._position_bubble()
        self.bubble_hide_at = time.time() + duration_sec

    def _position_bubble(self) -> None:
        if not self.bubble_win.winfo_viewable():
            return
        bw = self.bubble_win.winfo_reqwidth()
        bh = self.bubble_win.winfo_reqheight()
        bx = int(self.x + (self.canvas_w // 2) - (bw // 2))
        by = int(self.y - bh - 4)
        bx = max(12, min(self.screen_w - bw - 12, bx))
        if by < 12:
            by = int(self.y + self.canvas_h + 6)
        self.bubble_win.geometry(f"+{bx}+{by}")

    def open_chat_popup(self) -> None:
        if self.chat_win and self.chat_win.winfo_exists():
            self.chat_win.lift()
            if self.chat_entry:
                self.chat_entry.focus_force()
            return

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#1f2430", highlightbackground="#f472b6", highlightthickness=2)

        frame = tk.Frame(win, bg="#1f2430", padx=8, pady=7)
        frame.pack()

        entry = tk.Entry(
            frame,
            width=30,
            bg="#11141c",
            fg="#f9fafb",
            insertbackground="#f59e0b",
            relief="flat",
            font=("Segoe UI", 10),
        )
        entry.pack(side="left", padx=(0, 6), ipady=4)

        def submit(_event=None):
            text = entry.get().strip()
            if not text:
                return
            win.destroy()
            self.chat_win = None
            self._handle_user_chat(text)

        tk.Button(
            frame,
            text="Mic",
            command=lambda: (win.destroy(), self.trigger_listen_once()),
            bg="#ec4899",
            fg="#ffffff",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=3,
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            frame,
            text="Send",
            command=submit,
            bg="#f59e0b",
            fg="#111827",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=3,
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            frame,
            text="x",
            command=lambda: win.destroy(),
            bg="#2a3040",
            fg="#e5e7eb",
            relief="flat",
            font=("Segoe UI", 9),
            padx=6,
            pady=3,
        ).pack(side="left")

        entry.bind("<Return>", submit)
        entry.bind("<Escape>", lambda _e: win.destroy())

        win.update_idletasks()
        cw = win.winfo_reqwidth()
        ch = win.winfo_reqheight()
        cx = int(max(12, min(self.screen_w - cw - 12, self.x + self.canvas_w // 2 - cw // 2)))
        cy = int(self.y + self.canvas_h + 6)
        if cy + ch > self.screen_h - 45:
            cy = int(max(12, self.y - ch - 8))
        win.geometry(f"+{cx}+{cy}")
        entry.focus_force()

        self.chat_win = win
        self.chat_entry = entry

    def trigger_listen_once(self) -> None:
        """Push-to-talk: listen to the user's microphone once and respond naturally."""
        if self._is_listening_once or self.meeting_paused:
            return
        self._is_listening_once = True
        self.show_bubble("Haan bolo na, sun rahi hoon... (Listening)", expr_name="listening_intently", duration_sec=10.0, animate_mouth=False)

        def _work():
            try:
                cfg = load_config()
                wav = record_utterance(
                    max_duration_sec=12.0,
                    start_timeout_sec=7.0,
                    silence_stop_sec=1.25,
                    device_index=cfg.mic_device_index,
                    abort_check=lambda: self._stop_event.is_set() or self.meeting_paused,
                )
                if not wav:
                    self.events.put(
                        CompanionEvent("speak", text="Arey mujhe aawaz nahi aayi — phir se bolo na!", expression="curious_tilt", duration_sec=4.5)
                    )
                    return
                text, vocal_mood = transcribe_audio_sync(wav, cfg)
                if not text:
                    self.events.put(
                        CompanionEvent("speak", text="Sorry, clear sunai nahi diya — ek baar aur bolo na!", expression="curious_tilt", duration_sec=4.5)
                    )
                    return
                self._last_voice_chat_at = time.time()
                self._respond_to_heard_speech(text, vocal_mood)
            finally:
                self._is_listening_once = False

        threading.Thread(target=_work, daemon=True, name="SimiListenOnce").start()

    def _respond_to_heard_speech(self, user_text: str, vocal_mood: str = "neutral") -> None:
        cfg = load_config()
        recorded = natural_memory.capture_from_chat(user_text)
        if vocal_mood in {"crying", "sad"} and "mood" not in recorded:
            db.add_checkin("Crying" if vocal_mood == "crying" else "Stressed", energy=2, note=f"Voice tone: {vocal_mood}", source="voice")
            recorded["mood"] = "crying" if vocal_mood == "crying" else "distressed"

        db.add_message("user", user_text, event_type="voice_chat")
        summary = db.get_daily_summary()
        history = db.get_recent_messages(18)

        prompt_text = user_text
        if vocal_mood in {"crying", "sad", "tired", "stressed"}:
            prompt_text = f"{user_text} [Note: their voice sounded {vocal_mood}]"

        reply = asyncio.run(ai_engine.generate_chat_reply(prompt_text, history, cfg, summary))
        db.add_message("assistant", reply, event_type="voice_chat")

        expr = pick_expression_for_context(
            text=reply + " " + user_text,
            event_type="emotional_support" if vocal_mood in {"crying", "sad"} else "chat",
            hour=datetime.now().hour,
            mood=str(recorded.get("mood", "")),
        )
        dur = max(6.0, min(15.0, len(reply) * 0.065))
        if vocal_mood in {"crying", "sad"}:
            self.events.put(CompanionEvent("move", expression=expr.name, move_mode="run"))
        self.events.put(CompanionEvent("speak", text=reply, expression=expr.name, duration_sec=dur))
        voice_engine.speak(reply)

    def _hands_free_mic_loop(self) -> None:
        """Background hands-free listener: wakes when you say 'Simi' or continue a voice conversation."""
        time.sleep(3.5)
        while not self._stop_event.is_set():
            cfg = load_config()
            if (
                not cfg.hands_free_listening
                or self.meeting_paused
                or self._is_listening_once
                or voice_engine.is_speaking
                or not cfg.gemini_api_key.strip()
            ):
                time.sleep(0.8)
                continue

            wav = record_utterance(
                max_duration_sec=9.0,
                start_timeout_sec=4.0,
                silence_stop_sec=1.1,
                device_index=cfg.mic_device_index,
                abort_check=lambda: (
                    self._stop_event.is_set()
                    or self.meeting_paused
                    or self._is_listening_once
                    or voice_engine.is_speaking
                    or not load_config().hands_free_listening
                ),
            )
            if not wav:
                continue

            text, vocal_mood = transcribe_audio_sync(wav, cfg)
            if not text:
                continue

            low = text.lower()
            wake_words = (cfg.assistant_name.lower(), "simi", "seemi", "suno", "hey simi")
            in_active_convo = (time.time() - self._last_voice_chat_at) < 35.0
            if any(w in low for w in wake_words) or in_active_convo or vocal_mood == "crying":
                self._last_voice_chat_at = time.time()
                self._respond_to_heard_speech(text, vocal_mood)
                # Brief cooldown after Simi starts replying so we don't hear her own voice
                time.sleep(1.5)

    def _handle_user_chat(self, user_text: str) -> None:
        self.show_bubble("Hmm, sun rahi hoon...", expr_name="listening_intently", duration_sec=6.0, animate_mouth=False)

        def _work():
            cfg = load_config()
            recorded = natural_memory.capture_from_chat(user_text)
            db.add_message("user", user_text, event_type="chat")
            summary = db.get_daily_summary()
            history = db.get_recent_messages(18)
            reply = asyncio.run(ai_engine.generate_chat_reply(user_text, history, cfg, summary))
            db.add_message("assistant", reply, event_type="chat")

            expr = pick_expression_for_context(
                text=reply + " " + user_text,
                event_type="chat",
                hour=datetime.now().hour,
                mood=str(recorded.get("mood", "")),
            )
            dur = max(6.0, min(15.0, len(reply) * 0.065))
            self.events.put(CompanionEvent("speak", text=reply, expression=expr.name, duration_sec=dur))
            voice_engine.speak(reply)

        threading.Thread(target=_work, daemon=True).start()

    # ---------------- Compact Native Settings Dialog ----------------

    def open_settings_dialog(self) -> None:
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return

        cfg = load_config()
        win = tk.Toplevel(self.root)
        win.title("Simi — AI Brain & Profile")
        win.attributes("-topmost", True)
        win.configure(bg="#171a23")
        win.geometry("430x430")
        win.resizable(False, False)

        pad = {"padx": 14, "pady": 4}

        def lbl(txt):
            tk.Label(win, text=txt, bg="#171a23", fg="#cbd5e1", font=("Segoe UI", 9)).pack(
                anchor="w", **pad
            )

        lbl("Your first name (leave blank for natural 'suno na / tumne / aapne'):")
        name_var = tk.StringVar(value="" if (cfg.user_name or "").lower() == "partner" else cfg.user_name)
        tk.Entry(win, textvariable=name_var, bg="#1f2430", fg="#fff", insertbackground="#fff", relief="flat").pack(
            fill="x", padx=14, ipady=4
        )

        lbl("Simi's Voice:")
        voice_var = tk.StringVar(value=cfg.voice_name)
        ttk.Combobox(
            win,
            textvariable=voice_var,
            state="readonly",
            values=[
                "en-IN-NeerjaExpressiveNeural",
                "hi-IN-SwaraNeural",
                "en-IN-NeerjaNeural",
                "en-US-JennyNeural",
                "en-GB-SoniaNeural",
            ],
        ).pack(fill="x", padx=14, pady=2)

        lbl("AI Brain:")
        prov_var = tk.StringVar(value=cfg.ai_provider)
        ttk.Combobox(
            win,
            textvariable=prov_var,
            state="readonly",
            values=["auto", "gemini", "groq", "ollama", "builtin"],
        ).pack(fill="x", padx=14, pady=2)

        lbl("Google Gemini API Key:")
        gem_var = tk.StringVar(value=cfg.gemini_api_key)
        tk.Entry(win, textvariable=gem_var, show="*", bg="#1f2430", fg="#fff", insertbackground="#fff", relief="flat").pack(
            fill="x", padx=14, ipady=4
        )

        lbl("Groq Free API Key:")
        groq_var = tk.StringVar(value=cfg.groq_api_key)
        tk.Entry(win, textvariable=groq_var, show="*", bg="#1f2430", fg="#fff", insertbackground="#fff", relief="flat").pack(
            fill="x", padx=14, ipady=4
        )

        status_lbl = tk.Label(win, text="", bg="#171a23", fg="#fde68a", font=("Segoe UI", 9), wraplength=390)
        status_lbl.pack(anchor="w", padx=14, pady=6)

        btn_row = tk.Frame(win, bg="#171a23")
        btn_row.pack(fill="x", padx=14, pady=8)

        def save_only():
            c = load_config()
            c.user_name = name_var.get().strip()
            c.voice_name = voice_var.get().strip() or "en-IN-NeerjaExpressiveNeural"
            c.ai_provider = prov_var.get()
            c.gemini_api_key = gem_var.get().strip()
            c.groq_api_key = groq_var.get().strip()
            save_config(c)
            status_lbl.configure(text="Saved! Simi updated.")

        def test_voice_btn():
            save_only()
            voice_engine.speak("Suno na, tumne khana khaya? Aapne yeh kitne achhe se kiya, so proud!")
            status_lbl.configure(text="Speaking sample with selected voice...")

        def test_conn():
            save_only()
            status_lbl.configure(text="Testing AI connection...")

            def _t():
                res = asyncio.run(ai_engine.test_active_ai(load_config()))
                msg = f"Connected! Simi: {res['reply']}" if res.get("ok") else f"Note: {res.get('error')}"
                win.after(0, lambda: status_lbl.configure(text=msg))

            threading.Thread(target=_t, daemon=True).start()

        tk.Button(btn_row, text="Test Voice", command=test_voice_btn, bg="#2a3040", fg="#fff", relief="flat", padx=10, pady=5).pack(side="left", padx=(0, 6))
        tk.Button(btn_row, text="Test AI", command=test_conn, bg="#2a3040", fg="#fff", relief="flat", padx=10, pady=5).pack(side="left")
        tk.Button(btn_row, text="Save & Close", command=lambda: (save_only(), win.destroy()), bg="#f59e0b", fg="#111", relief="flat", font=("Segoe UI", 9, "bold"), padx=14, pady=5).pack(side="right")
        self.settings_win = win

    # ---------------- Walking, Running & Floating Movement ----------------

    def _start_move_to(self, tx: float, ty: float, mode: str = "walk") -> None:
        tx = max(14.0, min(float(self.screen_w - self.canvas_w - 14), tx))
        ty = max(20.0, min(float(self.screen_h - self.canvas_h - 46), ty))
        self.move_start_x = self.x
        self.move_start_y = self.y
        self.target_x = tx
        self.target_y = ty
        self.move_mode = mode
        dist = math.hypot(tx - self.x, ty - self.y)
        speed_px_s = 360.0 if mode == "run" else (165.0 if mode == "walk" else 220.0)
        self.move_duration = max(0.8, min(5.5, dist / speed_px_s))
        self.move_start_t = time.time()
        self.is_moving = True
        if abs(tx - self.x) > 8:
            self.facing = "right" if tx > self.x else "left"

    def _pick_autonomous_spot(self, mode: str = "walk") -> Tuple[float, float]:
        w, h = self.screen_w, self.screen_h
        cw, ch = self.canvas_w, self.canvas_h
        floor = h - ch - 48
        if mode in {"walk", "run"}:
            # Walk / run cleanly along the bottom taskbar floor!
            spots = [
                (w - cw - 30, floor),
                (w * 0.72, floor),
                (w * 0.48, floor),
                (w * 0.22, floor),
                (30, floor),
            ]
        else:
            # Float gracefully up to screen edges & corners
            spots = [
                (w - cw - 26, h * 0.44),
                (w - cw - 40, 55),
                (26, h * 0.42),
                (w * 0.76, 52),
                (w - cw - 30, floor),
            ]
        far = [s for s in spots if math.hypot(s[0] - self.x, s[1] - self.y) > 220]
        return random.choice(far or spots)

    def _update_geometry(self, bob_y: float = 0.0) -> None:
        gx = int(self.x)
        gy = int(self.y + bob_y)
        self.root.geometry(f"{self.canvas_w}x{self.canvas_h}+{gx}+{gy}")
        self._position_bubble()

    def _tick(self) -> None:
        if self._stop_event.is_set():
            return
        now = time.time()

        # Drain events from autonomous brain
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                break
            if ev.kind == "speak":
                self.show_bubble(ev.text, expr_name=ev.expression, duration_sec=ev.duration_sec, animate_mouth=True)
            elif ev.kind == "expression":
                self.set_expression(ev.expression, duration_sec=ev.duration_sec)
            elif ev.kind == "move":
                self.set_expression(ev.expression, duration_sec=max(6.0, ev.duration_sec))
                if ev.move_mode != "stay":
                    # Run or walk toward right-center along the taskbar so she catches your eye naturally
                    tx = self.screen_w * 0.68
                    ty = self.floor_y if ev.move_mode in {"walk", "run"} else self.screen_h * 0.46
                    self._start_move_to(tx, ty, mode=ev.move_mode)

        # Hide speech bubble after speaking completes
        if self.bubble_hide_at and now > self.bubble_hide_at and not voice_engine.is_speaking:
            self.bubble_win.withdraw()
            self.bubble_hide_at = 0.0

        # Autonomous micro-expressions when idle so she feels alive
        if not voice_engine.is_speaking and not self.is_moving and now > self.expr_until:
            if now >= self.next_micro_expr_at:
                h = datetime.now().hour
                if h >= 23 or h < 5:
                    pool = ["cozy_night", "sleepy_yawn", "drowsy_blink", "night_owl_company", "eye_rest_reminder"]
                elif 5 <= h < 11:
                    pool = ["morning_sunrise", "happy_wave", "proud_smile", "music_vibing", "curious_tilt"]
                else:
                    pool = [
                        "warm_smile", "happy_wave", "curious_tilt", "music_vibing",
                        "shy_blush", "peeking_curious", "proud_smile", "quiet_supervising",
                        "cozy_content", "loving_listen",
                    ]
                self.set_expression(random.choice(pool), duration_sec=random.uniform(9.0, 16.0))
                self.next_micro_expr_at = now + random.uniform(16.0, 30.0)
            else:
                self.current_expr = self._default_time_expression()

        # Autonomous walking, running, and floating decisions
        if not self._dragging:
            if self.is_moving:
                progress = (now - self.move_start_t) / max(0.1, self.move_duration)
                if progress >= 1.0:
                    self.x, self.y = self.target_x, self.target_y
                    self.is_moving = False
                    self.facing = "left" if self.x > self.screen_w * 0.5 else "right"
                    self.next_roam_at = now + random.uniform(10.0, 22.0)
                else:
                    # Linear for walking/running feet, smooth ease for floating
                    t_val = progress if self.move_mode in {"walk", "run"} else _ease_in_out(progress)
                    self.x = self.move_start_x + (self.target_x - self.move_start_x) * t_val
                    self.y = self.move_start_y + (self.target_y - self.move_start_y) * t_val
            elif self.free_roam and not (self.chat_win and self.chat_win.winfo_exists()) and now >= self.next_roam_at:
                h = datetime.now().hour
                if h >= 23 or h < 5:
                    mode = random.choices(["walk", "float"], weights=[75, 25])[0]
                else:
                    mode = random.choices(["walk", "run", "float"], weights=[55, 25, 20])[0]
                tx, ty = self._pick_autonomous_spot(mode)
                self._start_move_to(tx, ty, mode=mode)

        # Determine active sprite pose + bounce physics
        is_talking = voice_engine.is_speaking or (now < self.lip_sync_until)

        if self.is_moving and self.move_mode == "walk":
            step_frame = int(now / 0.175) % 2
            active_pose = "walk_1" if step_frame == 0 else "walk_2"
            bob = -abs(math.sin(now * 9.0)) * 7.0
        elif self.is_moving and self.move_mode == "run":
            step_frame = int(now / 0.11) % 2
            active_pose = "run_1" if step_frame == 0 else "run_2"
            bob = -abs(math.sin(now * 14.5)) * 12.0
        else:
            active_pose = self.current_expr.pose
            if is_talking and active_pose in {"idle", "walk_1", "walk_2", "run_1", "run_2"}:
                active_pose = "talk"
            bob = math.sin(now * self.current_expr.bob_speed) * self.current_expr.bob_amp

        # Working animated lip-sync mouth!
        if is_talking:
            if (now - self._last_lip_t) >= 0.088:
                self._last_lip_t = now
                self._lip_idx = (self._lip_idx + 1) % len(LIP_SYNC_SEQ)
            mouth_state = LIP_SYNC_SEQ[self._lip_idx]
            # Slight cheerful head-bob while speaking
            bob += math.sin(now * 16.0) * 1.4
        else:
            rest = self.current_expr.mouth_rest
            mouth_state = "default" if rest in {"default", "smile", "happy_open"} else rest

        photo = self._get_photo(active_pose, self.facing, mouth_state, self.current_expr.blush)
        self.canvas.itemconfigure(self._img_item, image=photo)

        # Animated floating emote glyph beside her head
        emote_key = "sparkle" if (self.is_moving and self.move_mode == "run") else self.current_expr.emote
        glyph, color = EMOTE_GLYPHS.get(emote_key, ("", "#fbbf24"))
        emote_y = 22 + math.sin(now * 4.0) * 4.5
        emote_x = (self.canvas_w - 22) if self.facing == "left" else 22
        self.canvas.coords(self._emote_shadow, emote_x + 1, emote_y + 1)
        self.canvas.coords(self._emote_item, emote_x, emote_y)
        self.canvas.itemconfigure(self._emote_shadow, text=glyph)
        self.canvas.itemconfigure(self._emote_item, text=glyph, fill=color)

        self._update_geometry(bob_y=bob)
        self.root.after(33, self._tick)

    # ---------------- Autonomous Clock & Screen Brain ----------------

    def _autonomous_brain_loop(self) -> None:
        time.sleep(6.0)
        while not self._stop_event.is_set():
            try:
                if self.meeting_paused:
                    time.sleep(2.0)
                    continue
                cfg = load_config()
                now = time.time()
                summary = db.get_daily_summary()

                # 1. Clock-aware autonomous daily routines (morning, meals, chai, hydration, late-night sleep care)
                decision = routine_engine.next_autonomous_routine(summary, cfg.user_name)
                if decision is not None:
                    msg = asyncio.run(ai_engine.generate_routine_message(decision, cfg, summary))
                    if decision.slot_key == "morning":
                        db.mark_morning_briefing_done()
                    db.add_message("assistant", msg, event_type=decision.event_type)
                    self.events.put(CompanionEvent("move", expression=decision.expression, move_mode=decision.move_mode))
                    self.events.put(CompanionEvent("speak", text=msg, expression=decision.expression, duration_sec=10.5))
                    voice_engine.speak(msg)
                    self._last_checkin_at = now

                # 2. Screen & distraction monitoring
                if cfg.screen_monitor_enabled:
                    title, proc = get_active_window_info()
                    cat = classify_window(title, proc, cfg)
                    shot_path = capture_screen_thumbnail() if cfg.save_screenshots else ""
                    db.log_screen_event(title, proc, cat, shot_path)

                    if cat == "distracted":
                        if self._distracted_since is None:
                            self._distracted_since = now
                        elif (now - self._distracted_since) >= cfg.distraction_threshold_sec and (
                            now - self._last_nudge_at
                        ) >= 180:
                            self._last_nudge_at = now
                            db.increment_distraction_count()
                            nudge = asyncio.run(ai_engine.generate_distraction_nudge(title, cfg, summary))
                            db.add_message("assistant", nudge, event_type="distraction_nudge")
                            expr = pick_expression_for_context(nudge, "distraction_nudge", datetime.now().hour)
                            self.events.put(CompanionEvent("move", expression=expr.name, move_mode="run"))
                            self.events.put(CompanionEvent("speak", text=nudge, expression=expr.name, duration_sec=10.0))
                            voice_engine.speak(nudge)
                    else:
                        self._distracted_since = None
                        if cat == "productive" and (now - self._last_praise_at) >= 1800:
                            self._last_praise_at = now
                            praise = "Shabash! Tumne kitne achhe se focus banaya hua hai — paani ka ek sip le lo aur keep going!"
                            self.events.put(CompanionEvent("speak", text=praise, expression="super_proud", duration_sec=6.5))

                # 3. Periodic wellness check-in (respecting configured interval)
                if (now - self._last_checkin_at) >= max(10, cfg.checkin_interval_min) * 60:
                    self._last_checkin_at = now
                    msg = asyncio.run(ai_engine.generate_checkin_prompt(cfg, summary))
                    db.add_message("assistant", msg, event_type="checkin")
                    expr = pick_expression_for_context(msg, "checkin", datetime.now().hour)
                    self.events.put(CompanionEvent("move", expression=expr.name, move_mode="walk"))
                    self.events.put(CompanionEvent("speak", text=msg, expression=expr.name, duration_sec=10.0))
                    voice_engine.speak(msg)

                # 4. Optional local webcam crying/distress care
                if cfg.webcam_emotion_enabled and (now - self._last_emotion_at) >= max(
                    5, cfg.webcam_check_interval_sec
                ):
                    self._last_emotion_at = now
                    res = emotion_detector.sample_webcam()
                    if res.get("distress_alert") and (now - self._last_emotion_alert_at) >= 300:
                        self._last_emotion_alert_at = now
                        db.add_checkin("Crying", energy=2, note="Detected via local webcam", source="webcam")
                        support = asyncio.run(ai_engine.generate_crying_support(cfg, summary))
                        db.add_message("assistant", support, event_type="emotional_support")
                        self.events.put(CompanionEvent("move", expression="crying_comfort", move_mode="run"))
                        self.events.put(CompanionEvent("speak", text=support, expression="crying_comfort", duration_sec=12.0))
                        voice_engine.speak(support)

                # 5. Cleanup old screenshots hourly
                if (now - self._last_cleanup_at) >= 3600:
                    self._last_cleanup_at = now
                    cleanup_old_screenshots(cfg.screenshot_retention_hours)

            except Exception as exc:
                logger.warning("Autonomous brain tick error: %s", exc)

            sleep_total = max(10, int(load_config().screen_capture_interval_sec))
            for _ in range(sleep_total):
                if self._stop_event.is_set():
                    break
                time.sleep(1.0)

    def run(self) -> None:
        self.root.mainloop()

    def quit(self) -> None:
        self._stop_event.set()
        voice_engine.stop()
        try:
            self.root.destroy()
        except Exception:
            pass
