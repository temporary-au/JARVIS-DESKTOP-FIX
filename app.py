from __future__ import annotations
import html
import sys
from datetime import datetime
from pathlib import Path
from core.paths import APP_DIR, DATA_DIR, ensure_layout
ensure_layout()  # establish in-folder TEMP/TMP before loading Qt and native dependencies
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QLineEdit, QFrame, QGridLayout, QMessageBox,
    QStackedWidget, QSizePolicy, QFileSystemModel, QTreeView, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog, QAbstractItemView
)
from PySide6.QtCore import QDir
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from core.hardware import detect_hardware, choose_model, MODEL_MODES, DEFAULT_MODE
from core.memory import MemoryStore
from core.ai import LocalAI
from core.voice import VoiceController
from core.knowledge import KnowledgeBase
from core.web_server import JarvisWebServer

STYLE = """
QWidget { background:#07111e; color:#d8f5ff; font-family:'Segoe UI'; }
QFrame#panel { background:#0b1b2b; border:1px solid #17445c; border-radius:12px; }
QLabel#muted { color:#75a9bd; }
QLabel#heading { color:#e7faff; font-size:15px; font-weight:600; }
QPushButton { background:#102c42; color:#c9f5ff; border:1px solid #1b7895; border-radius:8px; padding:9px 13px; }
QPushButton:hover { background:#16425d; border-color:#37d9ff; }
QPushButton:disabled { color:#58717d; border-color:#24404c; background:#0b1b27; }
QPushButton#nav { text-align:left; padding:10px; background:transparent; border:0; color:#8cb8c9; }
QPushButton#nav:checked { background:#10334a; color:#5be4ff; border-left:3px solid #35dfff; }
QLineEdit, QTextEdit { background:#06101b; border:1px solid #17445c; border-radius:8px; padding:9px; color:#e6fbff; }
"""

def make_panel(title: str, body: str = ""):
    frame = QFrame(); frame.setObjectName("panel")
    layout = QVBoxLayout(frame)
    heading = QLabel(title); heading.setObjectName("heading"); layout.addWidget(heading)
    label = QLabel(body); label.setObjectName("muted"); label.setWordWrap(True); label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(label); frame.body_label = label
    return frame


