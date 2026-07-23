from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserProfile:
    user_agent: str
    sec_ch_ua: str | None
    sec_ch_ua_mobile: str
    sec_ch_ua_platform: str
    device_type: str


# Realistic Saudi/mobile-heavy browser fingerprints — no bot/headless/crawl tokens.
BROWSER_PROFILES: tuple[BrowserProfile, ...] = (
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
            "Mobile/15E148 Safari/604.1"
        ),
        sec_ch_ua=None,
        sec_ch_ua_mobile="?1",
        sec_ch_ua_platform='"iOS"',
        device_type="mobile",
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
        ),
        sec_ch_ua='"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        sec_ch_ua_mobile="?1",
        sec_ch_ua_platform='"Android"',
        device_type="mobile",
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        sec_ch_ua='"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        sec_ch_ua_mobile="?0",
        sec_ch_ua_platform='"Windows"',
        device_type="desktop",
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        sec_ch_ua='"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        sec_ch_ua_mobile="?0",
        sec_ch_ua_platform='"macOS"',
        device_type="desktop",
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/124.0.6367.88 "
            "Mobile/15E148 Safari/604.1"
        ),
        sec_ch_ua=None,
        sec_ch_ua_mobile="?1",
        sec_ch_ua_platform='"iOS"',
        device_type="mobile",
    ),
)

BROWSE_PATHS: tuple[str, ...] = (
    "/",
    "/about",
    "/terms",
    "/privacy",
    "/delivery",
)


def pick_browser_profile() -> BrowserProfile:
    return random.choice(BROWSER_PROFILES)


def browser_headers(profile: BrowserProfile, *, referer: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {
        "User-Agent": profile.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if referer else "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    if profile.sec_ch_ua:
        headers["Sec-CH-UA"] = profile.sec_ch_ua
        headers["Sec-CH-UA-Mobile"] = profile.sec_ch_ua_mobile
        headers["Sec-CH-UA-Platform"] = profile.sec_ch_ua_platform
    if referer:
        headers["Referer"] = referer
    return headers
