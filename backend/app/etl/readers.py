"""CSV readers that match the dataset's conventions (master prompt §4.1).

* ``null`` is a literal string and must become ``None``
* JSON columns are strings and may be malformed → ``None`` + counter
* files are UTF-8 with a header row and may carry a BOM
"""
from __future__ import annotations

import csv
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

NULL_TOKENS = {"null", "NULL", "Null", "none", "None", ""}


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


def open_csv(path: Path) -> Iterator[dict]:
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            yield {k: (None if v is None else v) for k, v in row.items()}


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
        if stats:
            stats.json_bad += 1
        return None


def parse_float(value, stats: ParseStats | None = None) -> float | None:
    s = clean(value)
    if s is None:
        return None
    s = s.replace(",", "").replace("،", "")
    try:
        return float(s)
    except ValueError:
        if stats:
            stats.bad_prices += 1
        return None


def parse_bool_tristate(value) -> str:
    """``true``/``false``/``unknown`` — never guess (§3.1)."""
    s = (clean(value) or "").lower()
    if s == "true":
        return "true"
    if s == "false":
        return "false"
    return "unknown"


def find_dataset_file(data_dir: Path, name: str) -> Path | None:
    for candidate in (data_dir / f"{name}.csv", data_dir / f"{name}.CSV"):
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
