from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


REDACTION_NOTICE = "Sensitive-looking values were redacted before persistence."

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*([^\s,'\"}]+)"
        ),
        "credential",
    ),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"), "bearer"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "openai_key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws_key"),
    (
        re.compile(
            r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"
        ),
        "private_key",
    ),
    (
        re.compile(
            r"-----END (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"
        ),
        "private_key",
    ),
)


def redact_text(text: str) -> str:
    redacted = text
    for pattern, kind in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: _replacement(match, kind), redacted)
    return redacted


def redact_data(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {
            key: redact_data(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [redact_data(item) for item in value]
    return value


def redaction_applied(value: Any) -> bool:
    return redact_data(value) != value


def _replacement(match: re.Match[str], kind: str) -> str:
    if kind == "credential" and match.lastindex and match.lastindex >= 1:
        return f"{match.group(1)}=[REDACTED:{kind}]"
    return f"[REDACTED:{kind}]"
