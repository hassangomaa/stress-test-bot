#!/usr/bin/env python3
"""Parse competitor stress-test logs — per-node fleet matrix."""

from __future__ import annotations

import argparse
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

DEFAULT_NODES = ["fin-core", "slt-ocr", "ttakka"]


def parse_log(path: Path) -> dict[str, str]:
    steps_template = REACT_STEPS if "agdalreem" not in path.name else PHP_STEPS
    status = {s: "pending" for s in steps_template}
    meta = {"node_id": "", "egress_ip": "", "journeys_ok": 0, "journeys_fail": 0}

    if not path.exists():
        return {**status, **meta}

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue

        if ev.get("node_id"):
            meta["node_id"] = ev["node_id"]
        if ev.get("egress_ip"):
            meta["egress_ip"] = ev["egress_ip"]

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
                meta["journeys_ok"] += 1
            else:
                status["journey_complete"] = "blocked"
                meta["journeys_fail"] += 1
        elif event == "thread_crash":
            status["journey_complete"] = "blocked"

    return {**status, **meta}


def overall_label(status: dict[str, str], steps: list[str]) -> str:
    done = sum(1 for s in steps if status.get(s) == "done")
    if status.get("journey_complete") != "done":
        return "PARTIAL" if done > 0 else "NO_ACTIVITY"
    if status.get("payment_method_post") == "done":
        return "FULL_CHECKOUT"
    if status.get("checkout/approval") == "done":
        if status.get("checkout/submit-code") == "blocked":
            return "FULL_CHECKOUT_PENDING_ADMIN"
        return "FULL_CHECKOUT"
    return "PARTIAL" if done > 0 else "NO_ACTIVITY"


def render_node(log_dir: Path, node_id: str) -> list[str]:
    lines = [f"### Node `{node_id}` — {log_dir}", ""]
    egress = ""
    for slug in DOMAINS:
        path = log_dir / f"comp-{slug}.log"
        status = parse_log(path)
        if status.get("egress_ip"):
            egress = status["egress_ip"]
    lines.append(f"Egress IP: {egress or 'unknown'}")
    lines.append("")

    for slug, kind in DOMAINS.items():
        path = log_dir / f"comp-{slug}.log"
        status = parse_log(path)
        steps = REACT_STEPS if kind == "react" else PHP_STEPS
        overall = overall_label(status, steps)
        done = sum(1 for s in steps if status.get(s) == "done")
        blocked = [s for s in steps if status.get(s) == "blocked"]
        lines.append(f"  {slug}.com [{overall}] ({done}/{len(steps)}) ok={status.get('journeys_ok',0)} fail={status.get('journeys_fail',0)}")
        if blocked:
            lines.append(f"    blocked: {', '.join(blocked[:4])}")
    lines.append("")
    return lines


def discover_nodes(base: Path) -> list[str]:
    if not base.exists():
        return []
    nodes = [p.name for p in base.iterdir() if p.is_dir() and (p / "orchestrator.log").exists()]
    legacy = base / "orchestrator.log"
    if legacy.exists() and not nodes:
        return ["legacy"]
    return sorted(nodes)


def render_table(log_dir: Path, nodes: list[str] | None = None) -> str:
    base = log_dir
    node_ids = nodes or discover_nodes(base)
    if not node_ids:
        node_ids = ["."]
        dirs = {".": base}
    else:
        dirs = {n: (base / n if n != "legacy" else base) for n in node_ids}

    lines = [
        f"Competitor fleet status @ {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Base log dir: {base}",
        "",
    ]
    for node_id, ndir in dirs.items():
        label = node_id if node_id != "." else "default"
        lines.extend(render_node(ndir, label))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log_dir", nargs="?", default="/var/log/stress-test-bot")
    parser.add_argument("--node", action="append", dest="nodes", help="Limit to node id(s)")
    parser.add_argument("--all-nodes", action="store_true", help="Scan all node subdirs")
    args = parser.parse_args()

    base = Path(args.log_dir)
    nodes = args.nodes
    if args.all_nodes:
        nodes = discover_nodes(base) or DEFAULT_NODES
        existing = [n for n in nodes if (base / n).is_dir()]
        nodes = existing or nodes

    print(render_table(base, nodes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
