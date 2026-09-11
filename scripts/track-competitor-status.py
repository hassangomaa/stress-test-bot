#!/usr/bin/env python3
"""Parse competitor stress-test logs and print per-domain step status."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REACT_STEPS = [
    "browse",
    "marquee",
    "catalog",
    "auth_skipped",
    "checkout/manual-gate",
    "checkout/request-activation-code",
    "checkout/verify-activation-code",
    "checkout/approval",
    "checkout/submit-code",
    "journey_complete",
]

PHP_STEPS = [
    "browse",
    "auth_get",
    "auth_post",
    "payment_method_get",
    "coupon_post",
    "payment_method_post",
    "journey_complete",
]

DOMAINS = {
    "goldalreem": "react",
    "akdalreem": "react",
    "hussingold": "react",
    "sadadgold": "react",
    "goldsadad": "react",
    "hussinsadad": "react",
    "oqdalreem": "react",
    "sadadcash": "react",
    "agdalreem": "php",
}


def parse_log(path: Path) -> dict[str, str]:
    steps_template = REACT_STEPS if "agdalreem" not in path.name else PHP_STEPS
    status = {s: "pending" for s in steps_template}

    if not path.exists():
        return status

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue

        event = ev.get("event")
        if event == "journey_start":
            for k in status:
                status[k] = "pending"
        elif event == "step":
            step = ev.get("step", "")
            if step in status:
                status[step] = "done" if ev.get("ok") else "blocked"
        elif event == "auth_skipped":
            status["auth_skipped"] = "done"
        elif event == "auth_attempted":
            if "auth_post" in status:
                status["auth_post"] = "done"
        elif event == "coupon_attempted":
            if "coupon_post" in status:
                status["coupon_post"] = "done"
        elif event == "gate_skipped":
            if "auth_skipped" in status:
                pass  # gate is separate
        elif event == "step_blocked":
            step = ev.get("step", "")
            if step in status:
                status[step] = "blocked"
        elif event == "step_force_done":
            step = ev.get("step", "")
            if step in status:
                status[step] = "done"
        elif event == "journey_end":
            if ev.get("ok"):
                status["journey_complete"] = "done"
            else:
                status["journey_complete"] = "blocked"

    return status


def render_table(log_dir: Path) -> str:
    lines = [
        f"Competitor stress status @ {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Log dir: {log_dir}",
        "",
    ]

    for slug, kind in DOMAINS.items():
        path = log_dir / f"comp-{slug}.log"
        status = parse_log(path)
        steps = REACT_STEPS if kind == "react" else PHP_STEPS
        done = sum(1 for s in steps if status.get(s) == "done")
        blocked = [s for s in steps if status.get(s) == "blocked"]
        pending = [s for s in steps if status.get(s) == "pending"]

        if status.get("journey_complete") != "done":
            overall = "PARTIAL" if done > 0 else "NO_ACTIVITY"
        elif status.get("payment_method_post") == "done":
            overall = "FULL_CHECKOUT"
        elif status.get("checkout/approval") == "done":
            overall = (
                "FULL_CHECKOUT_PENDING_ADMIN"
                if status.get("checkout/submit-code") == "blocked"
                else "FULL_CHECKOUT"
            )
        elif done > 0:
            overall = "PARTIAL"
        else:
            overall = "NO_ACTIVITY"

        lines.append(f"## {slug}.com [{overall}] ({done}/{len(steps)} steps done)")
        for step in steps:
            st = status.get(step, "pending")
            icon = {"pending": "⏳", "done": "✅", "blocked": "🚫"}.get(st, "?")
            lines.append(f"  {icon} {step}: {st}")
        if blocked:
            lines.append(f"  blocked: {', '.join(blocked)}")
        if pending and status.get("journey_complete") != "done":
            lines.append(f"  pending: {', '.join(pending[:5])}{'...' if len(pending)>5 else ''}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    log_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "/var/log/stress-test-bot")
    print(render_table(log_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
