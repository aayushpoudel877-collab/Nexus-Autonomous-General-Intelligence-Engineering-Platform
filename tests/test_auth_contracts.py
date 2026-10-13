import re

from services.api.app.routes.auth import _organization_slug


def test_organization_slug_is_bounded_and_url_safe():
    slug = _organization_slug(" A Very Long Organization Name " * 10, "ab_cd-123")
    assert len(slug) <= 70
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug)


def test_organization_slug_has_fallback_for_punctuation_only_names():
    slug = _organization_slug(" !!! ", "12345678")
    assert slug == "organization-12345678"
