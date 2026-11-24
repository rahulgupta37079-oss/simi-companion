# Contributing & Creating Your Own Companion

We welcome PRs for new animations, voice presets, expressions, language packs, and macOS/Linux support!

## Create Your Own Companion in 3 Steps

1. **Run the companion customizer:**
   ```powershell
   python create_your_own.py
   ```
   Choose your companion's name, your name, voice accent (`en-IN-NeerjaNeural`, `en-US-JennyNeural`, `hi-IN-SwaraNeural`, etc.), and AI provider (free Google Gemini, Groq, or local Ollama).

2. **Swap in your own character sprites:**
   Place transparent PNGs (185px height recommended) in `assets/`:
   - `simi_idle.png` (waving / default)
   - `simi_talk.png` (speaking)
   - `simi_focus.png` (playful scold / focus nudge)
   - `simi_care.png` (emotional comfort)
   - `simi_walk_1.png`, `simi_walk_2.png` (walking stride cycle)
   - `simi_run_1.png`, `simi_run_2.png` (running stride cycle)
   - `simi_sleepy.png` (late-night drowsy pose)
   - `simi_laugh.png` (celebrating / laughing)

   If your sprites have a solid magenta (`#FF00FF`) background, drop them into `custom_raw/` with those same filenames and run `python create_your_own.py --convert-sprites` to auto-key and resize them!

3. **Run tests before opening a PR:**
   ```powershell
   python -m pytest -v
   ```
