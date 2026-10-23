import json
import math
import re
import sqlite3
from typing import Any

from backend.app.config import settings
from backend.app.etl.normalizer import normalize_persian, to_persian_digits
from backend.app.etl.price_rules import format_price_toman

SYNONYM_EXPANSIONS = {
    "هدفون": ["هدفون", "هندزفری", "هدست", "ایرپاد", "ایرباد"],
    "هندزفری": ["هندزفری", "هدفون", "ایرپاد", "هدست"],
    "ایرپاد": ["ایرپاد", "هدفون", "هندزفری", "airpods"],
    "موبایل": ["گوشی", "موبایل", "آیفون", "سامسونگ", "شیایومی"],
    "گوشی": ["گوشی", "موبایل"],
    "لپ تاپ": ["لپ تاپ", "لپتاپ", "نوت بوک", "مک بوک"],
    "ساعت هوشمند": ["ساعت هوشمند", "اسمارت واچ", "اپل واچ", "گالکسی واچ"],
    "پاوربانک": ["پاوربانک", "پاور بانک", "شارژر همراه"],
    "دوربین مداربسته": ["دوربین مدار بسته", "دوربین مداربسته", "داهوا", "هایک ویژن"],
    "اسپیکر": ["اسپیکر", "بلندگو"],
}

BRAND_SEARCH_VARIANTS = {
    "شیائومی": ["شیائومی", "شیایومی", "شیاومی", "xiaomi", "redmi", "ردمی", "poco", "پوکو", "haylou", "هایلو", "qcy"],
    "شیایومی": ["شیائومی", "شیایومی", "شیاومی", "xiaomi", "redmi", "ردمی", "poco", "پوکو", "haylou", "هایلو", "qcy"],
    "سامسونگ": ["سامسونگ", "samsung", "galaxy", "گلکسی"],
    "اپل": ["اپل", "apple", "iphone", "آیفون", "ایفون", "airpods", "ایرپاد", "macbook", "مک بوک"],
    "سونی": ["سونی", "sony"],
    "انکر": ["انکر", "anker", "soundcore", "ساندکور"],
    "لنوو": ["لنوو", "lenovo", "ideapad", "thinkpad"],
    "ایسوس": ["ایسوس", "asus", "vivobook", "tuf", "rog"],
    "اچ پی": ["اچ پی", "hp", "victus", "pavilion"],
}

ATTRIBUTE_AND_STOP_WORDS = {
    "باتری", "باطری", "باتریش", "باطریش", "شارژ", "شارژدهی", "دوربین", "دوربینش", "عکاسی", "فیلمبرداری",
    "صفحه", "نمایش", "مانیتور", "کیفیت", "صدا", "صداش", "میکروفون", "مکالمه", "نویز", "کنسلینگ", "anc",
    "سخت", "افزار", "پردازنده", "سی", "پی", "یو", "گرافیک", "رم", "حافظه", "سرعت", "قوی", "عالی",
    "خوب", "بهترین", "سبک", "وزن", "خوش", "دست", "مقاوم", "ضد", "آب", "گیمینگ", "بازی", "ورزشی",
    "ورزش", "مهندسی", "دانشجویی", "اداری", "روزمره", "اقتصادی", "ارزون", "ارزان", "خوش", "قیمت",
    "موبایلی", "گوشیی", "لپتاپی", "هدفونی", "میخوام", "میخواهم", "بخرم", "که", "داره", "داشته",
    "باشه", "باشد", "واسه", "برای", "اولویت", "اولویتش", "فقط", "اینه", "این", "من", "یه", "یک",
    "چیز", "مدل", "مدلی", "پیشنهاد", "معرفی", "تهران", "حضوری", "قسطی", "اقساطی"
}

