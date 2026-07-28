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


def _profile_with_exponential_schedule() -> ProfileConfig:
    return ProfileConfig.from_dict(
        {
            "name": "zaedl-ramp-10m",
            "brand": "zaedl",
            "schedule": {
                "mode": "interval",
                "window_minutes": 10,
                "ramp": "exponential",
                "visits_start": 1,
                "visits_multiplier": 2,
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
    assert schedule.ramp == "fixed"


def test_exponential_schedule_from_profile() -> None:
    schedule = IntervalSchedule.from_profile(_profile_with_exponential_schedule())
    assert schedule is not None
    assert schedule.window_minutes == 10
    assert schedule.ramp == "exponential"
    assert schedule.visits_start == 1
    assert schedule.visits_multiplier == 2
    assert schedule.visits_for_window(1) == 1
    assert schedule.visits_for_window(2) == 2
    assert schedule.visits_for_window(3) == 4
    assert schedule.visits_for_window(4) == 8
    assert schedule.visits_for_window(5) == 16


def test_exponential_schedule_respects_cap() -> None:
    schedule = IntervalSchedule(
        window_minutes=10,
        visits_min=1,
        visits_max=1,
        ramp="exponential",
        visits_start=1,
        visits_multiplier=2,
        visits_cap=8,
    )
    assert schedule.visits_for_window(4) == 8
    assert schedule.visits_for_window(5) == 8
    assert schedule.visits_for_window(10) == 8


def test_plan_visit_offsets_count_and_range() -> None:
    offsets = plan_visit_offsets(15, 3600.0)
    assert len(offsets) == 15
    assert offsets == sorted(offsets)
    assert all(0 <= o <= 3600 for o in offsets)


def test_plan_visit_offsets_empty() -> None:
    assert plan_visit_offsets(0, 3600.0) == []
