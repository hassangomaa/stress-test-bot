from __future__ import annotations

from stressbot.config import ProfileConfig
from stressbot.runners.interval_scheduler import IntervalSchedule, plan_visit_offsets


def _profile_with_schedule() -> ProfileConfig:
    return ProfileConfig.from_dict(
        {
            "name": "zaedl-vps",
            "brand": "zaedl",
            "schedule": {
                "mode": "interval",
                "window_minutes": 60,
                "visits_per_window": [10, 20],
                "loop": True,
            },
        },
        "https://zaedl.example.test",
    )


def test_interval_schedule_from_profile() -> None:
    schedule = IntervalSchedule.from_profile(_profile_with_schedule())
    assert schedule is not None
    assert schedule.window_minutes == 60
    assert schedule.visits_min == 10
    assert schedule.visits_max == 20
    assert schedule.loop is True


def test_plan_visit_offsets_count_and_range() -> None:
    offsets = plan_visit_offsets(15, 3600.0)
    assert len(offsets) == 15
    assert offsets == sorted(offsets)
    assert all(0 <= o <= 3600 for o in offsets)


def test_plan_visit_offsets_empty() -> None:
    assert plan_visit_offsets(0, 3600.0) == []
