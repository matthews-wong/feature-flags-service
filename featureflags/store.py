"""Flag storage.

A single ``FlagStore`` backs the service with an in-memory dict, optionally
persisted to a JSON file. This is intentionally the only IO seam: swap this
class for a Redis/Postgres-backed implementation with the same interface and
nothing else in the service needs to change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import Flag


class FlagNotFound(KeyError):
    """Raised when a flag key is not present in the store."""


class FlagStore:
    """In-memory flag store with optional JSON-file persistence.

    Pass ``path`` to load from and persist to a JSON file; omit it for a
    purely in-memory store (handy for tests). Writes are flushed to disk
    immediately when a path is configured — fine for a demo, and the obvious
    place to add batching/locking for a real backend.
    """

    def __init__(self, path: Optional[Path | str] = None) -> None:
        self._path: Optional[Path] = Path(path) if path else None
        self._flags: Dict[str, Flag] = {}
        if self._path and self._path.exists():
            self._load()

    def _load(self) -> None:
        assert self._path is not None
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        # Accept either {"flags": [...]} or a bare list of flag objects.
        items = raw["flags"] if isinstance(raw, dict) else raw
        self._flags = {item["key"]: Flag(**item) for item in items}

    def _persist(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"flags": [f.model_dump() for f in self._flags.values()]}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list(self) -> List[Flag]:
        """Return all flags."""
        return list(self._flags.values())

    def get(self, key: str) -> Flag:
        """Return a flag by key, or raise FlagNotFound."""
        try:
            return self._flags[key]
        except KeyError as exc:
            raise FlagNotFound(key) from exc

    def upsert(self, flag: Flag) -> Flag:
        """Create or replace a flag and persist."""
        self._flags[flag.key] = flag
        self._persist()
        return flag

    def delete(self, key: str) -> None:
        """Remove a flag by key, or raise FlagNotFound."""
        if key not in self._flags:
            raise FlagNotFound(key)
        del self._flags[key]
        self._persist()
