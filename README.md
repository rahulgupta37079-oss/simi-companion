# Simi Companion — Open-Source Autonomous Floating Desktop Companion

<p align="center">
  <img src="assets/simi_idle.png" height="150" alt="Simi Idle" />
  <img src="assets/simi_walk_1.png" height="150" alt="Simi Walking" />
  <img src="assets/simi_run_1.png" height="150" alt="Simi Running" />
  <img src="assets/simi_laugh.png" height="150" alt="Simi Celebrating" />
  <img src="assets/simi_care.png" height="150" alt="Simi Comforting" />
  <img src="assets/simi_sleepy.png" height="150" alt="Simi Sleepy" />
</p>

**Simi** is an open-source, human-like animated desktop companion for Windows 10/11 that floats, walks, and runs autonomously across your screen—no browser dashboard, no clutter. Anyone can fork this repo and **create their own personalized companion** with custom sprites, voice, and personality in minutes!

> **Live Website & Companion Customizer:** https://rahulgupta37079-oss.github.io/simi-companion/

## Features
- **108 Live Expressions + Working Animated Mouth (Lip-Sync):** Real-time mouth animation synced while speaking, soft rosy blush, and floating emote badges (`♥`, `✦`, `Zzz`, `💢`, `☕`, `💧`, `🔥`, `🏆`).
- **Animated Walking, Running & Floating Physics:** Walks along your taskbar, runs excitedly across the screen when catching distractions or celebrating wins, and hovers gracefully at screen edges.
- **24/7 Clock-Aware Autonomous Routines:** Knows the exact time of day—morning hype & goal check, breakfast/lunch/dinner reminders, afternoon chai breaks, hydration nudges, and sleepy late-night care.
- **Screen & Distraction Awareness:** Watches your active window locally, saves compressed local screenshots (`data/screenshots/`), and playfully nudges you back to your plan if you drift into distractions.
- **Natural Human Memory (No Forms):** Click her and chat naturally (*"I ate dosa and drank 2 glasses of water"*, *"My plan today is shipping v1"*, *"I'm feeling sad"*). Everything is remembered in local SQLite (`data/simi.db`).
- **Zero-Download AI + Indian English/Hindi Voice:** Connects to free **Google Gemini**, **Groq**, local **Ollama**, or works completely offline in Built-in Companion Mode, speaking with `edge-tts` (`en-IN-NeerjaNeural`) + `pyttsx3` fallback.

## Quick Start (Windows 10/11)

```powershell
git clone https://github.com/rahulgupta37079-oss/simi-companion.git
cd simi-companion
pip install -r requirements.txt
python create_your_own.py
python run_simi.py
```

Double-click `Start_Simi.vbs` to launch silently without a console window, or register Windows boot auto-start:
```powershell
.\install_autostart.ps1
```

## Create Your Own Companion
1. Run `python create_your_own.py` to set your companion's name, voice accent, and AI key.
2. Drop your own magenta-background (`#FF00FF`) character poses into `custom_raw/` and run:
   ```powershell
   python create_your_own.py --convert-sprites
   ```
3. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full sprite list and customization guide.

## Privacy First
All memory (`data/simi.db`), config (`data/config.json`), and screenshots (`data/screenshots/`) stay 100% local on your machine and are ignored by `.gitignore`.

## License
MIT License — free to fork, customize, and build your own companion!
