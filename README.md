# Guarded Autopilot Core

A small, reusable control-plane core for guarded autonomous workers.

This public repository intentionally contains only generic reliability primitives:
controller-build provenance, secret sanitization, hash-chained lifecycle events,
leases, heartbeats, explicit handoff, and a read-only local probe CLI.

## Public boundary

This repository deliberately contains **no** product source code, product repository
identifiers, product branch/SHA state, local workstation paths, live runtime state,
forensic evidence, project memory, API credentials, or business-domain logic.

The operational integration layer and all live state belong in private repositories
or private runtime storage.

## Quick start

```bash
python -m pip install -e '.[test]'
python -m pytest -q
python -m autopilot_core probe --root .autopilot-runtime --runner-id local-primary
```

The probe is deliberately non-destructive: it creates a generic tick/run, acquires
a lease, emits lifecycle events, records a heartbeat, completes, and releases the
lease. It does not know how to modify any product repository.

## Security model

- fail closed on malformed controller SHA provenance;
- redact credential-shaped values before persistence;
- require an expired lease **and** stale owner heartbeat before takeover;
- preserve a hash chain for lifecycle events;
- require explicit offer/accept for handoff;
- GitHub Actions CI runs with `contents: read` and requires no secrets.

## Copyright

Copyright © 2026 Gian Paolo Franceschini. All rights reserved.

No open-source license is granted by this repository.
