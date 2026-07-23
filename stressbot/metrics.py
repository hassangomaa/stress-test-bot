from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class JourneyResult:
    ok: bool
    step: str
    duration_s: float
    error: str | None = None
    order_uuid: str | None = None


class Metrics:
    """Thread-safe counters and latency samples."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started_at = time.monotonic()
        self.journeys_ok = 0
        self.journeys_fail = 0
        self.capacity_blocks = 0
        self.step_failures: dict[str, int] = defaultdict(int)
        self.step_success: dict[str, int] = defaultdict(int)
        self.latencies: list[float] = []
        self._last_ok_at = self.started_at

    def record_journey(self, result: JourneyResult) -> None:
        with self._lock:
            self.latencies.append(result.duration_s)
            if len(self.latencies) > 10_000:
                self.latencies = self.latencies[-5_000:]
            if result.ok:
                self.journeys_ok += 1
                self._last_ok_at = time.monotonic()
            else:
                self.journeys_fail += 1
                if result.step:
                    self.step_failures[result.step] += 1

    def record_step(self, step: str) -> None:
        with self._lock:
            self.step_success[step] += 1

    def record_capacity_block(self) -> None:
        with self._lock:
            self.capacity_blocks += 1

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            elapsed = max(time.monotonic() - self.started_at, 0.001)
            total = self.journeys_ok + self.journeys_fail
            lat = sorted(self.latencies)
            p50 = lat[len(lat) // 2] if lat else 0.0
            p95 = lat[int(len(lat) * 0.95)] if lat else 0.0
            return {
                "elapsed_s": round(elapsed, 1),
                "journeys_ok": self.journeys_ok,
                "journeys_fail": self.journeys_fail,
                "total": total,
                "rps": round(total / elapsed, 2),
                "capacity_blocks": self.capacity_blocks,
                "latency_p50_s": round(p50, 2),
                "latency_p95_s": round(p95, 2),
            }

    def format_live(self) -> str:
        s = self.snapshot()
        return (
            f"[{s['elapsed_s']}s] ok={s['journeys_ok']} fail={s['journeys_fail']} "
            f"rps={s['rps']} capacity={s['capacity_blocks']} "
            f"p50={s['latency_p50_s']}s p95={s['latency_p95_s']}s"
        )

    def format_summary(self) -> str:
        s = self.snapshot()
        with self._lock:
            fails = dict(self.step_failures)
        lines = [
            "=== Stress Test Summary ===",
            f"Duration: {s['elapsed_s']}s",
            f"Completed journeys: {s['journeys_ok']}",
            f"Failed journeys: {s['journeys_fail']}",
            f"Throughput: {s['rps']} journeys/s",
            f"Capacity blocks: {s['capacity_blocks']}",
            f"Latency p50: {s['latency_p50_s']}s",
            f"Latency p95: {s['latency_p95_s']}s",
        ]
        if fails:
            lines.append("Failures by step:")
            for step, count in sorted(fails.items(), key=lambda x: -x[1]):
                lines.append(f"  {step}: {count}")
        return "\n".join(lines)