class ResourceBrowserPage(QWidget):
    """Folder-aware browser: opens files from this JARVIS installation/data tree."""
    def __init__(self, title: str, locations: list[tuple[str, Path]], parent=None):
        super().__init__(parent)
        self.locations = locations
        layout = QVBoxLayout(self)
        intro = make_panel(title, "Browse the actual folders used by this desktop installation. Double-click a file to open it with its Windows default application.")
        layout.addWidget(intro)
        controls = QHBoxLayout()
        self.location = QComboBox()
        for label, path in locations:
            path.mkdir(parents=True, exist_ok=True)
            self.location.addItem(f"{label}  —  {path}", str(path))
        self.open_folder_button = QPushButton("OPEN FOLDER")
        self.open_selected_button = QPushButton("OPEN SELECTED")
        self.refresh_button = QPushButton("REFRESH")
        controls.addWidget(self.location, 1)
        controls.addWidget(self.open_folder_button)
        controls.addWidget(self.open_selected_button)
        controls.addWidget(self.refresh_button)
        layout.addLayout(controls)
        self.path_label = QLabel("")
        self.path_label.setObjectName("muted")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.path_label)
        self.model = QFileSystemModel(self)
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot | QDir.Filter.Hidden)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setAnimated(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        for column in (1, 2, 3):
            self.tree.hideColumn(column)
        layout.addWidget(self.tree, 1)
        self.location.currentIndexChanged.connect(self.set_location)
        self.open_folder_button.clicked.connect(self.open_folder)
        self.open_selected_button.clicked.connect(self.open_selected)
        self.refresh_button.clicked.connect(self.refresh)
        self.tree.doubleClicked.connect(self.open_index)
        self.set_location(0)

    def current_path(self) -> Path:
        return Path(self.location.currentData()).resolve()

    def set_location(self, _index: int):
        path = self.current_path()
        path.mkdir(parents=True, exist_ok=True)
        root_index = self.model.setRootPath(str(path))
        self.tree.setRootIndex(root_index)
        self.path_label.setText(str(path))

    def refresh(self):
        self.model.setRootPath("")
        self.set_location(self.location.currentIndex())

    def open_path(self, path: Path):
        path = Path(path).resolve()
        if not path.exists():
            QMessageBox.warning(self, "File not found", f"This JARVIS resource is missing:\n{path}")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(self, "Could not open item", f"Windows could not open this path:\n{path}")

    def open_folder(self):
        self.open_path(self.current_path())

    def open_index(self, index):
        path = Path(self.model.filePath(index))
        if path.is_dir():
            if self.tree.isExpanded(index):
                self.tree.collapse(index)
            else:
                self.tree.expand(index)
            return
        if path.is_file():
            self.open_path(path)

    def open_selected(self):
        index = self.tree.currentIndex()
        if not index.isValid():
            self.open_folder()
            return
        self.open_path(Path(self.model.filePath(index)))

class AIWorker(QThread):
    done = Signal(str)
    error = Signal(str)
    def __init__(self, ai: LocalAI, prompt: str, history: list[dict], knowledge: KnowledgeBase, mode: str):
        super().__init__(); self.ai = ai; self.prompt = prompt; self.history = history; self.knowledge = knowledge; self.mode = mode
    def run(self):
        try:
            refs = self.knowledge.context_for(self.prompt)
            self.done.emit(self.ai.reply(self.prompt, self.history, refs, self.mode))
        except Exception as exc: self.error.emit(str(exc))

class TranscribeWorker(QThread):
    done = Signal(str)
    error = Signal(str)
    def __init__(self, voice: VoiceController): super().__init__(); self.voice = voice
    def run(self):
        try: self.done.emit(self.voice.transcribe_last_recording())
        except Exception as exc: self.error.emit(str(exc))

class SpeechWorker(QThread):
    error = Signal(str)
    def __init__(self, voice: VoiceController, text: str): super().__init__(); self.voice = voice; self.text = text
    def run(self):
        try: self.voice.speak(self.text)
        except Exception as exc: self.error.emit(str(exc))


class MemoryManagerPage(QWidget):
    """Live view of every conversation-memory row in the active SQLite store."""
    def __init__(self, store: MemoryStore, parent=None):
        super().__init__(parent); self.store = store
        layout = QVBoxLayout(self)
        top = QHBoxLayout(); self.search = QLineEdit(); self.search.setPlaceholderText("Search all stored memories…")
        self.refresh_button = QPushButton("REFRESH"); self.edit_button = QPushButton("EDIT SELECTED"); self.delete_button = QPushButton("DELETE SELECTED")
        top.addWidget(self.search, 1); top.addWidget(self.refresh_button); top.addWidget(self.edit_button); top.addWidget(self.delete_button); layout.addLayout(top)
        self.count_label = QLabel("Loading stored memories…"); self.count_label.setObjectName("muted"); layout.addWidget(self.count_label)
        self.table = QTableWidget(0, 4); self.table.setHorizontalHeaderLabels(["ID", "Role", "Memory content", "Created"]); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch); self.table.setColumnHidden(0, True); layout.addWidget(self.table, 1)
        self.refresh_button.clicked.connect(self.refresh); self.search.textChanged.connect(self.refresh); self.edit_button.clicked.connect(self.edit_selected); self.delete_button.clicked.connect(self.delete_selected); self.refresh()
    def refresh(self, *_):
        rows = self.store.all(self.search.text()); self.table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            for c, value in enumerate((item["id"], item["role"], item["content"], item["created_at"])):
                cell = QTableWidgetItem(str(value)); cell.setData(Qt.ItemDataRole.UserRole, item["id"]); self.table.setItem(r, c, cell)
        self.count_label.setText(f"Showing {len(rows):,} of {self.store.count():,} stored memories. This is the live database, not sample data.")
    def selected_id(self):
        row = self.table.currentRow()
        if row < 0: return None
        return int(self.table.item(row, 0).text())
    def edit_selected(self):
        memory_id = self.selected_id()
        if memory_id is None: QMessageBox.information(self, "Select a memory", "Select a memory first."); return
        old = self.table.item(self.table.currentRow(), 2).text()
        value, ok = QInputDialog.getMultiLineText(self, "Edit memory", "Memory content:", old)
        if ok:
            try: self.store.update(memory_id, value); self.refresh()
            except Exception as exc: QMessageBox.warning(self, "Memory update failed", str(exc))
    def delete_selected(self):
        memory_id = self.selected_id()
        if memory_id is None: QMessageBox.information(self, "Select a memory", "Select a memory first."); return
        answer = QMessageBox.question(self, "Delete memory", f"Permanently delete memory #{memory_id}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            try: self.store.delete(memory_id); self.refresh()
            except Exception as exc: QMessageBox.warning(self, "Memory deletion failed", str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_layout()
        self.hw = detect_hardware()
        self.memory = MemoryStore(DATA_DIR / "Memory" / "jarvis.sqlite3")
        self.ai = LocalAI(APP_DIR, self.hw)
        self.voice = VoiceController(APP_DIR)
        self.knowledge = KnowledgeBase(APP_DIR)
        self.recording = False
        self.ai_busy = False
        self.speech_workers = []
        self.setWindowTitle("J.A.R.V.I.S. • Desktop Command System")
        self.resize(1480, 900); self.setMinimumSize(1020, 680); self.setStyleSheet(STYLE)
        self.build(); self.refresh()
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(7000)

    def build(self):
        central = QWidget(); self.setCentralWidget(central)
        outer = QHBoxLayout(central); outer.setContentsMargins(14, 14, 14, 14); outer.setSpacing(12)
        sidebar = QFrame(); sidebar.setObjectName("panel"); sidebar.setFixedWidth(205)
        sl = QVBoxLayout(sidebar)
        logo = QLabel("J.A.R.V.I.S."); logo.setStyleSheet("font-size:22px;font-weight:700;color:#56e6ff;letter-spacing:3px;")
        sl.addWidget(logo); tag = QLabel("DESKTOP COMMAND SYSTEM"); tag.setObjectName("muted"); sl.addWidget(tag); sl.addSpacing(14)
        self.pages = ["Command Center", "AI Core", "Agents", "Tasks", "Calendar", "Memory", "Conversations", "Knowledge Base", "Tools & Skills", "Workflows"]
        self.nav = []; self.stack = QStackedWidget()
        for index, name in enumerate(self.pages):
            button = QPushButton(name); button.setObjectName("nav"); button.setCheckable(True)
            button.clicked.connect(lambda checked=False, n=index: self.switch(n))
            sl.addWidget(button); self.nav.append(button)
        sl.addStretch(); sl.addWidget(QLabel("DESKTOP EDITION • LOCAL FIRST")); outer.addWidget(sidebar)
        right = QVBoxLayout(); right.setSpacing(10)
        top = QFrame(); top.setObjectName("panel"); tl = QHBoxLayout(top)
        self.heading = QLabel("COMMAND CENTER"); self.heading.setStyleSheet("font-size:18px;font-weight:700;letter-spacing:2px;color:#62e7ff;")
        self.status = QLabel("INITIALISING"); self.status.setObjectName("muted")
        tl.addWidget(self.heading); tl.addStretch(); self.mode_selector = QComboBox(); self.mode_selector.addItems(list(MODEL_MODES)); self.mode_selector.setCurrentText(DEFAULT_MODE); self.mode_selector.currentTextChanged.connect(self.change_mode); tl.addWidget(QLabel("AI MODE")); tl.addWidget(self.mode_selector); tl.addWidget(self.status); right.addWidget(top)
        self.stack.addWidget(self.command_page())
        data_memory = DATA_DIR / "Memory"
        pages = [
            ("AI CORE", [("Models", APP_DIR / "Models"), ("AI resources", APP_DIR / "AI")]),
            ("AGENTS", [("Plugins", APP_DIR / "Plugins")]),
            ("TASKS", [("Tasks", APP_DIR / "Tasks"), ("Configuration", APP_DIR / "Config")]),
            ("CALENDAR", [("Calendar", APP_DIR / "Calendar"), ("Configuration", APP_DIR / "Config")]),
            ("MEMORY", [("Memory database and files", data_memory), ("Logs", DATA_DIR / "Logs"), ("Application data", DATA_DIR)]),
            ("CONVERSATIONS", [("Conversation memory", data_memory)]),
            ("KNOWLEDGE BASE", [("Knowledge files", APP_DIR / "Knowledge"), ("Wikipedia archive", APP_DIR / "Knowledge" / "Wikipedia")]),
            ("TOOLS & SKILLS", [("Assets", APP_DIR / "Assets"), ("Voice resources", APP_DIR / "Voice"), ("Data and recordings", DATA_DIR / "Voice")]),
            ("WORKFLOWS", [("Workflows", APP_DIR / "Workflows"), ("Configuration", APP_DIR / "Config")]),
        ]
        for page_index, (title, locations) in enumerate(pages, start=1):
            if title == "MEMORY": self.stack.addWidget(MemoryManagerPage(self.memory))
            else: self.stack.addWidget(ResourceBrowserPage(title, locations))
        right.addWidget(self.stack, 1); outer.addLayout(right, 1); self.switch(0)

    def command_page(self):
        widget = QWidget(); layout = QVBoxLayout(widget); grid = QGridLayout(); grid.setSpacing(10)
        self.core = make_panel("AI CORE", "Checking local model…")
        self.feed = make_panel("LIVE INTELLIGENCE FEED", "Local system events will appear here.")
        self.agents = make_panel("ACTIVE AGENTS", "No autonomous agents are running.")
        self.mission = make_panel("MISSION TIMELINE", "No active missions.")
        self.monitor = make_panel("SYSTEM MONITOR", "Detecting host hardware…")
        self.mem = make_panel("MEMORY INSIGHTS", "Local desktop memory ready.")
        grid.addWidget(self.core, 0, 0, 2, 2); grid.addWidget(self.feed, 0, 2); grid.addWidget(self.agents, 1, 2)
        grid.addWidget(self.mission, 2, 0); grid.addWidget(self.monitor, 2, 1); grid.addWidget(self.mem, 2, 2)
        layout.addLayout(grid, 2)
        chat_panel = make_panel("JARVIS CONSOLE"); cl = QVBoxLayout(chat_panel)
        self.chat = QTextEdit(); self.chat.setReadOnly(True); self.chat.setMinimumHeight(150); cl.addWidget(self.chat)
        row = QHBoxLayout(); self.entry = QLineEdit(); self.entry.setPlaceholderText("Enter a message for local JARVIS…"); self.entry.returnPressed.connect(self.send)
        self.send_button = QPushButton("SEND"); self.send_button.clicked.connect(self.send)
        row.addWidget(self.entry, 1); row.addWidget(self.send_button); cl.addLayout(row)
        voice_row = QHBoxLayout(); self.ptt = QPushButton("HOLD TO TALK • RIGHT CTRL")
        self.ptt.pressed.connect(self.start_recording); self.ptt.released.connect(self.stop_recording)
        self.voice_status = QLabel("MICROPHONE IDLE"); self.voice_status.setObjectName("muted")
        self.voice_engine_status = QLabel("VOICE ENGINE: PIPER CHECKING"); self.voice_engine_status.setObjectName("muted")
        voice_row.addWidget(self.ptt); voice_row.addWidget(self.voice_status); voice_row.addStretch(); voice_row.addWidget(self.voice_engine_status); cl.addLayout(voice_row)
        folder_row = QHBoxLayout()
        open_app_folder = QPushButton("OPEN JARVIS FOLDER")
        open_data_folder = QPushButton("OPEN DATA FOLDER")
        open_app_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(APP_DIR))))
        open_data_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_DIR))))
        folder_row.addWidget(open_app_folder); folder_row.addWidget(open_data_folder); folder_row.addStretch()
        cl.addLayout(folder_row)
        layout.addWidget(chat_panel, 2)
        return widget

    def change_mode(self, mode):
        if getattr(self, "ai_busy", False):
            QMessageBox.information(self, "JARVIS is busy", "Wait for the current response to finish before switching AI modes.")
            return
        try:
            self.ai.unload()
            self.status.setText(f"AI MODE: {mode.upper()} • MODEL LOADS ON FIRST USE")
            if hasattr(self, "core"): self.core.body_label.setText(f"Selected {mode}: {MODEL_MODES[mode]['description']}. Model loads when first needed.")
        except Exception as exc:
            QMessageBox.warning(self, "Could not switch AI mode", str(exc))

    def switch(self, index):
        self.stack.setCurrentIndex(index); self.heading.setText(self.pages[index].upper())
        for i, button in enumerate(self.nav): button.setChecked(i == index)

    def refresh(self):
        mode = self.mode_selector.currentText() if hasattr(self, "mode_selector") else DEFAULT_MODE
        model = choose_model(APP_DIR, self.hw, mode)
        self.status.setText(f"DESKTOP MODE • {'MODEL READY' if model else 'MODEL MISSING'} • {self.hw['ram_gb']:.1f} GB RAM")
        self.core.body_label.setText((f"{mode.upper()} MODEL READY: {model.name}" if model else f"{mode.upper()} MODEL MISSING: {MODEL_MODES[mode]['file']}\nPlace that GGUF file in the desktop Models folder."))
        self.monitor.body_label.setText(
            f"CPU: {self.hw['cpu_name']}\nThreads: {self.hw['threads']}\nRAM: {self.hw['ram_gb']:.1f} GB\nOS: {self.hw['os']}\nArchitecture: {self.hw['arch']}\nCPU-first inference; GPU acceleration is not assumed.")
        self.feed.body_label.setText(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}\nLOCAL AI • NO CLOUD INFERENCE • {'PROCESSING' if self.ai_busy else 'IDLE'}")
        zim = self.knowledge.find_zim()
        wiki_status = self.knowledge.status()["wikipedia"]
        wiki_label = "SEARCH READY" if wiki_status.get("ready") else ("FOUND • READER UNAVAILABLE" if zim else "NOT INSTALLED")
        self.mem.body_label.setText(f"Saved messages: {self.memory.count()}\nWikipedia Nopic archive: {wiki_label}")
        if hasattr(self, 'voice_engine_status'):
            self.voice_engine_status.setText("VOICE ENGINE: " + self.voice.piper_status())

    def send(self):
        if self.ai_busy: return
        prompt = self.entry.text().strip()
        if not prompt: return
        mode = self.mode_selector.currentText()
        model_path = choose_model(APP_DIR, self.hw, mode)
        self.entry.clear()
        self.chat.append(f"<b style='color:#5be4ff'>YOU</b><br>{self.escape(prompt)}")
        if model_path is None:
            self.chat.append("<span style='color:#ffbd70'>JARVIS: Local model missing. Place the selected mode's GGUF model in the desktop Models folder, then retry.</span>")
            return
        # Capture history BEFORE adding the new user message: the prompt is appended once by LocalAI.
        history = self.memory.recent(12)
        self.memory.add("user", prompt)
        self.ai_busy = True; self.send_button.setEnabled(False); self.entry.setEnabled(False)
        self.chat.append("<span style='color:#83b7c8'>JARVIS is processing locally…</span>")
        self.worker = AIWorker(self.ai, prompt, history, self.knowledge, mode)
        self.worker.done.connect(self.reply); self.worker.error.connect(self.reply_error); self.worker.finished.connect(self.finish_ai_request)
        self.worker.start(); self.refresh()

    def finish_ai_request(self):
        self.ai_busy = False; self.send_button.setEnabled(True); self.entry.setEnabled(True); self.entry.setFocus(); self.refresh()

    def reply(self, text):
        self.chat.append(f"<b style='color:#d9faff'>JARVIS</b><br>{self.escape(text)}")
        self.memory.add("assistant", text)
        worker = SpeechWorker(self.voice, text)
        self.speech_workers.append(worker)
        worker.error.connect(self.speech_error)
        worker.finished.connect(lambda w=worker: self._release_speech_worker(w))
        worker.start()

    def _release_speech_worker(self, worker):
        if worker in self.speech_workers:
            self.speech_workers.remove(worker)

    def reply_error(self, error):
        self.chat.append(f"<span style='color:#ff9999'>LOCAL AI ERROR: {self.escape(error)}</span>")

    def speech_error(self, error):
        self.voice_engine_status.setText("VOICE ENGINE: PIPER ERROR")
        self.chat.append(f"<span style='color:#ffbd70'>PIPER VOICE ERROR: {self.escape(error)}</span>")

    def start_recording(self):
        if self.recording: return
        try:
            self.voice.start_recording(); self.recording = True
            self.voice_status.setText("LISTENING • RELEASE TO SEND"); self.ptt.setText("RECORDING… RELEASE TO SEND")
        except Exception as exc: QMessageBox.warning(self, "Microphone unavailable", str(exc))

    def stop_recording(self):
        if not self.recording: return
        self.recording = False
        try:
            self.voice.stop_recording(); self.voice_status.setText("TRANSCRIBING LOCALLY…")
            self.transcribe_worker = TranscribeWorker(self.voice)
            self.transcribe_worker.done.connect(self.transcript); self.transcribe_worker.error.connect(self.voice_error)
            self.transcribe_worker.start()
        except Exception as exc: self.voice_error(str(exc))
        self.ptt.setText("HOLD TO TALK • RIGHT CTRL")

    def transcript(self, text):
        self.voice_status.setText("MICROPHONE IDLE")
        if text.strip(): self.entry.setText(text); self.send()

    def voice_error(self, error):
        self.voice_status.setText("VOICE ERROR")
        self.chat.append(f"<span style='color:#ff9999'>VOICE ERROR: {self.escape(error)}</span>")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Control and not event.isAutoRepeat(): self.start_recording()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Control and not event.isAutoRepeat(): self.stop_recording()
        super().keyReleaseEvent(event)

    @staticmethod
    def escape(value: str) -> str:
        return html.escape(str(value)).replace("\n", "<br>")

    def closeEvent(self, event):
        try: self.voice.close()
        except Exception: pass
        for worker in list(self.speech_workers):
            if worker.isRunning():
                worker.wait(1500)
        event.accept()

def run_web_mode():
    ensure_layout()
    hw = detect_hardware()
    memory = MemoryStore(DATA_DIR / "Memory" / "jarvis.sqlite3")
    ai = LocalAI(APP_DIR, hw)
    knowledge = KnowledgeBase(APP_DIR)
    server = JarvisWebServer(APP_DIR, ai, memory, knowledge, hw)
    server.start(open_browser=True)
    print(f"JARVIS desktop web companion is running at http://127.0.0.1:{server.port}/")
    print("Keep this window open while using the HTML interface. Press Ctrl+C to stop.")
    try:
        import time
        while True: time.sleep(1)
    except KeyboardInterrupt:
        server.stop()

def main():
    if "--web" in sys.argv[1:]:
        run_web_mode(); return
    app = QApplication(sys.argv); app.setFont(QFont("Segoe UI", 9))
    window = MainWindow(); window.show(); sys.exit(app.exec())

if __name__ == "__main__": main()
