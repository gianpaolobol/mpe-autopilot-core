from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .control_plane import ControlPlane, LeaseBusyError
from .provenance import ProvenanceError, controller_sha_from_env, normalize_controller_sha
from .store import FileRuntimeStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autopilot-core")
    sub = parser.add_subparsers(dest="command", required=True)
    probe = sub.add_parser("probe", help="run a non-destructive control-plane probe")
    probe.add_argument("--root", default=".autopilot-runtime")
    probe.add_argument("--runner-id", default="local-primary")
    probe.add_argument("--controller-sha")
    return parser


def run_probe(*, root: str | Path, runner_id: str, controller_sha: str | None) -> dict:
    sha = (
        normalize_controller_sha(controller_sha)
        if controller_sha
        else controller_sha_from_env(required=True)
    )
    store = FileRuntimeStore(root)
    plane = ControlPlane(store)
    ctx = plane.start_run(runner_id, sha)
    plane.acquire_lease(ctx)
    plane.heartbeat(ctx)
    plane.complete_run(ctx, "PROBE_COMPLETED")
    plane.release_lease(ctx)
    store.load_ledger().verify()
    return {
        "status": "PASS",
        "result": "PROBE_COMPLETED",
        "runner_id": runner_id,
        "tick_id": ctx.tick_id,
        "run_id": ctx.run_id,
        "controller_sha": sha,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "probe":
            result = run_probe(
                root=args.root,
                runner_id=args.runner_id,
                controller_sha=args.controller_sha,
            )
            print(json.dumps(result, sort_keys=True))
            return 0
    except (ProvenanceError, LeaseBusyError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    return 2
