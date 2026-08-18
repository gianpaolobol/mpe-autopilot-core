from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_SENSITIVE_KEY = re.compile(
    r"(?:token|secret|password|passwd|api[_-]?key|authorization|credential|private[_-]?key)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_GITHUB_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")
_OPENAI_TOKEN = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")


def _sanitize_string(value: str, redaction: str) -> str:
    value = _BEARER.sub(f"Bearer {redaction}", value)
    value = _GITHUB_TOKEN.sub(redaction, value)
    value = _OPENAI_TOKEN.sub(redaction, value)
    return value


def sanitize(value: Any, *, redaction: str = "***") -> Any:
    """Recursively redact common credential fields and credential-shaped strings."""
    if isinstance(value, Mapping):
        result: dict[Any, Any] = {}
        for key, item in value.items():
            if _SENSITIVE_KEY.search(str(key)):
                result[key] = redaction
            else:
                result[key] = sanitize(item, redaction=redaction)
        return result
    if isinstance(value, str):
        return _sanitize_string(value, redaction)
    if isinstance(value, tuple):
        return tuple(sanitize(item, redaction=redaction) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [sanitize(item, redaction=redaction) for item in value]
    return value
