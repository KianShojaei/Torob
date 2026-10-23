from datetime import datetime, timezone
from backend.app.etl.normalizer import to_persian_digits

MIN_VALID_PRICE = 1_000
MAX_VALID_PRICE = 5_000_000_000
DEFAULT_SNAPSHOT_DATE = "2026-10-13"

def validate_price(price_raw) -> tuple[int | None, str]:
    """
    Rule 3: price_valid = price_toman is not null and 1_000 <= price_toman <= 5_000_000_000.
    Invalid -> (None, 'unknown'). Never return 0 as valid price.
    """
    if price_raw is None or price_raw == "" or price_raw == "null":
        return None, "unknown"
    try:
        val = int(float(price_raw))
    except (ValueError, TypeError):
        return None, "unknown"
    if MIN_VALID_PRICE <= val <= MAX_VALID_PRICE:
        return val, "valid"
    return None, "unknown"

def format_price_toman(price_toman: int | None) -> str:
    if price_toman is None:
        return "قیمت نامشخص"
    formatted = f"{price_toman:,}"
    return f"{to_persian_digits(formatted)} تومان"

def compute_price_age(last_changed_iso: str | None, ref_date_str: str = DEFAULT_SNAPSHOT_DATE) -> dict:
    """
    Rule 5: Compute age_days relative to snapshot_date (2026-10-13) or current date.
    Buckets: fresh <=7d, recent <=30d, old <=90d, stale >90d, unknown if null.
    """
    if not last_changed_iso or last_changed_iso == "null":
        return {
            "age_days": None,
            "bucket": "unknown",
            "label_fa": "زمان تغییر قیمت نامشخص",
            "is_stale": True
        }
    try:
        dt = datetime.fromisoformat(last_changed_iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ref_dt = datetime.fromisoformat(ref_date_str).replace(tzinfo=timezone.utc)
        # Take end of snapshot day so timestamps on 2026-10-13 have 0 days age
        ref_dt = ref_dt.replace(hour=23, minute=59, second=59)
        delta_days = max(0, (ref_dt - dt).days)
    except Exception:
        return {
            "age_days": None,
            "bucket": "unknown",
            "label_fa": "زمان تغییر قیمت نامشخص",
            "is_stale": True
        }

    if delta_days == 0:
        label = "به‌روزرسانی امروز"
    else:
        label = f"{to_persian_digits(delta_days)} روز پیش"

    if delta_days <= 7:
        bucket = "fresh"
    elif delta_days <= 30:
        bucket = "recent"
    elif delta_days <= 90:
        bucket = "old"
    else:
        bucket = "stale"

    return {
        "age_days": delta_days,
        "bucket": bucket,
        "label_fa": label,
        "is_stale": bucket in ("old", "stale", "unknown")
    }
