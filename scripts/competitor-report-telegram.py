#!/usr/bin/env python3
"""6-hour competitor OSINT health + fleet visit counts → Zaedl Telegram channel."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CONFIRMED = [
    "goldalreem.com",
    "akdalreem.com",
    "hussingold.com",
    "hussinsadad.com",
    "goldsadad.com",
    "sadadgold.com",
    "oqdalreem.com",
    "sadadcash.com",
    "agdalreem.com",
]

SLUGS = [d.replace(".com", "") for d in CONFIRMED]

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

ACTIVE_NODES = ("fin-core", "slt-ocr", "ttakka")


@dataclass
class HealthRow:
    domain: str
    home_code: int
    marquee_ok: bool
    products_code: int

    @property
    def label(self) -> str:
        if self.marquee_ok:
            return "يعمل"
        if self.home_code == 200:
            return "صيانة/API"
        return "غير متاح"


def _fetch_code(url: str, timeout: int = 12) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fin-core-competitor-report/1"})
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            return resp.status, resp.read(400).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(200).decode("utf-8", "replace") if exc.fp else ""
        return exc.code, body
    except Exception:
        return 0, ""


def probe_health(domain: str) -> HealthRow:
    home_code, _ = _fetch_code(f"https://{domain}/")
    _, marquee_body = _fetch_code(f"https://{domain}/api/settings/marquee")
    marquee_ok = False
    body = marquee_body.strip()
    if body.startswith("{") or '"text"' in body or '"storeName"' in body:
        try:
            data = json.loads(body) if body.startswith("{") else {}
            marquee_ok = isinstance(data, dict) and (
                "storeName" in data or "whatsapp" in data or "text" in data
            )
        except json.JSONDecodeError:
            marquee_ok = '"text"' in body or '"storeName"' in body
    products_code, _ = _fetch_code(f"https://{domain}/api/products")
    if domain == "agdalreem.com":
        pm_code, _ = _fetch_code(f"https://{domain}/payment_method.php")
        if pm_code == 200:
            marquee_ok = True
            products_code = 200
    return HealthRow(domain, home_code, marquee_ok, products_code)


def count_visits(log_dir: Path, slug: str, since_ts: float) -> int:
    path = log_dir / f"comp-{slug}.log"
    if not path.exists():
        return 0
    total = 0
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
        ts = float(ev.get("ts_unix", 0))
        if ts >= since_ts:
            total += 1
    return total


def aggregate_visits(hours: float, log_base: Path, nodes: list[str]) -> dict[str, dict[str, int]]:
    since_ts = time.time() - hours * 3600
    out: dict[str, dict[str, int]] = {slug: {} for slug in SLUGS}
    for node in nodes:
        log_dir = log_base / node
        for slug in SLUGS:
            out[slug][node] = count_visits(log_dir, slug, since_ts)
    return out


def remote_aggregate(
    hours: float,
    node: str,
    ssh_host: str,
    ssh_user: str,
    ssh_auth: str,
    log_base: str = "/var/log/stress-test-bot",
) -> dict[str, int]:
    remote_cmd = (
        f"python3 /opt/stress-test-bot/scripts/count-fleet-visits.py "
        f"--node {node} --hours {hours} --log-base {log_base}"
    )
    if ssh_auth == "password":
        password = os.environ.get(f"FLEET_SSH_PASS_{node.upper().replace('-', '_')}", "")
        if not password:
            return {slug: 0 for slug in SLUGS}
        proc = subprocess.run(
            [
                "sshpass",
                "-e",
                "ssh",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                "PreferredAuthentications=password",
                "-o",
                "PubkeyAuthentication=no",
                f"{ssh_user}@{ssh_host}",
                remote_cmd,
            ],
            env={**os.environ, "SSHPASS": password},
            capture_output=True,
            text=True,
            timeout=45,
        )
    else:
        key = ssh_auth
        proc = subprocess.run(
            [
                "ssh",
                "-i",
                key,
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                f"{ssh_user}@{ssh_host}",
                remote_cmd,
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
    if proc.returncode != 0:
        return {slug: -1 for slug in SLUGS}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {slug: -1 for slug in SLUGS}


def load_node_ssh() -> dict[str, dict[str, str]]:
    slt_key = os.environ.get("FLEET_SSH_KEY_SLT_OCR", "/root/.ssh/egyguests_vps")
    slt_auth = slt_key if Path(slt_key).exists() else "password"
    return {
        "slt-ocr": {
            "host": os.environ.get("FLEET_SSH_HOST_SLT_OCR", "69.62.114.63"),
            "user": "root",
            "auth": slt_auth,
        },
        "ttakka": {
            "host": os.environ.get("FLEET_SSH_HOST_TTAKKA", "187.124.9.225"),
            "user": "root",
            "auth": "password",
        },
    }


def build_message(hours: float, visits: dict[str, dict[str, int]], health: list[HealthRow]) -> str:
    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    lines = [
        "📊 تقرير المنافسين — كل 6 ساعات",
        f"🕐 {ts} (Asia/Riyadh)",
        "",
        f"✅ المنافسون المؤكدون: {len(CONFIRMED)}",
        "🆕 منافسون جدد: 0",
        "",
        f"🤖 زيارات البوت (آخر {int(hours)} ساعة):",
    ]
    for slug in SLUGS:
        domain = f"{slug}.com"
        per_node = visits.get(slug, {})
        total = sum(v for v in per_node.values() if v >= 0)
        parts = []
        for node in ACTIVE_NODES:
            v = per_node.get(node, 0)
            if v < 0:
                parts.append(f"{node}:؟")
            else:
                parts.append(f"{node}:{v}")
        h = next((x for x in health if x.domain == domain), None)
        status = h.label if h else "؟"
        lines.append(f"• {domain} — {total} ({' '.join(parts)}) [{status}]")
    lines.extend(["", "🌐 الحالة المباشرة:"])
    for h in health:
        icon = "✅" if h.label == "يعمل" else ("🟡" if h.label == "صيانة/API" else "❌")
        lines.append(f"{icon} {h.domain} — {h.label}")
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing", file=sys.stderr)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode()
    try:
        req = urllib.request.Request(url, data=body, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return bool(data.get("ok"))
    except Exception as exc:
        print(f"Telegram send failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=6.0)
    parser.add_argument("--log-base", default="/var/log/stress-test-bot")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()

    log_base = Path(args.log_base)
    visits: dict[str, dict[str, int]] = {slug: {} for slug in SLUGS}

    # Local fin-core logs
    for slug in SLUGS:
        since_ts = time.time() - args.hours * 3600
        visits[slug]["fin-core"] = count_visits(log_base / "fin-core", slug, since_ts)

    # Remote nodes
    for node, cfg in load_node_ssh().items():
        counts = remote_aggregate(args.hours, node, cfg["host"], cfg["user"], cfg["auth"], str(log_base))
        for slug in SLUGS:
            visits[slug][node] = counts.get(slug, 0)

    health = [probe_health(d) for d in CONFIRMED]
    message = build_message(args.hours, visits, health)
    print(message)

    if args.dry_run or args.no_telegram:
        return 0

    ok = send_telegram(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
