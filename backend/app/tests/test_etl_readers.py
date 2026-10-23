"""ETL robustness against real-world dataset quirks."""
import csv
import json
import zipfile
from pathlib import Path

from app.etl.readers import (
    canonical_headers,
    clean,
    dataset_mode,
    find_dataset_file,
    open_csv,
    parse_bool_tristate,
    parse_float,
    parse_json,
)
from app.etl.normalize import to_ascii_digits


def test_null_tokens_become_none():
    assert clean("null") is None
    assert clean(" NULL ") is None
    assert clean("") is None
    assert clean("متفرقه") == "متفرقه"


def test_price_variants():
    assert parse_float("۲٬۴۵۰٬۰۰۰") == 2_450_000
    assert parse_float("2,450,000 تومان") == 2_450_000
    assert parse_float("2450000.0") == 2_450_000
    assert parse_float("null") is None
    assert parse_float("تماس بگیرید") is None


def test_bool_tristate_never_guesses():
    assert parse_bool_tristate("true") == "true"
    assert parse_bool_tristate("1") == "true"
    assert parse_bool_tristate("false") == "false"
    assert parse_bool_tristate("unknown") == "unknown"
    assert parse_bool_tristate("شاید") == "unknown"


def test_broken_json_returns_none_and_counts():
    stats = type("S", (), {"json_bad": 0, "json_ok": 0})()
    assert parse_json("{broken", stats) is None
    assert stats.json_bad == 1
    assert parse_json('{"a":1}', stats) == {"a": 1}
    assert stats.json_ok == 1


def test_header_aliases():
    mapping = canonical_headers(
        ["ShopId", "shop name", "price", "Last Price Changed At", "lng", "brand"]
    )
    assert mapping["ShopId"] == "shop_id"
    assert mapping["shop name"] == "name"
    assert mapping["price"] == "price_toman"
    assert mapping["Last Price Changed At"] == "last_price_changed_at"
    assert mapping["lng"] == "lon"
    assert mapping["brand"] == "brand_name"


def test_semicolon_delimiter_and_bom(tmp_path: Path):
    p = tmp_path / "offers.csv"
    p.write_text("\ufeffshop_id;price;product_id\nshop_1;۲۵۰۰۰۰۰;product_1\n", encoding="utf-8")
    rows = list(open_csv(p))
    assert rows[0]["shop_id"] == "shop_1"
    assert rows[0]["price_toman"] == "۲۵۰۰۰۰۰"      # header alias normalised
    assert rows[0]["product_id"] == "product_1"


def test_zip_bundle_is_found(tmp_path: Path):
    csv_path = tmp_path / "shops.csv"
    csv_path.write_text("shop_id,name,lat,lon\ns1,مغازه,35.7,51.4\n", encoding="utf-8")
    bundle = tmp_path / "dataset.zip"
    with zipfile.ZipFile(bundle, "w") as zf:
        zf.write(csv_path, "dataset/shops.csv")
    csv_path.unlink()
    found = find_dataset_file(tmp_path, "shops")
    assert found is not None and found.exists()
    assert dataset_mode(tmp_path) == "missing"  # only one of the three tables


def test_quoted_values_with_delimiters(tmp_path: Path):
    p = tmp_path / "shops.csv"
    with open(p, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["shop_id", "name", "address"])
        w.writerow(["s1", "مغازه، شعبه دوم", "تهران، خیابان ولیعصر، پلاک ۱۲"])
    rows = list(open_csv(p))
    assert rows[0]["name"] == "مغازه، شعبه دوم"
    assert rows[0]["address"].startswith("تهران، خیابان")
    assert "پلاک ۱۲" in rows[0]["address"]


def test_extra_columns_do_not_crash(tmp_path: Path):
    p = tmp_path / "x.csv"
    p.write_text("shop_id,name,,\ns1,مغازه,extra1,extra2\n", encoding="utf-8")
    rows = list(open_csv(p))
    assert rows[0]["shop_id"] == "s1"


def test_persian_digits_helper():
    assert to_ascii_digits("۱۲۳۴") == "1234"
