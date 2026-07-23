from __future__ import annotations

import random
import re

from stressbot.config import ProfileConfig
from stressbot.fake_data import FakeUser, random_otp
from stressbot.http_session import CapacityBlockedError, StorefrontSession
from stressbot.metrics import JourneyResult
from stressbot.profiles.base import CatalogService


CHECKOUT_LINK_RE = re.compile(r'href=["\'](/checkout/([^"\']+))["\']', re.IGNORECASE)
SERVICE_ID_RE = re.compile(r'name=["\']financing_service_id["\'][^>]+value=["\'](\d+)["\']', re.IGNORECASE)


class AltmizProfile:
    """Shorter journey: register → checkout → pay → bank OTP."""

    def __init__(self, profile: ProfileConfig) -> None:
        self.profile = profile

    def run_once(self, session: StorefrontSession) -> JourneyResult:
        user = FakeUser.generate()
        try:
            session.with_retries(lambda: session.get("/", step="land"), "land")
            session.think()

            service = session.with_retries(lambda: self._pick_service(session), "catalog")
            session.think()

            if self.profile.steps.get("register", True):
                session.with_retries(lambda: self._register(session, user), "register")
                session.think()

            slug = service.slug
            session.with_retries(
                lambda: session.get(f"/checkout/{slug}", step="checkout"),
                "checkout",
            )
            session.think()

            order_uuid = None
            if self.profile.steps.get("payment", True):
                pay_resp = session.with_retries(
                    lambda: session.post_form(
                        "/process-payment",
                        {
                            "financing_service_id": service.id,
                            "client_name": user.name,
                            "client_phone": user.phone,
                            "client_email": user.email,
                            "card_number": user.card.number,
                            "card_expiry": user.card.expiry,
                            "card_cvv": user.card.cvv,
                        },
                        step="payment",
                        referer=f"/checkout/{slug}",
                    ),
                    "payment",
                )
                order_uuid = StorefrontSession.order_uuid_from_response(pay_resp)
                if not order_uuid:
                    return JourneyResult(
                        ok=False,
                        step="payment",
                        duration_s=0,
                        error="Could not extract order UUID from payment response",
                    )
                session.think()

            if self.profile.steps.get("bank_otp", True) and order_uuid:
                session.with_retries(
                    lambda: session.post_form(
                        "/verify-otp",
                        {
                            "order_uuid": order_uuid,
                            "otp_code": random_otp(6),
                        },
                        step="bank_otp",
                        referer=f"/order/{order_uuid}/otp-entry",
                    ),
                    "bank_otp",
                )

            return JourneyResult(ok=True, step="complete", duration_s=0, order_uuid=order_uuid)

        except CapacityBlockedError as exc:
            return JourneyResult(ok=False, step="capacity", duration_s=0, error=str(exc))
        except Exception as exc:
            return JourneyResult(ok=False, step="error", duration_s=0, error=str(exc))

    def _register(self, session: StorefrontSession, user: FakeUser) -> None:
        resp = session.get("/register", step="register_get")
        session.post_form(
            "/register",
            {
                "name": user.name,
                "phone": user.phone,
                "terms": "on",
            },
            step="register",
            referer="/register",
        )
        if resp.status_code >= 500:
            raise RuntimeError(f"Register page failed: {resp.status_code}")

    def _pick_service(self, session: StorefrontSession) -> CatalogService:
        resp = session.get("/", step="catalog_html")
        links = CHECKOUT_LINK_RE.findall(resp.text or "")
        slugs = [slug for _, slug in links if slug and slug not in ("create", "method")]
        if not slugs:
            raise RuntimeError("No checkout links found on homepage")
        slug = random.choice(slugs)
        checkout = session.get(f"/checkout/{slug}", step="checkout_resolve")
        m = SERVICE_ID_RE.search(checkout.text or "")
        if not m:
            raise RuntimeError(f"Could not resolve financing_service_id for {slug}")
        return CatalogService(id=int(m.group(1)), slug=slug)
