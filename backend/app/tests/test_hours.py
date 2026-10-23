from datetime import datetime

import pytest

from app.services.hours import (
    TEHRAN,
    is_hours_known,
    open_at_arrival,
    open_status,
    parse_week,
    week_display,
    will_be_open_for,
)


def dt(y, m, d, hh=12, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=TEHRAN)


def week(**days):
    return parse_week(days)


def declared(*shifts):
    return {"status": "declared", "shifts": [
        {"start_time": a, "end_time": b} for a, b in shifts]}


def test_empty_hours_are_unknown_never_open():
    w = week()
    st = open_status(w, dt(2026, 10, 20, 12))
    assert st.state == "unknown"
    assert not is_hours_known(w)


def test_dummy_midnight_shift_is_not_24h():
    w = week(sat=declared(("00:00:00", "00:00:00")))
    st = open_status(w, dt(2026, 10, 24, 12))
    assert st.state == "closed"
    assert st.closes_at is None


def test_unsupported_is_unknown_not_closed():
    w = week(sat={"status": "unsupported", "shifts": []})
    assert open_status(w, dt(2026, 10, 24, 12)).state == "unknown"


def test_simple_open_and_close_boundaries():
    w = week(sat=declared(("10:00:00", "19:00:00")))
    sat = dt(2026, 10, 24)  # a Saturday
    assert sat.weekday() == 5
    assert open_status(w, sat.replace(hour=9, minute=59)).state == "closed"
    inside = open_status(w, sat.replace(hour=10, minute=0))
    assert inside.state == "open"
    assert inside.closes_at == "19:00"
    assert inside.minutes_until_close == 9 * 60
    assert open_status(w, sat.replace(hour=19, minute=0)).state == "closed"


def test_two_shifts_break_in_the_middle():
    w = week(sat=declared(("10:00:00", "14:00:00"), ("17:00:00", "21:00:00")))
    sat = dt(2026, 10, 24)
    assert open_status(w, sat.replace(hour=15)).state == "closed"
    assert open_status(w, sat.replace(hour=15)).opens_at == "17:00"
    assert open_status(w, sat.replace(hour=19)).state == "open"


def test_cross_midnight_shift_spills_into_next_day():
    # Thursday 22:00 -> 02:00 (Friday early morning)
    w = week(thu=declared(("22:00:00", "02:00:00")))
    thu = dt(2026, 10, 22, 23, 30)
    assert thu.weekday() == 3
    st = open_status(w, thu)
    assert st.state == "open"
    assert st.closes_at == "02:00"

    fri = dt(2026, 10, 23, 1, 30)
    assert open_status(w, fri).state == "open"
    assert open_status(w, fri.replace(hour=3)).state != "open"


def test_cross_midnight_gap_does_not_bleed_previous_day():
    w = week(wed=declared(("10:00:00", "18:00:00")), thu=declared(("22:00:00", "02:00:00")))
    # Thursday morning is not covered by Wednesday's 10-18 shift
    assert open_status(w, dt(2026, 10, 22, 9)).state == "closed"


def test_friday_closed_reports_next_open_day():
    w = week(mon=declared(("09:00:00", "18:00:00")),
             fri={"status": "closed", "shifts": [{"start_time": "00:00:00", "end_time": "00:00:00"}]})
    fri = dt(2026, 10, 30, 12)
    assert fri.weekday() == 4
    st = open_status(w, fri)
    assert st.state == "closed"
    assert st.next_open_day == "دوشنبه"


def test_hours_unknown_day_does_not_claim_closed_next_to_known_days():
    w = week(sat=declared(("10:00:00", "19:00:00")))
    sun = dt(2026, 10, 25, 12)
    assert open_status(w, sun).state == "unknown"


def test_arrival_and_min_stay():
    w = week(sat=declared(("10:00:00", "12:00:00")))
    sat = dt(2026, 10, 24, 11, 30)
    assert open_status(w, sat).state == "open"
    assert open_at_arrival(w, sat, 45).state == "closed"       # arrives 12:15
    assert will_be_open_for(w, sat, 20, min_minutes=20) is False  # only 10 min left
    assert will_be_open_for(w, sat, 5, min_minutes=20) is True


def test_week_display_marks_unknown_days():
    w = week(sat=declared(("10:00:00", "19:00:00")))
    rows = week_display(w)
    assert [r["day"] for r in rows][:3] == ["شنبه", "یک‌شنبه", "دوشنبه"]
    assert rows[0]["text"] == "10:00–19:00"
    assert rows[1]["known"] is False and rows[1]["text"] == "نامشخص"


@pytest.mark.parametrize("bad", [None, {}, {"status": "weird"}, {"status": "declared"}])
def test_bad_payloads_never_raise(bad):
    assert parse_week({"sat": bad})["sat"].status in ("unknown", "closed")
