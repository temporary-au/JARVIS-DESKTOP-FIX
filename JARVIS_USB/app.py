from __future__ import annotations
import html
import sys
from datetime import datetime
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QLineEdit, QFrame, QGridLayout, QMessageBox,
    QStackedWidget, QSizePolicy
)
from core.paths import APP_DIR, ensure_layout
from core.hardware import detect_hardware, choose_model
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

class AIWorker(QThread):
    done = Signal(str)
    error = Signal(str)
    def __init__(self, ai: LocalAI, prompt: str, history: list[dict], knowledge: KnowledgeBase):
        super().__init__(); self.ai = ai; self.prompt = prompt; self.history = history; self.knowledge = knowledge
    def run(self):
        try:
            refs = self.knowledge.context_for(self.prompt)
            self.done.emit(self.ai.reply(self.prompt, self.history, refs))
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_layout()
        self.hw = detect_hardware()
        self.memory = MemoryStore(APP_DIR / "Memory" / "jarvis.sqlite3")
        self.ai = LocalAI(APP_DIR, self.hw)
        self.voice = VoiceController(APP_DIR)
        self.knowledge = KnowledgeBase(APP_DIR)
        self.recording = False
        self.ai_busy = False
        self.speech_workers = []
        self.setWindowTitle("J.A.R.V.I.S. • Portable Command System")
        self.resize(1480, 900); self.setMinimumSize(1020, 680); self.setStyleSheet(STYLE)
        self.build(); self.refresh()
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(7000)

    def build(self):
        central = QWidget(); self.setCentralWidget(central)
        outer = QHBoxLayout(central); outer.setContentsMargins(14, 14, 14, 14); outer.setSpacing(12)
        sidebar = QFrame(); sidebar.setObjectName("panel"); sidebar.setFixedWidth(205)
        sl = QVBoxLayout(sidebar)
        logo = QLabel("J.A.R.V.I.S."); logo.setStyleSheet("font-size:22px;font-weight:700;color:#56e6ff;letter-spacing:3px;")
        sl.addWidget(logo); tag = QLabel("PORTABLE COMMAND SYSTEM"); tag.setObjectName("muted"); sl.addWidget(tag); sl.addSpacing(14)
        self.pages = ["Command Center", "AI Core", "Agents", "Tasks", "Calendar", "Memory", "Conversations", "Knowledge Base", "Tools & Skills", "Workflows"]
        self.nav = []; self.stack = QStackedWidget()
        for index, name in enumerate(self.pages):
            button = QPushButton(name); button.setObjectName("nav"); button.setCheckable(True)
            button.clicked.connect(lambda checked=False, n=index: self.switch(n))
            sl.addWidget(button); self.nav.append(button)
        sl.addStretch(); sl.addWidget(QLabel("USB EDITION • LOCAL FIRST")); outer.addWidget(sidebar)
        right = QVBoxLayout(); right.setSpacing(10)
        top = QFrame(); top.setObjectName("panel"); tl = QHBoxLayout(top)
        self.heading = QLabel("COMMAND CENTER"); self.heading.setStyleSheet("font-size:18px;font-weight:700;letter-spacing:2px;color:#62e7ff;")
        self.status = QLabel("INITIALISING"); self.status.setObjectName("muted")
        tl.addWidget(self.heading); tl.addStretch(); tl.addWidget(self.status); right.addWidget(top)
        self.stack.addWidget(self.command_page())
        descriptions = [
            ("AI CORE", "Local GGUF model, host hardware and generation status."),
            ("AGENTS", "No autonomous agents are active in this USB build."),
            ("TASKS", "Task tracking is a reserved interface; task automation is not implemented."),
            ("CALENDAR", "No calendar provider is connected in this offline-first build."),
            ("MEMORY", "Conversation history is stored locally on this USB drive."),
            ("CONVERSATIONS", "Recent messages are stored in the local SQLite memory database."),
            ("KNOWLEDGE BASE", "External offline Wikipedia plugin with ZIM search, article retrieval and local AI context."),
            ("TOOLS & SKILLS", "Portable hardware information and local voice/model status."),
            ("WORKFLOWS", "Workflow execution and unattended actions are not enabled in this build."),
        ]
        for title, desc in descriptions:
            page = QWidget(); pl = QVBoxLayout(page); pl.addWidget(make_panel(title, desc)); pl.addStretch(); self.stack.addWidget(page)
        right.addWidget(self.stack, 1); outer.addLayout(right, 1); self.switch(0)

    def command_page(self):
        widget = QWidget(); layout = QVBoxLayout(widget); grid = QGridLayout(); grid.setSpacing(10)
        self.core = make_panel("AI CORE", "Checking local model…")
        self.feed = make_panel("LIVE INTELLIGENCE FEED", "Local system events will appear here.")
        self.agents = make_panel("ACTIVE AGENTS", "No autonomous agents are running.")
        self.mission = make_panel("MISSION TIMELINE", "No active missions.")
        self.monitor = make_panel("SYSTEM MONITOR", "Detecting host hardware…")
        self.mem = make_panel("MEMORY INSIGHTS", "USB-local memory ready.")
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
        layout.addWidget(chat_panel, 2)
        return widget

    def switch(self, index):
        self.stack.setCurrentIndex(index); self.heading.setText(self.pages[index].upper())
        for i, button in enumerate(self.nav): button.setChecked(i == index)

    def refresh(self):
        model = choose_model(APP_DIR, self.hw)
        self.status.setText(f"USB MODE • {'MODEL READY' if model else 'MODEL MISSING'} • {self.hw['ram_gb']:.1f} GB RAM")
        self.core.body_label.setText(("MODEL READY: " + model.name) if model else "LOCAL MODEL NOT INSTALLED. Run Prepare-USB.ps1.")
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
        model_path = choose_model(APP_DIR, self.hw)
        self.entry.clear()
        self.chat.append(f"<b style='color:#5be4ff'>YOU</b><br>{self.escape(prompt)}")
        if model_path is None:
            self.chat.append("<span style='color:#ffbd70'>JARVIS: Local model missing. Run Prepare-USB.ps1 while online, then restart.</span>")
            return
        # Capture history BEFORE adding the new user message: the prompt is appended once by LocalAI.
        history = self.memory.recent(12)
        self.memory.add("user", prompt)
        self.ai_busy = True; self.send_button.setEnabled(False); self.entry.setEnabled(False)
        self.chat.append("<span style='color:#83b7c8'>JARVIS is processing locally…</span>")
        self.worker = AIWorker(self.ai, prompt, history, self.knowledge)
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
    memory = MemoryStore(APP_DIR / "Memory" / "jarvis.sqlite3")
    ai = LocalAI(APP_DIR, hw)
    knowledge = KnowledgeBase(APP_DIR)
    server = JarvisWebServer(APP_DIR, ai, memory, knowledge, hw)
    server.start(open_browser=True)
    print("JARVIS HTML mode is running at http://127.0.0.1:8765/")
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
