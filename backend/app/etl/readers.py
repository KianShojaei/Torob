"""CSV readers that match the dataset's conventions (master prompt §4.1).

Real-world tolerance, because the challenge dataset is not always delivered exactly
as documented:

* ``null`` is a literal string and must become ``None``
* JSON columns are strings and may be malformed → ``None`` + counter
* files are UTF-8 with a header row and may carry a BOM
* headers may be CamelCase / snake_case / have spaces / be slightly renamed
  (``price`` vs ``price_toman``, ``title`` vs ``persian_title``) → normalised
* the delimiter may be ``;`` or a tab → sniffed
* bundles may arrive as a ``.zip`` → transparently extracted
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from app.etl.normalize import to_ascii_digits

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

NULL_TOKENS = {"null", "NULL", "Null", "none", "None", "nan", "NaN", "\\N", ""}


@dataclass
class ParseStats:
    rows: int = 0
    nulls: int = 0
    json_ok: int = 0
    json_bad: int = 0
    bad_prices: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "rows": self.rows,
            "nulls": self.nulls,
            "json_ok": self.json_ok,
            "json_bad": self.json_bad,
            "bad_prices": self.bad_prices,
            "notes": self.notes[:20],
        }

# canonical name → accepted spellings (already lower-cased, separators collapsed)
ALIASES: dict[str, set[str]] = {
    # shops
    "shop_id": {"shop_id", "shopid", "shop id", "seller_id", "store_id", "id"},
    "name": {"name", "shop_name", "shop name", "seller_title", "title"},
    "address": {"address", "shop_address", "full_address", "addr"},
    "lat": {"lat", "latitude", "lat_deg"},
    "lon": {"lon", "lng", "long", "longitude", "lon_deg"},
    "location_label": {"location_label", "location", "neighbourhood", "neighborhood",
                       "area", "district"},
    "category_names": {"category_names", "categories", "category", "category_name"},
    "contacts": {"contacts", "contact", "phones", "phone", "phone_numbers"},
    "instagram": {"instagram", "instagram_url", "insta"},
    "website_url": {"website_url", "website", "site", "url"},
    "payment_options": {"payment_options", "payments", "payment", "installments"},
    "weekly_hours": {"weekly_hours", "hours", "opening_hours", "schedule"},
    "supports_fast_delivery": {"supports_fast_delivery", "fast_delivery", "express"},
    # products
    "product_id": {"product_id", "productid", "product id", "pid", "id"},
    "persian_title": {"persian_title", "title", "product_title", "name", "product_name"},
    "brand_name": {"brand_name", "brand", "brand_title"},
    "category_name": {"category_name", "category", "category_title"},
    "model": {"model", "model_name", "model_number"},
    "image_urls": {"image_urls", "images", "image_url", "image"},
    "specs": {"specs", "specifications", "attributes"},
    # offers
    "offer_id": {"offer_id", "offerid", "offer id", "id"},
    "price_toman": {"price_toman", "price", "amount", "price_irr", "price_toman_rial"},
    "last_price_changed_at": {"last_price_changed_at", "last_price_change", "price_updated_at",
                              "updated_at", "last_changed_at", "price_date"},
    "seller_title": {"seller_title", "seller", "seller_name", "offer_title"},
    "description": {"description", "desc", "details"},
    "warranty": {"warranty", "guarantee", "warranty_info"},
}


def _norm_header(name: str) -> str:
    s = (name or "").replace("\ufeff", "").strip().lower()
    s = re.sub(r"[^0-9a-z\u0600-\u06ff]+", " ", s).strip()
    return s


def canonical_headers(fieldnames: list[str]) -> dict[str, str]:
    """Map raw header → canonical column name (unknown headers are kept as-is)."""
    reverse: dict[str, str] = {}
    for canonical, spellings in ALIASES.items():
        for spelling in spellings:
            reverse.setdefault(spelling, canonical)
    out: dict[str, str] = {}
    for raw in fieldnames or []:
        if raw is None:
            continue
        key = _norm_header(raw)
        out[raw] = reverse.get(key, key.replace(" ", "_"))
    return out


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def normalize_row(row: dict, header_map: dict[str, str]) -> dict:
    """Canonicalise a raw DictReader row and strip ``null`` tokens."""
    out: dict = {}
    for raw, value in row.items():
        if raw is None:  # extra columns from a stray delimiter
            continue
        out[header_map.get(raw, raw)] = clean(value)
    return out


def open_csv(path: Path) -> Iterator[dict]:
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(8192)
        fh.seek(0)
        delimiter = _sniff_delimiter(sample)
        reader = csv.DictReader(fh, delimiter=delimiter)
        header_map = canonical_headers(reader.fieldnames or [])
        for row in reader:
            yield normalize_row(row, header_map)


def clean(value):
    """Trim and turn the literal ``null`` into ``None``."""
    if value is None:
        return None
    s = str(value).strip()
    if s in NULL_TOKENS:
        return None
    return s


def parse_json(value, stats: ParseStats | None = None) -> object | None:
    s = clean(value)
    if s is None:
        return None
    try:
        out = json.loads(s)
        if stats:
            stats.json_ok += 1
        return out
    except (json.JSONDecodeError, TypeError, ValueError):
        # some exports double-encode or use single quotes
        try:
            out = json.loads(s.replace("'", '"'))
            if stats:
                stats.json_ok += 1
            return out
        except (json.JSONDecodeError, TypeError, ValueError):
            if stats:
                stats.json_bad += 1
            return None


_NUMBER_CLEAN = re.compile(r"[^\d.\-]")


def parse_float(value, stats: ParseStats | None = None) -> float | None:
    """Accept ``۲٬۴۵۰٬۰۰۰``, ``2,450,000``, ``2450000.0`` and ``2450000 تومان``."""
    s = clean(value)
    if s is None:
        return None
    s = to_ascii_digits(s).replace(",", "").replace("٬", "").replace("،", "")
    s = s.replace("تومان", "").replace("ریال", "").replace(" ", "")
    s = _NUMBER_CLEAN.sub("", s)
    if not s or s in {"-", ".", "-."}:
        if stats:
            stats.bad_prices += 1
        return None
    try:
        return float(s)
    except ValueError:
        if stats:
            stats.bad_prices += 1
        return None


def parse_bool_tristate(value) -> str:
    """``true``/``false``/``unknown`` — never guess (§3.1)."""
    s = (clean(value) or "").lower()
    if s in {"true", "1", "yes", "y", "بله"}:
        return "true"
    if s in {"false", "0", "no", "n", "خیر"}:
        return "false"
    return "unknown"


def _extract_zip(path: Path) -> Path | None:
    """Extract a dataset bundle next to the CSVs and return the folder."""
    target = path.parent / "_extracted"
    if (target / "shops.csv").exists() and (target / "offers.csv").exists():
        return target
    target.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(path) as zf:
            for member in zf.namelist():
                if member.lower().endswith(".csv"):
                    with zf.open(member) as src, open(target / Path(member).name, "wb") as dst:
                        dst.write(src.read())
    except (zipfile.BadZipFile, OSError):
        return None
    return target


def find_dataset_file(data_dir: Path, name: str) -> Path | None:
    for candidate in (data_dir / f"{name}.csv", data_dir / f"{name}.CSV"):
        if candidate.exists():
            return candidate
    # a bundled zip anywhere in data/
    for bundle in sorted(data_dir.glob("*.zip")):
        extracted = _extract_zip(bundle)
        if extracted:
            candidate = extracted / f"{name}.csv"
            if candidate.exists():
                return candidate
    return None


def dataset_mode(data_dir: Path) -> str:
    """``real`` when the three CSVs exist, ``synthetic`` when truth file exists."""
    needed = ["shops", "products", "offers"]
    have = [find_dataset_file(data_dir, n) for n in needed]
    if all(have):
        if (data_dir / "synthetic_truth.json").exists():
            return "synthetic"
        return "real"
    return "missing"


def read_text(path: Path) -> str:
    return io.TextIOWrapper(open(path, "rb"), encoding="utf-8-sig").read()
