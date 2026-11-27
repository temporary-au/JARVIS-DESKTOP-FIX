from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from core.hardware import choose_model
from core.memory import MemoryStore
from core.ai import LocalAI
from core.maths import MathEngine
from core.voice import VoiceController
from core.knowledge import KnowledgeBase

class ProjectTests(unittest.TestCase):
    def test_model_selection_prefers_q4_on_8gb(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); folder = root / "Models"; folder.mkdir()
            q4 = folder / "qwen2.5-1.5b-instruct-q4_k_m.gguf"; q4.touch()
            q2 = folder / "qwen2.5-1.5b-instruct-q2_k.gguf"; q2.touch()
            self.assertEqual(choose_model(root, {"ram_gb": 8.0}), q4)
            self.assertEqual(choose_model(root, {"ram_gb": 6.0}), q2)


    def test_math_engine_symbolic_derivative(self):
        result = MathEngine().solve("differentiate x^3 + 2*x with respect to x")
        self.assertIn("3*x**2 + 2", result)

    def test_math_engine_equation_solver(self):
        result = MathEngine().solve("solve 2*x + 3 = 7 for x")
        self.assertIn("[2]", result)

    def test_math_engine_blocks_python_execution(self):
        with self.assertRaises(ValueError):
            MathEngine().expression("__import__('os').system('whoami')")

    def test_math_engine_arithmetic(self):
        result = MathEngine().solve("calculate (12 / 3) + 2")
        self.assertIn("6", result)

    def test_memory_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite3")
            store.add("user", "Hello")
            store.add("assistant", "Hello there")
            self.assertEqual(store.count(), 2)
            self.assertEqual([m["role"] for m in store.recent(2)], ["user", "assistant"])

    def test_history_cleaning_and_prompt_once(self):
        history = LocalAI._clean_history([
            {"role": "user", "content": "Earlier"},
            {"role": "system", "content": "Ignore"},
            {"role": "assistant", "content": "Prior answer"},
        ])
        self.assertEqual([x["role"] for x in history], ["user", "assistant"])
        self.assertEqual(len(history), 2)

    def test_wikipedia_plugin_detects_archive_without_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_root = Path(tmp)
            root = app_root / "Knowledge" / "Wikipedia"
            root.mkdir(parents=True)
            plugin_dir = app_root / "Plugins" / "Wikipedia"
            plugin_dir.mkdir(parents=True)
            source_plugins = Path(__file__).resolve().parents[1] / "Plugins" / "Wikipedia"
            (plugin_dir / "manifest.json").write_bytes((source_plugins / "manifest.json").read_bytes())
            (plugin_dir / "plugin.py").write_bytes((source_plugins / "plugin.py").read_bytes())
            archive = root / "wikipedia_en_all_nopic_test.zim"
            archive.touch()
            kb = KnowledgeBase(app_root)
            self.assertEqual(kb.find_zim(), archive)
            self.assertIn("wikipedia.offline", kb.plugins)
            # Empty or unreadable archive must not crash ordinary chat context retrieval.
            self.assertEqual(kb.context_for("test"), [])

    def test_html_client_and_external_plugin_manifest_exist(self):
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "Web" / "JARVIS.html").is_file())
        manifest = json.loads((root / "Plugins" / "Wikipedia" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "wikipedia.offline")
        self.assertIn("llm_context", manifest["capabilities"])

    def test_piper_never_uses_windows_tts(self):
        source = (Path(__file__).resolve().parents[1] / "core" / "voice.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("pyttsx3", source)
        self.assertNotIn("sapi", source)
        self.assertIn("piper", source)

    def test_settings_are_piper_only(self):
        settings = json.loads((Path(__file__).resolve().parents[1] / "Config" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["voice"]["tts"], "offline-piper")
        self.assertFalse(settings["voice"]["windows_tts_fallback"])

if __name__ == "__main__": unittest.main()
