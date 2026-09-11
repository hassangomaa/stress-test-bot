from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any


def _log_dir() -> Path:
    raw = os.environ.get("STRESSBOT_LOG_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path.cwd() / "logs"


class EventLogger:
    """Structured JSON-line logger with unix timestamps."""

    _lock = threading.Lock()
    _instances: dict[str, EventLogger] = {}

    def __init__(self, profile: str, site: str, *, orchestrator: bool = False) -> None:
        self.profile = profile
        self.site = site
        self.orchestrator = orchestrator
        self._log_dir = _log_dir()
        self._log_dir.mkdir(parents=True, exist_ok=True)
        slug = profile.removeprefix("comp-") if profile.startswith("comp-") else profile
        self._profile_path = self._log_dir / f"comp-{slug}.log"
        self._orch_path = self._log_dir / "orchestrator.log"

    @classmethod
    def for_profile(cls, profile: str, site: str) -> EventLogger:
        with cls._lock:
            if profile not in cls._instances:
                cls._instances[profile] = cls(profile, site)
            return cls._instances[profile]

    @classmethod
    def orchestrator(cls) -> EventLogger:
        with cls._lock:
            key = "__orchestrator__"
            if key not in cls._instances:
                cls._instances[key] = cls("orchestrator", "", orchestrator=True)
            return cls._instances[key]

    def emit(self, event: str, **fields: Any) -> None:
        payload: dict[str, Any] = {
            "ts_unix": round(time.time(), 3),
            "profile": self.profile,
            "site": self.site,
            "event": event,
        }
        payload.update(fields)
        line = json.dumps(payload, ensure_ascii=False)

        with self._lock:
            print(line, flush=True)
            targets: list[Path] = [self._orch_path] if self.orchestrator else [self._profile_path, self._orch_path]
            for path in targets:
                try:
                    with path.open("a", encoding="utf-8") as fh:
                        fh.write(line + "\n")
                except OSError as exc:
                    print(
                        json.dumps(
                            {
                                "ts_unix": round(time.time(), 3),
                                "event": "log_write_error",
                                "path": str(path),
                                "error": str(exc),
                            }
                        ),
                        file=sys.stderr,
                        flush=True,
                    )

    def journey_start(self) -> None:
        self.emit("journey_start")

    def journey_end(self, ok: bool, step: str, duration_s: float, error: str | None = None) -> None:
        self.emit(
            "journey_end",
            ok=ok,
            step=step,
            duration_ms=round(duration_s * 1000, 1),
            error=error,
        )

    def step(
        self,
        name: str,
        *,
        ok: bool,
        http_status: int | None = None,
        duration_ms: float | None = None,
        detail: str | None = None,
    ) -> None:
        self.emit(
            "step",
            step=name,
            ok=ok,
            http_status=http_status,
            duration_ms=duration_ms,
            detail=detail,
        )

    def gate_skipped(self, reason: str) -> None:
        self.emit("gate_skipped", reason=reason)

    def capacity_blocked(self, step: str, detail: str | None = None) -> None:
        self.emit("capacity_blocked", step=step, detail=detail)

    def thread_crash(self, thread: str, error: str) -> None:
        self.emit("thread_crash", thread=thread, error=error)

    def orchestrator_stop(self, reason: str) -> None:
        self.emit("orchestrator_stop", reason=reason)
