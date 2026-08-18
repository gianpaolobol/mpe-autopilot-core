from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable

from .provenance import normalize_controller_sha
from .sanitize import sanitize


class LedgerIntegrityError(RuntimeError):
    """Raised when an event hash chain is malformed or has been tampered with."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _event_hash(event_without_hash: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(event_without_hash)).hexdigest()


class HashChainLedger:
    def __init__(self, events: Iterable[dict[str, Any]] | None = None) -> None:
        self._events: list[dict[str, Any]] = [dict(event) for event in (events or ())]

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(event) for event in self._events)

    def append(
        self,
        event_type: str,
        *,
        tick_id: str,
        run_id: str,
        runner_id: str,
        controller_sha: str,
        payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        sha = normalize_controller_sha(controller_sha)
        base = {
            "sequence": len(self._events) + 1,
            "event_type": event_type,
            "timestamp": timestamp or utc_now_iso(),
            "tick_id": tick_id,
            "run_id": run_id,
            "runner_id": runner_id,
            "controller_sha": sha,
            "payload": sanitize(payload or {}),
            "previous_event_hash": self._events[-1]["event_hash"] if self._events else None,
        }
        event = dict(base)
        event["event_hash"] = _event_hash(base)
        self._events.append(event)
        return dict(event)

    def verify(self) -> None:
        previous: str | None = None
        for index, event in enumerate(self._events, start=1):
            if event.get("sequence") != index:
                raise LedgerIntegrityError(f"ledger sequence mismatch at event {index}")
            if event.get("previous_event_hash") != previous:
                raise LedgerIntegrityError(f"ledger previous hash mismatch at event {index}")
            provided = event.get("event_hash")
            base = dict(event)
            base.pop("event_hash", None)
            expected = _event_hash(base)
            if provided != expected:
                raise LedgerIntegrityError(f"ledger event hash mismatch at event {index}")
            previous = provided
