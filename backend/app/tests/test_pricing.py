from datetime import date

from app.services.pricing import (
    age_bucket,
    age_days,
    is_valid_price,
    price_stats,
    price_status,
    relative_to_market,
)


def test_invalid_prices():
    for bad in (None, 0, -5, 9_999, 5_000_000_001, float("nan"), "abc"):
        assert not is_valid_price(bad)
        assert price_status(bad) == "unknown"


def test_valid_price_bounds():
    assert is_valid_price(10_000)
    assert is_valid_price(5_000_000_000)
    assert is_valid_price(2_500_000)


def test_age_from_iso_with_timezone():
    snap = date(2026, 10, 13)
    assert age_days("2026-10-01T12:00:00+03:30", snap) == 12
    assert age_days("2026-10-13", snap) == 0
    assert age_days(None, snap) is None
    assert age_days("garbage", snap) is None


def test_age_buckets():
    assert age_bucket(3)[0] == "fresh"
    assert age_bucket(21)[0] == "recent"
    assert age_bucket(60)[0] == "old"
    assert age_bucket(400)[0] == "stale"
    assert age_bucket(None)[0] == "unknown"


def test_price_stats_ignores_invalid_rows():
    stats = price_stats([0, 2_000_000, 4_000_000, None, 1_000_000])
    assert stats["count"] == 3
    assert stats["median"] == 2_000_000
    assert stats["min"] == 1_000_000


def test_relative_to_market_labels():
    stats = price_stats([1_000_000, 2_000_000, 3_000_000])
    assert relative_to_market(1_200_000, stats)["tone"] == "good"
    assert relative_to_market(2_000_000, stats)["tone"] == "neutral"
    assert relative_to_market(2_900_000, stats)["tone"] == "bad"
    assert relative_to_market(2_000_000, None) is None
