from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .ledger import HashChainLedger


class FileRuntimeStore:
    """Small local JSON store used by the generic probe and integration tests."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, *parts: str) -> Path:
        root = self.root.resolve()
        candidate = self.root.joinpath(*parts).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("runtime store path escapes configured root")
        return candidate

    def read_json(self, *parts: str) -> dict[str, Any] | None:
        path = self._path(*parts)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def write_json(self, value: dict[str, Any], *parts: str) -> None:
        path = self._path(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(data)
            temp_name = handle.name
        os.replace(temp_name, path)

    def load_ledger(self) -> HashChainLedger:
        path = self._path("ledger.json")
        if not path.exists():
            return HashChainLedger()
        data = json.loads(path.read_text(encoding="utf-8"))
        ledger = HashChainLedger(data.get("events", []))
        ledger.verify()
        return ledger

    def save_ledger(self, ledger: HashChainLedger) -> None:
        ledger.verify()
        self.write_json({"events": list(ledger.events)}, "ledger.json")
