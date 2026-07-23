from __future__ import annotations

import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from stressbot.config import ProfileConfig
from stressbot.metrics import Metrics
from stressbot.profiles.base import run_journey


class StopController:
    def __init__(self) -> None:
        self._event = threading.Event()

    def request_stop(self, *_args: object) -> None:
        self._event.set()

    def is_stopped(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._event.wait(timeout)


def _worker_loop(
    profile: ProfileConfig,
    metrics: Metrics,
    stop: StopController,
) -> None:
    while not stop.is_stopped():
        result = run_journey(profile, metrics)
        if not result.ok and result.step == "capacity":
            metrics.record_capacity_block()
            lo, hi = profile.capacity_sleep_s
            time.sleep(__import__("random").uniform(lo, hi))
        elif not result.ok:
            time.sleep(0.2)


def run_continuous_pool(
    profile: ProfileConfig,
    workers: int,
    *,
    stats_interval_s: float = 5.0,
    ramp: tuple[int, float] | None = None,
) -> Metrics:
    """
    Run until SIGINT/SIGTERM.

    ramp: optional (workers_per_tick, tick_interval_s) to grow pool gradually.
    """
    metrics = Metrics()
    stop = StopController()
    signal.signal(signal.SIGINT, stop.request_stop)
    signal.signal(signal.SIGTERM, stop.request_stop)

    target_workers = workers
    active_workers = 0
    executor: ThreadPoolExecutor | None = None
    futures: list = []

    def spawn_workers(count: int) -> None:
        nonlocal active_workers, executor, futures
        if executor is None:
            executor = ThreadPoolExecutor(max_workers=target_workers, thread_name_prefix="stress")
        for _ in range(count):
            if active_workers >= target_workers:
                break
            futures.append(executor.submit(_worker_loop, profile, metrics, stop))
            active_workers += 1

    print(
        f"Starting stress test: profile={profile.name} url={profile.base_url} "
        f"workers={target_workers}"
    )

    if ramp:
        per_tick, tick_s = ramp
        while not stop.is_stopped() and active_workers < target_workers:
            spawn_workers(per_tick)
            print(f"Ramped to {active_workers}/{target_workers} workers")
            stop.wait(tick_s)
    else:
        spawn_workers(target_workers)

    try:
        while not stop.is_stopped():
            print(metrics.format_live(), flush=True)
            stop.wait(stats_interval_s)
    finally:
        stop.request_stop()
        if executor:
            executor.shutdown(wait=False, cancel_futures=True)
        print(metrics.format_summary())

    return metrics
