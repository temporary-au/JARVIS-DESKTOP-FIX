from __future__ import annotations
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

class MemoryStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with closing(self._connect()) as db:
            with db:
                db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")

    def _connect(self):
        return sqlite3.connect(str(self.path), timeout=20)

    def add(self, role: str, content: str) -> None:
        if role not in ("user", "assistant", "system"):
            raise ValueError("Unsupported conversation role")
        with self._lock, closing(self._connect()) as db:
            with db:
                db.execute("INSERT INTO messages(role, content) VALUES(?, ?)", (role, content))

    def recent(self, count: int = 12) -> list[dict]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute("SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (max(0, int(count)),)).fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    def count(self) -> int:
        with self._lock, closing(self._connect()) as db:
            return int(db.execute("SELECT COUNT(*) FROM messages").fetchone()[0])

    def clear(self) -> None:
        with self._lock, closing(self._connect()) as db:
            with db:
                db.execute("DELETE FROM messages")
