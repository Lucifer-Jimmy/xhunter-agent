"""Deterministic secret and flag redaction for persisted control-plane data."""

import re
from dataclasses import dataclass
from hashlib import sha256

_DEFAULT_PATTERNS = (
    re.compile(r"(?i)\b(flag|ctf)\{[^}\r\n]{1,512}\}"),
    re.compile(
        r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*"
        r"([\"']?)[^\s,;\"']{4,}\2"
    ),
)


@dataclass(frozen=True, slots=True)
class RedactedText:
    text: str
    references: tuple[str, ...] = ()


class Redactor:
    def __init__(
        self, patterns: tuple[re.Pattern[str], ...] = _DEFAULT_PATTERNS
    ) -> None:
        self._patterns = patterns

    @classmethod
    def with_patterns(cls, *patterns: str) -> "Redactor":
        compiled = _DEFAULT_PATTERNS + tuple(
            re.compile(pattern, re.IGNORECASE) for pattern in patterns
        )
        return cls(compiled)

    def redact(self, content: str) -> RedactedText:
        references: list[str] = []

        def replace(match: re.Match[str]) -> str:
            value = match.group(0)
            reference = f"sha256:{sha256(value.encode()).hexdigest()}"
            references.append(reference)
            return f"[REDACTED:{reference}]"

        text = content
        for pattern in self._patterns:
            text = pattern.sub(replace, text)
        return RedactedText(text, tuple(references))
