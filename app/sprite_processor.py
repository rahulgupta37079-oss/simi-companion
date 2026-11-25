"""Surgical border-flood-fill chroma-keyer for realistic 3D CGI renders (zero holes in shaded white leggings)."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Tuple

from PIL import Image


def _is_pure_magenta(r: int, g: int, b: int) -> bool:
    """Strictly match bright chroma-key magenta (never shaded pink-lit white leggings)."""
    return r > 175 and b > 165 and g < 85 and (r - g) > 105 and (b - g) > 95


def _is_pure_green(r: int, g: int, b: int) -> bool:
    """Strictly match bright chroma-key green (never pastel mint dupatta or shaded leggings)."""
    return g > 130 and r < 75 and b < 75 and (g - r) > 75 and (g - b) > 75


def key_out_background(
    src_path: Path,
    dst_path: Path,
    target_height: int = 240,
    mode: str = "auto",
    hard_alpha: bool = True,
) -> Path:
    """Border-seeded flood-fill + interior pure-chroma cleanup + gentle despill (zero holes!)."""
    img = Image.open(src_path).convert("RGBA")
    w, h = img.size
    px = img.load()

    if mode == "auto":
        r0, g0, b0, _ = px[6, 6]
        mode = "green" if (g0 > r0 + 40 and g0 > b0 + 40) else "magenta"

    is_bg = _is_pure_green if mode == "green" else _is_pure_magenta

    # Pass 1: Clear strictly pure chroma-key pixels (including gaps between arms/legs)
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            if is_bg(r, g, b):
                px[x, y] = (0, 0, 0, 0)

    # Pass 2: 2-pixel tight anti-alias border cleanup adjacent to transparent background ONLY
    for _ in range(2):
        to_clear = []
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                if any(px[nx, ny][3] == 0 for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))):
                    if mode == "green":
                        if g > 105 and (g - r) > 42 and (g - b) > 42 and r < 100:
                            to_clear.append((x, y))
                    else:
                        if r > 135 and b > 125 and g < 95 and (r - g) > 58 and (b - g) > 50:
                            to_clear.append((x, y))
        for x, y in to_clear:
            px[x, y] = (0, 0, 0, 0)

    # Pass 3: Soft edge despill so zero green/magenta rim remains
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            if any(px[nx, ny][3] == 0 for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))):
                if mode == "green" and g > max(r, b) + 12:
                    px[x, y] = (r, int((r + b) * 0.52), b, a)
                elif mode == "magenta" and r > g + 22 and b > g + 22:
                    avg = int((g + min(r, b)) * 0.52)
                    px[x, y] = (avg, g, avg, a)

    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    cw, ch = img.size
    scale = target_height / float(ch)
    img = img.resize((max(1, int(cw * scale)), target_height), Image.Resampling.LANCZOS)

    if hard_alpha:
        out_px = img.load()
        nw, nh = img.size
        for y in range(nh):
            for x in range(nw):
                r, g, b, a = out_px[x, y]
                out_px[x, y] = (0, 0, 0, 0) if a < 145 else (r, g, b, 255)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst_path, "PNG")
    return dst_path


def key_out_magenta(src_path: Path, dst_path: Path, target_height: int = 240) -> Path:
    return key_out_background(src_path, dst_path, target_height=target_height, mode="magenta", hard_alpha=True)