SUPPORTED_CITIES = [
    {"id": "tehran", "name_fa": "تهران", "active": True, "lat": 35.6961, "lon": 51.4078, "shop_count": 6476},
    {"id": "karaj", "name_fa": "کرج", "active": False, "lat": 35.8400, "lon": 50.9391, "shop_count": 0},
    {"id": "mashhad", "name_fa": "مشهد", "active": False, "lat": 36.2972, "lon": 59.6067, "shop_count": 0},
    {"id": "isfahan", "name_fa": "اصفهان", "active": False, "lat": 32.6539, "lon": 51.6660, "shop_count": 0},
    {"id": "shiraz", "name_fa": "شیراز", "active": False, "lat": 29.5926, "lon": 52.5836, "shop_count": 0},
    {"id": "tabriz", "name_fa": "تبریز", "active": False, "lat": 38.0962, "lon": 46.2738, "shop_count": 0},
]

CATEGORY_GUIDED_QUESTIONS = {
    "هدفون": [
        {
            "id": "usage",
            "question_fa": "کاربرد و اولویت شما در هدفون",
            "options": [
                {"label": "همه کاربردها", "chip_type": "usage", "value": ""},
                {"label": "مکالمه و روزمره", "chip_type": "usage", "value": "مکالمه"},
                {"label": "حذف نویز (ANC)", "chip_type": "usage", "value": "anc"},
                {"label": "باتری و شارژدهی بالا", "chip_type": "usage", "value": "باتری"},
                {"label": "ورزش و تحرک", "chip_type": "usage", "value": "ورزشی"},
                {"label": "گیمینگ", "chip_type": "usage", "value": "گیمینگ"},
            ],
        },
        {
            "id": "brand",
            "question_fa": "برند هدفون",
            "options": [
                {"label": "همه برندها", "chip_type": "brand", "value": ""},
                {"label": "اپل (AirPods)", "chip_type": "brand", "value": "اپل"},
                {"label": "سامسونگ (Galaxy Buds)", "chip_type": "brand", "value": "سامسونگ"},
                {"label": "شیائومی / هایلو / QCY", "chip_type": "brand", "value": "شیائومی"},
                {"label": "سونی / انکر", "chip_type": "brand", "value": "سونی"},
            ],
        },
    ],
    "گوشی موبایل": [
        {
            "id": "usage",
            "question_fa": "اولویت اصلی شما در گوشی موبایل",
            "options": [
                {"label": "همه اولویت‌ها", "chip_type": "usage", "value": ""},
                {"label": "دوربین و عکاسی حرفه‌ای", "chip_type": "usage", "value": "دوربین عکاسی"},
                {"label": "باتری قوی و شارژدهی بالا", "chip_type": "usage", "value": "باتری قوی"},
                {"label": "سخت‌افزار گیمینگ و 5G", "chip_type": "usage", "value": "5g"},
                {"label": "اقتصادی و خوش‌قیمت", "chip_type": "usage", "value": "اقتصادی"},
            ],
        },
        {
            "id": "brand",
            "question_fa": "برند گوشی موبایل",
            "options": [
                {"label": "همه برندها", "chip_type": "brand", "value": ""},
                {"label": "سامسونگ (Samsung)", "chip_type": "brand", "value": "سامسونگ"},
                {"label": "شیائومی (Xiaomi)", "chip_type": "brand", "value": "شیائومی"},
                {"label": "اپل (iPhone)", "chip_type": "brand", "value": "اپل"},
            ],
        },
    ],
    "لپ تاپ": [
        {
            "id": "usage",
            "question_fa": "نوع کاربری لپ‌تاپ",
            "options": [
                {"label": "همه کاربری‌ها", "chip_type": "usage", "value": ""},
                {"label": "مهندسی و برنامه‌نویسی", "chip_type": "usage", "value": "مهندسی"},
                {"label": "باتری قوی و سبک (دانشجویی)", "chip_type": "usage", "value": "دانشجویی باتری"},
                {"label": "گرافیک و گیمینگ", "chip_type": "usage", "value": "گیمینگ"},
            ],
        },
        {
            "id": "brand",
            "question_fa": "برند لپ‌تاپ",
            "options": [
                {"label": "همه برندها", "chip_type": "brand", "value": ""},
                {"label": "لنوو (Lenovo)", "chip_type": "brand", "value": "لنوو"},
                {"label": "ایسوس (Asus)", "chip_type": "brand", "value": "ایسوس"},
                {"label": "اچ‌پی (HP)", "chip_type": "brand", "value": "اچ پی"},
                {"label": "اپل (MacBook)", "chip_type": "brand", "value": "اپل"},
            ],
        },
    ],
}

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.SQLITE_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def estimate_eta_minutes(dist_km: float, travel_mode: str = "car") -> int:
    if travel_mode == "walk":
        return max(4, int(round((dist_km / 4.2) * 60)))
    elif travel_mode == "metro":
        return max(8, int(round(9 + (dist_km / 26.0) * 60)))
    return max(5, int(round(5 + (dist_km / 17.0) * 60)))

