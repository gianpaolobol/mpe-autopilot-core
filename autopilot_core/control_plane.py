from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import uuid
from typing import Callable

from .ledger import HashChainLedger
from .provenance import normalize_controller_sha
from .sanitize import sanitize
from .store import FileRuntimeStore


class ControlPlaneError(RuntimeError):
    """Base error for guarded control-plane operations."""


class LeaseBusyError(ControlPlaneError):
    """Raised when another healthy runner still owns the lease."""


class HandoffError(ControlPlaneError):
    """Raised when a handoff cannot be accepted."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


@dataclass(frozen=True)
class RunContext:
    tick_id: str
    run_id: str
    runner_id: str
    controller_sha: str


class ControlPlane:
    def __init__(
        self,
        store: FileRuntimeStore,
        *,
        lease_ttl_seconds: int = 120,
        heartbeat_stale_seconds: int = 120,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if lease_ttl_seconds <= 0 or heartbeat_stale_seconds <= 0:
            raise ValueError("lease and heartbeat intervals must be positive")
        self.store = store
        self.lease_ttl_seconds = lease_ttl_seconds
        self.heartbeat_stale_seconds = heartbeat_stale_seconds
        self.clock = clock

    def _ledger(self) -> HashChainLedger:
        return self.store.load_ledger()

    def _emit(self, ctx: RunContext, event_type: str, payload: dict | None = None) -> dict:
        ledger = self._ledger()
        event = ledger.append(
            event_type,
            tick_id=ctx.tick_id,
            run_id=ctx.run_id,
            runner_id=ctx.runner_id,
            controller_sha=ctx.controller_sha,
            payload=payload or {},
            timestamp=_iso(self.clock()),
        )
        self.store.save_ledger(ledger)
        return event

    def start_run(self, runner_id: str, controller_sha: str) -> RunContext:
        sha = normalize_controller_sha(controller_sha)
        ctx = RunContext(
            tick_id=f"tick-{uuid.uuid4().hex}",
            run_id=f"run-{uuid.uuid4().hex}",
            runner_id=runner_id,
            controller_sha=sha,
        )
        now = _iso(self.clock())
        self.store.write_json(
            {
                "tick_id": ctx.tick_id,
                "runner_id": runner_id,
                "controller_sha": sha,
                "created_at": now,
                "state": "CREATED",
            },
            "ticks",
            f"{ctx.tick_id}.json",
        )
        self.store.write_json(
            {
                "run_id": ctx.run_id,
                "tick_id": ctx.tick_id,
                "runner_id": runner_id,
                "controller_sha": sha,
                "created_at": now,
                "state": "RUNNING",
            },
            "runs",
            f"{ctx.run_id}.json",
        )
        self._emit(ctx, "RUN_STARTED")
        return ctx

    def heartbeat(self, ctx: RunContext) -> None:
        now = self.clock()
        self.store.write_json(
            {
                "runner_id": ctx.runner_id,
                "run_id": ctx.run_id,
                "tick_id": ctx.tick_id,
                "controller_sha": ctx.controller_sha,
                "heartbeat_at": _iso(now),
            },
            "heartbeats",
            f"{ctx.runner_id}.json",
        )
        lease = self.store.read_json("lease.json")
        if lease and lease.get("runner_id") == ctx.runner_id and lease.get("run_id") == ctx.run_id:
            lease["renewed_at"] = _iso(now)
            lease["expires_at"] = _iso(now + timedelta(seconds=self.lease_ttl_seconds))
            self.store.write_json(lease, "lease.json")
        self._emit(ctx, "HEARTBEAT")

    def acquire_lease(self, ctx: RunContext) -> None:
        now = self.clock()
        existing = self.store.read_json("lease.json")
        takeover_from: str | None = None
        if existing:
            same_owner = (
                existing.get("runner_id") == ctx.runner_id
                and existing.get("run_id") == ctx.run_id
            )
            if not same_owner:
                expires_at = _parse_iso(existing["expires_at"])
                owner = str(existing["runner_id"])
                heartbeat = self.store.read_json("heartbeats", f"{owner}.json")
                heartbeat_at = _parse_iso(heartbeat["heartbeat_at"]) if heartbeat else None
                lease_expired = expires_at <= now
                heartbeat_stale = (
                    heartbeat_at is None
                    or heartbeat_at + timedelta(seconds=self.heartbeat_stale_seconds) <= now
                )
                if not (lease_expired and heartbeat_stale):
                    raise LeaseBusyError(f"lease is owned by healthy runner {owner}")
                takeover_from = owner

        self.store.write_json(
            {
                "lease_id": f"lease-{uuid.uuid4().hex}",
                "runner_id": ctx.runner_id,
                "run_id": ctx.run_id,
                "tick_id": ctx.tick_id,
                "controller_sha": ctx.controller_sha,
                "acquired_at": _iso(now),
                "renewed_at": _iso(now),
                "expires_at": _iso(now + timedelta(seconds=self.lease_ttl_seconds)),
                "previous_owner": takeover_from,
            },
            "lease.json",
        )
        if takeover_from:
            self._emit(ctx, "STALE_OWNER_DETECTED", {"previous_owner": takeover_from})
            self._emit(ctx, "TAKEOVER_ACCEPTED", {"previous_owner": takeover_from})
        else:
            self._emit(ctx, "LEASE_ACQUIRED")

    def release_lease(self, ctx: RunContext) -> None:
        lease = self.store.read_json("lease.json")
        if lease and lease.get("runner_id") == ctx.runner_id and lease.get("run_id") == ctx.run_id:
            self.store.write_json(
                {
                    **lease,
                    "released_at": _iso(self.clock()),
                    "state": "RELEASED",
                },
                "leases",
                f"{lease['lease_id']}.json",
            )
            lease_path = self.store.root / "lease.json"
            if lease_path.exists():
                lease_path.unlink()
            self._emit(ctx, "LEASE_RELEASED")

    def offer_handoff(self, ctx: RunContext, receiver_runner_id: str, payload: dict | None = None) -> str:
        handoff_id = f"handoff-{uuid.uuid4().hex}"
        record = {
            "handoff_id": handoff_id,
            "state": "OFFERED",
            "source_runner_id": ctx.runner_id,
            "source_run_id": ctx.run_id,
            "receiver_runner_id": receiver_runner_id,
            "controller_sha": ctx.controller_sha,
            "payload": sanitize(payload or {}),
            "offered_at": _iso(self.clock()),
        }
        self.store.write_json(record, "handoffs", f"{handoff_id}.json")
        self._emit(ctx, "HANDOFF_OFFERED", {"handoff_id": handoff_id, "receiver_runner_id": receiver_runner_id})
        return handoff_id

    def accept_handoff(self, ctx: RunContext, handoff_id: str) -> None:
        record = self.store.read_json("handoffs", f"{handoff_id}.json")
        if not record:
            raise HandoffError("handoff does not exist")
        if record.get("state") != "OFFERED":
            raise HandoffError("handoff is not open")
        if record.get("receiver_runner_id") != ctx.runner_id:
            raise HandoffError("handoff receiver does not match this runner")
        if record.get("controller_sha") != ctx.controller_sha:
            raise HandoffError("handoff controller SHA does not match receiving run")
        record["state"] = "ACCEPTED"
        record["accepted_at"] = _iso(self.clock())
        record["receiver_run_id"] = ctx.run_id
        self.store.write_json(record, "handoffs", f"{handoff_id}.json")
        self._emit(ctx, "HANDOFF_ACCEPTED", {"handoff_id": handoff_id, "source_run_id": record["source_run_id"]})

    def complete_run(self, ctx: RunContext, result: str = "COMPLETED") -> None:
        run = self.store.read_json("runs", f"{ctx.run_id}.json")
        if run is None:
            raise ControlPlaneError("run does not exist")
        run["state"] = "COMPLETED"
        run["result"] = result
        run["completed_at"] = _iso(self.clock())
        self.store.write_json(run, "runs", f"{ctx.run_id}.json")
        self._emit(ctx, "COMPLETED", {"result": result})
