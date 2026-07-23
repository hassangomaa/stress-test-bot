from __future__ import annotations

import random
import re
import time
import uuid
from typing import Any
from urllib.parse import unquote, urljoin

import httpx

from stressbot.config import ProfileConfig


CAPACITY_MARKERS = (
    "capacity_blocked",
    "موارد الخادم",
    "capacity",
    "ممتلئة",
)

CSRF_META_RE = re.compile(
    r'<meta\s+name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
CSRF_INPUT_RE = re.compile(
    r'<input[^>]+name=["\']_token["\'][^>]+value=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
VISITOR_META_RE = re.compile(
    r'<meta\s+name=["\']visitor-token["\']\s+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
ORDER_UUID_RE = re.compile(r"/order/([0-9a-f-]{36})")


class CapacityBlockedError(Exception):
    """Raised when storefront capacity gate blocks the request."""


class StorefrontSession:
    """httpx client with CSRF + cookie jar for Laravel storefront."""

    def __init__(self, profile: ProfileConfig) -> None:
        self.profile = profile
        self.base_url = profile.base_url
        self._csrf_token: str | None = None
        self.visitor_token: str | None = None
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=profile.timeout_s,
            follow_redirects=True,
            headers={
                "User-Agent": profile.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/json",
                "Accept-Language": "ar,en;q=0.9",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> StorefrontSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def think(self) -> None:
        lo, hi = self.profile.think_delay_ms
        if hi > 0:
            time.sleep(random.uniform(lo, hi) / 1000.0)

    @staticmethod
    def extract_csrf(html: str) -> str | None:
        m = CSRF_META_RE.search(html)
        if m:
            return m.group(1)
        m = CSRF_INPUT_RE.search(html)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def extract_visitor_token(html: str) -> str | None:
        m = VISITOR_META_RE.search(html)
        return m.group(1) if m else None

    def _xsrf_header(self) -> dict[str, str]:
        token = self._csrf_token
        if not token:
            xsrf = self._client.cookies.get("XSRF-TOKEN")
            if xsrf:
                token = unquote(xsrf)
        if token:
            return {"X-CSRF-TOKEN": token, "X-XSRF-TOKEN": token}
        return {}

    def _is_capacity_blocked(self, response: httpx.Response) -> bool:
        if response.status_code == 503:
            return True
        text = response.text[:8000] if response.text else ""
        return any(marker in text for marker in CAPACITY_MARKERS)

    def _handle_response(self, response: httpx.Response, step: str) -> httpx.Response:
        if self._is_capacity_blocked(response):
            raise CapacityBlockedError(f"Capacity blocked at step {step}")
        if response.headers.get("content-type", "").startswith("text/html"):
            token = self.extract_csrf(response.text)
            if token:
                self._csrf_token = token
            vtoken = self.extract_visitor_token(response.text)
            if vtoken:
                self.visitor_token = vtoken
        cookie = self._client.cookies.get(self.profile.visitor_cookie)
        if cookie and not self.visitor_token:
            self.visitor_token = cookie
        return response

    def get(self, path: str, *, step: str = "get", **kwargs: Any) -> httpx.Response:
        response = self._client.get(path, **kwargs)
        return self._handle_response(response, step)

    def post_form(
        self,
        path: str,
        data: dict[str, Any],
        *,
        step: str = "post",
        referer: str | None = None,
    ) -> httpx.Response:
        payload = dict(data)
        if self._csrf_token:
            payload.setdefault("_token", self._csrf_token)
        headers = self._xsrf_header()
        if referer:
            headers["Referer"] = urljoin(self.base_url + "/", referer.lstrip("/"))
        response = self._client.post(path, data=payload, headers=headers)
        return self._handle_response(response, step)

    def post_json(self, path: str, data: dict[str, Any], *, step: str = "post_json") -> httpx.Response:
        headers = {
            **self._xsrf_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = self._client.post(path, json=data, headers=headers)
        return self._handle_response(response, step)

    def ensure_visitor_token(self) -> str:
        if not self.visitor_token:
            self.visitor_token = str(uuid.uuid4())
        return self.visitor_token

    def send_heartbeat(self, path: str = "/") -> None:
        if not self.profile.heartbeat.get("enabled"):
            return
        token = self.ensure_visitor_token()
        self.post_json(
            "/visitor/heartbeat",
            {
                "visitor_token": token,
                "path": path,
                "duration_delta": random.randint(5, 30),
            },
            step="heartbeat",
        )

    @staticmethod
    def order_uuid_from_response(response: httpx.Response) -> str | None:
        for candidate in (str(response.url), response.headers.get("location", "")):
            m = ORDER_UUID_RE.search(candidate)
            if m:
                return m.group(1)
        m = ORDER_UUID_RE.search(response.text or "")
        return m.group(1) if m else None

    def with_retries(self, fn, step: str):
        max_retries = int(self.profile.retry.get("max", 3))
        backoffs = self.profile.retry.get("backoff_ms", [500, 2000])
        cap_lo, cap_hi = self.profile.capacity_sleep_s

        for attempt in range(max_retries + 1):
            try:
                return fn()
            except CapacityBlockedError:
                if attempt >= max_retries:
                    raise
                sleep_s = random.uniform(cap_lo, cap_hi)
                time.sleep(sleep_s)
            except httpx.HTTPError:
                if attempt >= max_retries:
                    raise
                idx = min(attempt, len(backoffs) - 1)
                time.sleep(backoffs[idx] / 1000.0)
        raise RuntimeError(f"Retry exhausted for {step}")