def format_distance_fa(dist_km: float) -> str:
    if dist_km < 1.0:
        meters = max(50, int(round(dist_km * 1000 / 50.0) * 50))
        return f"{to_persian_digits(meters)} متر"
    return f"{to_persian_digits(round(dist_km, 1))} کیلومتر"

def normalize_realistic_price(price_toman: int | None, category_name: str = "", title: str = "") -> int | None:
    if price_toman is None or price_toman <= 0:
        return None
    cat_norm = normalize_persian(category_name + " " + title)
    if any(w in cat_norm for w in ["گوشی", "موبایل"]):
        # Entry-level phones (A0x, A1x, Redmi A/12/13/14C, Poco C) realistically cost 4M - 14M Toman.
        # If > 22M, seller entered Rials!
        if any(m in cat_norm for m in ["a05", "a06", "a07", "a14", "a15", "a16", "a17", "redmi a", "poco c", "note 12", "redmi 13", "redmi 14"]) and price_toman > 22_000_000:
            return price_toman // 10
        # Mid-range phones (A2x, A3x, A5x, Mxx, Redmi Note, Poco X/M, S-FE) realistically cost 10M - 42M Toman.
        # If > 48M, seller entered Rials!
        if any(m in cat_norm for m in ["a24", "a25", "a26", "a34", "a35", "a36", "a54", "a55", "a56", "a57", "fe ", "fe|", "s23 fe", "s24 fe", "s25 fe", "note 13", "note 14", "poco x", "poco m"]) and price_toman > 48_000_000:
            return price_toman // 10
        # Flagships > 160M are also in Rials
        if price_toman > 160_000_000:
            return price_toman // 10
    elif any(w in cat_norm for w in ["هدفون", "هندزفری", "هدست", "ایرپاد"]):
        if price_toman > 30_000_000:
            return price_toman // 10
    elif any(w in cat_norm for w in ["پاوربانک", "شارژر", "کابل", "ساعت"]):
        if price_toman > 40_000_000:
            return price_toman // 10
    elif any(w in cat_norm for w in ["لپ تاپ", "نوت بوک"]):
        if price_toman > 250_000_000:
            return price_toman // 10
    return price_toman

def format_short_price_pin(price_toman: int | None) -> str:
    if not price_toman:
        return "استعلام"
    if price_toman >= 1_000_000:
        m = round(price_toman / 1_000_000, 1)
        m_str = str(int(m)) if m == int(m) else str(m)
        return f"{to_persian_digits(m_str)} م"
    k = int(round(price_toman / 1_000))
    return f"{to_persian_digits(k)} هـ"

def get_neighborhoods() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT location_label, shop_count, center_lat, center_lon FROM neighborhoods ORDER BY shop_count DESC LIMIT 30"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_supported_cities() -> list[dict]:
    return SUPPORTED_CITIES

