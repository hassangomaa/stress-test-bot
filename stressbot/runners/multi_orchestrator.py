from __future__ import annotations

import signal
import threading
import time
from typing import Any

from stressbot.config import load_manifest, load_profile
from stressbot.event_log import EventLogger
from stressbot.runners.continuous_pool import StopController
from stressbot.runners.interval_scheduler import IntervalSchedule, run_interval_schedule


def run_multi_orchestrator(
    manifest_name: str,
    *,
    url_key: str | None = None,
    stats_interval_s: float = 30.0,
) -> None:
    """Run interval schedules for multiple profiles in parallel threads."""
    manifest = load_manifest(manifest_name)
    profile_names: list[str] = list(manifest.get("profiles", []))
    if not profile_names:
        raise ValueError(f"Manifest {manifest_name} has no profiles")

    orch_log = EventLogger.orchestrator()
    stop = StopController()
    signal.signal(signal.SIGINT, stop.request_stop)
    signal.signal(signal.SIGTERM, stop.request_stop)

    orch_log.emit(
        "orchestrator_start",
        manifest=manifest_name,
        profile_count=len(profile_names),
        profiles=profile_names,
    )

    threads: list[threading.Thread] = []
    errors: dict[str, str] = {}

    def _worker(profile_name: str) -> None:
        try:
            profile = load_profile(profile_name, url_key)
            schedule = IntervalSchedule.from_profile(profile)
            if schedule is None:
                raise ValueError(f"Profile {profile_name} has no interval schedule")
            run_interval_schedule(profile, schedule, stats_interval_s=stats_interval_s)
        except Exception as exc:
            errors[profile_name] = str(exc)
            EventLogger.for_profile(profile_name, "").thread_crash(profile_name, str(exc))

    for name in profile_names:
        thread = threading.Thread(target=_worker, name=f"stress-{name}", daemon=True)
        thread.start()
        threads.append(thread)
        orch_log.emit("thread_started", thread=name)

    try:
        while not stop.is_stopped():
            alive = [t for t in threads if t.is_alive()]
            if not alive:
                break
            stop.wait(5.0)
    finally:
        stop.request_stop()
        reason = "signal" if stop.is_stopped() else "all_threads_finished"
        if errors:
            orch_log.emit("orchestrator_errors", errors=errors)
        orch_log.orchestrator_stop(reason)

        for thread in threads:
            thread.join(timeout=10.0)
            if thread.is_alive():
                orch_log.emit("thread_timeout", thread=thread.name)
