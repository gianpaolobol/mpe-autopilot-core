from __future__ import annotations

import os
import re
from collections.abc import Mapping

_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class ProvenanceError(ValueError):
    """Raised when controller build provenance is absent or malformed."""


def normalize_controller_sha(value: str | None, *, required: bool = True) -> str | None:
    if value is None or not value.strip():
        if required:
            raise ProvenanceError("controller SHA provenance is required")
        return None
    normalized = value.strip().lower()
    if not _SHA40.fullmatch(normalized):
        raise ProvenanceError("controller SHA provenance must be exactly 40 hexadecimal characters")
    return normalized


def controller_sha_from_env(
    env: Mapping[str, str] | None = None,
    *,
    required: bool = True,
) -> str | None:
    source = os.environ if env is None else env
    value = source.get("AUTOPILOT_CONTROLLER_SHA") or source.get("GITHUB_SHA")
    return normalize_controller_sha(value, required=required)
