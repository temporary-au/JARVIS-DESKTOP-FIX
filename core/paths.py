from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

def _application_dir() -> Path:
    # In onedir builds the executable is beside _internal; in source runs use project root.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

APP_DIR = _application_dir().resolve()
DATA_DIR = APP_DIR / "Data"
TEMP_DIR = APP_DIR / "Temp"

def confined_path(relative: str | Path) -> Path:
    candidate = (APP_DIR / relative).resolve()
    try:
        candidate.relative_to(APP_DIR)
    except ValueError as exc:
        raise ValueError("JARVIS paths must remain inside the desktop installation folder") from exc
    return candidate

def ensure_layout() -> None:
    # Every writable application directory is under APP_DIR. If this fails,
    # startup must stop; never fall back to AppData, the user's profile or Temp.
    for name in (
        "AI", "Models", "Voice/Piper", "Voice/whisper-base", "Voice/Recordings",
        "Knowledge/Wikipedia", "Knowledge/Personal", "Knowledge/Imported", "Knowledge/Index",
        "Assets", "Config", "Plugins", "Web", "Tasks", "Calendar", "Workflows",
        "Data/Memory", "Data/Logs", "Data/Voice", "Data/Backups", "Temp",
        "JARVIS_USB",
    ):
        confined_path(name).mkdir(parents=True, exist_ok=True)
    # Direct common temporary-file APIs and child processes to the in-folder temp area.
    os.environ["TEMP"] = str(TEMP_DIR)
    os.environ["TMP"] = str(TEMP_DIR)
    os.environ["TMPDIR"] = str(TEMP_DIR)
    tempfile.tempdir = str(TEMP_DIR)

def resource_path(relative: str | Path) -> Path:
    return confined_path(relative)
