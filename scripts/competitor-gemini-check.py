#!/usr/bin/env python3
"""2x-daily competitor discovery (Gemini) + fallback probes → DB + Telegram."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "competitor_report_telegram",
    _SCRIPT_DIR / "competitor-report-telegram.py",
)
_cr = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["competitor_report_telegram"] = _cr
_spec.loader.exec_module(_cr)

ACTIVE_NODES = _cr.ACTIVE_NODES
CONFIRMED = _cr.CONFIRMED
SLUGS = _cr.SLUGS
HealthRow = _cr.HealthRow
load_node_ssh = _cr.load_node_ssh
probe_health = _cr.probe_health
remote_aggregate = _cr.remote_aggregate
send_telegram = _cr.send_telegram
count_visits = _cr.count_visits

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

OUR = re.compile(r"altmiz-store|zaedl")
EXCLUDE = {
    "golden-logic.com.sa",
    "reemgold.com",
    "alreemgold.com",
    "alreemjewelry.com",
    "investigate-islam.com",
    "shatharat.net",
    "majaz.online",
    "takween-agency.net",
    "server1.mostdeef.com",
    "rihana-hotel.com",
    "mostdeef.com",
    "job-sa.com",
    "ahmedhany.online",
    "al-fayez.net",
    "atbaa-alkahra.com",
    "azbarga.com",
    "futurelinkeg.com",
    "hydra-world-tv.com",
    "qrtab.net",
    "alseha-aljamal.com",
    "mf.com.eg",
    "skynodelabs.com",
    "smartkitcheneg.com",
    "clients.mostdeef.com",
    "dr-mostafa-dessouky-pediatric-surgery.com",
    "dr-mostafa-dessouky-pediatric-surgery.com.atbaa-alkahra.com",
    "arvs.job-sa.com",
    "65-108-65-217.cprapid.com",
    "agdalreem.com.ybabcc.com",
}

FINGERPRINTS = [
    "حسين ابراهيم حسين للسداد",
    "سارة الأحمدي",
    "نورة المطيري",
    "checkoutGateEnabled",
    "44.8",
    "سبيكة ذهب",
    "gove.business",
]

DEFAULT_IPS = ["65.108.65.217", "194.39.149.208"]
WATCH_DOMAINS = ["ogdallreem.store", "reemgold.store"]
def reverse_ip_cache_path() -> Path:
    return Path(os.environ.get(
        "REVERSE_IP_CACHE_PATH",
        "/var/lib/stress-test-bot/reverse-ip-cache.json",
    ))


def fetch(url: str, timeout: int = 12) -> tuple[str, int]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fin-core-gemini-check/1"})
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            return resp.read().decode("utf-8", "replace"), resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read(400).decode("utf-8", "replace") if exc.fp else ""
        return body, exc.code
    except Exception:
        return "", 0


def reverse_ip(ip: str) -> list[str]:
    body, _ = fetch(f"https://api.hackertarget.com/reverseiplookup/?q={ip}", 30)
    hosts: list[str] = []
    for line in body.splitlines():
        h = line.strip().lower().lstrip("www.")
        if not h or "." not in h or h.startswith("mail."):
            continue
        if h in EXCLUDE or h.endswith(".sa") or OUR.search(h):
            continue
        hosts.append(h)
    return sorted(set(hosts))


def has_dns(domain: str) -> bool:
    try:
        socket.getaddrinfo(domain, 443)
        return True
    except OSError:
        return False


def fingerprint_probe(domain: str) -> dict[str, Any] | None:
    if not has_dns(domain):
        return None

    score = 0
    signals: list[str] = []
    stack = "unknown"

    marquee, _ = fetch(f"https://{domain}/api/settings/marquee")
    if marquee and ("whatsapp" in marquee or "storeName" in marquee or '"text"' in marquee):
        try:
            data = json.loads(marquee)
            if isinstance(data, dict):
                score += 2
                signals.append("api-settings-marquee-json")
                stack = "react"
        except json.JSONDecodeError:
            pass

    products, _ = fetch(f"https://{domain}/api/products")
    if products:
        try:
            data = json.loads(products)
            if isinstance(data, list) and data and isinstance(data[0], dict) and "price" in data[0]:
                score += 1
                signals.append("api-products-json")
                stack = "react"
        except json.JSONDecodeError:
            pass

    pm, pm_code = fetch(f"https://{domain}/payment_method.php")
    if pm_code == 200 and pm and re.search(r"tamara|tabby|تمارا|تابي", pm, re.I):
        score += 2
        signals.append("checkout:payment_method.php")
        stack = "php"

    listing, _ = fetch(f"https://{domain}/assets/")
    body = pm + listing
    for js in re.findall(r'href="((?:Index|Layout)-[^"]+\.js)"', listing)[:5]:
        chunk, _ = fetch(f"https://{domain}/assets/{js}")
        body += chunk

    fp_hits = sum(1 for fp in FINGERPRINTS if fp in body)
    if fp_hits:
        score += min(fp_hits, 2)
        signals.append(f"copy-fingerprint:{fp_hits}")

    if re.search(r"reem|gold|sadad|dalreem", domain, re.I):
        score += 1
        signals.append("brand-domain-family")

    if score < 4:
        return None

    return {
        "domain": domain,
        "score": score,
        "signals": signals,
        "stack": stack,
    }


def load_lookup(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def known_domains_from_lookup(data: dict[str, Any]) -> set[str]:
    known: set[str] = set(CONFIRMED)
    for row in data.get("confirmed_competitors", []):
        for url in row.get("urls", []):
            m = re.search(r"https?://([^/]+)", url)
            if m:
                known.add(m.group(1).lower().replace("www.", ""))
        if row.get("id"):
            slug = str(row["id"])
            if "." in slug:
                known.add(slug.lower())
            else:
                known.add(f"{slug}.com")
    return known


def load_known_from_artisan(artisan: str) -> set[str]:
    if not Path(artisan).exists():
        return set()
    try:
        proc = subprocess.run(
            ["php", artisan, "competitors:export-json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return set()
        payload = json.loads(proc.stdout.strip().splitlines()[-1] if proc.stdout else "{}")
        return {c["domain"].lower() for c in payload.get("competitors", [])}
    except Exception:
        return set()


def gemini_candidates(known: set[str], regex_patterns: list[str]) -> tuple[list[str], str]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    if not api_key:
        return [], "no_api_key"

    prompt = (
        "You are an OSINT analyst finding Saudi gold-bar storefront clone domains.\n"
        f"Known confirmed competitors (do NOT repeat): {', '.join(sorted(known))}\n"
        f"Copy fingerprints / regex: {json.dumps(regex_patterns, ensure_ascii=False)}\n"
        "Return ONLY a JSON array of new apex domain strings (e.g. [\"example.com\"]). "
        "Rules: no .sa domains, no subdomains, no our domains (zaedl/altmiz), max 10 candidates.\n"
        "If none found, return []"
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={urllib.parse.quote(api_key)}"
    )
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
        }
    ).encode()

    try:
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45, context=CTX) as resp:
            data = json.loads(resp.read().decode())
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text.strip())
        m = re.search(r"\[[\s\S]*?\]", text)
        if not m:
            return [], "invalid_json"
        candidates = json.loads(m.group(0))
        if not isinstance(candidates, list):
            return [], "invalid_json"
        out = []
        for item in candidates:
            if not isinstance(item, str):
                continue
            d = item.lower().strip().lstrip("www.")
            if d and d not in known and "." in d and not d.endswith(".sa"):
                out.append(d)
        return out, "gemini"
    except Exception as exc:
        return [], f"gemini_error:{exc.__class__.__name__}"


def fallback_reverse_ip_delta() -> list[str]:
    current: set[str] = set()
    for ip in DEFAULT_IPS:
        current.update(reverse_ip(ip))

    cache_path = reverse_ip_cache_path()
    previous: set[str] = set()
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            previous = set(cached.get("hosts", []))
        except json.JSONDecodeError:
            previous = set()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"updated_at": time.time(), "hosts": sorted(current)}, indent=2),
        encoding="utf-8",
    )

    return sorted(current - previous)


def register_domain(artisan: str, hit: dict[str, Any], source: str) -> bool:
    meta = json.dumps({"signals": hit.get("signals", []), "stack": hit.get("stack", "")})
    proc = subprocess.run(
        [
            "php",
            artisan,
            "competitors:register",
            hit["domain"],
            "--status=confirmed",
            f"--stack={hit.get('stack', 'unknown')}",
            f"--score={hit.get('score', 0)}",
            f"--source={source}",
            f"--meta={meta}",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode == 0


def build_first_line(new_domains: list[str]) -> str:
    if new_domains:
        return f"منافسون جدد: نعم — {', '.join(new_domains)}"
    return "منافسون جدد: لا"


def build_message(
    new_domains: list[str],
    mode: str,
    health: list[HealthRow],
    visits: dict[str, dict[str, int]],
    hours: float,
) -> str:
    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    live = sum(1 for h in health if h.label == "يعمل")
    lines = [
        build_first_line(new_domains),
        f"📊 تقرير المنافسين — مرتين يومياً",
        f"🕐 {ts} (Asia/Riyadh)",
        f"🔧 الوضع: {mode}",
        "",
        f"✅ المؤكدون: {len(CONFIRMED)} | يعمل الآن: {live}",
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
            parts.append(f"{node}:{'؟' if v < 0 else v}")
        h = next((x for x in health if x.domain == domain), None)
        status = h.label if h else "؟"
        lines.append(f"• {domain} — {total} ({' '.join(parts)}) [{status}]")
    lines.extend(["", "🌐 الحالة المباشرة:"])
    for h in health:
        icon = "✅" if h.label == "يعمل" else ("🟡" if h.label == "صيانة/API" else "❌")
        lines.append(f"{icon} {h.domain} — {h.label}")
    return "\n".join(lines)


def collect_visits(hours: float, log_base: Path) -> dict[str, dict[str, int]]:
    visits: dict[str, dict[str, int]] = {slug: {} for slug in SLUGS}
    since_ts = time.time() - hours * 3600

    for slug in SLUGS:
        visits[slug]["fin-core"] = count_visits(log_base / "fin-core", slug, since_ts)
    for node, cfg in load_node_ssh().items():
        counts = remote_aggregate(hours, node, cfg["host"], cfg["user"], cfg["auth"], str(log_base))
        for slug in SLUGS:
            visits[slug][node] = counts.get(slug, 0)
    return visits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=12.0)
    parser.add_argument("--log-base", default="/var/log/stress-test-bot")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-telegram", action="store_true")
    parser.add_argument("--force-fallback", action="store_true")
    args = parser.parse_args()

    lookup_path = Path(os.environ.get(
        "COMPETITOR_LOOKUP_PATH",
        "/var/www/zaedl/credentials/competitor-lookup.json",
    ))
    artisan = os.environ.get("ZAEDL_ARTISAN", "/var/www/zaedl/artisan")

    lookup = load_lookup(lookup_path)
    known = known_domains_from_lookup(lookup) | load_known_from_artisan(artisan)
    regex_patterns = lookup.get("copy_fingerprints", {}).get("discovery_regex", FINGERPRINTS)

    new_registered: list[str] = []
    mode = "gemini"

    if args.force_fallback:
        candidates: list[str] = []
        mode = "fallback_forced"
    else:
        candidates, gemini_status = gemini_candidates(known, regex_patterns)
        if gemini_status != "gemini":
            mode = f"fallback ({gemini_status})"
            candidates = []

    if mode.startswith("fallback") or not candidates:
        if not candidates:
            candidates = fallback_reverse_ip_delta()
        for watch in WATCH_DOMAINS:
            if has_dns(watch) and watch not in known:
                candidates.append(watch)

    for domain in candidates:
        if domain in known:
            continue
        hit = fingerprint_probe(domain)
        if not hit:
            continue
        if args.dry_run:
            new_registered.append(domain)
            known.add(domain)
            continue
        if register_domain(artisan, hit, "gemini" if mode == "gemini" else "reverse_ip"):
            new_registered.append(domain)
            known.add(domain)

    health = [probe_health(d) for d in CONFIRMED]
    visits = collect_visits(args.hours, Path(args.log_base))
    message = build_message(new_registered, mode, health, visits, args.hours)
    print(message)

    if args.dry_run or args.no_telegram:
        return 0

    return 0 if send_telegram(message) else 1


if __name__ == "__main__":
    raise SystemExit(main())