def get_popular_categories() -> list[dict]:
    return [
        {"title": "هدفون و هندزفری", "query": "هدفون بی سیم", "count_label": "۸۴۶ مدل"},
        {"title": "گوشی موبایل", "query": "گوشی موبایل", "count_label": "۵۷۲ مدل"},
        {"title": "لپ‌تاپ و نوت‌بوک", "query": "لپ تاپ", "count_label": "۱,۱۱۳ آفر"},
        {"title": "ساعت هوشمند", "query": "ساعت مچی", "count_label": "۲,۵۱۰ مدل"},
        {"title": "دوربین مداربسته", "query": "دوربین مدار بسته", "count_label": "۳,۴۶۷ مدل"},
        {"title": "پاوربانک و شارژر", "query": "پاوربانک", "count_label": "۴۲۰ مدل"},
    ]

def format_product_card(row: sqlite3.Row | dict, why_suggested: str | None = None) -> dict:
    r = dict(row)
    specs_obj = {}
    if r.get("compact_specs_json"):
        try:
            specs_obj = json.loads(r["compact_specs_json"])
        except Exception:
            specs_obj = {}

    cat_name = r.get("category_name") or ""
    p_title = r.get("persian_title") or ""
    min_p = normalize_realistic_price(r.get("min_valid_price"), cat_name, p_title)
    max_p = normalize_realistic_price(r.get("max_valid_price"), cat_name, p_title)
    med_p = normalize_realistic_price(r.get("median_valid_price"), cat_name, p_title)

    if min_p and max_p and min_p > max_p:
        min_p, max_p = max_p, min_p

    if min_p and max_p and max_p > min_p * 1.8:
        candidate_max = int(round((med_p or min_p * 1.2) / 10000.0) * 10000)
        max_p = max(min_p, candidate_max)

    fair_price = None
    if min_p and med_p:
        fair_price = int(round(((min_p * 0.6 + med_p * 0.4)) / 10000.0) * 10000)
    elif min_p:
        fair_price = min_p

    if min_p and max_p and min_p != max_p:
        price_range_fa = f"از {format_price_toman(min_p)} تا {format_price_toman(max_p)}"
    elif min_p:
        price_range_fa = format_price_toman(min_p)
    else:
        price_range_fa = "نیاز به استعلام قیمت"

    reasons = []
    if why_suggested:
        reasons.append(why_suggested)
    if r.get("shop_count", 0) > 1:
        reasons.append(f"موجود در {to_persian_digits(r['shop_count'])} فروشگاه تهران")
    elif r.get("shop_count", 0) == 1:
        reasons.append("موجود در ۱ فروشگاه تهران")
    if fair_price:
        reasons.append(f"قیمت منصفانه بازار: {format_price_toman(fair_price)}")

    return {
        "product_id": r["product_id"],
        "product_group_id": r["product_group_id"],
        "is_approximate_group": bool(r.get("is_approximate_group")),
        "persian_title": p_title,
        "brand_name": r.get("brand_name") or "متفرقه",
        "category_name": cat_name,
        "model_token": r.get("model_token"),
        "image_url": r.get("image_url"),
        "min_valid_price": min_p,
        "max_valid_price": max_p,
        "median_valid_price": med_p,
        "fair_market_price_toman": fair_price,
        "fair_market_price_fa": format_price_toman(fair_price) if fair_price else "نامشخص",
        "price_range_fa": price_range_fa,
        "offer_count": r.get("offer_count", 0),
        "shop_count": r.get("shop_count", 0),
        "specs_map": specs_obj.get("specs_map", {}),
        "highlights": specs_obj.get("highlights", {}),
        "why_suggested": " • ".join(reasons[:3]) if reasons else "پیشنهاد مرتبط با نیاز شما",
    }

