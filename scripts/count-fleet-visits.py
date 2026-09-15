#!/usr/bin/env python3
"""Count journey_start events per competitor slug in a node log dir."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SLUGS = [
    "goldalreem",
    "akdalreem",
    "hussingold",
    "hussinsadad",
    "goldsadad",
    "sadadgold",
    "oqdalreem",
    "sadadcash",
    "agdalreem",
]


def count_visits(log_dir: Path, since_ts: float) -> dict[str, int]:
    out: dict[str, int] = {}
    for slug in SLUGS:
        path = log_dir / f"comp-{slug}.log"
        total = 0
        if not path.exists():
            out[slug] = 0
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("event") != "journey_start":
                continue
            if float(ev.get("ts_unix", 0)) >= since_ts:
                total += 1
        out[slug] = total
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", required=True)
    parser.add_argument("--hours", type=float, default=6.0)
    parser.add_argument("--log-base", default="/var/log/stress-test-bot")
    args = parser.parse_args()
    log_dir = Path(args.log_base) / args.node
    since_ts = time.time() - args.hours * 3600
    print(json.dumps(count_visits(log_dir, since_ts), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
