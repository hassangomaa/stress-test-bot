#!/usr/bin/env python3
"""TtaKkaa fleet worker node — Gemini health ping → TtaKkaa ops Telegram."""

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
from pathlib import Path

CTX = ssl.create_default_context()
NODE_ID = os.environ.get("STRESSBOT_NODE_ID", "ttakka")
LOG_BASE = Path(os.environ.get("STRESSBOT_LOG_BASE", "/var/log/stress-test-bot"))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def gemini_ping(api_key: str) -> tuple[bool, str]:
    if not api_key:
        return False, "missing_api_key"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}"
        f":generateContent?key={urllib.parse.quote(api_key)}"
    )
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": "Reply with exactly: TtaKkaa Gemini OK"}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 32},
        }
    ).encode()
    try:
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30, context=CTX) as resp:
            data = json.loads(resp.read().decode())
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
        return True, text[:120] or "empty_reply"
    except Exception as exc:
        return False, str(exc)[:120]


def local_visit_total(hours: float) -> int:
    script = Path("/opt/stress-test-bot/scripts/count-fleet-visits.py")
    if not script.exists():
        return 0
    try:
        proc = subprocess.run(
            ["python3", str(script), "--node", NODE_ID, "--hours", str(hours)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            return -1
        counts = json.loads(proc.stdout.strip().splitlines()[-1])
        return sum(int(v) for v in counts.values())
    except Exception:
        return -1


def egress_ip() -> str:
    try:
        with urllib.request.urlopen(
            "https://api.ipify.org", timeout=12, context=CTX
        ) as resp:
            return resp.read().decode().strip()
    except Exception:
        return "unknown"


def build_message(gemini_ok: bool, gemini_detail: str, visits: int, hours: float) -> str:
    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    status = "نعم" if gemini_ok else "لا"
    lines = [
        f"Gemini جاهز: {status}",
        "📡 تقرير عقدة TtaKkaa — stress-test-bot",
        f"🕐 {ts} (Asia/Riyadh)",
        f"🖥 العقدة: {NODE_ID}",
        f"🌐 IP الخارج: {egress_ip()}",
        f"🤖 زيارات المنافسين (آخر {int(hours)} ساعة): {visits if visits >= 0 else '؟'}",
        f"🧠 Gemini: {gemini_detail}",
    ]
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing", file=sys.stderr)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    ).encode()
    try:
        req = urllib.request.Request(url, data=body, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return bool(data.get("ok"))
    except Exception as exc:
        print(f"Telegram failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=12.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    ok, detail = gemini_ping(api_key)
    visits = local_visit_total(args.hours)
    message = build_message(ok, detail, visits, args.hours)
    print(message)

    if args.dry_run or args.no_telegram:
        return 0
    return 0 if send_telegram(message) else 1


if __name__ == "__main__":
    raise SystemExit(main())
