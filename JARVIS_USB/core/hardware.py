from __future__ import annotations
import os
import platform
from pathlib import Path
try:
    import psutil
except Exception:
    psutil = None

def detect_hardware() -> dict:
    ram = (psutil.virtual_memory().total / (1024 ** 3)) if psutil else 8.0
    return {
        "cpu_name": platform.processor() or platform.machine() or "Unknown CPU",
        "threads": os.cpu_count() or 2,
        "ram_gb": ram,
        "os": platform.platform(),
        "arch": platform.machine(),
    }

def choose_model(app_dir: Path, hw: dict) -> Path | None:
    # Conservative defaults: Q4_K_M at 8GB+ RAM; Q2_K below 8GB.
    candidates = ["qwen2.5-1.5b-instruct-q4_k_m.gguf"] if hw.get("ram_gb", 0) >= 8 else []
    candidates += ["qwen2.5-1.5b-instruct-q2_k.gguf", "qwen2.5-1.5b-instruct-q3_k_m.gguf"]
    for name in candidates:
        path = Path(app_dir) / "Models" / name
        if path.is_file():
            return path
    return None
