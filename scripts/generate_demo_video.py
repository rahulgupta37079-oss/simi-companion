"""Generate a narrated 720p H.264 demo video (docs/assets/simi_demo.mp4) showcasing how Simi works."""

from __future__ import annotations

import asyncio
import math
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

from app.config import BASE_DIR
from app.expression_engine import bake_mouth_frame

ASSETS = BASE_DIR / "assets"
OUT_VIDEO = BASE_DIR / "docs" / "assets" / "simi_demo.mp4"
W, H = 1280, 720
FPS = 24

SCENES = [
    {
        "title": "1. Meet Simi — Floating Right on Your Windows Screen",
        "window_label": "Visual Studio Code — main.py",
        "clock": "09:15 AM",
        "narration": "Suno na! Main Simi hoon — your open-source floating desktop companion. I walk, run, and talk right on your Windows screen with zero browser clutter.",
        "bubble": "Suno na! Main Simi hoon — chalo aaj saath mein jeetenge!",
        "mode": "walk_greet",
    },
    {
        "title": "2. Catches Distractions & Keeps You Winning",
        "window_label": "YouTube Shorts — Distraction Detected!",
        "clock": "11:40 AM",
        "narration": "If you drift onto YouTube or Reels, I run right over across your screen and lovingly pull you back to your plan!",
        "bubble": "Arey pakde gaye! Reels band karo aur wapas apne kaam pe aao!",
        "mode": "run_scold",
    },
    {
        "title": "3. 108 Expressions, Clock Routines & Emotional Care",
        "window_label": "Late Night Study & Wellness Care",
        "clock": "01:30 AM",
        "narration": "I see exact timings all day — reminding you about meals, chai breaks, and sleep, and staying right beside you whenever you feel low.",
        "bubble": "Koi baat nahi, main hoon na yahan. Tumne khana khaya aur paani piya?",
        "mode": "care_sleep",
    },
    {
        "title": "4. Open Source — Create Your Own Companion in 60 Seconds",
        "window_label": "github.com/rahulgupta37079-oss/simi-companion",
        "clock": "MIT Open Source",
        "narration": "Fork the repo, run create your own dot py, swap in your own character sprites and voice, and build your personal AI partner today!",
        "bubble": "Shabash! Fork on GitHub and build your own companion!",
        "mode": "celebrate_oss",
    },
]


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> List[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _probe_duration(ffmpeg: str, audio_path: Path) -> float:
    proc = subprocess.run([ffmpeg, "-i", str(audio_path)], capture_output=True, text=True)
    for line in proc.stderr.splitlines():
        if "Duration:" in line:
            part = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = part.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 5.5


async def _synth_scene_audio(text: str, out_mp3: Path) -> None:
    comm = edge_tts.Communicate(
        text=text,
        voice="en-IN-NeerjaExpressiveNeural",
        rate="+3%",
        pitch="+1Hz",
    )
    await comm.save(str(out_mp3))


def _load_sprites_2x() -> dict[str, Image.Image]:
    out = {}
    for name in ("idle", "talk", "focus", "care", "walk_1", "walk_2", "run_1", "run_2", "sleepy", "laugh"):
        im = Image.open(ASSETS / f"simi_{name}.png").convert("RGBA")
        # Scale up nicely for 720p video (~260px tall)
        scale = 260 / float(im.height)
        out[name] = im.resize((int(im.width * scale), 260), Image.Resampling.LANCZOS)
    return out


def _draw_desktop_bg(scene: dict, t_local: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), (12, 14, 22, 255))
    d = ImageDraw.Draw(img, "RGBA")

    # Subtle ambient glow orbs
    d.ellipse((-120, -100, 480, 420), fill=(244, 114, 182, 26))
    d.ellipse((820, -80, 1400, 460), fill=(245, 158, 11, 24))

    # Top header banner
    f_title = _load_font(30, bold=True)
    f_sub = _load_font(18)
    d.text((54, 34), scene["title"], fill=(248, 250, 252, 255), font=f_title)

    # Mock Windows desktop app window in background
    win_box = (64, 96, 1216, 634)
    d.rounded_rectangle(win_box, radius=18, fill=(21, 25, 36, 255), outline=(48, 56, 78, 255), width=2)
    # Title bar
    d.rounded_rectangle((64, 96, 1216, 142), radius=18, fill=(28, 34, 49, 255))
    d.rectangle((64, 124, 1216, 142), fill=(28, 34, 49, 255))
    for i, col in enumerate(((239, 68, 68, 255), (245, 158, 11, 255), (34, 197, 94, 255))):
        d.ellipse((86 + i * 22, 112, 100 + i * 22, 126), fill=col)
    d.text((164, 108), scene["window_label"], fill=(203, 213, 225, 255), font=f_sub)

    # Scene-specific mock content inside window
    f_code = _load_font(20)
    f_big = _load_font(26, bold=True)
    mode = scene["mode"]
    if mode == "walk_greet":
        lines = [
            "# Working on your daily goals...",
            "plan = 'Build & ship open-source Simi Companion'",
            "mood = 'Focused & energized'",
            "water_glasses = 4",
            "",
            "# Simi walks & floats autonomously right above your taskbar!",
        ]
        for idx, ln in enumerate(lines):
            col = (148, 163, 184, 255) if ln.startswith("#") else (134, 239, 172, 255)
            d.text((104, 178 + idx * 36), ln, fill=col, font=f_code)
    elif mode == "run_scold":
        d.rounded_rectangle((110, 178, 640, 480), radius=14, fill=(38, 22, 32, 255), outline=(239, 68, 68, 200), width=2)
        d.text((144, 214), "YouTube Shorts / Instagram Reels", fill=(252, 165, 165, 255), font=f_big)
        d.text((144, 266), "Distraction detected after 90 seconds...", fill=(226, 232, 240, 255), font=f_code)
        d.text((144, 314), "Simi runs across your screen automatically", fill=(253, 230, 138, 255), font=f_code)
        d.text((144, 352), "to pull you back to your active plan!", fill=(253, 230, 138, 255), font=f_code)
    elif mode == "care_sleep":
        cards = [
            ("08:00 AM", "Morning Hype & Daily Plan"),
            ("01:15 PM", "Lunch & Hydration Check-in"),
            ("04:45 PM", "Chai Break & Stretch"),
            ("01:30 AM", "Sleepy Late-Night Care & Comfort"),
        ]
        for idx, (tm, desc) in enumerate(cards):
            y = 176 + idx * 78
            d.rounded_rectangle((106, y, 660, y + 60), radius=12, fill=(30, 36, 52, 255), outline=(244, 114, 182, 140), width=1)
            d.text((128, y + 17), tm, fill=(253, 230, 138, 255), font=_load_font(20, bold=True))
            d.text((255, y + 17), desc, fill=(226, 232, 240, 255), font=f_code)
    else:
        d.text((110, 182), "Create Your Own Companion in 3 Commands:", fill=(253, 230, 138, 255), font=f_big)
        cmds = [
            "git clone https://github.com/rahulgupta37079-oss/simi-companion",
            "pip install -r requirements.txt",
            "python create_your_own.py   # custom name, voice & sprites!",
            "python run_simi.py          # floats right on your desktop",
        ]
        d.rounded_rectangle((106, 236, 860, 424), radius=12, fill=(10, 13, 20, 255), outline=(56, 189, 248, 160), width=1)
        for idx, c in enumerate(cmds):
            d.text((128, 258 + idx * 38), c, fill=(125, 211, 252, 255), font=_load_font(18))
        d.text((110, 456), "MIT Licensed • 108 Expressions • Lip-Sync • Interview Prep Mode", fill=(244, 114, 182, 255), font=_load_font(20, bold=True))

    # Windows taskbar at bottom
    d.rectangle((0, 668, W, H), fill=(18, 22, 32, 255))
    d.line((0, 668, W, 668), fill=(52, 62, 86, 255), width=1)
    d.text((26, 682), "Simi Companion • Open Source Windows 10/11", fill=(148, 163, 184, 255), font=_load_font(16))
    d.text((W - 150, 682), scene["clock"], fill=(248, 250, 252, 255), font=_load_font(16, bold=True))
    return img


