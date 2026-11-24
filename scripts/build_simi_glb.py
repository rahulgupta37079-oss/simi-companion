"""Build a standalone high-detail 3D GLB model (models/simi_3d_model.glb) of Simi."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Tuple

import numpy as np
import trimesh

from app.config import BASE_DIR


def _transform(
    mesh: trimesh.Trimesh,
    pos: Tuple[float, float, float] = (0, 0, 0),
    scale: Tuple[float, float, float] = (1, 1, 1),
    rot_xyz: Tuple[float, float, float] = (0, 0, 0),
    rgba: Tuple[int, int, int, int] = (200, 140, 100, 255),
) -> trimesh.Trimesh:
    m = mesh.copy()
    if scale != (1, 1, 1):
        m.apply_scale(scale)
    if rot_xyz != (0, 0, 0):
        rx = trimesh.transformations.rotation_matrix(rot_xyz[0], [1, 0, 0])
        ry = trimesh.transformations.rotation_matrix(rot_xyz[1], [0, 1, 0])
        rz = trimesh.transformations.rotation_matrix(rot_xyz[2], [0, 0, 1])
        m.apply_transform(rz @ ry @ rx)
    if pos != (0, 0, 0):
        m.apply_translation(pos)
    m.visual.face_colors = np.tile(np.array(rgba, dtype=np.uint8), (len(m.faces), 1))
    return m


def _sphere(r: float = 1.0, sub: int = 3) -> trimesh.Trimesh:
    return trimesh.creation.icosphere(subdivisions=sub, radius=r)


def _cyl(r: float, h: float, sec: int = 32) -> trimesh.Trimesh:
    # Align axis along Y (trimesh defaults to Z)
    m = trimesh.creation.cylinder(radius=r, height=h, sections=sec)
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    return m


def _capsule(r: float, h: float) -> trimesh.Trimesh:
    m = trimesh.creation.capsule(height=h, radius=r, count=[16, 16])
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    return m


def _cone(r: float, h: float, sec: int = 24) -> trimesh.Trimesh:
    m = trimesh.creation.cone(radius=r, height=h, sections=sec)
    m.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0]))
    return m


def _box(ext: Tuple[float, float, float]) -> trimesh.Trimesh:
    return trimesh.creation.box(extents=ext)


def build_simi_scene() -> trimesh.Scene:
    skin = (201, 139, 99, 255)
    hair = (24, 21, 26, 255)
    glasses_col = (20, 22, 28, 255)
    kurti = (242, 164, 156, 255)
    embroidery = (250, 220, 195, 255)
    dupatta = (167, 227, 181, 255)
    legging = (242, 245, 250, 255)
    sandal = (176, 125, 86, 255)
    gold = (246, 196, 83, 255)
    silver = (216, 222, 233, 255)
    white = (255, 255, 255, 255)
    iris = (44, 22, 12, 255)
    smile_inner = (155, 52, 66, 255)
    pink_tie = (244, 114, 182, 255)

    scene = trimesh.Scene()

    def add(name: str, mesh: trimesh.Trimesh) -> None:
        scene.add_geometry(mesh, node_name=name)

    # Pedestal
    add("pedestal", _transform(_cyl(0.55, 0.06, 48), pos=(0, -0.03, 0), rgba=(32, 38, 56, 255)))

    # Torso & Kurti
    add("torso", _transform(_cyl(0.18, 0.42, 36), pos=(0, 1.00, 0), scale=(1.12, 1.0, 0.84), rgba=kurti))
    add("yoke_panel", _transform(_box((0.16, 0.24, 0.03)), pos=(0, 1.08, 0.145), rgba=embroidery))
    add("kurti_skirt", _transform(_cone(0.30, 0.42, 36), pos=(0, 0.56, 0), scale=(1.08, 1.0, 0.88), rgba=kurti))
    add("dupatta_front", _transform(_capsule(0.042, 0.48), pos=(0.15, 0.94, 0.12), rot_xyz=(-0.08, 0, 0.14), rgba=dupatta))
    add("dupatta_back", _transform(_capsule(0.042, 0.46), pos=(0.15, 0.92, -0.11), rot_xyz=(0.08, 0, 0.10), rgba=dupatta))

    # Neck & Gold Chain
    add("neck", _transform(_cyl(0.075, 0.15, 24), pos=(0, 1.25, 0), rgba=skin))
    add("gold_chain", _transform(trimesh.creation.torus(0.095, 0.008), pos=(0, 1.21, 0.03), rot_xyz=(1.35, 0, 0), rgba=gold))

    # Head & Face
    hy = 1.58
    add("head", _transform(_sphere(0.295, 4), pos=(0, hy, 0), scale=(0.95, 1.04, 0.94), rgba=skin))
    add("nose", _transform(_sphere(0.028, 2), pos=(0, hy - 0.02, 0.278), scale=(0.9, 1.15, 1.05), rgba=skin))

    # Eyes & Eyebrows
    for side, tag in ((-1, "L"), (1, "R")):
        ex = side * 0.098
        add(f"sclera_{tag}", _transform(_sphere(0.048, 3), pos=(ex, hy + 0.025, 0.238), scale=(1.08, 0.96, 0.72), rgba=white))
        add(f"iris_{tag}", _transform(_sphere(0.032, 3), pos=(ex, hy + 0.023, 0.260), scale=(1.0, 1.0, 0.6), rgba=iris))
        add(f"glint_{tag}", _transform(_sphere(0.009, 2), pos=(ex + 0.012, hy + 0.036, 0.278), rgba=white))
        add(f"brow_{tag}", _transform(_capsule(0.009, 0.068), pos=(ex, hy + 0.095, 0.258), rot_xyz=(0, 0, math.pi / 2 - side * 0.12), rgba=hair))

        # Ear + Silver Jhumka
        add(f"ear_{tag}", _transform(_sphere(0.052, 2), pos=(side * 0.272, hy - 0.02, -0.01), scale=(0.55, 1.15, 0.8), rgba=skin))
        add(f"jhumka_bell_{tag}", _transform(_cone(0.028, 0.044, 18), pos=(side * 0.29, hy - 0.11, 0.0), rgba=silver))

        # Rectangular Black Glasses
        gx = side * 0.102
        gy = hy + 0.025
        gz = 0.285
        w, h, t = 0.145, 0.105, 0.012
        add(f"gl_top_{tag}", _transform(_box((w, t, t)), pos=(gx, gy + h / 2, gz), rgba=glasses_col))
        add(f"gl_bot_{tag}", _transform(_box((w, t, t)), pos=(gx, gy - h / 2, gz), rgba=glasses_col))
        add(f"gl_out_{tag}", _transform(_box((t, h, t)), pos=(gx + side * w / 2, gy, gz), rgba=glasses_col))
        add(f"gl_in_{tag}", _transform(_box((t, h, t)), pos=(gx - side * w / 2, gy, gz), rgba=glasses_col))
        add(f"gl_arm_{tag}", _transform(_box((0.01, 0.01, 0.29)), pos=(gx + side * w / 2, gy + 0.015, gz - 0.145), rgba=glasses_col))

    add("gl_bridge", _transform(_box((0.06, 0.012, 0.012)), pos=(0, hy + 0.040, 0.285), rgba=glasses_col))

    # Cheerful Smile
    add("mouth", _transform(_sphere(0.048, 2), pos=(0, hy - 0.105, 0.258), scale=(1.35, 0.55, 0.4), rgba=smile_inner))
    add("teeth", _transform(_box((0.09, 0.022, 0.02)), pos=(0, hy - 0.095, 0.268), rgba=white))

    # Hair + Sweeps + Side Wisps + Low Ponytail
    add("hair_cap", _transform(_sphere(0.312, 4), pos=(0, hy + 0.03, -0.025), scale=(0.98, 1.04, 1.0), rgba=hair))
    for side, tag in ((-1, "L"), (1, "R")):
        add(f"hair_sweep_{tag}", _transform(_capsule(0.065, 0.22), pos=(side * 0.175, hy + 0.10, 0.13), rot_xyz=(0.22, 0, side * 0.62), rgba=hair))
        add(f"hair_wisp_{tag}", _transform(_capsule(0.015, 0.17), pos=(side * 0.255, hy - 0.09, 0.11), rot_xyz=(0, 0, -side * 0.15), rgba=hair))
    add("pony_tie", _transform(trimesh.creation.torus(0.045, 0.013), pos=(0, hy - 0.09, -0.27), rgba=pink_tie))
    add("ponytail", _transform(_cone(0.115, 0.44, 24), pos=(0, hy - 0.46, -0.32), rot_xyz=(math.pi + 0.22, 0, 0), rgba=hair))

    # Arms (Right arm waving warmly!)
    add("arm_L_upper", _transform(_capsule(0.055, 0.20), pos=(-0.24, 1.05, 0), rot_xyz=(0, 0, -0.18), rgba=kurti))
    add("arm_L_lower", _transform(_capsule(0.042, 0.18), pos=(-0.28, 0.85, 0.03), rot_xyz=(-0.15, 0, -0.12), rgba=skin))
    add("hand_L", _transform(_sphere(0.048, 2), pos=(-0.30, 0.74, 0.05), rgba=skin))

    add("arm_R_upper", _transform(_capsule(0.055, 0.20), pos=(0.27, 1.20, 0.04), rot_xyz=(-0.25, 0, 1.15), rgba=kurti))
    add("arm_R_lower", _transform(_capsule(0.042, 0.18), pos=(0.40, 1.33, 0.08), rot_xyz=(-0.2, 0, 0.35), rgba=skin))
    add("hand_R", _transform(_sphere(0.048, 2), pos=(0.44, 1.44, 0.09), rgba=skin))

    # Legs & Sandals
    for side, tag in ((-1, "L"), (1, "R")):
        lx = side * 0.105
        add(f"thigh_{tag}", _transform(_capsule(0.068, 0.24), pos=(lx, 0.44, 0), rgba=legging))
        add(f"shin_{tag}", _transform(_capsule(0.054, 0.22), pos=(lx, 0.20, 0), rgba=legging))
        add(f"foot_{tag}", _transform(_sphere(0.056, 2), pos=(lx, 0.055, 0.035), scale=(0.85, 0.52, 1.45), rgba=skin))
        add(f"sandal_{tag}", _transform(_box((0.095, 0.022, 0.17)), pos=(lx, 0.02, 0.035), rgba=sandal))

    return scene


def main() -> None:
    scene = build_simi_scene()
    for rel in ("models/simi_3d_model.glb", "docs/assets/simi_3d_model.glb"):
        out = BASE_DIR / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(scene.export(file_type="glb"))
        print(f"Exported 3D GLB: {out} ({out.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
