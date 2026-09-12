from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache

import httpx

_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


@dataclass(frozen=True)
class NodeContext:
    node_id: str
    egress_ip: str
    proxy_url: str | None = None


def _extract_ipv4(text: str) -> str | None:
    text = (text or "").strip()
    if _IPV4_RE.fullmatch(text):
        return text
    match = _IPV4_RE.search(text)
    return match.group(0) if match else None


def detect_egress_ip(timeout_s: float = 12.0) -> str:
    headers = {"User-Agent": "stressbot-egress/1.0", "Accept": "text/plain"}
    endpoints = (
        "https://api.ipify.org",
        "https://ipv4.icanhazip.com",
        "https://ipv4.ifconfig.me/ip",
    )
    for url in endpoints:
        try:
            response = httpx.get(url, timeout=timeout_s, headers=headers)
            response.raise_for_status()
            ip = _extract_ipv4(response.text)
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
    else:
        egress_ip = _extract_ipv4(egress_ip) or egress_ip
    proxy_raw = os.environ.get("STRESSBOT_PROXY_URL", "").strip()
    proxy_url = proxy_raw or None
    return NodeContext(node_id=node_id, egress_ip=egress_ip, proxy_url=proxy_url)


def get_proxy_url() -> str | None:
    return get_node_context().proxy_url


def init_node_context() -> NodeContext:
    """Resolve egress IP once at process start (cached)."""
    get_node_context.cache_clear()
    return get_node_context()
