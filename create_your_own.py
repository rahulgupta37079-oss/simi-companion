"""Interactive open-source wizard so anyone can create their own personalized desktop companion."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.config import BASE_DIR, load_config, save_config
from app.sprite_processor import key_out_magenta

VOICE_PRESETS = {
    "1": ("en-IN-NeerjaNeural", "Indian English (Female — Neerja)"),
    "2": ("hi-IN-SwaraNeural", "Hindi (Female — Swara)"),
    "3": ("en-US-JennyNeural", "US English (Female — Jenny)"),
    "4": ("en-GB-SoniaNeural", "British English (Female — Sonia)"),
    "5": ("en-IN-PrabhatNeural", "Indian English (Male — Prabhat)"),
}


def convert_custom_sprites(raw_dir: Path) -> None:
    assets_dir = BASE_DIR / "assets"
    if not raw_dir.exists():
        raw_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created {raw_dir}. Drop magenta-keyed (#FF00FF) images named simi_idle.jpg, simi_walk_1.jpg, etc. and re-run!")
        return
    converted = 0
    for src in raw_dir.iterdir():
        if src.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        dst = assets_dir / f"{src.stem}.png"
        key_out_magenta(src, dst, target_height=185)
        print(f"Converted {src.name} -> {dst}")
        converted += 1
    if converted == 0:
        print(f"No images found in {raw_dir}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create your own Simi Desktop Companion")
    parser.add_argument("--convert-sprites", action="store_true", help="Key out magenta sprites from custom_raw/ into assets/")
    args = parser.parse_args()

    if args.convert_sprites:
        convert_custom_sprites(BASE_DIR / "custom_raw")
        return

    cfg = load_config()
    print("\n=== Create Your Own Floating Desktop Companion ===\n")

    aname = input(f"Companion name [{cfg.assistant_name}]: ").strip()
    if aname:
        cfg.assistant_name = aname

    uname = input(f"What should {cfg.assistant_name} call you? [{cfg.user_name}]: ").strip()
    if uname:
        cfg.user_name = uname

    print("\nChoose a voice:")
    for k, (_, label) in VOICE_PRESETS.items():
        print(f"  {k}. {label}")
    vchoice = input("Select 1-5 [1]: ").strip() or "1"
    if vchoice in VOICE_PRESETS:
        cfg.voice_name = VOICE_PRESETS[vchoice][0]

    print("\nAI Brain (all optional — works offline in Built-in mode without any key):")
    gkey = input("Google Gemini API key (free at aistudio.google.com/apikey, press Enter to skip): ").strip()
    if gkey:
        cfg.ai_provider = "gemini"
        cfg.gemini_api_key = gkey
    else:
        qkey = input("Groq API key (free at console.groq.com/keys, press Enter to skip): ").strip()
        if qkey:
            cfg.ai_provider = "groq"
            cfg.groq_api_key = qkey

    save_config(cfg)
    print(f"\nAll set! Run `python run_simi.py` or double-click `Start_Simi.vbs` to meet {cfg.assistant_name}!")


if __name__ == "__main__":
    main()
