"""End-to-end ETL on a tiny dataset shaped like the real Torob export.

These tests exist because the real CSVs are not in the repository: the fixture below
reproduces the documented pathologies (null strings, duplicate offers, invalid prices,
`unsupported` hours, mall addresses, missing brands) so the pipeline is still proven
before the real bundle arrives.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SHOPS = [
    {
        "shop_id": "shop_a",
        "name": "دیجیتال آلتون",
        "address": "تهران، خیابان ولیعصر، پاساژ آلتون، طبقه ۲، واحد ۲۰۵",
        "lat": "35.7442", "lon": "51.4095", "location_label": "سعادت‌آباد",
        "category_names": json.dumps(["هدفون، هندزفری و اسپیکر"], ensure_ascii=False),
        "contacts": json.dumps([{"channel": "phone", "display_number": "۰۲۱۱۲۳۴۵۶۷۸"}],
                               ensure_ascii=False),
        "instagram": "https://instagram.com/example", "website_url": "null",
        "payment_options": json.dumps(
            [{"provider_name": "اسنپ‌پی", "channel": "in_person",
              "installment_plans": [{"months": 4, "min_price": 0, "max_price": 0}]}],
            ensure_ascii=False),
        "weekly_hours": json.dumps(
            {"saturday": {"open": "10:00", "close": "21:00"},
             "sunday": {"open": "10:00", "close": "21:00"},
             "monday": "unsupported",
             "tuesday": {"open": "22:00", "close": "02:00"},
             "wednesday": {"open": "10:00", "close": "21:00"},
             "thursday": {"open": "10:00", "close": "21:00"},
             "friday": {"open": "10:00", "close": "21:00"}},
            ensure_ascii=False),
        "supports_fast_delivery": "true",
    },
    {
        "shop_id": "shop_b",
        "name": "صوتی تصویری ونک",
        "address": "تهران، خیابان ملاصدرا، پلاک ۱۲",
        "lat": "35.7570", "lon": "51.4100", "location_label": "ونک",
        "category_names": json.dumps(["هدفون، هندزفری و اسپیکر"], ensure_ascii=False),
        "contacts": json.dumps([{"channel": "whatsapp", "display_number": "۰۹۱۲۰۰۰۰۰۰۰"}],
                               ensure_ascii=False),
        "instagram": "null", "website_url": "null",
        "payment_options": "null",
        "weekly_hours": "null",
        "supports_fast_delivery": "null",
    },
    {
        "shop_id": "shop_c",
        "name": "مغازه بدون مختصات",
        "address": "null",
        "lat": "null", "lon": "null", "location_label": "null",
        "category_names": "null", "contacts": "null", "instagram": "null",
        "website_url": "null", "payment_options": "null", "weekly_hours": "null",
        "supports_fast_delivery": "null",
    },
]

PRODUCTS = [
    {
        "product_id": "product_1",
        "persian_title": "انکر هدفون بلوتوثی A167 خاکستری",
        "brand_name": "انکر",
        "category_name": "هدفون، هندزفری و اسپیکر",
        "model": "A167",
        "image_urls": json.dumps(["https://image.torob.com/x.jpg"]),
        "specs": json.dumps([{"key": "نوع اتصال", "value": "بلوتوث"}], ensure_ascii=False),
    },
    {
        "product_id": "product_2",
        "persian_title": "هدفون سیمی بی‌نام",
        "brand_name": "null",
        "category_name": "هدفون، هندزفری و اسپیکر",
        "model": "null",
        "image_urls": "null",
        "specs": "{broken json",
    },
]

OFFERS = [
    # valid
    {"offer_id": "o1", "shop_id": "shop_a", "product_id": "product_1",
     "price_toman": "۲٬۴۵۰٬۰۰۰", "last_price_changed_at": "2026-10-10T10:00:00+00:00",
     "seller_title": "هدفون A167", "description": "null", "warranty": "null"},
    # duplicate pair, newer → wins
    {"offer_id": "o2", "shop_id": "shop_a", "product_id": "product_1",
     "price_toman": "2390000", "last_price_changed_at": "2026-10-12T10:00:00+00:00",
     "seller_title": "هدفون A167", "description": "null", "warranty": "null"},
    # null price
    {"offer_id": "o3", "shop_id": "shop_b", "product_id": "product_1",
     "price_toman": "null", "last_price_changed_at": "2026-09-01T10:00:00+00:00",
     "seller_title": "هدفون A167", "description": "null", "warranty": "null"},
    # zero price
    {"offer_id": "o4", "shop_id": "shop_b", "product_id": "product_2",
     "price_toman": "0", "last_price_changed_at": "2026-10-01T10:00:00+00:00",
     "seller_title": "هدفون", "description": "null", "warranty": "null"},
    # above the 5e9 ceiling
    {"offer_id": "o5", "shop_id": "shop_c", "product_id": "product_2",
     "price_toman": "99999999999", "last_price_changed_at": "2026-10-01T10:00:00+00:00",
     "seller_title": "هدفون", "description": "null", "warranty": "null"},
    # a second valid offer for product_2 so stats exist
    {"offer_id": "o6", "shop_id": "shop_a", "product_id": "product_2",
     "price_toman": "890000", "last_price_changed_at": "2026-08-01T10:00:00+00:00",
     "seller_title": "هدفون سیمی", "description": "null", "warranty": "null"},
]


def _write(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("realish")
    data = root / "data"
    data.mkdir()
    _write(data / "shops.csv", SHOPS)
    _write(data / "products.csv", PRODUCTS)
    _write(data / "offers.csv", OFFERS)
    db = root / "app.db"
    proc = subprocess.run(
        [sys.executable, "-m", "app.etl.build", "--data", str(data), "--db", str(db)],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return db


@pytest.fixture(scope="module")
def conn(built: Path):
    c = sqlite3.connect(built)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def test_no_duplicate_pairs(conn):
    dup = conn.execute(
        "SELECT COUNT(*) FROM (SELECT shop_id, product_id FROM offers "
        "GROUP BY shop_id, product_id HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    assert dup == 0


def test_duplicate_keeps_the_latest_price(conn):
    row = conn.execute(
        "SELECT price FROM offers WHERE shop_id='shop_a' AND product_id='product_1'"
    ).fetchone()
    assert row is not None
    assert int(row["price"]) == 2_390_000


def test_invalid_prices_are_kept_but_flagged(conn):
    rows = {r["price"]: r["price_valid"] for r in conn.execute(
        "SELECT price, price_valid FROM offers WHERE product_id='product_2'")}
    assert rows.get(0.0) == 0
    assert rows.get(99999999999.0) == 0
    assert 890000.0 in {p for p, valid in rows.items() if valid == 1}


def test_null_price_marks_the_product_unpriced(conn):
    row = conn.execute("SELECT price_median, offer_count FROM products WHERE id='product_1'")
    product = row.fetchone()
    # only the valid 2.39M offer counts; the null one must not become a price
    assert product["price_median"] == 2_390_000


def test_hours_unsupported_is_unknown_not_closed(conn):
    row = conn.execute("SELECT hours_known FROM shops WHERE id='shop_a'").fetchone()
    assert row["hours_known"] == 1  # other days are known
    b = conn.execute("SELECT hours_known FROM shops WHERE id='shop_b'").fetchone()
    assert b["hours_known"] == 0


def test_mall_and_unit_extracted(conn):
    row = conn.execute(
        "SELECT mall_name, floor, unit, addr_confidence FROM shops WHERE id='shop_a'"
    ).fetchone()
    assert row["mall_name"] == "پاساژ آلتون"
    assert row["floor"] == "2"
    assert row["unit"] == "205"
    assert row["addr_confidence"] >= 0.8

    b = conn.execute("SELECT addr_confidence FROM shops WHERE id='shop_b'").fetchone()
    assert b["addr_confidence"] < 0.8


def test_installment_only_confirmed_for_in_person(conn):
    a = conn.execute(
        "SELECT has_in_person_installment, has_any_installment FROM shops WHERE id='shop_a'"
    ).fetchone()
    assert a["has_in_person_installment"] == 1 and a["has_any_installment"] == 1
    b = conn.execute(
        "SELECT has_in_person_installment, has_any_installment FROM shops WHERE id='shop_b'"
    ).fetchone()
    assert b["has_in_person_installment"] == 0 and b["has_any_installment"] == 0


def test_missing_brand_is_null_not_invented(conn):
    row = conn.execute("SELECT brand FROM products WHERE id='product_2'").fetchone()
    assert row["brand"] is None


def test_broken_specs_json_does_not_crash(conn):
    row = conn.execute("SELECT specs FROM products WHERE id='product_2'").fetchone()
    assert row["specs"] in (None, "[]")


def test_shop_without_coordinates_is_kept_for_search(conn):
    row = conn.execute("SELECT lat, lon FROM shops WHERE id='shop_c'").fetchone()
    assert row["lat"] is None and row["lon"] is None
