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

    def add_exchange(self, user_content: str, assistant_content: str) -> None:
        """Persist a completed chat turn atomically, never a failed prompt alone."""
        user_value = str(user_content).strip()
        assistant_value = str(assistant_content).strip()
        if not user_value or not assistant_value:
            raise ValueError("A completed exchange requires both messages")
        with self._lock, closing(self._connect()) as db:
            with db:
                db.executemany(
                    "INSERT INTO messages(role, content) VALUES(?, ?)",
                    (("user", user_value), ("assistant", assistant_value)),
                )

    def recent(self, count: int = 12) -> list[dict]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute("SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (max(0, int(count)),)).fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    def all(self, search: str = "") -> list[dict]:
        term = str(search).strip()
        with self._lock, closing(self._connect()) as db:
            if term:
                rows = db.execute("SELECT id, role, content, created_at FROM messages WHERE content LIKE ? ORDER BY id DESC", (f"%{term}%",)).fetchall()
            else:
                rows = db.execute("SELECT id, role, content, created_at FROM messages ORDER BY id DESC").fetchall()
        return [{"id": r[0], "role": r[1], "content": r[2], "created_at": r[3]} for r in rows]

    def update(self, memory_id: int, content: str) -> None:
        value = str(content).strip()
        if not value: raise ValueError("Memory content cannot be empty")
        with self._lock, closing(self._connect()) as db:
            with db:
                cur = db.execute("UPDATE messages SET content=? WHERE id=?", (value, int(memory_id)))
                if cur.rowcount != 1: raise KeyError(f"Memory {memory_id} was not found")

    def delete(self, memory_id: int) -> None:
        with self._lock, closing(self._connect()) as db:
            with db:
                cur = db.execute("DELETE FROM messages WHERE id=?", (int(memory_id),))
                if cur.rowcount != 1: raise KeyError(f"Memory {memory_id} was not found")

    def count(self) -> int:
        with self._lock, closing(self._connect()) as db:
            return int(db.execute("SELECT COUNT(*) FROM messages").fetchone()[0])

    def clear(self) -> None:
        with self._lock, closing(self._connect()) as db:
            with db:
                db.execute("DELETE FROM messages")
