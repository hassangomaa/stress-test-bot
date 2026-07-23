from __future__ import annotations

from unittest.mock import MagicMock

from stressbot.config import load_profile
from stressbot.profiles.zaedl import ZaedlProfile


def test_pick_service_from_html_parses_slug_and_id() -> None:
    profile = load_profile("zaedl", url_key="local")
    profile.catalog_source = "html"

    session = MagicMock()
    slug = "demo-financing-plan"

    def fake_get(path: str, **kwargs: object):
        resp = MagicMock()
        step = kwargs.get("step", "")
        if path == "/" or step == "catalog_html":
            resp.text = f'<a href="/checkout/{slug}">Buy</a>'
        elif path == f"/checkout/{slug}":
            resp.text = f'<input name="financing_service_id" value="99" />'
        else:
            resp.text = ""
        return resp

    session.get.side_effect = fake_get

    runner = ZaedlProfile(profile)
    service = runner._pick_service_from_html(session)

    assert service.slug == slug
    assert service.id == 99
    assert session.get.call_count >= 2
