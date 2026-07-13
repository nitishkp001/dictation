"""Persistent recording history stored as JSON under the XDG state dir.

Each entry keeps its transcription plus enough metadata to re-transcribe (the
captured audio is copied alongside so a different model can be re-run later).
"""

from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .config import STATE_DIR

HISTORY_PATH = STATE_DIR / "history.json"
AUDIO_DIR = STATE_DIR / "recordings"
DEFAULT_LIMIT = 100


@dataclass
class Recording:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)
    text: str = ""
    duration: float = 0.0
    model: str = ""
    audio_path: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Recording":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


class RecordingStore:
    def __init__(self, path: Path = HISTORY_PATH, audio_dir: Path = AUDIO_DIR,
                 limit: int = DEFAULT_LIMIT):
        self._path = path
        self._audio_dir = audio_dir
        self._limit = limit
        self._lock = threading.Lock()
        self._items: list[Recording] = self._load()

    # -- persistence ----------------------------------------------------------

    def _load(self) -> list[Recording]:
        if not self._path.exists():
            return []
        try:
            # ValueError covers JSONDecodeError and UnicodeDecodeError (corrupt bytes).
            data = json.loads(self._path.read_text())
        except (OSError, ValueError):
            return []
        if not isinstance(data, list):  # a dict/int/str is valid JSON but not our shape
            return []
        items: list[Recording] = []
        for d in data:
            if not isinstance(d, dict):
                continue
            try:
                items.append(Recording.from_dict(d))
            except (TypeError, ValueError):
                continue
        return items

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(r) for r in self._items], indent=2))
        tmp.replace(self._path)

    # -- audio ----------------------------------------------------------------

    def persist_media(self, src: Path, rec_id: str) -> str | None:
        """Copy captured/imported audio into the store so it survives for
        re-transcription (and so deleting a history entry never touches a file the
        user still owns). The source suffix is preserved."""
        try:
            self._audio_dir.mkdir(parents=True, exist_ok=True)
            suffix = src.suffix or ".wav"
            dst = self._audio_dir / f"{rec_id}{suffix}"
            shutil.copyfile(src, dst)
            return str(dst)
        except OSError:
            return None

    # -- mutations ------------------------------------------------------------

    def add(self, rec: Recording) -> Recording:
        with self._lock:
            self._items.insert(0, rec)
            self._enforce_limit_locked()
            self._save()
        return rec

    def update_text(self, rec_id: str, text: str, model: str | None = None) -> None:
        with self._lock:
            for r in self._items:
                if r.id == rec_id:
                    r.text = text
                    if model is not None:  # keep model metadata in sync on re-transcribe
                        r.model = model
                    break
            self._save()

    def delete(self, rec_id: str) -> None:
        with self._lock:
            for r in self._items:
                if r.id == rec_id:
                    self._remove_audio(r)
                    break
            self._items = [r for r in self._items if r.id != rec_id]
            self._save()

    def clear(self) -> None:
        with self._lock:
            for r in self._items:
                self._remove_audio(r)
            self._items = []
            self._save()

    def _enforce_limit_locked(self) -> None:
        while len(self._items) > self._limit:
            self._remove_audio(self._items.pop())

    def _remove_audio(self, rec: Recording) -> None:
        if rec.audio_path:
            Path(rec.audio_path).unlink(missing_ok=True)

    # -- queries --------------------------------------------------------------

    def all(self) -> list[Recording]:
        with self._lock:
            return list(self._items)

    def get(self, rec_id: str) -> Recording | None:
        with self._lock:
            return next((r for r in self._items if r.id == rec_id), None)

    def search(self, query: str) -> list[Recording]:
        q = query.strip().lower()
        if not q:
            return self.all()
        return [r for r in self.all() if q in r.text.lower()]
