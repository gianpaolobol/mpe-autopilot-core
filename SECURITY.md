# Security Policy

## Scope

This repository contains only generic controller reliability primitives. It is intentionally separated from private product repositories, live operational state, credentials, project memory and business-domain integration.

## Reporting a vulnerability

Please report suspected security vulnerabilities privately to the repository owner rather than opening a public issue containing exploit details, credentials, private infrastructure information or sensitive logs.

## Security invariants

- No production credentials are required by public CI.
- GitHub Actions permissions are read-only (`contents: read`).
- Controller-build provenance must be an exact 40-hex commit SHA.
- Credential-shaped values are sanitized before ledger/handoff persistence.
- Runtime-store paths must remain under their configured root.
- Lease takeover requires both lease expiry and stale owner heartbeat.
- Explicit handoff requires the named receiver and the same controller build.
- The local file store is not a distributed concurrency backend.

The private operational integration layer is responsible for providing a concurrency-safe shared-state backend and for preserving these invariants.
