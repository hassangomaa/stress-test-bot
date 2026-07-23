from __future__ import annotations

import argparse
import sys

from stressbot.config import list_profiles, load_profile
from stressbot.profiles.base import run_journey
from stressbot.runners.continuous_pool import run_continuous_pool
from stressbot.runners.interval_scheduler import IntervalSchedule, run_interval_schedule


def _parse_ramp(value: str | None) -> tuple[int, float] | None:
    if not value:
        return None
    parts = value.split(":")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("Ramp format: WORKERS:SECONDS e.g. 50:10")
    return int(parts[0]), float(parts[1].rstrip("s"))


def cmd_list_profiles(_args: argparse.Namespace) -> int:
    for name in list_profiles():
        print(name)
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile, args.url_key)
    if args.workers:
        profile.workers = args.workers
    print(f"Dry run: {profile.name} → {profile.base_url}")
    result = run_journey(profile)
    if result.ok:
        print(f"OK — order_uuid={result.order_uuid} duration={result.duration_s:.2f}s")
        return 0
    print(f"FAIL at {result.step}: {result.error} ({result.duration_s:.2f}s)")
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile, args.url_key)
    workers = args.workers or profile.workers
    profile.workers = workers

    schedule = IntervalSchedule.from_profile(profile)
    if schedule is not None:
        run_interval_schedule(profile, schedule, stats_interval_s=args.stats_interval)
        return 0

    ramp = _parse_ramp(args.ramp)
    run_continuous_pool(
        profile,
        workers,
        stats_interval_s=args.stats_interval,
        ramp=ramp,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stressbot",
        description="CLI stress tester for fin-core storefront journeys",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list-profiles", help="List available JSON profiles")
    list_p.set_defaults(func=cmd_list_profiles)

    dry = sub.add_parser("dry-run", help="Run a single journey (smoke test)")
    dry.add_argument("--profile", default="zaedl")
    dry.add_argument("--url-key", default=None, choices=["prod", "local"])
    dry.add_argument("--workers", type=int, default=None)
    dry.set_defaults(func=cmd_dry_run)

    run = sub.add_parser("run", help="Run stress test until Ctrl+C (continuous or interval per profile)")
    run.add_argument("--profile", default="zaedl")
    run.add_argument("--url-key", default=None, choices=["prod", "local"])
    run.add_argument("--workers", type=int, default=None, help="Worker count (default from profile)")
    run.add_argument(
        "--ramp",
        default=None,
        help="Gradual ramp e.g. 50:10s adds 50 workers every 10 seconds",
    )
    run.add_argument("--stats-interval", type=float, default=5.0)
    run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
