from __future__ import annotations

import random
import re
import time

from stressbot.config import ProfileConfig
from stressbot.event_log import EventLogger
from stressbot.fake_data import FakeUser, random_otp
from stressbot.http_session import CapacityBlockedError, StorefrontSession
from stressbot.metrics import JourneyResult


COUPON_FIELD_RE = re.compile(
    r'name=["\']([^"\']*(?:coupon|code|activation)[^"\']*)["\']',
    re.IGNORECASE,
)


class PhpCloneProfile:
    """PHP LiteSpeed clone (agdalreem) — form-based auth + payment_method.php."""

    def __init__(self, profile: ProfileConfig) -> None:
        self.profile = profile
        self.log = EventLogger.for_profile(profile.name, profile.base_url)
        self.checkout_cfg = profile.raw.get("checkout", {})
        self.auth_cfg = profile.raw.get("auth", {})

    def run_once(self, session: StorefrontSession) -> JourneyResult:
        user = FakeUser.generate()
        self.log.journey_start()
        started = time.monotonic()

        try:
            if self.profile.steps.get("browse", True):
                self._timed_step(session, "browse", lambda: session.get("/index.php", step="browse"))
                session.think()

            if self.profile.steps.get("auth", True):
                self._auth(session, user)
                session.think()

            if self.profile.steps.get("checkout", True):
                product_id = self.checkout_cfg.get("product_id", 1)
                payment_path = self.checkout_cfg.get("payment_path", "/payment_method.php")
                query = f"{payment_path}?product_id={product_id}"
                resp = self._timed_step(
                    session,
                    "payment_method_get",
                    lambda: session.get(query, step="payment_method_get"),
                )
                session.think()

                if self.profile.steps.get("coupon") and self.checkout_cfg.get("coupon_required"):
                    self._attempt_coupon(session, resp.text or "", payment_path, product_id)
                    session.think()

                payment_method = random.choice(self.profile.payment_methods or ["tamara", "tabby"])
                self._timed_step(
                    session,
                    "payment_method_post",
                    lambda: session.post_form(
                        payment_path,
                        {
                            "product_id": product_id,
                            "payment_method": payment_method,
                        },
                        step="payment_method_post",
                        referer=query,
                    ),
                )

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

    def _auth(self, session: StorefrontSession, user: FakeUser) -> None:
        login_path = self.auth_cfg.get("login_path", "/auth.php")
        fields = self.auth_cfg.get("fields", {})
        email_field = fields.get("email", "email")
        password_field = fields.get("password", "password")

        self._timed_step(session, "auth_get", lambda: session.get(login_path, step="auth_get"))
        session.think()

        session.post_form(
            login_path,
            {
                email_field: user.email,
                password_field: random_otp(8),
            },
            step="auth_post",
            referer=login_path,
        )
        self.log.step("auth_post", ok=True, http_status=200)
        self.log.emit("auth_attempted", mode=self.auth_cfg.get("mode", "email_login"))

    def _attempt_coupon(
        self,
        session: StorefrontSession,
        html: str,
        payment_path: str,
        product_id: int,
    ) -> None:
        field = self.checkout_cfg.get("coupon_field", "coupon_code")
        match = COUPON_FIELD_RE.search(html)
        if match:
            field = match.group(1)

        session.post_form(
            payment_path,
            {
                "product_id": product_id,
                field: random_otp(6),
            },
            step="coupon_post",
            referer=f"{payment_path}?product_id={product_id}",
        )
        self.log.step("coupon_post", ok=True, http_status=200)
        self.log.emit("coupon_attempted", field=field)

    def _timed_step(self, session: StorefrontSession, name: str, fn):
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
