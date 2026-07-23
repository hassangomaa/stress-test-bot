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

    @classmethod
    def from_profile(cls, profile: ProfileConfig) -> IntervalSchedule | None:
        schedule = profile.raw.get("schedule")
        if not schedule or schedule.get("mode") != "interval":
            return None
        visits = schedule.get("visits_per_window", [10, 20])
        return cls(
            window_minutes=int(schedule.get("window_minutes", 60)),
            visits_min=int(visits[0]),
            visits_max=int(visits[1]),
            loop=bool(schedule.get("loop", True)),
        )


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

    print(
        f"Interval mode: profile={profile.name} url={profile.base_url} "
        f"visits={schedule.visits_min}-{schedule.visits_max} per {schedule.window_minutes}min"
    )

    try:
        while not stop.is_stopped():
            window_num += 1
            visit_count = random.randint(schedule.visits_min, schedule.visits_max)
            offsets = plan_visit_offsets(visit_count, window_s)
            window_start = time.monotonic()

            print(
                f"Window #{window_num}: scheduling {visit_count} visits "
                f"over {schedule.window_minutes} minutes",
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
