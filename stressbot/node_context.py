from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

import httpx


@dataclass(frozen=True)
class NodeContext:
    node_id: str
    egress_ip: str
    proxy_url: str | None = None


def detect_egress_ip(timeout_s: float = 12.0) -> str:
    for url in ("https://ifconfig.me", "https://api.ipify.org"):
        try:
            response = httpx.get(url, timeout=timeout_s)
            response.raise_for_status()
            ip = response.text.strip()
            if ip:
                return ip
        except httpx.HTTPError:
            continue
    return "unknown"


@lru_cache(maxsize=1)
def get_node_context() -> NodeContext:
    node_id = os.environ.get("STRESSBOT_NODE_ID", "local").strip() or "local"
    egress_ip = os.environ.get("STRESSBOT_EGRESS_IP", "").strip()
    if not egress_ip:
        egress_ip = detect_egress_ip()
    proxy_raw = os.environ.get("STRESSBOT_PROXY_URL", "").strip()
    proxy_url = proxy_raw or None
    return NodeContext(node_id=node_id, egress_ip=egress_ip, proxy_url=proxy_url)


def get_proxy_url() -> str | None:
    return get_node_context().proxy_url


def init_node_context() -> NodeContext:
    """Resolve egress IP once at process start (cached)."""
    get_node_context.cache_clear()
    return get_node_context()