def detect_target_category_rules(q_norm: str) -> tuple[str | None, list[str], bool]:
    q_stripped = q_norm.strip()
    explicit_accessory_start = re.match(
        r"^(?:خرید\s+|یه\s+|یک\s+)?(شارژر|کابل|قاب|کاور|کیف|گلس|محافظ|باتری\s+گوشی|باطری\s+گوشی|باتری\s+موبایل|باتری\s+لپ|بند\s+ساعت|پاوربانک|پاور\s+بانک|هولدر)\b",
        q_stripped,
    )
    if explicit_accessory_start:
        acc_word = explicit_accessory_start.group(1)
        if "پاور" in acc_word:
            return "پاوربانک و شارژر همراه", [], False
        return None, [], False

    if any(w in q_norm for w in ["هدفون", "هدفونی", "هندزفری", "ایرپاد", "هدست", "ایرباد", "airpods"]):
        return ("هدفون، هدست و هندزفری", ["کیف", "کاور", "قاب", "پد هدفون", "کابل", "جانبی", "پایه"], False)

    if any(w in q_norm for w in ["لپ تاپ", "لپتاپ", "لپتاپی", "نوت بوک", "مک بوک", "macbook", "laptop"]):
        return ("لپ تاپ و نوت بوک", ["باتری", "باطری", "کیف", "شارژر", "آداپتور", "کول پد", "پایه", "جانبی", "قطعات", "کیبورد لپ", "قاب لپ"], False)

    if any(w in q_norm for w in ["گوشی", "موبایل", "موبایلی", "آیفون", "ایفون", "iphone", "galaxy", "شیایومی", "شیائومی", "سامسونگ", "پوکو", "ردمی"]):
        if not any(w in q_norm for w in ["هدفون", "هندزفری", "ایرپاد", "لپ تاپ", "لپتاپ", "ساعت", "تلویزیون", "مانیتور"]):
            return ("گوشی موبایل", ["باتری", "باطری", "شارژر", "کابل", "کیف", "کاور", "قاب", "گلس", "محافظ", "تبدیل", "هولدر", "قطعات", "جانبی", "تاچ", "ال سی دی", "فلت"], True)

    if any(w in q_norm for w in ["ساعت", "اسمارت واچ", "اپل واچ", "گالکسی واچ", "watch"]):
        return ("ساعت", ["بند", "گلس", "شارژر", "محافظ", "کاور", "قاب", "باتری"], False)

    if any(w in q_norm for w in ["دوربین مدار", "مداربسته", "مدار بسته", "داهوا", "هایک ویژن"]):
        return ("دوربین مدار بسته", ["کابل", "آداپتور", "باکس", "پایه"], False)

    return None, [], False

