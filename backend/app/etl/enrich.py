"""Product enrichment, grouping and key-spec extraction (master prompt §4.11, §4.12)."""
from __future__ import annotations

import re

from app.etl.normalize import detect_brand, fold, to_ascii_digits
from app.etl.taxonomy import CATEGORY_BY_NAME, key_specs_for

_MODEL_TOKEN_RE = re.compile(
    r"\b(?=[a-z0-9\-]*\d)[a-z0-9][a-z0-9\-]{2,18}\b"
)
_CAPACITY_RE = re.compile(r"\b(\d{1,4})\s*(gb|gigabyte|گیگابایت|tb|ترابایت|ترا)\b")
_VARIANT_WORDS = {
    "مشکی", "سفید", "نقره‌ای", "طلایی", "آبی", "خاکستری", "قرمز", "سبز",
    "صورتی", "بنفش", "black", "white", "silver", "gold", "blue",
}


def extract_brand(raw_brand: str | None, title: str, specs: list[dict] | None) -> str | None:
    """§4.11: brand_name → specs key → title dictionary."""
    if raw_brand:
        return raw_brand
    for row in specs or []:
        key = fold(row.get("key"))
        if key in ("نام تجاری", "برند", "شرکت سازنده", "سازنده"):
            if row.get("value"):
                return str(row["value"]).strip()
    return detect_brand(title)


def _spec_dict(specs: list[dict] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in specs or []:
        k = fold(row.get("key"))
        v = row.get("value")
        if k and v not in (None, ""):
            out[str(row.get("key"))] = str(v)
    return out


def extract_key_specs(category: str | None, specs: list[dict] | None) -> dict:
    """Keep only the category's key specs (table-driven, §4.11)."""
    wanted = [fold(s) for s in key_specs_for(category)]
    if not wanted:
        return {}
    flat = _spec_dict(specs)
    folded = {fold(k): (k, v) for k, v in flat.items()}
    out: dict[str, str] = {}
    for w in wanted:
        hit = folded.get(w)
        if hit:
            out[hit[0]] = hit[1]
    return out


def extract_model(title: str, model_field: str | None, specs: list[dict] | None) -> str | None:
    if model_field:
        return model_field
    for row in specs or []:
        if fold(row.get("key")) in ("مدل", "شماره مدل"):
            if row.get("value"):
                return str(row["value"])
    tokens = _MODEL_TOKEN_RE.findall(to_ascii_digits(title).lower())
    # prefer the longest alphanumeric token that contains a digit
    tokens = [t for t in tokens if not t.isdigit() or len(t) >= 6]
    if not tokens:
        return None
    return max(tokens, key=len)


def family_of(title: str, category: str | None) -> str:
    """First family phrase found in the title, else the category itself."""
    if category and category in CATEGORY_BY_NAME:
        cat = CATEGORY_BY_NAME[category]
        folded_title = fold(title)
        for fam in cat.families:
            if fold(fam) in folded_title:
                return fam
    # fall back to the first two words
    words = fold(title).split()
    return " ".join(words[:2]) if words else ""


def group_key(title: str, brand: str | None, model: str | None, category: str | None) -> str:
    """§4.12 — conservative grouping: same brand + model tokens + normalised title.

    Precision over recall: variants (colour, size) are stripped, but a different
    model number always yields a different group.
    """
    folded = fold(title)
    words = [w for w in folded.split() if w not in _VARIANT_WORDS]
    # drop capacity/size tokens that differ harmlessly between sellers
    base = " ".join(words)
    base = _CAPACITY_RE.sub(lambda m: f"{m.group(1)}{m.group(2)[:1]}", base)
    brand_key = fold(brand) if brand else ""
    model_key = to_ascii_digits(model or "").lower()
    if model_key and model_key in base:
        base = base.replace(model_key, " ")
    return "|".join(x for x in (fold(category or ""), brand_key, model_key, base.strip()) if x)


def pick_primary_image(image_urls) -> str | None:
    if isinstance(image_urls, list) and image_urls:
        first = image_urls[0]
        if isinstance(first, str) and first.startswith("http"):
            return first
    return None


def warranty_info(raw) -> tuple[str | None, int | None]:
    import json

    if raw is None:
        return None, None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return json.dumps({"description": raw}, ensure_ascii=False), None
    if not isinstance(raw, dict):
        return None, None
    months = raw.get("period_months")
    try:
        months = int(months) if months is not None else None
    except (TypeError, ValueError):
        months = None
    return json.dumps(raw, ensure_ascii=False), months
