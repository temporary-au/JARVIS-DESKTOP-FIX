from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from core.hardware import choose_model, model_candidates
from core.memory import MemoryStore
from core.ai import LocalAI
from core.maths import MathEngine
from core.voice import VoiceController
from core.knowledge import KnowledgeBase
from core.paths import APP_DIR, DATA_DIR, resource_path

class ProjectTests(unittest.TestCase):
    def test_application_paths_are_relative_to_current_package(self):
        self.assertTrue(APP_DIR.is_absolute())
        self.assertEqual(resource_path("Models"), (APP_DIR / "Models").resolve())
        self.assertTrue(DATA_DIR.is_absolute())
        with self.assertRaises(ValueError):
            resource_path("../outside")

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


    def test_math_engine_implicit_multiplication(self):
        engine = MathEngine()
        self.assertIn("6*x + 2", engine.solve("differentiate 3x^2 + 2x"))
        self.assertIn("x**2 + C", engine.solve("integrate 2x"))
        self.assertIn("14", engine.solve("calculate 2(3+4)"))

    def test_math_engine_common_notation(self):
        engine = MathEngine()
        self.assertIn("2*x", engine.solve("d/dx (x^2)"))
        self.assertIn("[2]", engine.solve("solve 2*x + 3 = 7 for x"))
        self.assertIn("2", engine.solve("limit of (x^2-1)/(x-1) as x approaches 1"))
        self.assertIn("-2", engine.solve("determinant of [[1,2],[3,4]]"))
        self.assertIn("x: 2", engine.solve("solve system: 2x+y=5; x-y=1 for x,y"))
        self.assertIn("2*x", engine.solve("differentiate the function x^2"))
        self.assertIn("10", engine.solve("summation(x, x, 1, 4)"))
        self.assertIn("1/3", engine.solve("integrate x^2 from 0 to 1"))

    def test_context_budget_never_truncates_current_prompt(self):
        class FakeModel:
            def tokenize(self, data, add_bos=True):
                return list(data)
        ai = LocalAI(Path('.'), {"threads": 2})
        ai.INPUT_BUDGET = 80
        with self.assertRaises(RuntimeError):
            ai._fit_messages(FakeModel(), "system", [], "x" * 200)

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

    def test_history_cleaning_repairs_failed_request_role_sequence(self):
        history = LocalAI._clean_history([
            {"role": "user", "content": "old failed request"},
            {"role": "user", "content": "new failed request"},
            {"role": "assistant", "content": "completed answer"},
            {"role": "user", "content": "latest failed request"},
        ])
        self.assertEqual([x["role"] for x in history], ["user", "assistant"])
        self.assertEqual(history[0]["content"], "new failed request")
        self.assertEqual(history[1]["content"], "completed answer")
        self.assertEqual(history[-1]["role"], "assistant")

    def test_history_cleaning_drops_incomplete_leading_and_trailing_turns(self):
        history = LocalAI._clean_history([
            {"role": "assistant", "content": "orphan answer"},
            {"role": "user", "content": "completed question"},
            {"role": "assistant", "content": "completed answer"},
            {"role": "user", "content": "unanswered old request"},
        ])
        self.assertEqual([x["role"] for x in history], ["user", "assistant"])

    def test_memory_add_exchange_persists_complete_turn_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite3")
            store.add_exchange("Question", "Answer")
            self.assertEqual([m["role"] for m in store.recent(2)], ["user", "assistant"])

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


    def test_memory_all_search_update_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite3")
            store.add("user", "alpha memory")
            store.add("assistant", "beta memory")
            self.assertEqual(store.count(), 2)
            self.assertEqual(len(store.all()), 2)
            self.assertEqual(len(store.all("alpha")), 1)
            first = store.all("alpha")[0]
            store.update(first["id"], "updated alpha")
            self.assertEqual(store.all("updated")[0]["content"], "updated alpha")
            store.delete(first["id"])
            self.assertEqual(store.count(), 1)

    def test_desktop_model_modes_are_separate(self):
        from core.hardware import MODEL_MODES, model_path
        self.assertEqual(set(MODEL_MODES), {"Intelligent", "Balanced", "Speed"})
        self.assertNotIn("qwen", " ".join(x["file"].lower() for x in MODEL_MODES.values()))
        self.assertEqual(model_path(Path("/tmp/jarvis"), "Speed").name, MODEL_MODES["Speed"]["file"])

    def test_visible_resource_folder_readmes_exist(self):
        root = Path(__file__).resolve().parents[1]
        required = (
            "Models", "AI", "Assets", "Tasks", "Calendar", "Workflows",
            "Data", "Memory", "Logs", "Voice/whisper-base", "Voice/Piper",
            "Knowledge/Wikipedia",
        )
        for relative in required:
            folder = root / relative
            self.assertTrue(folder.is_dir(), f"Missing resource folder: {relative}")
            self.assertTrue((folder / "README.txt").is_file(),
                            f"Missing visible README.txt in: {relative}")
            self.assertFalse((folder / ".keep").exists(),
                             f"Hidden .keep placeholder remains in: {relative}")

    def test_nested_usb_source_is_present_and_independent(self):
        root = Path(__file__).resolve().parents[1] / "JARVIS_USB"
        self.assertTrue((root / "app.py").is_file())
        self.assertTrue((root / ".github/workflows/build-usb.yml").is_file())
        for relative in (
            "Models", "AI", "Assets", "Memory", "Logs",
            "Voice/whisper-base", "Voice/Piper", "Knowledge/Wikipedia",
        ):
            folder = root / relative
            self.assertTrue(folder.is_dir(), f"Missing nested USB folder: {relative}")
            self.assertTrue((folder / "README.txt").is_file(),
                            f"Missing nested USB README.txt in: {relative}")
        self.assertFalse(any(root.rglob(".keep")), "Nested USB source still contains hidden .keep placeholders")

    def test_path_confinement_rejects_parent_escape(self):
        from core.paths import confined_path, APP_DIR
        self.assertEqual(confined_path("Data/Logs").parent, APP_DIR / "Data")
        with self.assertRaises(ValueError): confined_path("../outside.txt")

if __name__ == "__main__": unittest.main()
