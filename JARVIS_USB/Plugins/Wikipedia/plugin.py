from __future__ import annotations
import re
import threading
from pathlib import Path


def _html_unescape(value: str) -> str:
    """Decode common and numeric HTML entities without importing html.parser."""
    named = {
        "amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'",
        "nbsp": " ", "ndash": "–", "mdash": "—", "lsquo": "‘",
        "rsquo": "’", "ldquo": "“", "rdquo": "”", "hellip": "…",
        "copy": "©", "reg": "®", "trade": "™",
    }
    def replace(match):
        entity = match.group(1)
        if entity.startswith(("#x", "#X")):
            try: return chr(int(entity[2:], 16))
            except (ValueError, OverflowError): return match.group(0)
        if entity.startswith("#"):
            try: return chr(int(entity[1:], 10))
            except (ValueError, OverflowError): return match.group(0)
        return named.get(entity, match.group(0))
    return re.sub(r"&(#(?:[xX][0-9A-Fa-f]+|[0-9]+)|[A-Za-z][A-Za-z0-9]+);", replace, str(value))


def _html_to_text(source: str) -> str:
    """Convert article HTML to readable text using only re and stdlib basics."""
    text = str(source)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?is)<(script|style|noscript|svg|head)\b[^>]*>.*?</\1\s*>", " ", text)
    text = re.sub(r"(?i)</?(?:p|div|br|li|h[1-6]|tr|td|th|section|article|blockquote)\b[^>]*>", " ", text)
    text = re.sub(r"(?s)<[^>]*>", " ", text)
    text = _html_unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class WikipediaPlugin:
    """Offline ZIM search and article retrieval using python-libzim."""
    plugin_id = "wikipedia.offline"

    def __init__(self, app_dir: Path):
        self.app_dir = Path(app_dir)
        self.root = self.app_dir / "Knowledge" / "Wikipedia"
        self._lock = threading.RLock()
        self._archive_path = None
        self._archive = None
        self._searcher = None
        self._load_error = None

    def find_zim(self):
        patterns = ("wikipedia_en_all_nopic_*.zim", "*wikipedia*.zim", "*.zim")
        for pattern in patterns:
            matches = sorted(p for p in self.root.glob(pattern) if p.is_file())
            if matches:
                return matches[0]
        return None

    def _open(self):
        path = self.find_zim()
        if path is None:
            raise RuntimeError("No ZIM archive found in Knowledge/Wikipedia.")
        if self._archive is not None and self._archive_path == path:
            return
        try:
            from libzim.reader import Archive
            from libzim.search import Searcher
            archive = Archive(str(path))
            searcher = Searcher(archive)
            self._archive = archive
            self._searcher = searcher
            self._archive_path = path
            self._load_error = None
        except Exception as exc:
            self._load_error = str(exc)
            raise RuntimeError(f"Could not open Wikipedia ZIM archive: {exc}") from exc

    def status(self):
        path = self.find_zim()
        if path is None:
            return {"installed": False, "ready": False,
                    "message": "Wikipedia ZIM archive not found."}
        try:
            self._open()
            return {"installed": True, "ready": True, "archive": path.name,
                    "message": "Offline Wikipedia ready."}
        except Exception as exc:
            return {"installed": True, "ready": False, "archive": path.name,
                    "message": str(exc)}

    def search(self, query: str, limit: int = 8):
        query = str(query).strip()
        if not query:
            return []
        with self._lock:
            self._open()
            from libzim.search import Query
            result_set = self._searcher.search(Query().set_query(query))

            # python-libzim 4.0 renamed camelCase methods to snake_case.
            # Support both API generations because portable JARVIS builds may
            # bundle either version.
            get_results = getattr(result_set, "get_results", None)
            if not callable(get_results):
                get_results = getattr(result_set, "getResults", None)
            if not callable(get_results):
                raise RuntimeError(
                    "The installed libzim Search object has neither get_results() nor getResults()."
                )

            results = []
            for item in get_results(0, min(max(1, int(limit)), 25)):
                # libzim 4.x returns SearchResult objects; older releases may
                # return article paths. Resolve path-only results via Archive.
                if isinstance(item, (str, bytes)):
                    path = item.decode("utf-8", errors="replace") if isinstance(item, bytes) else item
                    entry = self._archive.get_entry_by_path(path)
                    title = getattr(entry, "title", path)
                    snippet = ""
                else:
                    path = getattr(item, "path", "")
                    title = getattr(item, "title", path)
                    snippet = getattr(item, "snippet", "")
                    if not path:
                        raise RuntimeError("libzim returned a search result without an article path.")
                results.append({"title": str(title), "path": str(path),
                                "snippet": str(snippet or "")})
            return results

    def article(self, path: str, max_chars: int = 12000):
        path = str(path).strip().lstrip("/")
        if not path or ".." in Path(path).parts:
            raise ValueError("Invalid Wikipedia article path.")
        with self._lock:
            self._open()
            entry = self._archive.get_entry_by_path(path)
            item = entry.get_item()
            raw = bytes(item.content).decode("utf-8", errors="replace")
            text = _html_to_text(raw)
            return {"title": str(entry.title), "path": path,
                    "text": text[:max(500, min(int(max_chars), 20000))],
                    "source": f"Offline Wikipedia ZIM: {entry.title}"}

    @staticmethod
    def _search_topic(prompt: str) -> str:
        """Extract the topic from explicit natural-language Wikipedia requests."""
        value = str(prompt).strip()
        patterns = (
            r"(?is)\b(?:search|look\s+up|find)\s+(?:the\s+)?(?:offline\s+)?wikipedia\s+(?:for|about|on)\s+(.+?)"
            r"(?=\s+and\s+(?:give|show|tell|provide|summari[sz]e|explain|read)\b|[?.!]|$)",
            r"(?is)\b(?:search|look\s+up|find)\s+(.+?)\s+(?:on|in)\s+(?:the\s+)?(?:offline\s+)?wikipedia\b",
        )
        for pattern in patterns:
            match = re.search(pattern, value)
            if match:
                topic = match.group(1).strip(" \t\r\n:;,.!?\"'")
                if topic:
                    return topic
        return ""

    def context_for(self, query: str, max_chars: int = 7000):
        # Only invoke retrieval for an explicit Wikipedia request. This prevents
        # ordinary chat prompts from being treated as literal article titles.
        topic = self._search_topic(query)
        if not topic:
            return []

        # Do not hide retrieval failures: the caller should display the actual
        # error instead of letting the local model claim it cannot access ZIM.
        hits = self.search(topic, limit=3)
        if not hits:
            raise RuntimeError(f"Offline Wikipedia found no matching articles for: {topic}")

        articles = []
        remaining = max_chars
        errors = []
        for hit in hits:
            try:
                article = self.article(hit["path"], max_chars=min(5000, remaining))
            except Exception as exc:
                errors.append(str(exc))
                continue
            if article.get("text"):
                articles.append(article)
                remaining -= len(article["text"])
            if remaining <= 500:
                break
        if not articles:
            detail = errors[0] if errors else "The matching articles contained no readable text."
            raise RuntimeError(f"Wikipedia search found results for '{topic}', but article retrieval failed: {detail}")
        return articles
