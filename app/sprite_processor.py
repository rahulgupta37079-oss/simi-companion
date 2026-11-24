"""Convert magenta-keyed raw sprites into clean transparent PNGs with zero enclosed holes or fringe."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def _is_magenta_bg(r: int, g: int, b: int) -> bool:
    """Detect chroma-key magenta (outer & enclosed gaps) while preserving pastel peach-pink kurti & coral heart."""
    return r > 155 and b > 155 and g < 115 and (r - g) > 70 and (b - g) > 70


def key_out_magenta(src_path: Path, dst_path: Path, target_height: int = 185) -> Path:
    """Remove all chroma-key magenta (including enclosed gaps between hair/arms), despill edges, trim & resize."""
    img = Image.open(src_path).convert("RGBA")
    w, h = img.size
    px = img.load()

    # Pass 1: Clear all pure/near magenta background pixels (including enclosed gaps!)
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            if _is_magenta_bg(r, g, b):
                px[x, y] = (0, 0, 0, 0)

    # Pass 2: Clean 2px magenta anti-aliasing fringe adjacent to transparent pixels
    for _ in range(3):
        to_clear = []
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                if any(
                    px[nx, ny][3] == 0
                    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                ):
                    if r > 95 and b > 95 and g < 130 and (r - g) > 30 and (b - g) > 30:
                        to_clear.append((x, y))
        for x, y in to_clear:
            px[x, y] = (0, 0, 0, 0)

    # Crop tightly to character bounding box
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    # Resize cleanly to target height
    cw, ch = img.size
    scale = target_height / float(ch)
    new_size = (max(1, int(cw * scale)), target_height)
    img = img.resize(new_size, Image.Resampling.LANCZOS)

    # Harden semi-transparent border pixels cleanly for Windows Tk transparentcolor compositing
    out_px = img.load()
    nw, nh = img.size
    for y in range(nh):
        for x in range(nw):
            r, g, b, a = out_px[x, y]
            if a < 135:
                out_px[x, y] = (0, 0, 0, 0)
            else:
                # Despill any residual purple tint on dark outline pixels
                if r > g + 20 and b > g + 20 and g < 90:
                    avg = int((g + min(r, b)) * 0.35)
                    out_px[x, y] = (avg, avg, avg, 255)
                else:
                    out_px[x, y] = (r, g, b, 255)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst_path, "PNG")
    return dst_path
