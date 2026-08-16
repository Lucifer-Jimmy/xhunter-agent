"""Append-only local JSONL tracer."""

import asyncio
import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path

from xhunter.contracts.event_bus import Event
from xhunter.services.redaction import Redactor


class NoopTracer:
    async def record(self, event: Event) -> None:
        del event


class JsonlTracer:
    def __init__(self, path: Path, redactor: Redactor) -> None:
        self._path = path
        self._redactor = redactor
        self._lock = asyncio.Lock()

    async def record(self, event: Event) -> None:
        serialized = json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "name": event.name,
                "payload": _json_value(event.payload),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        redacted = self._redactor.redact(serialized).text
        async with self._lock:
            await asyncio.to_thread(self._append, redacted)

    def _append(self, line: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as stream:
            stream.write(line)
            stream.write("\n")


def _json_value(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return value
