"""Durable newline-delimited JSON buffer for disconnected node gateways.

This is a software integration helper for a node/gateway client. It does not
claim to provide ESP32 firmware or physical offline alerting by itself.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable


class OfflineReadingBuffer:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, reading: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as buffer_file:
            buffer_file.write(json.dumps(reading, separators=(",", ":"), default=str) + "\n")

    def pending(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        readings = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                readings.append(value)
        return readings

    def synchronize(self, sender: Callable[[dict[str, Any]], bool]) -> int:
        pending = self.pending()
        sent = 0
        remaining = []
        for reading in pending:
            if sender(reading):
                sent += 1
            else:
                remaining.append(reading)
        if remaining:
            descriptor, temporary_name = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                temporary.write_text("".join(json.dumps(item, separators=(",", ":"), default=str) + "\n" for item in remaining), encoding="utf-8")
                os.replace(temporary, self.path)
            finally:
                if temporary.exists():
                    temporary.unlink()
        elif self.path.exists():
            self.path.unlink()
        return sent
