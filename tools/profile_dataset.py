#!/usr/bin/env python3
"""
پروفایلر دیتاست چالش ترب.

بدون هیچ وابستگی خارجی کار می‌کند و روی فایل zip یا پوشه‌ی CSV اجرا می‌شود.

نمونه اجرا:
    python3 tools/profile_dataset.py data/starcoach-dataset.zip
    python3 tools/profile_dataset.py data/ --out reports

خروجی:
    reports/dataset-profile.md
    reports/dataset-profile.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

MAX_UNIQUE_TRACK = 20_000
MAX_EXAMPLES = 3
MAX_VALUES_FOR_STATS = 200_000

TEHRAN_LAT = (35.55, 35.90)
TEHRAN_LNG = (51.10, 51.65)

PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")
URL_RE = re.compile(r"^https?://|instagram\.com|wa\.me|t\.me|ble\.ir", re.I)
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2})?")
JALALI_DATE_RE = re.compile(r"^1[34]\d{2}[/-]\d{1,2}[/-]\d{1,2}")
EPOCH_RE = re.compile(r"^1[5-9]\d{8}(\d{3})?$")

def is_id_column(name: str) -> bool:
    """تشخیص ستون شناسه؛ از تطبیق سادهٔ زیررشته («provider» ≠ id) پرهیز می‌کند."""
    n = name.strip().lower()
    return n in ("id", "شناسه", "کد") or n.endswith("_id") or n.endswith("id") or n.endswith("شناسه")


LAT_HINTS = ("lat", "latitude", "عرض")
LNG_HINTS = ("lng", "lon", "long", "longitude", "طول")
PRICE_HINTS = ("price", "قیمت", "مبلغ")
PHONE_HINTS = ("phone", "mobile", "tel", "تلفن", "موبایل", "همراه")


# --------------------------------------------------------------------------- #
# ورودی
# --------------------------------------------------------------------------- #
def detect_encoding(head: bytes) -> str:
    """کدگذاری را از ابتدای فایل حدس می‌زند؛ خطای مرز بلوک را نادیده می‌گیرد."""
    for enc in ("utf-8-sig", "cp1256"):
        try:
            head.decode(enc)
            return enc
        except UnicodeDecodeError as e:
            # کاراکتر چندبایتی که دقیقاً روی مرز ۶۴KB افتاده
            if e.start >= len(head) - 4:
                return enc
    return "latin-1"


def sniff_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def iter_csv_sources(path: Path):
    """جریان‌دهی به فایل‌ها بدون خواندن کل CSV در حافظه: (نام, حجم, file object)."""
    if path.is_dir():
        for p in sorted(path.rglob("*.csv")):
            if "__MACOSX" in str(p):
                continue
            with open(p, "rb") as fh:
                yield p.name, p.stat().st_size, fh
        return

    if path.is_file() and path.suffix.lower() == ".csv":
        with open(path, "rb") as fh:
            yield path.name, path.stat().st_size, fh
        return

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".csv"):
                    continue
                if "__MACOSX" in info.filename:
                    continue
                with zf.open(info) as fh:
                    yield Path(info.filename).name, info.file_size, fh
        return

    raise SystemExit(f"ورودی نه پوشه است نه zip: {path}")


# --------------------------------------------------------------------------- #
# تحلیل ستون
# --------------------------------------------------------------------------- #
def classify_value(v: str) -> str:
    """نوع تقریبی یک مقدار. ترتیب مهم است: تاریخ/لینک/بول قبل از عدد."""
    s = v.strip()
    if not s:
        return "empty"

    if URL_RE.search(s):
        return "url_like"

    low = s.lower()
    if low in ("true", "false", "yes", "no", "بله", "خیر"):
        return "bool_like"

    first = s[0]
    if first.isdigit() or first in "+-":
        if len(s) >= 7 and (
            ISO_DATE_RE.match(s) or JALALI_DATE_RE.match(s) or EPOCH_RE.match(s)
        ):
            return "date_like"

        # شماره‌ی موبایل/تلفن: طول مشخص و شروع با 0 یا +98
        digits = re.sub(r"\D", "", s)
        if (
            (s.startswith("0") or s.startswith("+98") or s.startswith("0098"))
            and 10 <= len(digits) <= 13
        ):
            return "phone_like"

        cleaned = s.replace(",", "").replace("٬", "")
        try:
            int(cleaned)
            return "int_like"
        except ValueError:
            pass
        try:
            float(cleaned.replace("%", ""))
            return "float_like"
        except ValueError:
            pass

    return "text"


def to_number(v: str):
    s = v.strip().replace(",", "").replace("٬", "").replace("،", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def percentile(sorted_vals, q):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return sorted_vals[int(k)]
    return sorted_vals[lo] * (hi - k) + sorted_vals[hi] * (k - lo)


class ColumnProfile:
    def __init__(self, name: str):
        self.name = name
        self.count = 0
        self.null = 0
        self.empty = 0
        self.types: Counter[str] = Counter()
        self.unique: set[str] = set()
        self.unique_overflow = False
        self.examples: list[str] = []
        self.min_len = None
        self.max_len = 0
        self.persian_hits = 0
        self.numbers: list[float] = []
        self.top: Counter[str] = Counter()
        self.date_formats: Counter[str] = Counter()

    def add(self, raw: str):
        self.count += 1
        if raw is None:
            self.null += 1
            return
        s = raw.strip()
        if not s:
            self.empty += 1
            return

        kind = classify_value(s)

        # اگر نام ستون صراحتاً تلفن است، حتی بدون 0 ابتدایی هم شماره حساب می‌شود
        if kind != "phone_like" and any(h in self.name.lower() for h in PHONE_HINTS):
            if re.fullmatch(r"\+?[\d\s()\-]{8,16}", s):
                kind = "phone_like"

        self.types[kind] += 1

        if len(self.examples) < MAX_EXAMPLES:
            self.examples.append(s[:180])

        L = len(s)
        self.min_len = L if self.min_len is None else min(self.min_len, L)
        self.max_len = max(self.max_len, L)

        if PERSIAN_RE.search(s):
            self.persian_hits += 1

        if not self.unique_overflow:
            self.unique.add(s[:120])
            if len(self.unique) >= MAX_UNIQUE_TRACK:
                self.unique_overflow = True
                self.unique.clear()

        # کاردینالیتی کم → top values
        if len(self.top) < 5000 or s in self.top:
            self.top[s[:120]] += 1

        if kind in ("int_like", "float_like") and len(self.numbers) < MAX_VALUES_FOR_STATS:
            n = to_number(s)
            if n is not None:
                self.numbers.append(n)

        if kind == "date_like":
            if ISO_DATE_RE.match(s):
                self.date_formats["ISO"] += 1
            elif JALALI_DATE_RE.match(s):
                self.date_formats["Jalali"] += 1
            elif EPOCH_RE.match(s):
                self.date_formats["epoch"] += 1

    def summary(self) -> dict:
        present = self.count - self.null - self.empty
        dominant = self.types.most_common(1)[0][0] if self.types else "empty"
        nums = sorted(self.numbers)
        out = {
            "name": self.name,
            "non_empty": present,
            "null_or_empty": self.null + self.empty,
            "null_rate": round((self.null + self.empty) / self.count, 4) if self.count else None,
            "dominant_type": dominant,
            "type_counts": dict(self.types),
            "distinct_estimated": (
                None if self.unique_overflow else len(self.unique)
            ),
            "distinct_overflow": self.unique_overflow,
            "min_length": self.min_len,
            "max_length": self.max_len,
            "persian_ratio": round(self.persian_hits / present, 4) if present else None,
            "examples": self.examples,
        }

        numeric_share = (
            (self.types.get("int_like", 0) + self.types.get("float_like", 0)) / present
            if present
            else 0
        )
        if nums and numeric_share >= 0.8:
            out["numeric"] = {
                "count": len(nums),
                "min": nums[0],
                "p05": round(percentile(nums, 0.05), 4),
                "median": round(percentile(nums, 0.5), 4),
                "p95": round(percentile(nums, 0.95), 4),
                "max": nums[-1],
                "zeros": sum(1 for n in nums if n == 0),
                "negatives": sum(1 for n in nums if n < 0),
            }
        if self.date_formats:
            out["date_formats"] = dict(self.date_formats)

        if present and len(self.top) <= 200 and not self.unique_overflow:
            out["top_values"] = self.top.most_common(10)

        lname = self.name.lower()
        if any(h in lname for h in LAT_HINTS + LNG_HINTS) and nums:
            lo, hi = (TEHRAN_LAT if any(h in lname for h in LAT_HINTS) else TEHRAN_LNG)
            outside = sum(1 for n in nums if not (lo <= n <= hi))
            out["geo_check"] = {
                "expected_range": [lo, hi],
                "outside_range": outside,
                "outside_rate": round(outside / len(nums), 4),
            }
        if any(h in lname for h in PRICE_HINTS) and nums:
            out["price_check"] = {
                "zeros": sum(1 for n in nums if n == 0),
                "negatives": sum(1 for n in nums if n < 0),
                "median": round(percentile(nums, 0.5), 2),
                "max": max(nums),
            }
        return out


def profile_table(name: str, fh) -> dict:
    head = fh.read(65536)
    enc = detect_encoding(head)
    dialect = sniff_dialect(head.decode(enc, errors="replace"))

    fh.seek(0)
    text = io.TextIOWrapper(fh, encoding=enc, errors="replace", newline="")

    reader = csv.DictReader(text, dialect=dialect)
    raw_headers = reader.fieldnames or []
    headers = [h for h in raw_headers if h is not None]
    duplicate_headers = sorted({h for h, c in Counter(headers).items() if c > 1})
    missing_headers = sum(1 for h in raw_headers if h is None)

    cols = {h: ColumnProfile(h) for h in headers}
    rows = 0
    extra_fields = 0
    id_sets: dict[str, set[str]] = defaultdict(set)

    for row in reader:
        rows += 1
        if None in row:
            extra_fields += 1
        for h in headers:
            v = row.get(h, "")
            cols[h].add(v)
            if v and is_id_column(h) and len(id_sets[h]) < 400_000:
                id_sets[h].add(v.strip())

    return {
        "table": Path(name).stem,
        "file": name,
        "encoding": enc,
        "delimiter": repr(dialect.delimiter),
        "rows": rows,
        "columns_count": len(headers),
        "columns": headers,
        "duplicate_headers": duplicate_headers,
        "missing_headers": missing_headers,
        "malformed_rows": extra_fields,
        "profiles": [cols[h].summary() for h in headers],
        "_id_sets": {k: v for k, v in id_sets.items()},
    }


# --------------------------------------------------------------------------- #
# خروجی
# --------------------------------------------------------------------------- #
def build_key_insights(tables: list[dict]) -> list[str]:
    notes = []
    for t in tables:
        if t.get("duplicate_headers"):
            notes.append(f"`{t['table']}`: ستون تکراری → {', '.join(t['duplicate_headers'])}")
        if t.get("missing_headers"):
            notes.append(f"`{t['table']}`: {t['missing_headers']} ستون بدون نام.")
        for p in t["profiles"]:
            name = p["name"].lower()
            if p.get("geo_check") and p["geo_check"]["outside_rate"] > 0.01:
                notes.append(
                    f"`{t['table']}.{p['name']}`: {p['geo_check']['outside_rate']*100:.1f}% خارج از محدوده‌ی تهران."
                )
            if p.get("price_check") and (p["price_check"]["zeros"] or p["price_check"]["negatives"]):
                notes.append(
                    f"`{t['table']}.{p['name']}`: {p['price_check']['zeros']} قیمت صفر و "
                    f"{p['price_check']['negatives']} قیمت منفی."
                )
            if p["null_rate"] is not None and p["null_rate"] > 0.9:
                notes.append(f"`{t['table']}.{p['name']}`: بالای ۹۰٪ خالی — قابل اتکا نیست.")
    return notes


def join_report(tables: list[dict]) -> list[dict]:
    """همپوشانی کلیدهای شناسه بین جدول‌ها."""
    out = []
    for i, a in enumerate(tables):
        for b in tables[i + 1:]:
            for ca, sa in a["_id_sets"].items():
                for cb, sb in b["_id_sets"].items():
                    if not sa or not sb:
                        continue
                    if ca.lower() == cb.lower() or (
                        ("shop" in ca.lower() and "shop" in cb.lower())
                        or ("product" in ca.lower() and "product" in cb.lower())
                    ):
                        inter = len(sa & sb)
                        out.append(
                            {
                                "left": f"{a['table']}.{ca}",
                                "right": f"{b['table']}.{cb}",
                                "left_unique": len(sa),
                                "right_unique": len(sb),
                                "overlap": inter,
                                "left_coverage": round(inter / len(sa), 4),
                                "right_coverage": round(inter / len(sb), 4),
                            }
                        )
    return out


def render_markdown(result: dict) -> str:
    lines = [
        "# پروفایل دیتاست",
        "",
        f"- تعداد جداول: **{len(result['tables'])}**",
        f"- جمع ردیف‌ها: **{result['total_rows']:,}**",
        "",
    ]

    for t in result["tables"]:
        file_note = f" · فایل: `{t['file']}`" if t.get("file") and t["file"] != t["table"] else ""
        lines += [
            f"## `{t['table']}`",
            "",
            f"- کدگذاری: `{t['encoding']}` · جداکننده: `{t['delimiter']}`{file_note}",
            f"- ردیف‌ها: **{t['rows']:,}** · ستون‌ها: **{t['columns_count']}**",
            f"- ردیف‌های بدشکل: {t['malformed_rows']}",
        ]
        if t.get("duplicate_headers"):
            lines.append(f"- ⚠️ ستون‌های تکراری: {', '.join(t['duplicate_headers'])}")
        if t.get("missing_headers"):
            lines.append(f"- ⚠️ ستون‌های بدون نام: {t['missing_headers']}")
        lines += [
            "",
            "| ستون | نوع غالب | خالی | یکتا | نمونه |",
            "|---|---|---:|---:|---|",
        ]
        for p in t["profiles"]:
            distinct = "—" if p["distinct_estimated"] is None else f"{p['distinct_estimated']:,}"
            ex = (p["examples"][0] if p["examples"] else "").replace("|", "\\|")[:60]
            lines.append(
                f"| `{p['name']}` | {p['dominant_type']} | "
                f"{(p['null_rate'] or 0)*100:.0f}% | {distinct} | {ex} |"
            )
        lines.append("")

        numeric_cols = [p for p in t["profiles"] if p.get("numeric")]
        if numeric_cols:
            lines += ["**ستون‌های عددی مهم:**", ""]
            for p in numeric_cols:
                n = p["numeric"]
                lines.append(
                    f"- `{p['name']}`: کمینه {n['min']:,} · میانه {n['median']:,} · "
                    f"بیشینه {n['max']:,} · صفرها {n['zeros']} · منفی {n['negatives']}"
                )
            lines.append("")

        date_cols = [p for p in t["profiles"] if p.get("date_formats")]
        if date_cols:
            lines += ["**ستون‌های تاریخ:**", ""]
            for p in date_cols:
                fmt = " · ".join(f"{k}: {v:,}" for k, v in p["date_formats"].items())
                lines.append(f"- `{p['name']}` → {fmt}")
            lines.append("")

        geo_cols = [p for p in t["profiles"] if p.get("geo_check")]
        if geo_cols:
            lines += ["**بررسی مختصات:**", ""]
            for p in geo_cols:
                g = p["geo_check"]
                lines.append(
                    f"- `{p['name']}`: {g['outside_range']:,} مقدار خارج از "
                    f"[{g['expected_range'][0]}, {g['expected_range'][1]}] "
                    f"({g['outside_rate']*100:.1f}%)"
                )
            lines.append("")

    if result["joins"]:
        lines += ["## همپوشانی کلیدها", "", "| چپ | راست | همپوشانی | پوشش چپ | پوشش راست |", "|---|---|---:|---:|---:|"]
        for j in result["joins"]:
            lines.append(
                f"| `{j['left']}` | `{j['right']}` | {j['overlap']:,} | "
                f"{j['left_coverage']*100:.1f}% | {j['right_coverage']*100:.1f}% |"
            )
        lines.append("")

    if result["insights"]:
        lines += ["## هشدارهای داده", ""] + [f"- {n}" for n in result["insights"]] + [""]

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="پروفایل دیتاست CSV چالش ترب")
    ap.add_argument("path", help="مسیر فایل zip یا پوشه‌ی CSV")
    ap.add_argument("--out", default="reports", help="پوشه‌ی خروجی")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"❌ مسیر پیدا نشد: {path}", file=sys.stderr)
        return 2

    csv.field_size_limit(10_000_000)

    tables = []
    for name, size, fh in iter_csv_sources(path):
        print(f"⏳ در حال خواندن {name} ({size/1e6:.1f} MB) ...")
        t = profile_table(name, fh)
        print(f"   ✓ {t['rows']:,} ردیف · {t['columns_count']} ستون")
        tables.append(t)

    if not tables:
        print("❌ هیچ فایل CSV پیدا نشد.", file=sys.stderr)
        return 1

    joins = join_report(tables)
    for t in tables:
        t.pop("_id_sets", None)

    result = {
        "tables": tables,
        "total_rows": sum(t["rows"] for t in tables),
        "joins": joins,
        "insights": build_key_insights(tables),
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dataset-profile.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "dataset-profile.md").write_text(render_markdown(result), encoding="utf-8")

    print(f"\n✅ خروجی: {out_dir/'dataset-profile.md'} و {out_dir/'dataset-profile.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
