from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from stressbot.config import ProfileConfig
from stressbot.http_session import StorefrontSession
from stressbot.metrics import JourneyResult, Metrics


@dataclass
class CatalogService:
    id: int
    slug: str
    name: str | None = None


class ProfileRunner(Protocol):
    def run_once(self, session: StorefrontSession) -> JourneyResult: ...


def build_runner(profile: ProfileConfig) -> ProfileRunner:
    runner = profile.raw.get("runner")
    if runner == "react_clone":
        from stressbot.profiles.react_clone import ReactCloneProfile

        return ReactCloneProfile(profile)
    if runner == "php_clone":
        from stressbot.profiles.php_clone import PhpCloneProfile

        return PhpCloneProfile(profile)
    if profile.brand == "zaedl" or profile.name == "zaedl":
        from stressbot.profiles.zaedl import ZaedlProfile

        return ZaedlProfile(profile)
    from stressbot.profiles.altmiz import AltmizProfile

    return AltmizProfile(profile)


def run_journey(
    profile: ProfileConfig,
    metrics: Metrics | None = None,
) -> JourneyResult:
    runner = build_runner(profile)
    import time

    started = time.monotonic()
    with StorefrontSession(profile) as session:
        try:
            result = runner.run_once(session)
            result.duration_s = time.monotonic() - started
            if metrics:
                metrics.record_journey(result)
            return result
        except Exception as exc:
            result = JourneyResult(
                ok=False,
                step="exception",
                duration_s=time.monotonic() - started,
                error=str(exc),
            )
            if metrics:
                metrics.record_journey(result)
            return result
