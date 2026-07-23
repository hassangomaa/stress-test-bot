from __future__ import annotations

import random
import re
from typing import Any

from stressbot.config import ProfileConfig
from stressbot.fake_data import FakeUser, random_otp
from stressbot.http_session import CapacityBlockedError, StorefrontSession
from stressbot.metrics import JourneyResult
from stressbot.profiles.base import CatalogService


CHECKOUT_LINK_RE = re.compile(r'href=["\'](/checkout/([^"\']+))["\']', re.IGNORECASE)
SERVICE_ID_RE = re.compile(r'name=["\']financing_service_id["\'][^>]+value=["\'](\d+)["\']', re.IGNORECASE)


class ZaedlProfile:
    def __init__(self, profile: ProfileConfig) -> None:
        self.profile = profile

    def run_once(self, session: StorefrontSession) -> JourneyResult:
        user = FakeUser.generate()
        try:
            session.with_retries(lambda: session.get("/", step="land"), "land")
            session.think()
            session.send_heartbeat("/")

            service = session.with_retries(lambda: self._pick_service(session), "catalog")
            session.think()

            if self.profile.steps.get("register", True):
                session.with_retries(lambda: self._register(session, user), "register")
                session.think()

            slug = service.slug
            payment_method = random.choice(self.profile.payment_methods or ["tamara", "tabby"])

            if self.profile.steps.get("checkout_method", True):
                session.with_retries(
                    lambda: session.get(f"/checkout/{slug}/method", step="checkout_method_get"),
                    "checkout_method_get",
                )
                session.think()
                session.with_retries(
                    lambda: session.post_form(
                        f"/checkout/{slug}/method",
                        {"payment_method": payment_method},
                        step="checkout_method",
                        referer=f"/checkout/{slug}/method",
                    ),
                    "checkout_method",
                )
                session.think()

            if self.profile.steps.get("phone", True):
                session.with_retries(
                    lambda: session.post_form(
                        f"/checkout/{slug}/phone",
                        {"client_phone": user.phone},
                        step="phone",
                        referer=f"/checkout/{slug}/phone",
                    ),
                    "phone",
                )
                session.think()

            if self.profile.steps.get("phone_otp", True):
                session.with_retries(
                    lambda: session.post_form(
                        f"/checkout/{slug}/phone-otp",
                        {"otp_code": random_otp(4)},
                        step="phone_otp",
                        referer=f"/checkout/{slug}/phone-otp",
                    ),
                    "phone_otp",
                )
                session.think()

            if self.profile.steps.get("installment", True):
                counts = self.profile.installment_counts.get(payment_method, [4])
                installment_count = random.choice(counts)
                session.with_retries(
                    lambda: session.post_form(
                        f"/checkout/{slug}/installment",
                        {"installment_count": installment_count},
                        step="installment",
                        referer=f"/checkout/{slug}/installment",
                    ),
                    "installment",
                )
                session.think()

            order_uuid = None
            if self.profile.steps.get("payment", True):
                session.with_retries(
                    lambda: session.get(f"/checkout/{slug}/card", step="card_page"),
                    "card_page",
                )
                session.think()
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
                        referer=f"/checkout/{slug}/card",
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
        session.get("/register", step="register_get")
        session.post_form(
            "/register",
            {
                "name": user.name,
                "email": user.email,
                "phone": user.phone,
                "terms": "on",
            },
            step="register",
            referer="/register",
        )

    def _pick_service(self, session: StorefrontSession) -> CatalogService:
        if self.profile.catalog_source == "api":
            resp = session.get("/api/storefront/catalog", step="catalog")
            if resp.status_code != 200:
                raise RuntimeError(f"Catalog API failed: {resp.status_code}")
            data = resp.json()
            services = [
                s
                for s in data.get("services", [])
                if not s.get("is_sdad") and not s.get("is_unavailable")
            ]
            if not services:
                raise RuntimeError("No purchasable services in catalog")
            chosen = random.choice(services)
            return CatalogService(
                id=int(chosen["id"]),
                slug=str(chosen["slug"]),
                name=chosen.get("name_ar"),
            )
        return self._pick_service_from_html(session)

    def _pick_service_from_html(self, session: StorefrontSession) -> CatalogService:
        resp = session.get("/", step="catalog_html")
        links = CHECKOUT_LINK_RE.findall(resp.text or "")
        slugs = [slug for _, slug in links if slug and slug != "create"]
        if not slugs:
            raise RuntimeError("No checkout links found on homepage")
        slug = random.choice(slugs)
        checkout = session.get(f"/checkout/{slug}", step="checkout_resolve")
        m = SERVICE_ID_RE.search(checkout.text or "")
        if not m:
            raise RuntimeError(f"Could not resolve financing_service_id for {slug}")
        return CatalogService(id=int(m.group(1)), slug=slug)
