from datetime import datetime, timedelta, timezone

import pytest

from autopilot_core.control_plane import ControlPlane, HandoffError, LeaseBusyError
from autopilot_core.store import FileRuntimeStore


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds: int):
        self.now += timedelta(seconds=seconds)


def test_primary_probe_records_provenance_and_releases_lease(tmp_path):
    clock = FakeClock()
    store = FileRuntimeStore(tmp_path)
    plane = ControlPlane(store, clock=clock)
    ctx = plane.start_run("primary", "a" * 40)
    plane.acquire_lease(ctx)
    plane.heartbeat(ctx)
    plane.complete_run(ctx, "PROBE_COMPLETED")
    plane.release_lease(ctx)

    run = store.read_json("runs", f"{ctx.run_id}.json")
    assert run["controller_sha"] == "a" * 40
    assert run["result"] == "PROBE_COMPLETED"
    assert store.read_json("lease.json") is None
    events = store.load_ledger().events
    assert {event["event_type"] for event in events} >= {
        "RUN_STARTED",
        "LEASE_ACQUIRED",
        "HEARTBEAT",
        "COMPLETED",
        "LEASE_RELEASED",
    }
    assert all(event["controller_sha"] == "a" * 40 for event in events)


def test_secondary_cannot_take_over_healthy_owner(tmp_path):
    clock = FakeClock()
    store = FileRuntimeStore(tmp_path)
    plane = ControlPlane(store, lease_ttl_seconds=60, heartbeat_stale_seconds=60, clock=clock)
    primary = plane.start_run("primary", "a" * 40)
    plane.acquire_lease(primary)
    plane.heartbeat(primary)

    secondary = plane.start_run("secondary", "b" * 40)
    with pytest.raises(LeaseBusyError):
        plane.acquire_lease(secondary)


def test_secondary_takes_over_only_after_lease_expiry_and_stale_heartbeat(tmp_path):
    clock = FakeClock()
    store = FileRuntimeStore(tmp_path)
    plane = ControlPlane(store, lease_ttl_seconds=30, heartbeat_stale_seconds=30, clock=clock)
    primary = plane.start_run("primary", "a" * 40)
    plane.acquire_lease(primary)
    plane.heartbeat(primary)

    clock.advance(31)
    secondary = plane.start_run("secondary", "b" * 40)
    plane.acquire_lease(secondary)

    lease = store.read_json("lease.json")
    assert lease["runner_id"] == "secondary"
    assert lease["previous_owner"] == "primary"
    event_types = [event["event_type"] for event in store.load_ledger().events]
    assert "STALE_OWNER_DETECTED" in event_types
    assert "TAKEOVER_ACCEPTED" in event_types


def test_handoff_requires_named_receiver_and_records_acceptance(tmp_path):
    clock = FakeClock()
    store = FileRuntimeStore(tmp_path)
    plane = ControlPlane(store, clock=clock)
    primary = plane.start_run("primary", "a" * 40)
    handoff_id = plane.offer_handoff(primary, "secondary", {"token": "secret-value"})

    secondary = plane.start_run("secondary", "a" * 40)
    plane.accept_handoff(secondary, handoff_id)

    record = store.read_json("handoffs", f"{handoff_id}.json")
    assert record["state"] == "ACCEPTED"
    assert record["payload"]["token"] == "***"
    assert record["receiver_run_id"] == secondary.run_id


def test_handoff_rejects_different_controller_build(tmp_path):
    clock = FakeClock()
    store = FileRuntimeStore(tmp_path)
    plane = ControlPlane(store, clock=clock)
    primary = plane.start_run("primary", "a" * 40)
    handoff_id = plane.offer_handoff(primary, "secondary")

    secondary = plane.start_run("secondary", "b" * 40)
    with pytest.raises(HandoffError, match="controller SHA"):
        plane.accept_handoff(secondary, handoff_id)