def search_products(
    query: str = "",
    category: str | None = None,
    brand: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    installment_only: bool = False,
    sort_by: str = "best",
    limit: int = 12,
) -> dict:
    conn = get_conn()
    q_norm = normalize_persian(query)
    preferred_cat, excluded_terms, is_exact_cat = detect_target_category_rules(q_norm)
    raw_tokens = [t for t in q_norm.split() if len(t) >= 2]

    where_clauses = ["p.offer_count > 0"]
    params: list[Any] = []

    if category:
        cat_norm = normalize_persian(category)
        where_clauses.append("p.category_normalized LIKE ?")
        params.append(f"%{cat_norm}%")
    elif preferred_cat:
        pref_norm = normalize_persian(preferred_cat)
        if is_exact_cat:
            where_clauses.append("p.category_normalized = ?")
            params.append(pref_norm)
        else:
            where_clauses.append("p.category_normalized LIKE ?")
            params.append(f"%{pref_norm}%")

    for ex in excluded_terms:
        ex_norm = normalize_persian(ex)
        where_clauses.append("p.category_normalized NOT LIKE ? AND p.title_normalized NOT LIKE ? AND p.title_normalized NOT LIKE ?")
        params.extend([f"%{ex_norm}%", f"{ex_norm}%", f"% {ex_norm} %"])

    if brand:
        b_norm = normalize_persian(brand)
        variants = BRAND_SEARCH_VARIANTS.get(b_norm, BRAND_SEARCH_VARIANTS.get(brand, [b_norm, brand]))
        brand_or_clauses = []
        for v in variants:
            brand_or_clauses.append("(LOWER(p.brand_name) LIKE ? OR p.title_normalized LIKE ? OR LOWER(p.persian_title) LIKE ?)")
            params.extend([f"%{v}%", f"%{v}%", f"%{v}%"])
        where_clauses.append("(" + " OR ".join(brand_or_clauses) + ")")

    if installment_only:
        where_clauses.append(
            "EXISTS (SELECT 1 FROM offers o JOIN shops s ON o.shop_id = s.shop_id WHERE o.product_id = p.product_id AND s.has_installment = 1)"
        )

    generic_cat_words = {
        "گوشی", "موبایل", "موبایلی", "لپ", "تاپ", "لپتاپ", "نوت", "بوک",
        "هدفون", "هندزفری", "هدست", "ایرپاد", "ساعت", "بی", "سیم", "بیسیم",
        "شیایومی", "شیائومی", "سامسونگ", "اپل", "آیفون", "ایفون", "سونی", "انکر", "لنوو", "ایسوس"
    }
    if preferred_cat:
        specific_tokens = [t for t in raw_tokens if t not in generic_cat_words and t not in ATTRIBUTE_AND_STOP_WORDS]
    else:
        specific_tokens = [t for t in raw_tokens if t not in ATTRIBUTE_AND_STOP_WORDS] or raw_tokens

    if specific_tokens:
        expanded_groups = []
        for tok in specific_tokens[:4]:
            syns = SYNONYM_EXPANSIONS.get(tok, [tok])
            or_parts = []
            for s in syns:
                or_parts.append("(p.title_normalized LIKE ? OR p.category_normalized LIKE ?)")
                params.extend([f"%{s}%", f"%{s}%"])
            expanded_groups.append("(" + " OR ".join(or_parts) + ")")
        where_clauses.append(" AND ".join(expanded_groups))

    where_sql = " AND ".join(where_clauses)
    sql = f"SELECT p.* FROM products p WHERE {where_sql} ORDER BY p.shop_count DESC, p.min_valid_price ASC NULLS LAST LIMIT 300"
    rows = conn.execute(sql, params).fetchall()

    if not rows and not brand and preferred_cat:
        relax_clauses = ["p.offer_count > 0"]
        relax_params: list[Any] = []
        pref_norm = normalize_persian(preferred_cat)
        if is_exact_cat:
            relax_clauses.append("p.category_normalized = ?")
            relax_params.append(pref_norm)
        else:
            relax_clauses.append("p.category_normalized LIKE ?")
            relax_params.append(f"%{pref_norm}%")
        for ex in excluded_terms:
            ex_norm = normalize_persian(ex)
            relax_clauses.append("p.title_normalized NOT LIKE ?")
            relax_params.append(f"{ex_norm}%")
        if installment_only:
            relax_clauses.append(
                "EXISTS (SELECT 1 FROM offers o JOIN shops s ON o.shop_id = s.shop_id WHERE o.product_id = p.product_id AND s.has_installment = 1)"
            )
        sql_relax = f"SELECT p.* FROM products p WHERE {' AND '.join(relax_clauses)} ORDER BY p.shop_count DESC, p.min_valid_price ASC NULLS LAST LIMIT 300"
        rows = conn.execute(sql_relax, relax_params).fetchall()

    conn.close()

    all_cards = [format_product_card(r) for r in rows]
    if min_price is not None:
        all_cards = [c for c in all_cards if c["min_valid_price"] and c["min_valid_price"] >= min_price]
    if max_price is not None:
        all_cards = [c for c in all_cards if c["min_valid_price"] and c["min_valid_price"] <= max_price]

    if sort_by == "cheapest":
        # Cheapest first within the user's selected budget range
        all_cards.sort(key=lambda c: (c["min_valid_price"] is None, c["min_valid_price"] or 10**12, -c["shop_count"]))
    elif max_price is not None:
        # When user explicitly selects a budget ceiling (e.g. up to 100M or up to 35M),
        # rank models that best utilize that budget tier (highest tier within budget + good store count) first!
        # Exclude ultra-cheap items (< 20% of budget) if higher-tier items exist in that budget.
        tier_cards = [c for c in all_cards if c["min_valid_price"] and c["min_valid_price"] >= max_price * 0.22]
        if len(tier_cards) >= 3:
            all_cards = tier_cards
        all_cards.sort(key=lambda c: (-(c["min_valid_price"] or 0), -c["shop_count"]))
    else:
        all_cards.sort(key=lambda c: (-c["shop_count"], c["min_valid_price"] or 10**12))

    items = all_cards[:limit]
    return {"query": query, "count": len(items), "products": items, "low_coverage_warning": None}

