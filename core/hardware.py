from __future__ import annotations
import os, platform
from pathlib import Path
try:
    import psutil
except Exception:
    psutil = None

MODEL_MODES = {
    "Intelligent": {"file": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", "description": "Maximum practical reasoning", "context": 4096, "threads": 6},
    "Balanced": {"file": "gemma-3-4b-it-Q4_K_M.gguf", "description": "Capability and response-speed balance", "context": 4096, "threads": 6},
    "Speed": {"file": "smollm2-1.7b-instruct-Q4_K_M.gguf", "description": "Fast lightweight responses", "context": 4096, "threads": 4},
}
DEFAULT_MODE = "Balanced"

def detect_hardware() -> dict:
    ram = (psutil.virtual_memory().total / (1024 ** 3)) if psutil else 8.0
    available = (psutil.virtual_memory().available / (1024 ** 3)) if psutil else ram
    return {"cpu_name": platform.processor() or platform.machine() or "Unknown CPU",
            "threads": os.cpu_count() or 2, "ram_gb": ram, "available_ram_gb": available,
            "os": platform.platform(), "arch": platform.machine(), "gpu": "Integrated graphics / CPU-first mode"}

def model_path(app_dir: Path, mode: str) -> Path:
    if mode not in MODEL_MODES: raise ValueError(f"Unknown AI mode: {mode}")
    return Path(app_dir).resolve() / "Models" / MODEL_MODES[mode]["file"]

def model_candidates(app_dir: Path, hw: dict, mode: str = DEFAULT_MODE) -> list[Path]:
    path = model_path(app_dir, mode)
    return [path] if path.is_file() else []

def choose_model(app_dir: Path, hw: dict, mode: str = DEFAULT_MODE) -> Path | None:
    candidates = model_candidates(app_dir, hw, mode)
    return candidates[0] if candidates else None
