from __future__ import annotations

import httpx

from stressbot.config import ProfileConfig
from stressbot.http_session import CapacityBlockedError, StorefrontSession


def _minimal_profile() -> ProfileConfig:
    return ProfileConfig.from_dict(
        {
            "name": "test",
            "brand": "zaedl",
            "workers": 1,
            "think_delay_ms": [0, 0],
            "heartbeat": {"enabled": False},
            "visitor_cookie": "zaedl_vid",
            "steps": {},
            "payment_methods": [],
            "installment_counts": {},
            "catalog_source": "api",
            "timeout_s": 5,
            "retry": {"max": 1, "backoff_ms": [100]},
            "on_capacity_blocked": "sleep_and_retry",
            "capacity_sleep_s": [0.01, 0.02],
        },
        "https://example.test",
    )


def test_extract_csrf_meta() -> None:
    html = '<html><meta name="csrf-token" content="meta-token-abc"></html>'
    assert StorefrontSession.extract_csrf(html) == "meta-token-abc"


def test_extract_csrf_input_fallback() -> None:
    html = '<form><input name="_token" value="input-token-xyz"></form>'
    assert StorefrontSession.extract_csrf(html) == "input-token-xyz"


def test_order_uuid_from_url_and_body() -> None:
    uid = "550e8400-e29b-41d4-a716-446655440000"
    req = httpx.Request("GET", f"https://example.test/order/{uid}/thanks")
    resp = httpx.Response(200, request=req, text="ok")
    assert StorefrontSession.order_uuid_from_response(resp) == uid

    req2 = httpx.Request("POST", "https://example.test/pay")
    resp2 = httpx.Response(
        302,
        request=req2,
        headers={"location": f"/order/{uid}/otp-entry"},
        text="",
    )
    assert StorefrontSession.order_uuid_from_response(resp2) == uid

    req3 = httpx.Request("GET", "https://example.test/")
    resp3 = httpx.Response(200, request=req3, text=f'<a href="/order/{uid}/otp-entry">')
    assert StorefrontSession.order_uuid_from_response(resp3) == uid


def test_capacity_markers_raise() -> None:
    profile = _minimal_profile()
    session = StorefrontSession(profile)
    try:
        req = httpx.Request("GET", "https://example.test/")
        resp503 = httpx.Response(503, request=req, text="busy")
        assert session._is_capacity_blocked(resp503)

        resp_text = httpx.Response(200, request=req, text="موارد الخادم ممتلئة capacity_blocked")
        assert session._is_capacity_blocked(resp_text)

        with session:
            session._handle_response(resp503, "test")
        raise AssertionError("expected CapacityBlockedError")
    except CapacityBlockedError:
        pass
    finally:
        session.close()
