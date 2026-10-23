import json
import re
import hashlib
from backend.app.etl.normalizer import normalize_persian, to_ascii_digits

KNOWN_BRANDS = [
    ("سامسونگ", "samsung"), ("اپل", "apple"), ("شیائومی", "xiaomi"),
    ("سونی", "sony"), ("ال جی", "lg"), ("ایسوس", "asus"),
    ("لنوو", "lenovo"), ("اچ پی", "hp"), ("دل", "dell"),
    ("ایسر", "acer"), ("ام اس آی", "msi"), ("هواوی", "huawei"),
    ("آنر", "honor"), ("نوکیا", "nokia"), ("جی بی ال", "jbl"),
    ("انکر", "anker"), ("کیو سی وای", "qcy"), ("هایلو", "haylou"),
    ("باسئوس", "baseus"), ("لاجیتک", "logitech"), ("ریزر", "razer"),
    ("داهوا", "dahua"), ("هایک ویژن", "hikvision"), ("کانن", "canon"),
    ("نیکون", "nikon"), ("بوش", "bosch"), ("فیلیپس", "philips"),
]

MODEL_TOKEN_RE = re.compile(r"\b([a-zA-Z]{1,6}[-\s]?\d{1,5}[a-zA-Z0-9\-]*)\b")

def parse_specs_compact(raw_specs: str | None, title: str = "") -> dict:
    """
    Rule 11 & 13: Parse heavy specs JSON array and extract compact key attributes
    for comparison & recommendation without bloating the serving DB.
    """
    compact = {}
    if raw_specs and raw_specs != "null":
        try:
            arr = json.loads(raw_specs)
            if isinstance(arr, list):
                for item in arr[:25]:
                    if isinstance(item, dict):
                        k = str(item.get("key", "")).strip()
                        v = str(item.get("value", "")).strip()
                        if k and v and len(v) <= 120:
                            compact[k] = v
        except Exception:
            pass

    t_norm = normalize_persian(title)
    # Enrich key highlights from title + specs
    combined_text = t_norm + " " + " ".join(f"{k} {v}" for k, v in compact.items())
    highlights = {}

    if any(w in combined_text for w in ["بی سیم", "بیسیم", "بلوتوث", "بلوتوثی", "wireless", "bluetooth", "tws"]):
        highlights["connectivity"] = "بی‌سیم (بلوتوث)"
    elif any(w in combined_text for w in ["با سیم", "باسیم", "سیمی", "wired"]):
        highlights["connectivity"] = "باسیم"

    if any(w in combined_text for w in ["نویز کنسلینگ", "anc", "noise cancelling", "حذف نویز"]):
        highlights["anc"] = "دارد (ANC)"

    ram_m = re.search(r"(\d{1,2})\s*(?:gb|گیگ|گیگابایت)\s*(?:ram|رم)", combined_text)
    if ram_m:
        highlights["ram"] = f"{ram_m.group(1)} گیگابایت"

    return {
        "specs_map": dict(list(compact.items())[:10]),
        "highlights": highlights
    }

def enrich_and_group_product(
    product_id: str,
    persian_title: str,
    brand_name: str | None,
    model_raw: str | None,
    category_name: str,
    specs_raw: str | None,
) -> dict:
    """
    Rule 11 & Rule 12:
    Extract brand, model tokens, compact specs, and conservative product_group_id.
    """
    title_norm = normalize_persian(persian_title)
    brand = brand_name if (brand_name and brand_name != "null") else None

    specs_info = parse_specs_compact(specs_raw, persian_title)
    specs_map = specs_info["specs_map"]

    if not brand:
        for b_key in ("برند", "شرکت سازنده", "نام تجاری"):
            if b_key in specs_map:
                brand = specs_map[b_key]
                break

    if not brand:
        for fa_b, en_b in KNOWN_BRANDS:
            if fa_b in title_norm or en_b in title_norm:
                brand = fa_b
                break

    model_token = model_raw if (model_raw and model_raw != "null") else None
    if not model_token:
        ascii_t = to_ascii_digits(persian_title).lower()
        tokens = MODEL_TOKEN_RE.findall(ascii_t)
        if tokens:
            model_token = " ".join(sorted(set(t.replace(" ", "") for t in tokens[:2])))

    # Rule 12: Conservative product grouping
    if brand and model_token and len(model_token) >= 3:
        group_key = f"{normalize_persian(category_name)}|{normalize_persian(brand)}|{model_token.lower()}"
        group_id = "grp_" + hashlib.md5(group_key.encode("utf-8")).hexdigest()[:12]
        is_approximate_group = True
    else:
        group_id = product_id
        is_approximate_group = False

    return {
        "brand_resolved": brand or "متفرقه / نامشخص",
        "model_resolved": model_token,
        "product_group_id": group_id,
        "is_approximate_group": is_approximate_group,
        "compact_specs_json": json.dumps(specs_info, ensure_ascii=False),
        "title_normalized": title_norm,
    }
