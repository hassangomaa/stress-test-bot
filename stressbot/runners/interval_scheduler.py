from __future__ import annotations

import random
import signal
import time
from dataclasses import dataclass

from stressbot.config import ProfileConfig
from stressbot.metrics import Metrics
from stressbot.profiles.base import run_journey
from stressbot.runners.continuous_pool import StopController


@dataclass(frozen=True)
class IntervalSchedule:
    window_minutes: int
    visits_min: int
    visits_max: int
    loop: bool = True
    ramp: str = "fixed"  # "fixed" | "exponential"
    visits_start: int = 1
    visits_multiplier: int = 2
    visits_cap: int | None = None

    @classmethod
    def from_profile(cls, profile: ProfileConfig) -> IntervalSchedule | None:
        schedule = profile.raw.get("schedule")
        if not schedule or schedule.get("mode") != "interval":
            return None
        visits = schedule.get("visits_per_window", [10, 20])
        ramp = str(schedule.get("ramp", "fixed")).lower()
        if ramp not in {"fixed", "exponential"}:
            ramp = "fixed"
        visits_cap_raw = schedule.get("visits_cap")
        return cls(
            window_minutes=int(schedule.get("window_minutes", 60)),
            visits_min=int(visits[0]) if isinstance(visits, (list, tuple)) else 1,
            visits_max=int(visits[1] if isinstance(visits, (list, tuple)) and len(visits) > 1 else visits[0])
            if isinstance(visits, (list, tuple))
            else int(visits),
            loop=bool(schedule.get("loop", True)),
            ramp=ramp,
            visits_start=int(schedule.get("visits_start", 1)),
            visits_multiplier=max(2, int(schedule.get("visits_multiplier", 2))),
            visits_cap=int(visits_cap_raw) if visits_cap_raw is not None else None,
        )

    def visits_for_window(self, window_num: int) -> int:
        """1-based window index → visit count for that window."""
        if self.ramp == "exponential":
            # window 1 → start, then * multiplier each subsequent window
            count = self.visits_start * (self.visits_multiplier ** (window_num - 1))
            if self.visits_cap is not None:
                count = min(count, self.visits_cap)
            return max(1, int(count))
        return random.randint(self.visits_min, self.visits_max)


def plan_visit_offsets(count: int, window_s: float) -> list[float]:
    """Spread `count` visit times randomly across [0, window_s]."""
    if count <= 0:
        return []
    return sorted(random.uniform(0, window_s) for _ in range(count))


def run_interval_schedule(
    profile: ProfileConfig,
    schedule: IntervalSchedule,
    *,
    stats_interval_s: float = 30.0,
) -> Metrics:
    """Run N visits per window, spread randomly across the hour. Repeats until stopped."""
    metrics = Metrics()
    stop = StopController()
    signal.signal(signal.SIGINT, stop.request_stop)
    signal.signal(signal.SIGTERM, stop.request_stop)

    window_s = schedule.window_minutes * 60
    window_num = 0

    if schedule.ramp == "exponential":
        print(
            f"Interval mode (exponential): profile={profile.name} url={profile.base_url} "
            f"start={schedule.visits_start} x{schedule.visits_multiplier} "
            f"every {schedule.window_minutes}min"
            + (f" cap={schedule.visits_cap}" if schedule.visits_cap else " (no cap)"),
            flush=True,
        )
    else:
        print(
            f"Interval mode: profile={profile.name} url={profile.base_url} "
            f"visits={schedule.visits_min}-{schedule.visits_max} per {schedule.window_minutes}min",
            flush=True,
        )

    try:
        while not stop.is_stopped():
            window_num += 1
            visit_count = schedule.visits_for_window(window_num)
            offsets = plan_visit_offsets(visit_count, window_s)
            window_start = time.monotonic()

            print(
                f"Window #{window_num}: scheduling {visit_count} visits "
                f"over {schedule.window_minutes} minutes"
                + (f" [ramp={schedule.ramp}]" if schedule.ramp == "exponential" else ""),
                flush=True,
            )

            for idx, offset in enumerate(offsets, start=1):
                if stop.is_stopped():
                    break

                wait_s = (window_start + offset) - time.monotonic()
                if wait_s > 0:
                    stop.wait(wait_s)
                if stop.is_stopped():
                    break

                print(f"  Visit {idx}/{visit_count} (t+{offset:.0f}s)", flush=True)
                result = run_journey(profile, metrics)
                if not result.ok and result.step == "capacity":
                    metrics.record_capacity_block()
                    lo, hi = profile.capacity_sleep_s
                    stop.wait(random.uniform(lo, hi))

            elapsed = time.monotonic() - window_start
            remaining = window_s - elapsed
            if remaining > 0 and not stop.is_stopped():
                print(
                    f"Window #{window_num} done — sleeping {remaining:.0f}s until next window",
                    flush=True,
                )
                stop.wait(remaining)

            print(metrics.format_live(), flush=True)

            if not schedule.loop:
                break

    finally:
        stop.request_stop()
        print(metrics.format_summary())

    return metrics
