"""Routing-integrity guard: two accounts must never resolve to the same webhook URL
(would fire one account's orders into another's broker). See auto_safety.webhook_route_collisions
+ the launch refuse in auto_live.main()."""
from auto_safety import webhook_route_collisions

U1 = "https://webhooks.traderspost.io/trading/webhook/aaa/111"
U2 = "https://webhooks.traderspost.io/trading/webhook/bbb/222"


def test_distinct_urls_no_collision():
    routes = [("APEX-50K-1", U1), ("APEX-50K-2", U2)]
    assert webhook_route_collisions(routes) == {}


def test_shared_url_is_a_collision():
    # the classic mistake: two books fall back to the SAME TRADERSPOST_APEX_URL
    routes = [("APEX-50K-1", U1), ("APEX-50K-2", U1)]
    coll = webhook_route_collisions(routes)
    assert coll == {U1: ["APEX-50K-1", "APEX-50K-2"]}


def test_primary_colliding_with_a_book():
    routes = [("APEX-50K-1", U1), ("APEX-50K-2", U2), ("APEX-50K-3", U1)]
    coll = webhook_route_collisions(routes)
    assert list(coll) == [U1] and coll[U1] == ["APEX-50K-1", "APEX-50K-3"]


def test_empty_or_none_urls_ignored():
    # dry-run / unconfigured: None or "" URLs are not collisions even if several share them
    routes = [("APEX-50K-1", None), ("APEX-50K-2", None), ("APEX-50K-3", "")]
    assert webhook_route_collisions(routes) == {}


def test_same_account_twice_on_its_own_url_is_fine():
    # an account legitimately listed twice on its OWN url is not a cross-account collision
    routes = [("APEX-50K-1", U1), ("APEX-50K-1", U1), ("APEX-50K-2", U2)]
    assert webhook_route_collisions(routes) == {}
