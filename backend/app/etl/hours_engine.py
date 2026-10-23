import json
from datetime import datetime, timedelta
import pytz
from backend.app.etl.normalizer import to_persian_digits

TEHRAN_TZ = pytz.timezone("Asia/Tehran")

WEEKDAY_TO_KEY = {
    5: "sat",
    6: "sun",
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
}

PERSIAN_DAY_NAMES = {
    "sat": "شنبه",
    "sun": "یکشنبه",
    "mon": "دوشنبه",
    "tue": "سه‌شنبه",
    "wed": "چهارشنبه",
    "thu": "پنجشنبه",
    "fri": "جمعه",
}

def parse_hhmm(s: str) -> tuple[int, int] | None:
    try:
        parts = s.strip().split(":")
        return int(parts[0]), int(parts[1])
    except Exception:
        return None

def parse_weekly_hours(raw_hours: str | dict | None) -> dict:
    if not raw_hours or raw_hours == "null":
        return {}
    if isinstance(raw_hours, dict):
        return raw_hours
    try:
        data = json.loads(raw_hours)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def evaluate_open_status(weekly_hours_raw: str | dict | None, dt: datetime | None = None) -> dict:
    """
    Rule 7:
    - Empty {} -> status='unknown', label='ساعت کاری نامشخص'
    - status=='closed' -> status='closed' (ignore dummy 00:00-00:00 shift!)
    - status=='unsupported' -> status='unknown' (ignore dummy 08:00-08:00 shift!)
    - status=='declared' -> check 1 or 2 shifts, including cross-midnight shifts (e.g., 08:00 to 02:00)
      and 24h shifts where start == end on declared days.
    """
    wh = parse_weekly_hours(weekly_hours_raw)
    if not wh:
        return {
            "status": "unknown",
            "label_fa": "ساعت کاری نامشخص",
            "opens_at": None,
            "closes_at": None,
            "minutes_until_close": None,
        }

    if dt is None:
        dt = datetime.now(TEHRAN_TZ)
    elif dt.tzinfo is None:
        dt = TEHRAN_TZ.localize(dt)
    else:
        dt = dt.astimezone(TEHRAN_TZ)

    now_mins = dt.hour * 60 + dt.minute
    today_key = WEEKDAY_TO_KEY[dt.weekday()]
    yesterday_dt = dt - timedelta(days=1)
    yesterday_key = WEEKDAY_TO_KEY[yesterday_dt.weekday()]

    # 1. Check spillover cross-midnight shift from yesterday
    y_info = wh.get(yesterday_key, {})
    if isinstance(y_info, dict) and y_info.get("status") == "declared":
        for shift in y_info.get("shifts", []):
            st = parse_hhmm(shift.get("start_time", ""))
            et = parse_hhmm(shift.get("end_time", ""))
            if st and et:
                st_m = st[0] * 60 + st[1]
                et_m = et[0] * 60 + et[1]
                if et_m < st_m and now_mins < et_m:
                    rem = et_m - now_mins
                    close_str = shift.get("end_time")
                    return {
                        "status": "open",
                        "label_fa": f"باز است • تا {to_persian_digits(close_str)}",
                        "opens_at": shift.get("start_time"),
                        "closes_at": close_str,
                        "minutes_until_close": rem,
                    }

    # 2. Check today's schedule
    t_info = wh.get(today_key)
    if not isinstance(t_info, dict):
        return {
            "status": "unknown",
            "label_fa": "ساعت کاری نامشخص",
            "opens_at": None,
            "closes_at": None,
            "minutes_until_close": None,
        }

    day_status = t_info.get("status")
    if day_status == "unsupported":
        return {
            "status": "unknown",
            "label_fa": "ساعت کاری نامشخص",
            "opens_at": None,
            "closes_at": None,
            "minutes_until_close": None,
        }
    if day_status == "closed":
        return {
            "status": "closed",
            "label_fa": "امروز تعطیل است",
            "opens_at": None,
            "closes_at": None,
            "minutes_until_close": 0,
        }
    if day_status != "declared":
        return {
            "status": "unknown",
            "label_fa": "ساعت کاری نامشخص",
            "opens_at": None,
            "closes_at": None,
            "minutes_until_close": None,
        }

    shifts = t_info.get("shifts", [])
    if not shifts:
        return {
            "status": "unknown",
            "label_fa": "ساعت کاری نامشخص",
            "opens_at": None,
            "closes_at": None,
            "minutes_until_close": None,
        }

    next_open = None
    for shift in shifts:
        st_str = shift.get("start_time", "")
        et_str = shift.get("end_time", "")
        st = parse_hhmm(st_str)
        et = parse_hhmm(et_str)
        if not st or not et:
            continue
        st_m = st[0] * 60 + st[1]
        et_m = et[0] * 60 + et[1]

        # 24h declared shift
        if st_m == et_m:
            return {
                "status": "open",
                "label_fa": "باز است (شبانه‌روزی)",
                "opens_at": st_str,
                "closes_at": et_str,
                "minutes_until_close": 24 * 60 - now_mins,
            }

        # Normal shift within same day
        if st_m < et_m:
            if st_m <= now_mins < et_m:
                rem = et_m - now_mins
                return {
                    "status": "open",
                    "label_fa": f"باز است • تا {to_persian_digits(et_str)}",
                    "opens_at": st_str,
                    "closes_at": et_str,
                    "minutes_until_close": rem,
                }
            elif now_mins < st_m and next_open is None:
                next_open = st_str
        else:
            # Cross-midnight shift starting today (e.g. 08:00 to 02:00 next day)
            if now_mins >= st_m:
                rem = (24 * 60 - now_mins) + et_m
                return {
                    "status": "open",
                    "label_fa": f"باز است • تا {to_persian_digits(et_str)} بامداد",
                    "opens_at": st_str,
                    "closes_at": et_str,
                    "minutes_until_close": rem,
                }
            elif now_mins < st_m and next_open is None:
                next_open = st_str

    if next_open:
        return {
            "status": "closed",
            "label_fa": f"بسته است • بازگشایی ساعت {to_persian_digits(next_open)}",
            "opens_at": next_open,
            "closes_at": None,
            "minutes_until_close": 0,
        }

    return {
        "status": "closed",
        "label_fa": "بسته است",
        "opens_at": None,
        "closes_at": None,
        "minutes_until_close": 0,
    }

def check_open_at_arrival(weekly_hours_raw: str | dict | None, arrival_dt: datetime, min_buffer_minutes: int = 20) -> dict:
    status = evaluate_open_status(weekly_hours_raw, arrival_dt)
    will_be_open = status["status"] == "open" and (
        status["minutes_until_close"] is None or status["minutes_until_close"] >= min_buffer_minutes
    )
    closing_soon = (
        status["status"] == "open"
        and status["minutes_until_close"] is not None
        and status["minutes_until_close"] < min_buffer_minutes
    )
    return {
        **status,
        "will_be_open_ safely": will_be_open,
        "closing_soon_on_arrival": closing_soon,
    }
