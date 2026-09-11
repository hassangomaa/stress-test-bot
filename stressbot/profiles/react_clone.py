from __future__ import annotations

import random
import time
from typing import Any

from stressbot.config import ProfileConfig
from stressbot.event_log import EventLogger
from stressbot.fake_data import FakeUser, random_otp
from stressbot.http_session import CapacityBlockedError, StorefrontSession
from stressbot.metrics import JourneyResult


SADAD_MARKERS = ("سداد", "رسوم")


def pick_product(products: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    if not products:
        raise RuntimeError("Empty product catalog")

    if variant == "sadad":
        sadad = [
            p
            for p in products
            if any(marker in str(p.get("name", "")) for marker in SADAD_MARKERS)
        ]
        if sadad:
            return sadad[0]
        if len(products) == 1:
            return products[0]
        raise RuntimeError("No sadad-fee product found in catalog")

    return random.choice(products)


def checkout_payload_for_step(step: str, product: dict[str, Any], user: FakeUser) -> dict[str, Any]:
    product_id = product.get("id") or product.get("productId") or product.get("product_id")
    base = {
        "productId": product_id,
        "product_id": product_id,
        "id": product_id,
        "phone": user.phone,
        "email": user.email,
        "name": user.name,
    }
    if step == "manual-gate":
        return {k: v for k, v in base.items() if v is not None}
    if step == "request-activation-code":
        return {"phone": user.phone, "email": user.email, "productId": product_id}
    if step == "verify-activation-code":
        return {"code": random_otp(6), "productId": product_id}
    if step == "submit-code":
        return {"activationCode": random_otp(6), "productId": product_id}
    if step == "approval":
        return {"productId": product_id, "approved": True}
    return base


class ReactCloneProfile:
    """React SPA clone family (goldalreem network) — JSON API checkout."""

    def __init__(self, profile: ProfileConfig) -> None:
        self.profile = profile
        self.log = EventLogger.for_profile(profile.name, profile.base_url)
        self.checkout_cfg = profile.raw.get("checkout", {})
        self.auth_cfg = profile.raw.get("auth", {})
        self.variant = profile.raw.get("variant", "gold")

    def run_once(self, session: StorefrontSession) -> JourneyResult:
        user = FakeUser.generate()
        self.log.journey_start()
        started = time.monotonic()

        try:
            if self.profile.steps.get("browse", True):
                self._timed_step(session, "browse", lambda: session.get("/", step="browse"))
                session.think()

            settings = {}
            if self.checkout_cfg.get("settings_api"):
                resp = self._timed_step(
                    session,
                    "marquee",
                    lambda: session.get(self.checkout_cfg["settings_api"], step="marquee"),
                )
                if resp.status_code == 200:
                    try:
                        settings = resp.json()
                    except Exception:
                        settings = {}

            product = None
            if self.profile.steps.get("catalog", True):
                catalog_path = self.checkout_cfg.get("catalog_api", "/api/products")
                resp = self._timed_step(
                    session,
                    "catalog",
                    lambda: session.get(catalog_path, step="catalog"),
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"Catalog failed: {resp.status_code}")
                data = resp.json()
                products = data if isinstance(data, list) else data.get("products", data.get("data", []))
                product = pick_product(products, self.variant)
                session.think()

            if self.profile.steps.get("auth") or self.auth_cfg.get("mode") == "login_optional":
                if self.profile.steps.get("auth"):
                    self._attempt_login(session, user)
                else:
                    self.log.emit("auth_skipped", reason="login_optional_disabled_in_steps")

            if self.profile.steps.get("checkout", True) and product:
                gate_enabled = bool(settings.get("checkoutGateEnabled"))
                gate_mode = self.profile.steps.get("activation_gate", "auto")
                run_gate = gate_enabled or gate_mode == "force"

                if not run_gate:
                    self.log.gate_skipped("checkoutGateEnabled=false")

                checkout_steps = list(self.checkout_cfg.get("steps", ["manual-gate"]))
                if not run_gate:
                    checkout_steps = checkout_steps[:1]

                for step_name in checkout_steps:
                    path = f"/api/checkout/{step_name}"
                    payload = checkout_payload_for_step(step_name, product, user)
                    resp = self._timed_step(
                        session,
                        f"checkout/{step_name}",
                        lambda p=path, pl=payload: session.post_json(p, pl, step=f"checkout_{step_name}"),
                    )
                    session.think()
                    if resp.status_code >= 500:
                        detail = (resp.text or "")[:200]
                        raise RuntimeError(f"Checkout {step_name} server error {resp.status_code}: {detail}")

            duration = time.monotonic() - started
            self.log.journey_end(True, "complete", duration)
            return JourneyResult(ok=True, step="complete", duration_s=duration)

        except CapacityBlockedError as exc:
            duration = time.monotonic() - started
            self.log.capacity_blocked("journey", str(exc))
            self.log.journey_end(False, "capacity", duration, str(exc))
            return JourneyResult(ok=False, step="capacity", duration_s=duration, error=str(exc))
        except Exception as exc:
            duration = time.monotonic() - started
            self.log.journey_end(False, "error", duration, str(exc))
            return JourneyResult(ok=False, step="error", duration_s=duration, error=str(exc))

    def _attempt_login(self, session: StorefrontSession, user: FakeUser) -> None:
        login_path = self.auth_cfg.get("login_path", "/login")
        fields = self.auth_cfg.get("fields", {})
        phone_field = fields.get("phone", "phone")
        password_field = fields.get("password", "password")

        self._timed_step(session, "auth_get", lambda: session.get(login_path, step="auth_get"))
        session.think()

        payload = {
            phone_field: user.phone,
            password_field: random_otp(8),
        }
        for api_path in ("/api/auth/login", "/api/login", "/api/user/login"):
            resp = session.post_json(api_path, payload, step="auth_post")
            self.log.step(
                "auth_post",
                ok=resp.status_code < 500,
                http_status=resp.status_code,
                detail=api_path,
            )
            if resp.status_code in (200, 201, 400, 401, 422):
                return

        self.log.emit("auth_attempted", detail="no_public_auth_api; login_page_only")

    def _timed_step(self, session: StorefrontSession, name: str, fn) -> Any:
        t0 = time.monotonic()
        try:
            result = session.with_retries(fn, name)
            status = getattr(result, "status_code", None)
            self.log.step(
                name,
                ok=True if status is None or status < 500 else False,
                http_status=status,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
            )
            return result
        except Exception as exc:
            self.log.step(
                name,
                ok=False,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
                detail=str(exc)[:200],
            )
            raise
