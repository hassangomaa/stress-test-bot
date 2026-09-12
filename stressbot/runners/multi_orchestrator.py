from __future__ import annotations

import signal
import threading
import time
from typing import Any

from stressbot.config import ProfileConfig, load_manifest, load_profile
from stressbot.event_log import EventLogger
from stressbot.node_context import init_node_context
from stressbot.runners.continuous_pool import StopController
from stressbot.runners.interval_scheduler import IntervalSchedule, run_interval_schedule


def _apply_manifest_schedule(profile: ProfileConfig, manifest: dict[str, Any]) -> None:
    schedule = manifest.get("schedule")
    if schedule and isinstance(schedule, dict):
        merged = dict(profile.raw.get("schedule", {}))
        merged.update(schedule)
        profile.raw["schedule"] = merged


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

    node = init_node_context()
    orch_log = EventLogger.orchestrator()
    orch_log.emit(
        "fleet_node_ready",
        node_id=node.node_id,
        egress_ip=node.egress_ip,
        proxy_url=node.proxy_url,
    )
    stop = StopController()
    signal.signal(signal.SIGINT, stop.request_stop)
    signal.signal(signal.SIGTERM, stop.request_stop)

    orch_log.emit(
        "orchestrator_start",
        manifest=manifest_name,
        profile_count=len(profile_names),
        profiles=profile_names,
        node_id=node.node_id,
        egress_ip=node.egress_ip,
    )

    threads: list[threading.Thread] = []
    errors: dict[str, str] = {}

    def _worker(profile_name: str) -> None:
        try:
            profile = load_profile(profile_name, url_key)
            _apply_manifest_schedule(profile, manifest)
            schedule = IntervalSchedule.from_profile(profile)
            if schedule is None:
                raise ValueError(f"Profile {profile_name} has no interval schedule")
            run_interval_schedule(
                profile,
                schedule,
                stats_interval_s=stats_interval_s,
                stop=stop,
            )
        except Exception as exc:
            errors[profile_name] = str(exc)
            EventLogger.for_profile(profile_name, "").thread_crash(profile_name, str(exc))

    for name in profile_names:
        thread = threading.Thread(target=_worker, args=(name,), name=f"stress-{name}", daemon=False)
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
