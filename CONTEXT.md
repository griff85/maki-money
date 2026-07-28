# MakiBot v2 — Project Context

## What this is
A GUI automation bot for makichat.com's match-3 tile game. Plays the game automatically, farming Aura and optionally switching to Coins mode to collect coins. Built in Python with tkinter (GUI) and Playwright (browser automation).

## Architecture
Modular plugin system. `maki_main.py` is a lean shell — it checks GitHub for plugin updates on startup, downloads any that are new/updated, then loads whatever it finds in `plugins/` as tabs in the main window.

### Adding a new plugin
Create a `.py` file in `plugins/` that exposes:
```python
TAB_NAME = "My Feature"

def build_tab(frame, log_fn):
    # build tkinter widgets into `frame`
    # call log_fn("message") to write to the shared log
```
Then bump its version in `manifest.json` and push. The app picks it up automatically on next launch.

### manifest.json format
```json
{
  "plugins": [
    {"file": "tile_game.py", "version": "1.1.1"}
  ]
}
```
Increment the version string whenever a plugin changes — that's what triggers the auto-download.

## File structure
```
maki_v2_prototype/
├── maki_main.py          — shell: window, dark theme, updater, plugin loader
├── MakiBot.spec          — PyInstaller build spec (bundles playwright, icons)
├── build.py              — build script: compiles exe, copies runtime files, zips
├── manifest.json         — plugin version registry (used by auto-updater)
├── requirements.txt      — pip dependencies (playwright)
├── small_maki_money.png  — titlebar icon
├── maki_money_logo.png   — desktop/exe icon
├── .gitignore            — excludes accounts.json, __pycache__, build/dist
└── plugins/
    └── tile_game.py      — the match-3 bot plugin
```

## GitHub repo
https://github.com/griff85/maki-money
- `dist/MakiBot.zip` — compiled distributable (Python not required on target machine)
- Auto-updater points to raw.githubusercontent.com/griff85/maki-money/main

## Key design decisions
- **System Chrome** (`channel="chrome"`) instead of bundled Chromium — keeps zip ~51MB vs ~300MB
- **Dark theme** via `ttk.Style` with clam base — no extra dependencies
- **DPI awareness** via `ctypes.windll.shcore.SetProcessDpiAwareness(2)` — crisp rendering on high-DPI screens
- **accounts.json** stores credentials (email→password dict) — gitignored, lives next to exe
- **Collect Coins / Aura threshold** are live-adjustable mid-run via tkinter vars passed by reference
- **Optional maximized Chrome launch** detects Windows `DISPLAY1`, moves Chrome there, and opens it maximized
- **Automatic 7x gem multiplier** applies and confirms once per Coins phase whenever Aura is over 30
- **Shared log panel** sits outside the notebook — all plugins write to it via `log_fn`
- **Stop is clean** — `threading.Event` checked every loop iteration and during reconnect waits

## Building
```
cd maki_v2_prototype
python build.py
```
Output: `dist/MakiBot.zip` — extract and run `MakiBot.exe`. Chrome must be installed on target machine.

## Distributing a plugin update
1. Edit the plugin in `plugins/`
2. Bump its version in `manifest.json`
3. Commit and push — users get it automatically on next launch
