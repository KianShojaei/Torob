"""Price validity, freshness and statistics (master prompt §4.3, §4.5, §4.12)."""
from __future__ import annotations

from datetime import date, datetime

# §4.3 validity window, in Toman
PRICE_MIN = 10_000
PRICE_MAX = 5_000_000_000

AGE_BUCKETS = (
    ("fresh", 7, "به‌روز"),
    ("recent", 30, "۲ تا ۴ هفته پیش"),
    ("old", 90, "قدیمی"),
    ("stale", 10_000, "خیلی قدیمی"),
)


def is_valid_price(value) -> bool:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return v == v and PRICE_MIN <= v <= PRICE_MAX  # v==v rejects NaN


def price_status(value) -> str:
    return "known" if is_valid_price(value) else "unknown"


def age_days(changed_at: str | datetime | None, snapshot: date) -> int | None:
    if not changed_at:
        return None
    if isinstance(changed_at, datetime):
        d = changed_at.date()
    else:
        try:
            d = datetime.fromisoformat(str(changed_at).replace("Z", "+00:00")).date()
        except ValueError:
            try:
                d = date.fromisoformat(str(changed_at)[:10])
            except ValueError:
                return None
    return max(0, (snapshot - d).days)


def age_bucket(days: int | None) -> tuple[str, str]:
    if days is None:
        return "unknown", "نامشخص"
    for key, limit, label in AGE_BUCKETS:
        if days <= limit:
            return key, label
    return "stale", "خیلی قدیمی"


def price_stats(prices: list[float]) -> dict | None:
    valid = sorted(p for p in prices if is_valid_price(p))
    if not valid:
        return None
    n = len(valid)

    def pct(q: float) -> float:
        k = (n - 1) * q
        lo, hi = int(k), min(int(k) + 1, n - 1)
        return valid[lo] + (valid[hi] - valid[lo]) * (k - lo)

    return {
        "count": n,
        "min": valid[0],
        "p25": pct(0.25),
        "median": pct(0.5),
        "p75": pct(0.75),
        "max": valid[-1],
    }


def relative_to_market(price: float, stats: dict | None) -> dict | None:
    """Human-meaningful position of a price inside the market distribution."""
    if not stats or not is_valid_price(price):
        return None
    median = stats["median"] or 0
    if median <= 0:
        return None
    delta = (price - median) / median * 100
    if delta <= -15:
        label, tone = "خیلی زیر میانه بازار", "good"
    elif delta <= -5:
        label, tone = "زیر میانه بازار", "good"
    elif delta < 5:
        label, tone = "نزدیک میانه بازار", "neutral"
    elif delta < 15:
        label, tone = "بالای میانه بازار", "warn"
    else:
        label, tone = "خیلی بالای میانه بازار", "bad"
    return {"delta_pct": round(delta, 1), "label": label, "tone": tone}