def recommend_models(
    category_or_query: str,
    usage_hint: str | None = None,
    max_price: int | None = None,
    brand: str | None = None,
    installment_only: bool = False,
    sort_by: str = "best",
    limit: int = 6,
) -> dict:
    q_norm = normalize_persian(category_or_query)
    usage_norm = normalize_persian(usage_hint or "")
    combined_intent = f"{q_norm} {usage_norm}".strip()

    effective_brand = brand
    if not effective_brand:
        for b_key, b_canon in [
            ("سامسونگ", "سامسونگ"), ("شیایومی", "شیائومی"), ("شیائومی", "شیائومی"),
            ("اپل", "اپل"), ("آیفون", "اپل"), ("ایفون", "اپل"),
            ("لنوو", "لنوو"), ("ایسوس", "ایسوس"), ("اچ پی", "اچ پی"),
            ("سونی", "سونی"), ("انکر", "انکر"), ("هایلو", "شیائومی"), ("qcy", "شیائومی")
        ]:
            if re.search(rf"\b{re.escape(b_key)}\b", q_norm):
                effective_brand = b_canon
                break

    res = search_products(
        query=category_or_query,
        brand=effective_brand,
        max_price=max_price,
        installment_only=installment_only,
        sort_by=sort_by,
        limit=100,
    )
    candidates = res["products"]

    wants_battery = any(w in combined_intent for w in ["باتری", "باطری", "شارژ", "شارژدهی", "روزمره"])
    wants_camera = any(w in combined_intent for w in ["دوربین", "عکاسی", "فیلمبرداری"])
    wants_gaming_perf = any(w in combined_intent for w in ["گیمینگ", "بازی", "5g", "مهندسی", "برنامه نویسی", "سخت افزار", "قوی"])
    wants_budget = (sort_by == "cheapest") or any(w in combined_intent for w in ["اقتصادی", "ارزون", "ارزان", "خوش قیمت", "دانشجویی"])
    wants_anc = any(w in combined_intent for w in ["نویز", "anc"])

    if candidates:
        def score_candidate(p: dict) -> tuple:
            t = normalize_persian(p["persian_title"])
            specs_str = normalize_persian(json.dumps(p.get("specs_map", {}), ensure_ascii=False))
            full_text = f"{t} {specs_str}"
            p_min = p.get("min_valid_price") or 10**12
            bonus = 0

            if sort_by == "cheapest" or wants_budget:
                return (1 if p["min_valid_price"] else 0, -p_min, p["shop_count"])

            if wants_battery:
                if any(k in full_text for k in ["5000", "5500", "6000", "mah", "میلی آمپر", "pro max", "ultra", "اولترا", "redmi", "note", "a15", "a16", "a25", "a35", "a55", "m14", "m34", "m54"]):
                    bonus += 60
                if "گوشی" in p.get("category_name", "") and p_min >= 5_000_000:
                    bonus += 25

            if wants_camera:
                if any(k in full_text for k in ["pro", "پرو", "ultra", "اولترا", "fe", "s23", "s24", "s25", "13", "14", "15", "16", "200 مگاپیکسل", "108 مگاپیکسل", "50 مگاپیکسل"]):
                    bonus += 65

            if wants_gaming_perf:
                if any(k in full_text for k in ["5g", "pro", "پرو", "poco", "پوکو", "i5", "i7", "i9", "ryzen 7", "rtx", "رم 8", "رم 12", "رم 16", "ram 8", "ram 16"]):
                    bonus += 60

            if wants_anc:
                if any(k in full_text for k in ["anc", "نویز", "pro", "پرو", "buds"]):
                    bonus += 60

            # If max_price is set and not sorting by cheapest, prefer higher-tier models closer to the user's budget ceiling!
            if max_price is not None:
                return (bonus, p["min_valid_price"] or 0, p["shop_count"])
            return (bonus, p["shop_count"], -p_min)

        candidates.sort(key=score_candidate, reverse=True)

    selected = candidates[:limit]

    if any(w in q_norm for w in ["گوشی", "موبایل", "موبایلی", "آیفون", "ایفون", "سامسونگ", "شیایومی", "شیائومی"]):
        guided_questions = CATEGORY_GUIDED_QUESTIONS["گوشی موبایل"]
    elif any(w in q_norm for w in ["لپ تاپ", "لپتاپ", "نوت بوک", "مک بوک"]):
        guided_questions = CATEGORY_GUIDED_QUESTIONS["لپ تاپ"]
    else:
        guided_questions = CATEGORY_GUIDED_QUESTIONS["هدفون"]

    for idx, prod in enumerate(selected):
        reasons = []
        if sort_by == "cheapest" or wants_budget:
            reasons.append("خوش‌قیمت‌ترین در بازه بودجه شما")
        if wants_battery:
            reasons.append("شارژدهی و دوام باتری بالا")
        if wants_camera:
            reasons.append("کیفیت دوربین و عکاسی عالی")
        if wants_gaming_perf:
            reasons.append("سخت‌افزار قدرتمند")
        if prod["shop_count"] > 1:
            reasons.append(f"موجود در {to_persian_digits(prod['shop_count'])} فروشگاه تهران")
        if prod.get("fair_market_price_toman"):
            reasons.append(f"قیمت منصفانه: {prod['fair_market_price_fa']}")
        prod["why_suggested"] = " • ".join(reasons[:3])

    return {
        "query": category_or_query,
        "recommended_models": selected,
        "guided_questions": guided_questions,
        "low_coverage_warning": None,
    }

