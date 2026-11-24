"""Main launcher for Simi — Autonomous Floating Animated Desktop Companion (No Dashboard)."""

from __future__ import annotations

import threading
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from app.config import BASE_DIR
from app.floating_companion import FloatingSimiApp


def _tray_icon_image() -> Image.Image:
    sprite = BASE_DIR / "assets" / "simi_idle.png"
    if sprite.exists():
        img = Image.open(sprite).convert("RGBA")
        # Crop upper half (her smiling face!) for crisp system tray icon
        w, h = img.size
        face = img.crop((0, 0, w, min(h, w)))
        return face.resize((64, 64), Image.Resampling.LANCZOS)
    img = Image.new("RGBA", (64, 64), (244, 114, 182, 255))
    draw = ImageDraw.Draw(img)
    draw.text((24, 21), "S", fill=(255, 255, 255, 255))
    return img


def main() -> None:
    companion = FloatingSimiApp()

    def _run_tray() -> None:
        def on_talk(_icon, _item):
            companion.root.after(0, companion.open_chat_popup)

        def on_comfort(_icon, _item):
            companion.root.after(0, companion._trigger_comfort)

        def on_morning(_icon, _item):
            companion.root.after(0, companion._trigger_morning)

        def on_settings(_icon, _item):
            companion.root.after(0, companion.open_settings_dialog)

        def on_roam(_icon, _item):
            companion.root.after(0, companion._toggle_roam)

        def on_meeting(_icon, _item):
            companion.root.after(0, companion.toggle_meeting_pause)

        def on_prep(_icon, _item):
            companion.root.after(0, companion._toggle_interview_prep)

        def on_quit(icon, _item):
            icon.stop()
            companion.root.after(0, companion.quit)

        menu = pystray.Menu(
            pystray.MenuItem("Talk to Simi", on_talk, default=True),
            pystray.MenuItem("Show / Hide (Meeting Pause)", on_meeting),
            pystray.MenuItem("Toggle Interview & Study Prep", on_prep),
            pystray.MenuItem("I'm Feeling Low / Comfort", on_comfort),
            pystray.MenuItem("Morning Check-in", on_morning),
            pystray.MenuItem("Toggle Free Roaming", on_roam),
            pystray.MenuItem("AI Brain & Voice Settings", on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit Simi", on_quit),
        )
        tray = pystray.Icon("SimiCompanion", _tray_icon_image(), "Simi — Your Companion", menu)
        tray.run()

    tray_thread = threading.Thread(target=_run_tray, daemon=True, name="SimiTray")
    tray_thread.start()

    companion.run()


if __name__ == "__main__":
    main()
