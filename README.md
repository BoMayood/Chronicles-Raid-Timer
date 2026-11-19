# ArcheAge Chronicles - Raid Timer Overlay

A lightweight, customizable Windows desktop HUD overlay that tracks scheduled in-game world events and boss raids with real-time countdowns, timezone synchronization, and audio cues.

Developed by **NoYz** (`BoMayood`).

---

## Key Features

- **Real-Time Event Tracking**: Live countdown timers for Crimson Rift and Celtak world events with automatic local timezone conversion.
- **Dynamic Status Indicators**: Visual states indicating upcoming events (`STARTS IN`) and active ongoing battles (`ENDS IN`).
- **Pass-Through HUD Mode**: Seamlessly toggle click-through transparency (`WS_EX_TRANSPARENT`) so the overlay remains visible without interrupting mouse clicks during gameplay.
- **Customizable Global Hotkey**: Default `F8` pass-through toggle, fully rebindable to any keyboard key via the settings dialog.
- **Audio Notification Engine**: Built-in audio cues (including default Viking Horn) with volume controls, advance alert timing, and custom audio file import (`.wav`, `.mp3`, `.ogg`, `.flac`).
- **Low Footprint & Silent Execution**: Runs with zero console popups and minimal system resource overhead.
- **Standalone Setup & Uninstaller**: Pre-built graphical installer and uninstaller wizards that require no Python or external runtime dependencies.

---

## Controls 

| Action | Shortcut / Button | Description |
|---|---|---|
| Toggle Click-Through | `F8` (Default) | Locks or unlocks mouse pass-through mode |
| Settings Dialog | `⚙` Icon | Configure alert audio, volume, timings, and hotkeys |
| Close & Save Position | `✕` Button | Exits overlay and preserves window position |

---

## Running from Source

### Prerequisites
- Python 3.10+
- Windows 10 / 11

### Setup
```bash
pip install -r requirements.txt
python main.py
```

---

## License
MIT License - Created by NoYz
