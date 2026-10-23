"""Weekly opening-hours engine (master prompt §4.7, §5.3 tool 7).

Data shape (from ``shops.weekly_hours``)::

    {"sat": {"status": "declared", "shifts": [{"start_time": "10:00:00",
                                               "end_time": "19:00:00"}]},
     "sun": {"status": "closed", "shifts": [{"start_time": "00:00:00",
                                             "end_time": "00:00:00"}]},
     ...}

Rules implemented here (each has a unit test):

* ``{}`` / missing day  -> unknown, never guessed.
* ``status=closed``     -> the shop declared itself closed that day.
* ``status=unsupported``-> unknown (never closed, never open).
* dummy ``00:00–00:00`` -> no real shift, never 24h.
* 1 or 2 shifts per day, shifts may cross midnight (08:00 → 02:00).
* week starts Saturday; timezone Asia/Tehran (fixed +03:30 since 2022).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

TEHRAN = timezone(timedelta(hours=3, minutes=30))

# Python weekday(): Mon=0 ... Sun=6
DAY_KEYS = _DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_FA = {
    "sat": "شنبه", "sun": "یک‌شنبه", "mon": "دوشنبه", "tue": "سه‌شنبه",
    "wed": "چهارشنبه", "thu": "پنج‌شنبه", "fri": "جمعه",
}
DAY_ORDER = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"]


@dataclass(frozen=True)
class DayHours:
    status: str            # declared | closed | unsupported | unknown
    shifts: tuple[tuple[int, int], ...]  # minutes from midnight


@dataclass(frozen=True)
class OpenStatus:
    state: str                  # open | closed | unknown
    opens_at: str | None = None      # "10:30"
    closes_at: str | None = None
    minutes_until_close: int | None = None
    day_status: str = "unknown"
    next_open_day: str | None = None


def parse_time(value: str) -> int | None:
    """"10:30:00" -> 630 minutes. Also accepts "10:30"."""
    if not value or not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if len(parts) < 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= h <= 24 and 0 <= m < 60):
        return None
    return h * 60 + m


def _fmt(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_day(raw) -> DayHours:
    """Normalise one day of the dataset's ``weekly_hours``.

    Accepts every shape seen in Torob exports:

    * ``{"status": "declared", "shifts": [{"start_time": "10:00", "end_time": "21:00"}]}``
    * ``{"open": "10:00", "close": "21:00"}`` (or ``open_time``/``close_time``)
    * ``[{"start_time": "10:00", "end_time": "21:00"}]``
    * ``"unsupported"`` / ``"closed"`` / ``"24h"``

    ``unsupported``, missing and unparseable values are **unknown**, never "closed".
    """
    if raw is None:
        return DayHours("unknown", ())
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("", "null", "none", "unsupported", "unknown", "نامشخص"):
            return DayHours("unknown", ())
        if s in ("closed", "تعطیل", "بسته"):
            return DayHours("closed", ())
        if s in ("24h", "24/7", "always", "همیشه"):
            return DayHours("declared", ((0, 24 * 60),))
        return DayHours("unknown", ())
    if isinstance(raw, list):
        raw = {"status": "declared", "shifts": raw}
    if not isinstance(raw, dict):
        return DayHours("unknown", ())

    status = str(raw.get("status") or "").lower()
    if not status:
        o = (raw.get("open") or raw.get("open_time") or raw.get("start")
             or raw.get("start_time") or raw.get("from"))
        e = (raw.get("close") or raw.get("close_time") or raw.get("end")
             or raw.get("end_time") or raw.get("to"))
        if o and e:
            s_min, e_min = parse_time(str(o)), parse_time(str(e))
            if s_min is not None and e_min is not None and s_min != e_min:
                return DayHours("declared", ((s_min, e_min),))
        return DayHours("unknown", ())

    shifts: list[tuple[int, int]] = []
    raw_shifts = raw.get("shifts")
    if isinstance(raw_shifts, dict):
        raw_shifts = [raw_shifts]
    for sh in raw_shifts or []:
        if not isinstance(sh, dict):
            continue
        s_min = parse_time(sh.get("start_time") or sh.get("open") or sh.get("from"))
        e_min = parse_time(sh.get("end_time") or sh.get("close") or sh.get("to"))
        if s_min is None or e_min is None:
            continue
        if s_min == e_min:
            continue
        shifts.append((s_min, e_min))
    if status == "declared":
        return DayHours("declared", tuple(shifts)) if shifts else DayHours("closed", ())
    if status == "closed":
        return DayHours("closed", ())
    if status == "unsupported":
        return DayHours("unsupported", ())
    return DayHours("unknown", tuple(shifts))


DAY_ALIASES = {
    "sat": "sat", "saturday": "sat", "sh": "sat", "شنبه": "sat",
    "sun": "sun", "sunday": "sun", "یک‌شنبه": "sun", "یکشنبه": "sun", "يكشنبه": "sun",
    "mon": "mon", "monday": "mon", "دوشنبه": "mon",
    "tue": "tue", "tuesday": "tue", "سه‌شنبه": "tue", "سهشنبه": "tue", "سه شنبه": "tue",
    "wed": "wed", "wednesday": "wed", "چهارشنبه": "wed", "چهار‌شنبه": "wed",
    "thu": "thu", "thursday": "thu", "پنج‌شنبه": "thu", "پنجشنبه": "thu", "پنج شنبه": "thu",
    "fri": "fri", "friday": "fri", "جمعه": "fri",
    # numeric weeks: the dataset is Saturday-first
    "0": "sat", "1": "sun", "2": "mon", "3": "tue", "4": "wed", "5": "thu", "6": "fri",
}


def _canonical_week(raw: dict) -> dict:
    out: dict = {}
    for key, value in raw.items():
        name = str(key).strip().lower().replace("\u200c", "").replace("-", " ")
        canonical = DAY_ALIASES.get(name) or DAY_ALIASES.get(name.replace(" ", ""))
        if canonical:
            out[canonical] = value
    return out


def parse_week(raw: dict | None) -> dict[str, DayHours]:
    """Normalise a weekly schedule whatever the day keys look like.

    The export has used ``sat``/``saturday``/``شنبه`` and ``0..6`` across versions;
    all of them map to the same seven slots. Unknown keys are ignored, missing days
    stay **unknown**.
    """
    raw = _canonical_week(raw or {}) if isinstance(raw, dict) else {}
    return {k: parse_day(raw.get(k)) for k in _DAY_KEYS}


def _intervals_for(week: dict[str, DayHours], day: date) -> list[tuple[int, int]]:
    """Intervals (in minutes from that day's midnight) including yesterday's
    cross-midnight tail spilling into ``day``."""
    key = _DAY_KEYS[day.weekday()]
    out: list[tuple[int, int]] = []
    dh = week.get(key, DayHours("unknown", ()))
    if dh.status == "declared":
        for s, e in dh.shifts:
            out.append((s, e if e > s else e + 24 * 60))
    prev = day - timedelta(days=1)
    pkey = _DAY_KEYS[prev.weekday()]
    pdh = week.get(pkey, DayHours("unknown", ()))
    if pdh.status == "declared":
        for s, e in pdh.shifts:
            if e <= s:  # crosses midnight → tail belongs to today
                out.append((0, e))
    return out


def _at_minute(now: datetime) -> int:
    return now.hour * 60 + now.minute


def open_status(week: dict[str, DayHours], now: datetime | None = None) -> OpenStatus:
    now = (now or datetime.now(TEHRAN)).astimezone(TEHRAN)
    today = now.date()
    minute = _at_minute(now)
    key = _DAY_KEYS[today.weekday()]
    day = week.get(key, DayHours("unknown", ()))

    intervals = _intervals_for(week, today)
    for s, e in intervals:
        if s <= minute < e:
            return OpenStatus(
                "open",
                closes_at=_fmt(e),
                minutes_until_close=e - minute,
                day_status=day.status,
            )

    # closed right now: distinguish "known closed" from "unknown"
    if day.status == "unknown" or day.status == "unsupported":
        # yesterday's schedule may still be running (rare, handled above),
        # otherwise we honestly do not know.
        return OpenStatus("unknown", day_status=day.status)

    upcoming = sorted(s for s, _ in intervals if s > minute)
    nxt = None
    if not upcoming:
        for step in range(1, 8):
            d = today + timedelta(days=step)
            iv = _intervals_for(week, d)
            if iv:
                key2 = _DAY_KEYS[d.weekday()]
                if week.get(key2, DayHours("unknown", ())).status == "declared":
                    nxt = (DAY_FA[key2], _fmt(min(iv)[0]))
                    break
    return OpenStatus(
        "closed",
        opens_at=_fmt(upcoming[0]) if upcoming else None,
        day_status=day.status,
        next_open_day=nxt[0] if nxt else None,
    )


def open_at(week: dict[str, DayHours], at: datetime) -> OpenStatus:
    return open_status(week, at)


def _shift_end_for_arrival(week: dict[str, DayHours], at: datetime) -> int | None:
    """Minutes until close if open at ``at``; else None."""
    at = at.astimezone(TEHRAN)
    minute = _at_minute(at)
    for s, e in _intervals_for(week, at.date()):
        if s <= minute < e:
            return e - minute
    return None


def open_at_arrival(week, now: datetime, travel_minutes: int) -> OpenStatus:
    """Status at the moment the user would actually arrive."""
    return open_status(week, now + timedelta(minutes=max(0, travel_minutes)))


def will_be_open_for(week, now: datetime, travel_minutes: int, min_minutes: int = 20) -> bool:
    """True only when we are *sure* the shop is open on arrival for long enough."""
    arrival = now + timedelta(minutes=max(0, travel_minutes))
    remaining = _shift_end_for_arrival(week, arrival)
    if remaining is None:
        return False
    return remaining >= min_minutes


def week_display(week: dict[str, DayHours]) -> list[dict]:
    """Compact structure for the UI (no invented hours)."""
    out = []
    for key in DAY_ORDER:
        dh = week.get(key, DayHours("unknown", ()))
        if dh.status == "declared":
            label = " و ".join(f"{_fmt(s)}–{_fmt(e)}" for s, e in dh.shifts)
            out.append({"day": DAY_FA[key], "known": True, "text": label,
                        "closed": False, "ranges": [[s, e] for s, e in dh.shifts]})
        elif dh.status == "closed":
            out.append({"day": DAY_FA[key], "known": True, "text": "تعطیل",
                        "closed": True, "ranges": []})
        else:
            out.append({"day": DAY_FA[key], "known": False,
                        "text": "نامشخص", "closed": False, "ranges": []})
    return out


def is_hours_known(week: dict[str, DayHours]) -> bool:
    return any(dh.status in ("declared", "closed") for dh in week.values())