def _draw_bubble(img: Image.Image, text: str, cx: int, top_y: int) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    font = _load_font(19, bold=True)
    lines = _wrap_text(d, text, font, 340)
    line_h = 26
    bw = min(380, max(200, int(max(d.textlength(l, font=font) for l in lines) + 34)))
    bh = len(lines) * line_h + 24
    bx = max(80, min(W - bw - 40, cx - bw // 2))
    by = max(152, top_y - bh - 14)
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=16, fill=(255, 247, 243, 255), outline=(244, 114, 182, 255), width=3)
    for i, ln in enumerate(lines):
        d.text((bx + 17, by + 12 + i * line_h), ln, fill=(31, 41, 55, 255), font=font)


def main() -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    sprites = _load_sprites_2x()
    lip_seq = ("closed", "small", "mid", "wide", "mid", "o")

    OUT_VIDEO.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        audio_files: List[Path] = []
        durations: List[float] = []

        for idx, sc in enumerate(SCENES):
            mp3 = tmp_dir / f"scene_{idx}.mp3"
            asyncio.run(_synth_scene_audio(sc["narration"], mp3))
            dur = _probe_duration(ffmpeg, mp3) + 0.5
            audio_files.append(mp3)
            durations.append(dur)
            print(f"Scene {idx+1} audio: {dur:.2f}s")

        # Concat audio tracks with brief 0.5s padding per scene
        concat_list = tmp_dir / "audio.txt"
        padded_wavs: List[Path] = []
        for idx, (mp3, dur) in enumerate(zip(audio_files, durations)):
            wav = tmp_dir / f"scene_{idx}.wav"
            subprocess.run(
                [ffmpeg, "-y", "-i", str(mp3), "-af", f"apad=whole_dur={dur:.3f}", "-ar", "44100", "-ac", "2", str(wav)],
                check=True,
                capture_output=True,
            )
            padded_wavs.append(wav)
        concat_list.write_text("\n".join(f"file '{w.as_posix()}'" for w in padded_wavs), encoding="utf-8")
        full_audio = tmp_dir / "full_audio.wav"
        subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(full_audio)],
            check=True,
            capture_output=True,
        )

        # Stream raw RGB frames directly into ffmpeg H.264 encoder
        cmd = [
            ffmpeg,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{W}x{H}",
            "-r", str(FPS),
            "-i", "-",
            "-i", str(full_audio),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "24",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-shortest",
            str(OUT_VIDEO),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdin is not None

        for sc, dur in zip(SCENES, durations):
            total_frames = int(round(dur * FPS))
            for f in range(total_frames):
                t = f / float(FPS)
                frac = f / max(1, total_frames - 1)
                frame = _draw_desktop_bg(sc, t)

                mode = sc["mode"]
                flip = False
                mouth = lip_seq[(f // 2) % len(lip_seq)]
                blush = 0.25

                if mode == "walk_greet":
                    if t < 2.2:
                        sx = int(1080 - (t / 2.2) * 210)
                        sy = int(410 - abs(math.sin(t * 9.0)) * 10)
                        pose = "walk_1" if int(t / 0.18) % 2 == 0 else "walk_2"
                        flip = True
                        mouth = "default"
                    else:
                        sx = 870
                        sy = int(410 + math.sin(t * 2.8) * 7)
                        pose = "talk"
                elif mode == "run_scold":
                    if t < 1.5:
                        sx = int(1120 - (t / 1.5) * 320)
                        sy = int(410 - abs(math.sin(t * 14.0)) * 16)
                        pose = "run_1" if int(t / 0.11) % 2 == 0 else "run_2"
                        flip = True
                        mouth = "default"
                    else:
                        sx = 800
                        sy = int(410 + math.sin(t * 3.4) * 6)
                        pose = "focus"
                elif mode == "care_sleep":
                    sx = 870
                    sy = int(410 + math.sin(t * 2.0) * 6)
                    if frac < 0.45:
                        pose = "sleepy"
                        blush = 0.35
                    else:
                        pose = "care"
                        blush = 0.55
                else:
                    sx = 975
                    sy = int(405 + math.sin(t * 3.8) * 9)
                    pose = "laugh"
                    blush = 0.5

                sp = bake_mouth_frame(sprites[pose], mouth, blush=blush)
                if flip:
                    sp = sp.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                frame.alpha_composite(sp, (sx, sy))
                _draw_bubble(frame, sc["bubble"], sx + sp.width // 2, sy)

                proc.stdin.write(frame.convert("RGB").tobytes())

        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"ffmpeg failed ({ret}): {stderr[-400:]}")
        size_mb = OUT_VIDEO.stat().st_size / (1024 * 1024)
        print(f"Created demo video: {OUT_VIDEO} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
