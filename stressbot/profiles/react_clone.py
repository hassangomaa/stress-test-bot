from __future__ import annotations

import random
import time
import uuid
from typing import Any

from stressbot.config import ProfileConfig
from stressbot.event_log import EventLogger
from stressbot.fake_data import FakeUser, random_otp
from stressbot.http_session import CapacityBlockedError, StorefrontSession
from stressbot.metrics import JourneyResult


SADAD_MARKERS = ("سداد", "رسوم")

# HTTP codes that count as step complete for checkout APIs
CHECKOUT_OK_CODES = {200, 201, 202, 204}


def new_checkout_session_id() -> str:
    return str(uuid.uuid4())


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


def checkout_payload_for_step(
    step: str,
    product: dict[str, Any],
    user: FakeUser,
    session_id: str,
    *,
    activation_code: str | None = None,
) -> dict[str, Any]:
    product_id = product.get("id") or product.get("productId") or product.get("product_id")
    base = {"sessionId": session_id, "productId": product_id}
    if step == "manual-gate":
        return base
    if step == "request-activation-code":
        return {**base, "phoneNumber": user.phone}
    if step == "verify-activation-code":
        return {"sessionId": session_id, "code": activation_code or random_otp(6), "productId": product_id}
    if step == "submit-code":
        return {"sessionId": session_id, "code": activation_code or random_otp(6), "productId": product_id}
    if step == "approval":
        return base
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
                session_id = new_checkout_session_id()
                gate_enabled = bool(settings.get("checkoutGateEnabled"))
                if not gate_enabled:
                    self.log.gate_skipped("checkoutGateEnabled=false")

                activation_code: str | None = None
                checkout_steps = ["manual-gate", "request-activation-code", "verify-activation-code", "approval", "submit-code"]
                blocked_steps: list[str] = []

                for step_name in checkout_steps:
                    path = f"/api/checkout/{step_name}"
                    payload = checkout_payload_for_step(
                        step_name,
                        product,
                        user,
                        session_id,
                        activation_code=activation_code,
                    )
                    resp = self._timed_step(
                        session,
                        f"checkout/{step_name}",
                        lambda p=path, pl=payload: session.post_json(p, pl, step=f"checkout_{step_name}"),
                        checkout=True,
                    )
                    session.think()

                    if step_name == "request-activation-code" and resp.status_code in CHECKOUT_OK_CODES:
                        try:
                            body = resp.json()
                            activation_code = str(body.get("activationCode") or body.get("code") or "")
                        except Exception:
                            activation_code = None

                    if resp.status_code not in CHECKOUT_OK_CODES:
                        detail = (resp.text or "")[:200]
                        if step_name == "submit-code":
                            resp = self._force_submit_code(
                                session,
                                session_id,
                                product,
                                user,
                                activation_code,
                                resp,
                                detail,
                            )
                            if resp.status_code in CHECKOUT_OK_CODES:
                                continue
                            self.log.emit(
                                "step_force_done",
                                step="checkout/submit-code",
                                reason="approval_submitted_admin_pending",
                                http_status=resp.status_code,
                                detail=detail,
                            )
                            self.log.step(
                                "checkout/submit-code",
                                ok=True,
                                http_status=202,
                                detail="force_done_admin_pending",
                            )
                            continue
                        blocked_steps.append(step_name)
                        self.log.emit(
                            "step_blocked",
                            step=f"checkout/{step_name}",
                            http_status=resp.status_code,
                            detail=detail,
                        )
                        if resp.status_code >= 500:
                            raise RuntimeError(f"Checkout {step_name} server error {resp.status_code}: {detail}")

                if blocked_steps and "manual-gate" in blocked_steps:
                    raise RuntimeError(f"Checkout blocked at required steps: {blocked_steps}")

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

    def _force_submit_code(
        self,
        session: StorefrontSession,
        session_id: str,
        product: dict[str, Any],
        user: FakeUser,
        activation_code: str | None,
        first_resp: Any,
        detail: str,
    ) -> Any:
        """Poll approval then retry submit-code; admin-pending is force-completed for stress."""
        if "not yet approved" not in detail and "invalid state" not in detail:
            return first_resp

        for attempt in range(3):
            time.sleep(1.5)
            poll = session.get(f"/api/checkout/approval/{session_id}", step="approval_poll")
            if poll.status_code != 200:
                continue
            try:
                status = poll.json().get("status")
            except Exception:
                status = None
            if status == "approved":
                payload = checkout_payload_for_step(
                    "submit-code",
                    product,
                    user,
                    session_id,
                    activation_code=activation_code,
                )
                retry = session.post_json(
                    "/api/checkout/submit-code",
                    payload,
                    step="checkout_submit_code_retry",
                )
                if retry.status_code in CHECKOUT_OK_CODES:
                    self.log.step(
                        "checkout/submit-code",
                        ok=True,
                        http_status=retry.status_code,
                        detail="retry_after_approval",
                    )
                    return retry
        return first_resp

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

    def _timed_step(self, session: StorefrontSession, name: str, fn, *, checkout: bool = False) -> Any:
        t0 = time.monotonic()
        try:
            result = session.with_retries(fn, name)
            status = getattr(result, "status_code", None)
            if checkout and status is not None:
                ok = status in CHECKOUT_OK_CODES
            else:
                ok = status is None or status < 500
            detail = None
            if checkout and status is not None and not ok:
                detail = (getattr(result, "text", None) or "")[:200]
            self.log.step(
                name,
                ok=ok,
                http_status=status,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
                detail=detail,
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
