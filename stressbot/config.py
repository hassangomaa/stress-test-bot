from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = ROOT / "configs"
PROFILES_DIR = CONFIGS_DIR / "profiles"
URLS_FILE = CONFIGS_DIR / "urls.json"


@dataclass
class ProfileConfig:
    name: str
    brand: str
    base_url: str
    url_key: str
    workers: int
    think_delay_ms: tuple[int, int]
    heartbeat: dict[str, Any]
    visitor_cookie: str
    steps: dict[str, bool]
    payment_methods: list[str]
    installment_counts: dict[str, list[int]]
    catalog_source: str
    timeout_s: float
    retry: dict[str, Any]
    on_capacity_blocked: str
    capacity_sleep_s: tuple[float, float]
    user_agent: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any], base_url: str) -> ProfileConfig:
        think = data.get("think_delay_ms", [50, 400])
        cap_sleep = data.get("capacity_sleep_s", [10, 30])
        return cls(
            name=data["name"],
            brand=data["brand"],
            base_url=base_url.rstrip("/"),
            url_key=data.get("url_key", "prod"),
            workers=int(data.get("workers", 200)),
            think_delay_ms=(int(think[0]), int(think[1])),
            heartbeat=data.get("heartbeat", {}),
            visitor_cookie=data.get("visitor_cookie", "zaedl_vid"),
            steps=data.get("steps", {}),
            payment_methods=list(data.get("payment_methods", [])),
            installment_counts=dict(data.get("installment_counts", {})),
            catalog_source=data.get("catalog_source", "api"),
            timeout_s=float(data.get("timeout_s", 30)),
            retry=data.get("retry", {"max": 3, "backoff_ms": [500, 2000]}),
            on_capacity_blocked=data.get("on_capacity_blocked", "sleep_and_retry"),
            capacity_sleep_s=(float(cap_sleep[0]), float(cap_sleep[1])),
            user_agent=data.get(
                "user_agent",
                "Mozilla/5.0 (compatible; StressTestBot/0.1)",
            ),
            raw=data,
        )


def load_urls() -> dict[str, dict[str, str]]:
    with URLS_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def list_profiles() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def load_profile(name: str, url_key: str | None = None) -> ProfileConfig:
    profile_path = PROFILES_DIR / f"{name}.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {name}")

    with profile_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    urls = load_urls()
    brand = data.get("brand", name)
    if brand not in urls:
        raise KeyError(f"No URLs configured for brand '{brand}'")

    key = url_key or data.get("url_key", "prod")
    if key not in urls[brand]:
        raise KeyError(f"URL key '{key}' not found for brand '{brand}'")

    return ProfileConfig.from_dict(data, urls[brand][key])
