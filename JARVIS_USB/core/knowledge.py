from __future__ import annotations
import importlib.util
import json
from pathlib import Path

class KnowledgeBase:
    """Discovers and loads external JARVIS plugins from the portable Plugins folder."""
    def __init__(self, app_dir: Path):
        self.app_dir = Path(app_dir)
        self.plugin_root = self.app_dir / "Plugins"
        self.plugin_root.mkdir(parents=True, exist_ok=True)
        self.plugins = {}
        self.plugin_errors = {}
        self._discover_plugins()

    def _discover_plugins(self):
        for manifest_path in sorted(self.plugin_root.glob("*/manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                plugin_id = str(manifest.get("id", "")).strip()
                entry_point = str(manifest.get("entry_point", "plugin:WikipediaPlugin"))
                module_name, separator, class_name = entry_point.partition(":")
                if not plugin_id or not separator or not module_name or not class_name:
                    raise ValueError("Plugin manifest has an invalid id or entry_point.")
                module_path = manifest_path.parent / (module_name.replace(".", "/") + ".py")
                if not module_path.is_file(): raise FileNotFoundError(f"Plugin module missing: {module_path}")
                safe_name = "jarvis_plugin_" + "".join(c for c in plugin_id if c.isalnum() or c in "._-")
                spec = importlib.util.spec_from_file_location(safe_name, module_path)
                if spec is None or spec.loader is None: raise ImportError("Could not create plugin loader.")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                plugin_class = getattr(module, class_name)
                plugin = plugin_class(self.app_dir)
                self.plugins[plugin_id] = plugin
            except Exception as exc:
                self.plugin_errors[manifest_path.parent.name] = str(exc)

    @property
    def wikipedia(self):
        return self.plugins.get("wikipedia.offline")

    def find_zim(self):
        return self.wikipedia.find_zim() if self.wikipedia else None

    def status(self):
        wiki = self.wikipedia.status() if self.wikipedia else {"installed": False, "ready": False, "message": "Wikipedia plugin not loaded."}
        return {"wikipedia": wiki, "plugins": list(self.plugins), "plugin_errors": self.plugin_errors}

    def search(self, query: str):
        if not self.wikipedia: raise RuntimeError("Offline Wikipedia plugin is not loaded.")
        return self.wikipedia.search(query)

    def context_for(self, query: str):
        if not self.wikipedia: return []
        return self.wikipedia.context_for(query)
