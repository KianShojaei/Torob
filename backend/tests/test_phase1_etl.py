from datetime import datetime
import pytz
from backend.app.etl.normalizer import normalize_persian
from backend.app.etl.price_rules import validate_price, compute_price_age
from backend.app.etl.hours_engine import evaluate_open_status
from backend.app.etl.address_parser import parse_shop_address
from backend.app.etl.installment_parser import parse_payment_options

TEHRAN_TZ = pytz.timezone("Asia/Tehran")

def test_persian_normalizer():
    raw = "هدفونِ بی‌سیم اپل مدل AirPods Pro ٢ با كابل"
    norm = normalize_persian(raw)
    assert "هدفون بی سیم اپل مدل airpods pro 2 با کابل" == norm

def test_price_validation_rules():
    assert validate_price(None) == (None, "unknown")
    assert validate_price(0) == (None, "unknown")
    assert validate_price(500) == (None, "unknown")
    assert validate_price(15_000_000_000) == (None, "unknown")
    assert validate_price(3_500_000) == (3_500_000, "valid")

def test_price_age_buckets():
    fresh = compute_price_age("2026-10-10T12:00:00+00:00", "2026-10-13")
    assert fresh["bucket"] == "fresh"
    assert fresh["age_days"] == 3

    stale = compute_price_age("2025-01-01T12:00:00+00:00", "2026-10-13")
    assert stale["bucket"] == "stale"
    assert stale["is_stale"] is True

    unk = compute_price_age(None, "2026-10-13")
    assert unk["bucket"] == "unknown"

def test_hours_engine_dummy_and_cross_midnight():
    # Empty {} -> unknown
    res_empty = evaluate_open_status("{}")
    assert res_empty["status"] == "unknown"

    # Unsupported with dummy 08:00-08:00 -> must be unknown, NOT 24h open!
    wh_unsup = {"sat": {"status": "unsupported", "shifts": [{"start_time": "08:00", "end_time": "08:00"}]}}
    dt_sat = TEHRAN_TZ.localize(datetime(2026, 10, 10, 12, 0))  # Saturday
    res_unsup = evaluate_open_status(wh_unsup, dt_sat)
    assert res_unsup["status"] == "unknown"

    # Closed with dummy 00:00-00:00 -> closed
    wh_closed = {"fri": {"status": "closed", "shifts": [{"start_time": "00:00", "end_time": "00:00"}]}}
    dt_fri = TEHRAN_TZ.localize(datetime(2026, 10, 9, 14, 0))  # Friday
    res_closed = evaluate_open_status(wh_closed, dt_fri)
    assert res_closed["status"] == "closed"

    # Cross-midnight shift (Saturday 08:00 to 02:00 Sunday morning)
    wh_cross = {
        "sat": {"status": "declared", "shifts": [{"start_time": "08:00", "end_time": "02:00"}]},
        "sun": {"status": "closed", "shifts": []}
    }
    dt_sun_1am = TEHRAN_TZ.localize(datetime(2026, 10, 11, 1, 0))  # Sunday 01:00 AM
    res_cross = evaluate_open_status(wh_cross, dt_sun_1am)
    assert res_cross["status"] == "open"
    assert res_cross["minutes_until_close"] == 60

def test_address_parser_golden_examples():
    addr1 = "خیابان جمهوری، نبش شیخ هادی، پاساژ علاالدین 2، طبقه 6، واحد 622"
    p1 = parse_shop_address(addr1, "شیخ هادی")
    assert p1["mall_name"] == "پاساژ علاءالدین"
    assert p1["floor"] == "۶"
    assert p1["unit"] == "۶۲۲"
    assert p1["confidence"] == "high"

    addr2 = "میدان فردوسی، پاساژ تجارت جهانی فردوسی، طبقه منفی یک"
    p2 = parse_shop_address(addr2, "فردوسی")
    assert "فردوسی" in p2["mall_name"]
    assert p2["floor"] == "منفی یک"
    assert p2["unit"] is None
    assert "نامشخص" in p2["guide_summary_fa"]

def test_installment_parser():
    assert parse_payment_options("[]")["has_installment"] is False
    raw = '[{"provider_name": "ترب پی", "channel": "in_person", "min_price_toman": 0, "max_price_toman": 0}]'
    res = parse_payment_options(raw)
    assert res["has_installment"] is True
    assert res["installment_level"] == "in_person"
    assert res["details"][0]["min_price_toman"] is None
