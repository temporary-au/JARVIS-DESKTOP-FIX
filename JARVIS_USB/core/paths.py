from __future__ import annotations
import sys
from pathlib import Path

# In a PyInstaller onedir build app.py and the runtime folders are copied into
# the same JARVIS_USB directory. In source mode, this resolves to the repo root.
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]

def ensure_layout() -> None:
    for name in ("AI", "Models", "Voice/Piper", "Voice/whisper-base", "Knowledge/Wikipedia", "Memory", "Assets", "Config", "Logs", "Launcher"):
        (APP_DIR / name).mkdir(parents=True, exist_ok=True)

def resource_path(relative: str) -> Path:
    return APP_DIR / relative