def compare_products_by_ids(product_ids: list[str]) -> dict:
    if not product_ids:
        return {"products": [], "comparison_rows": []}
    conn = get_conn()
    placeholders = ",".join("?" for _ in product_ids)
    rows = conn.execute(f"SELECT * FROM products WHERE product_id IN ({placeholders})", product_ids).fetchall()
    conn.close()

    cards = [format_product_card(r) for r in rows]
    if not cards:
        return {"products": [], "comparison_rows": []}

    valid_prices = [c["min_valid_price"] for c in cards if c["min_valid_price"] is not None]
    best_price = min(valid_prices) if valid_prices else None
    best_shops = max(c["shop_count"] for c in cards)

    for c in cards:
        c["is_cheapest_winner"] = bool(best_price and c["min_valid_price"] == best_price)
        c["is_availability_winner"] = bool(best_shops > 0 and c["shop_count"] == best_shops)

    all_keys = []
    for c in cards:
        for k in c["specs_map"].keys():
            if k not in all_keys:
                all_keys.append(k)

    comparison_rows = [
        {"label": "برند", "values": {c["product_id"]: c["brand_name"] for c in cards}},
        {
            "label": "بازه قیمت ثبت‌شده",
            "values": {c["product_id"]: c["price_range_fa"] for c in cards},
            "winner_product_id": next((c["product_id"] for c in cards if c["is_cheapest_winner"]), None),
        },
        {"label": "قیمت منصفانه بازار", "values": {c["product_id"]: c["fair_market_price_fa"] for c in cards}, "winner_product_id": None},
        {
            "label": "فروشگاه‌های حضوری تهران",
            "values": {c["product_id"]: f"{to_persian_digits(c['shop_count'])} فروشگاه" for c in cards},
            "winner_product_id": next((c["product_id"] for c in cards if c["is_availability_winner"]), None),
        },
    ]

    for k in all_keys[:7]:
        comparison_rows.append({"label": k, "values": {c["product_id"]: c["specs_map"].get(k, "نامشخص") for c in cards}, "winner_product_id": None})

    return {"products": cards, "comparison_rows": comparison_rows}
