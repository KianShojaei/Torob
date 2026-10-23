"""Schema-faithful synthetic dataset generator.

The real CSVs are not reachable from this environment, so this module produces a
dataset with **exactly** the documented columns, JSON-in-string encoding, ``null``
literals and dirty-data rates of Section 3. When the real files land in ``/data``
nothing else changes — the ETL reads whichever is there.

Deliberately reproduced quirks
------------------------------
* ``null`` as a literal string for missing values
* 98% fake shop names / 2% with a real instagram or website
* 4,473/6,476 shops with ``weekly_hours`` (full 7-day object)
* ``payment_options`` present for ~4% of shops, ``channel`` in ``in_person|unknown``
* ``min/max_price_toman`` sentinel ``0/0`` for "no limit info"
* prices: 15,083 null, 2,282 ≤ 1,000, 211 > 1e10 (scaled to the chosen size)
* duplicate ``(shop_id, product_id)`` offers with different timestamps

Usage::

    python -m app.etl.synthetic --out ../data --shops 1200 --products 30000 --offers 60000
    python -m app.etl.synthetic --out ../data --full        # real cardinalities
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.etl.taxonomy import CATEGORIES, CATEGORY_BY_NAME, Category

SNAPSHOT = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
TEHRAN_OFFSET = timezone(timedelta(hours=3, minutes=30))

# 30 neighbourhood anchors (name, lat, lon, weight)
NEIGHBOURHOODS = [
    ("شیخ هادی", 35.6949, 51.4071, 300),
    ("فردوسی", 35.6930, 51.4230, 260),
    ("بهارستان", 35.6870, 51.4330, 150),
    ("باغ فیض", 35.7550, 51.3350, 60),
    ("ایرانشهر", 35.7300, 51.4100, 45),
    ("سنایی", 35.7250, 51.4150, 40),
    ("سهروردی", 35.7270, 51.4300, 40),
    ("تجریش", 35.8000, 51.4330, 35),
    ("جنت‌آباد جنوبی", 35.7450, 51.3100, 35),
    ("مجیدیه", 35.7450, 51.4700, 30),
    ("آذربایجان", 35.6900, 51.3500, 28),
    ("آشتیانی", 35.7600, 51.4900, 24),
    ("کن", 35.7600, 51.2900, 22),
    ("بهار", 35.6900, 51.4400, 22),
    ("ونک", 35.7570, 51.4100, 40),
    ("نارمک", 35.7300, 51.5000, 38),
    ("سعادت‌آباد", 35.7820, 51.3760, 36),
    ("پونک", 35.7500, 51.3300, 24),
    ("یوسف‌آباد", 35.7300, 51.3900, 34),
    ("گیشا", 35.7350, 51.3700, 20),
    ("شهرک غرب", 35.7600, 51.3700, 26),
    ("اکباتان", 35.7100, 51.3100, 16),
    ("تهرانپارس", 35.7400, 51.5400, 22),
    ("افسریه", 35.6600, 51.4900, 18),
    ("نازی‌آباد", 35.6600, 51.4000, 16),
    ("خزانه", 35.6600, 51.4300, 14),
    ("دولاب", 35.6800, 51.4700, 14),
    ("هفت‌حوض", 35.7350, 51.5050, 12),
    ("شهرزیبا", 35.7350, 51.3200, 12),
    ("ستارخان", 35.7200, 51.3450, 18),
]

STREETS = [
    "خیابان جمهوری", "خیابان ولیعصر", "خیابان انقلاب", "خیابان آزادی",
    "خیابان شریعتی", "خیابان مطهری", "خیابان بهشتی", "خیابان کریم‌خان زند",
    "خیابان گاندی", "خیابان میرداماد", "بلوار کشاورز", "خیابان حافظ",
    "خیابان سعدی", "خیابان فردوسی", "خیابان کارگر شمالی", "خیابان امام خمینی",
    "بلوار فردین", "خیابان آیت‌الله کاشانی", "خیابان ستارخان", "خیابان شریعتی",
]
LANDMARKS = [
    "نبش خیابان شهید بهشتی", "جنب بانک ملی", "روبه‌روی داروخانه", "بعد از چهارراه",
    "قبل از تقاطع", "نبش کوچه بهار", "جنب مترو", "روبه‌روی بیمارستان",
]
MALLS = [
    "پاساژ علاءالدین", "پاساژ آلتون", "پاساژ بوشهری", "پاساژ گلستان",
    "مجتمع تجاری نور", "بازار موبایل ایران", "بازار چارسو", "پاساژ کویتی‌ها",
    "مجتمع تجاری ارم", "پاساژ پایتخت", "پاساژ عباسی", "پاساژ ونک",
    "مجتمع تجاری سعادت", "پاساژ گاندی", "پاساژ آرمان", "پاساژ نگین",
    "مجتمع تجاری میلاد نور", "پاساژ تخت جمشید", "پاساژ سینا", "بازار بزرگ",
]
FLOORS = ["همکف", "۱", "۲", "۳", "۴", "۵", "زیرزمین", "منفی ۱", "منفی ۲"]

FAKE_PREFIX = ["فروشگاه", "بازرگانی", "پخش", "تعاونی", "مرکز پخش", "خانه", "دنیای", "فروشگاه بزرگ"]
FAKE_CORE = ["لوازم خانگی", "دیجیتال", "موبایل", "برق و روشنایی", "صنعتی", "ابزار",
             "کفش", "پوشاک", "صوتی و تصویری", "کالای ایرانی", "لوازم اداری", "تجهیزات"]
FAKE_NAME = ["پارس", "آریا", "البرز", "نگین", "ستاره", "امید", "سپهر", "کوروش",
             "میلاد", "پویا", "آرمان", "مهر", "آفتاب", "بازار", "ایرانی", "مدرن",
             "پرتو", "رایان", "سپید", "کاسپین"]
REAL_NAMES = [
    "موبایل تخت جمشید", "دیجیتال کوروش", "لوازم خانگی البرز", "کفش سرای ونک",
    "پخش عمده پارس", "فروشگاه آفتاب", "بازرگانی نگین", "مرکز موبایل ایران",
    "لوازم برقی رایان", "فروشگاه سپهر", "دیجی‌شاپ مرکزی", "صوتی تصویری مهر",
]

PROVIDERS = ["ترب‌پی", "اسنپ‌پی", "دیجی‌پی", "تارا", "ازکی‌وام"]
VARIANTS = ["مشکی", "سفید", "نقره‌ای", "آبی", "خاکستری", "طلایی", "سبز", "قرمز"]


def _jitter(rng: random.Random, scale: float = 0.012) -> float:
    return rng.gauss(0, scale)


def _pick_neighbourhood(rng: random.Random) -> tuple[str, float, float]:
    total = sum(n[3] for n in NEIGHBOURHOODS)
    r = rng.uniform(0, total)
    acc = 0.0
    for name, lat, lon, w in NEIGHBOURHOODS:
        acc += w
        if r <= acc:
            return name, lat, lon
    return NEIGHBOURHOODS[0][0], NEIGHBOURHOODS[0][1], NEIGHBOURHOODS[0][2]


def _shop_name(rng: random.Random, real: bool) -> str:
    if real:
        return rng.choice(REAL_NAMES)
    style = rng.random()
    if style < 0.45:
        return f"{rng.choice(FAKE_PREFIX)} {rng.choice(FAKE_NAME)}"
    if style < 0.8:
        return f"{rng.choice(FAKE_PREFIX)} {rng.choice(FAKE_CORE)} {rng.choice(FAKE_NAME)}"
    return f"{rng.choice(FAKE_CORE)} {rng.choice(FAKE_NAME)}"


def _phone(rng: random.Random) -> str:
    if rng.random() < 0.55:
        return "۰۲۱" + "".join(str(rng.randint(0, 9)) for _ in range(8))
    return "۰۹" + "".join(str(rng.randint(0, 9)) for _ in range(9))


def _address(rng: random.Random, has_mall: bool, has_floor: bool, has_unit: bool) -> str:
    street = rng.choice(STREETS)
    parts = ["تهران", street]
    if rng.random() < 0.5:
        parts.append(rng.choice(LANDMARKS))
    if has_mall:
        parts.append(rng.choice(MALLS))
        if has_floor:
            parts.append(f"طبقه {rng.choice(FLOORS)}")
        if has_unit:
            parts.append(f"واحد {rng.randint(1, 320)}")
    elif rng.random() < 0.6:
        parts.append(f"پلاک {rng.randint(1, 400)}")
    return "، ".join(parts)


def _weekly_hours(rng: random.Random) -> dict:
    week = {}
    # most shops: one shift; some: two shifts with a midday break
    two_shift = rng.random() < 0.12
    open_h, close_h = rng.choice([(9, 18), (9, 21), (10, 20), (10, 19), (8, 17), (11, 22)])
    cross = rng.random() < 0.04
    for day in ("sat", "sun", "mon", "tue", "wed", "thu", "fri"):
        if day == "fri" and rng.random() < 0.82:
            week[day] = {"status": "closed",
                         "shifts": [{"start_time": "00:00:00", "end_time": "00:00:00"}]}
            continue
        if rng.random() < 0.015:
            week[day] = {"status": "unsupported", "shifts": []}
            continue
        if rng.random() < 0.03:
            week[day] = {"status": "closed",
                         "shifts": [{"start_time": "00:00:00", "end_time": "00:00:00"}]}
            continue
        if cross:
            shifts = [{"start_time": f"{close_h:02d}:00:00", "end_time": "02:00:00"}]
        elif two_shift:
            mid = (open_h + close_h) // 2
            shifts = [
                {"start_time": f"{open_h:02d}:00:00", "end_time": f"{mid:02d}:00:00"},
                {"start_time": f"{mid + 3:02d}:00:00", "end_time": f"{close_h:02d}:00:00"},
            ]
        else:
            shifts = [{"start_time": f"{open_h:02d}:00:00", "end_time": f"{close_h:02d}:00:00"}]
        week[day] = {"status": "declared", "shifts": shifts}
    return week


def _price_for(rng: random.Random, cat: Category) -> int:
    low, median, high = cat.price
    # lognormal centred on the category median, clipped to the band
    import math

    mu = math.log(median)
    val = math.exp(rng.gauss(mu, 0.55))
    val = max(low, min(high, val))
    # round to the nearest 10k like real sellers do
    return int(round(val / 10_000) * 10_000)


def _offer_price(rng: random.Random, cat: Category, base: int) -> int:
    """Same product, different seller: ±8% typical spread, occasional outlier.

    This is what makes the comparison screen meaningful instead of random noise.
    """
    import math

    if rng.random() < 0.05:  # clearance / grey-market outlier
        factor = rng.uniform(0.55, 1.75)
    else:
        factor = math.exp(rng.gauss(0, 0.08))
        factor = max(0.72, min(1.38, factor))
    low, _median, high = cat.price
    val = max(low, min(high, base * factor))
    return int(round(val / 10_000) * 10_000)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _maybe_null(rng: random.Random, p: float, value):
    return "null" if rng.random() < p else value


def generate(
    out_dir: Path,
    shops_n: int,
    products_n: int,
    offers_n: int,
    seed: int = 20261013,
    full: bool = False,
) -> dict:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    if full:
        shops_n, products_n, offers_n = 6476, 225_903, 331_506

    # ---------------- shops ----------------
    shop_ids: list[str] = []
    shop_cats: dict[str, list[str]] = {}
    hours_shops: set[str] = set()
    real_shops: set[str] = set()
    truth = {"mall": 0, "floor": 0, "unit": 0, "addresses": 0}

    with open(out_dir / "shops.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["address", "category_names", "contacts", "instagram", "lat",
                    "location_label", "lon", "name", "payment_options", "shop_id",
                    "supports_fast_delivery", "website_url", "weekly_hours"])
        for i in range(shops_n):
            sid = f"shop_{uuid.UUID(int=rng.getrandbits(128)).hex}"
            shop_ids.append(sid)
            nbhd, lat0, lon0 = _pick_neighbourhood(rng)
            lat = lat0 + _jitter(rng)
            lon = lon0 + _jitter(rng)

            cat_count = 1 if rng.random() < 0.75 else 2
            cats = [c.name for c in rng.choices(CATEGORIES, weights=[c.weight for c in CATEGORIES], k=cat_count)]
            cats = list(dict.fromkeys(cats))
            shop_cats[sid] = cats

            has_mall = rng.random() < 0.58
            has_floor = rng.random() < 0.65
            has_unit = has_mall and rng.random() < 0.37
            addr = _address(rng, has_mall, has_floor, has_unit)
            truth["addresses"] += 1
            truth["mall"] += has_mall
            truth["floor"] += has_floor and has_mall
            truth["unit"] += has_unit and has_mall

            is_real = rng.random() < 0.017
            if is_real:
                real_shops.add(sid)
            name = _shop_name(rng, is_real)
            instagram = (f"https://instagram.com/{rng.choice(['shop','store','bazar'])}"
                         f"{rng.randint(1000, 99999)}" if is_real and rng.random() < 0.2 else "")
            website = (f"https://www.{rng.choice(['takhtjamshidmobile','aria-digital','pars-store'])}.com"
                       if is_real and rng.random() < 0.8 else "")

            phone = _phone(rng)
            contacts = json.dumps([{"channel": "phone", "display_number": phone}],
                                  ensure_ascii=False, separators=(",", ":"))

            pay = []
            if rng.random() < 0.041:
                for _ in range(rng.choice([1, 1, 1, 2])):
                    prov = rng.choice(PROVIDERS)
                    channel = "in_person" if rng.random() < 0.31 else "unknown"
                    sentinel = rng.random() < 0.55
                    pay.append({
                        "provider_name": prov,
                        "channel": channel,
                        "min_price_toman": 0 if sentinel else None,
                        "max_price_toman": 0 if sentinel else None,
                        "category_names": [] if rng.random() < 0.6 else cats[:1],
                    })
            pay_json = json.dumps(pay, ensure_ascii=False, separators=(",", ":"))

            fast = rng.choices(["true", "false", "null"], weights=[18, 7, 75], k=1)[0]

            has_hours = rng.random() < 0.69
            if has_hours:
                hours_shops.add(sid)
                hours_json = json.dumps(_weekly_hours(rng), ensure_ascii=False, separators=(",", ":"))
            else:
                hours_json = "null"

            w.writerow([addr, json.dumps(cats, ensure_ascii=False, separators=(",", ":")),
                        contacts, instagram, round(lat, 6), nbhd, round(lon, 6), name,
                        pay_json, sid, fast, website, hours_json])

    # ---------------- products ----------------
    product_rows = []
    base_by_pid: dict[str, int] = {}
    cat_weight_total = sum(c.weight for c in CATEGORIES)
    for i in range(products_n):
        r = rng.uniform(0, cat_weight_total)
        acc = 0.0
        cat = CATEGORIES[0]
        for c in CATEGORIES:
            acc += c.weight
            if r <= acc:
                cat = c
                break
        brand = None if rng.random() < 0.745 else rng.choice(cat.brands)
        family = rng.choice(cat.families)
        model = (f"{rng.choice(['X','S','A','Z','M','V','P'])}{rng.randint(10, 999)}"
                 f"{rng.choice(['', ' Pro', ' Plus', ' Max', ' Ultra', ' Lite'])}")
        variant = rng.choice(VARIANTS)
        title_parts = [family]
        if brand:
            title_parts.insert(0, brand)
        title_parts.append(model)
        title_parts.append(variant)
        title = " ".join(title_parts)
        model_field = model if rng.random() < 0.02 else "null"

        specs = []
        for k in cat.key_specs[:4]:
            opts = cat.spec_options.get(k)
            if opts:
                specs.append({"key": k, "section": "مشخصات کلی", "value": rng.choice(opts)})
        specs_json = json.dumps(specs[:4], ensure_ascii=False, separators=(",", ":"))
        images = json.dumps(
            [f"https://image.torob.com/base/images/{uuid.UUID(int=rng.getrandbits(128)).hex[:3]}"
             f"/{uuid.UUID(int=rng.getrandbits(128)).hex[:8]}.jpg"],
            ensure_ascii=False, separators=(",", ":"),
        )
        pid = f"product_{uuid.UUID(int=rng.getrandbits(128)).hex}"
        base_by_pid[pid] = _price_for(rng, cat)
        product_rows.append((pid, title, brand or "null", cat.name, model_field, images, specs_json, cat))

    with open(out_dir / "products.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["brand_name", "category_name", "image_urls", "model",
                    "persian_title", "product_id", "specs"])
        for pid, title, brand, cat, model_field, images, specs_json, _ in product_rows:
            w.writerow([brand, cat, images, model_field, title, pid, specs_json])

    # ---------------- offers ----------------
    # 4.5% of shops carry no offers at all (§3.3: 3,792 of 6,476 have one)
    shops_with_offers = [sh for sh in shop_ids if rng.random() > 0.045]
    rng.shuffle(shops_with_offers)

    # per-shop capacity: median 27, mean ~87, hard cap 300, scaled to the budget
    weights = [rng.paretovariate(1.2) for _ in shops_with_offers]
    scale = offers_n / sum(weights)
    capacity = {
        shop: max(1, min(300, int(w * scale)))
        for shop, w in zip(shops_with_offers, weights)
    }
    # make sure the total capacity can cover every product at least once
    target_total = min(offers_n, max(products_n, int(offers_n * 0.8)))
    guard = 0
    while sum(capacity.values()) < target_total and guard < 200_000:
        for shop in shops_with_offers:
            if sum(capacity.values()) >= target_total:
                break
            if capacity[shop] < 300:
                capacity[shop] += 1
        guard += 1

    assigned: dict[str, set[str]] = {shop: set() for shop in shops_with_offers}
    remaining = dict(capacity)
    title_by_pid = {pid: title for pid, title, *_ in product_rows}
    by_cat: dict[str, list[tuple[str, str, Category]]] = {}
    for pid, title, _brand, cname, _m, _im, _sp, cat_obj in product_rows:
        by_cat.setdefault(cname, []).append((pid, title, cat_obj))

    shops_by_cat: dict[str, list[str]] = {}
    for shop in shops_with_offers:
        for cname in shop_cats[shop]:
            shops_by_cat.setdefault(cname, []).append(shop)

    def _take(shop: str, pid: str) -> bool:
        if remaining.get(shop, 0) <= 0 or pid in assigned[shop]:
            return False
        assigned[shop].add(pid)
        remaining[shop] -= 1
        return True

    # 1) every product gets 1–3 offers from shops that sell its category
    shuffled_products = [row[0] for row in product_rows]
    rng.shuffle(shuffled_products)
    cat_of = {row[0]: row[3] for row in product_rows}
    for pid in shuffled_products:
        cname = cat_of[pid]
        candidates = [sh for sh in shops_by_cat.get(cname, []) if remaining[sh] > 0]
        if not candidates:
            candidates = [sh for sh in shops_with_offers if remaining[sh] > 0]
        if not candidates:
            break
        want = rng.choices([1, 2, 3], weights=[55, 33, 12])[0]
        for shop in rng.sample(candidates, min(want, len(candidates))):
            _take(shop, pid)

    # 2) spend any leftover capacity to reach the requested offer budget
    while sum(len(v) for v in assigned.values()) < min(offers_n, sum(capacity.values())):
        open_shops = [sh for sh in shops_with_offers if remaining[sh] > 0]
        if not open_shops:
            break
        shop = rng.choice(open_shops)
        pid = rng.choice(shuffled_products)
        if not _take(shop, pid):
            remaining[shop] = 0

    all_pairs: list[tuple[str, str, Category]] = []
    cat_obj_by_name = {c.name: c for c in CATEGORIES}
    for shop, pids in assigned.items():
        for pid in pids:
            all_pairs.append((shop, pid, cat_obj_by_name[cat_of[pid]]))
    rng.shuffle(all_pairs)

    # 4) duplicates: ~6% of rows (§3.3), added on top and removed by the ETL
    dup_target = int(len(all_pairs) * 0.061)
    extra = [(s_, p_, c_) for s_, p_, c_ in rng.sample(all_pairs, min(dup_target, len(all_pairs)))]
    all_pairs = all_pairs + extra
    rng.shuffle(all_pairs)

    n = len(all_pairs)
    null_prices = set(rng.sample(range(n), int(n * 0.0455)))
    tiny_prices = set(rng.sample(range(n), int(n * 0.0069)))
    huge_prices = set(rng.sample(range(n), int(n * 0.00064)))
    null_dates = set(rng.sample(range(n), int(n * 0.002)))

    with open(out_dir / "offers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["description", "last_price_changed_at", "offer_id", "price_toman",
                    "product_id", "seller_title", "shop_id", "warranty"])
        for idx, (shop, pid, cat) in enumerate(all_pairs):
            oid = f"offer_{uuid.UUID(int=rng.getrandbits(128)).hex}"
            if idx in null_prices:
                price = "null"
            elif idx in tiny_prices:
                price = str(rng.choice([0, 0, 500, 1000]))
            elif idx in huge_prices:
                price = str(rng.randint(10**10, 10**17))
            else:
                price = str(_offer_price(rng, cat, base_by_pid[pid]))

            if idx in null_dates:
                changed = "null"
            else:
                days = rng.randint(0, 30) if rng.random() < 0.5 else rng.randint(31, 2100)
                changed = _iso(SNAPSHOT - timedelta(days=days, hours=rng.randint(0, 23)))

            warranty = "null"
            if rng.random() < 0.18:
                warranty = json.dumps(
                    {
                        "description": None,
                        "period_months": rng.choice([6, 12, 18, 24]),
                        "provider": rng.choice(["شرکتی", "تست و تحویل در شرکت",
                                                "بدون گارانتی", "گارانتی مشتری"]),
                    },
                    ensure_ascii=False, separators=(",", ":"),
                )

            title = title_by_pid.get(pid, "محصول")
            seller_title = title if rng.random() < 0.7 else f"{title} {rng.choice(VARIANTS)}"
            desc = "null" if rng.random() < 0.88 else json.dumps(
                {"text": f"{title} با گارانتی معتبر"}, ensure_ascii=False)

            w.writerow([desc, changed, oid, price, pid, seller_title, shop, warranty])

    # 3) pad towards the requested offer budget, still respecting caps
    wanted = min(offers_n, sum(len(v) for v in assigned.values()))
    while sum(len(v) for v in assigned.values()) < wanted:
        progressed = False
        for shop in shops_with_offers:
            if len(assigned[shop]) >= capacity[shop]:
                continue
            pid, _t, _c = rng.choice(product_rows)
            if pid in assigned[shop]:
                continue
            assigned[shop].add(pid)
            progressed = True
            if sum(len(v) for v in assigned.values()) >= wanted:
                break
        if not progressed:
            break

    all_pairs: list[tuple[str, str, Category]] = []
    for shop, pids in assigned.items():
        for pid in pids:
            cat_name = next(b[3] for b in product_rows if b[0] == pid)
            all_pairs.append((shop, pid, CATEGORY_BY_NAME[cat_name]))
    rng.shuffle(all_pairs)

    # 4) duplicates: ~6% of rows (§3.3), added on top and removed by the ETL
    dup_target = int(len(all_pairs) * 0.061)
    extra = [(s_, p_, c_) for s_, p_, c_ in rng.sample(all_pairs, min(dup_target, len(all_pairs)))]
    all_pairs = all_pairs + extra
    rng.shuffle(all_pairs)

    n = len(all_pairs)
    null_prices = set(rng.sample(range(n), int(n * 0.0455)))
    tiny_prices = set(rng.sample(range(n), int(n * 0.0069)))
    huge_prices = set(rng.sample(range(n), int(n * 0.00064)))
    null_dates = set(rng.sample(range(n), int(n * 0.002)))

    with open(out_dir / "offers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["description", "last_price_changed_at", "offer_id", "price_toman",
                    "product_id", "seller_title", "shop_id", "warranty"])
        for idx, (shop, pid, cat) in enumerate(all_pairs):
            oid = f"offer_{uuid.UUID(int=rng.getrandbits(128)).hex}"
            if idx in null_prices:
                price = "null"
            elif idx in tiny_prices:
                price = str(rng.choice([0, 0, 500, 1000]))
            elif idx in huge_prices:
                price = str(rng.randint(10**10, 10**17))
            else:
                price = str(_offer_price(rng, cat, base_by_pid[pid]))

            if idx in null_dates:
                changed = "null"
            else:
                days = rng.randint(0, 30) if rng.random() < 0.5 else rng.randint(31, 2100)
                changed = _iso(SNAPSHOT - timedelta(days=days, hours=rng.randint(0, 23)))

            warranty = "null"
            if rng.random() < 0.18:
                warranty = json.dumps(
                    {
                        "description": None,
                        "period_months": rng.choice([6, 12, 18, 24]),
                        "provider": rng.choice(["شرکتی", "تست و تحویل در شرکت",
                                                "بدون گارانتی", "گارانتی مشتری"]),
                    },
                    ensure_ascii=False, separators=(",", ":"),
                )

            title = title_by_pid.get(pid, "محصول")
            seller_title = title if rng.random() < 0.7 else f"{title} {rng.choice(VARIANTS)}"
            desc = "null" if rng.random() < 0.88 else json.dumps(
                {"text": f"{title} با گارانتی معتبر"}, ensure_ascii=False)

            w.writerow([desc, changed, oid, price, pid, seller_title, shop, warranty])

    truth.update({
        "shops": len(shop_ids),
        "shops_with_offers": len(shops_with_offers),
        "shops_with_hours": len(hours_shops),
        "real_shop_names": len(real_shops),
        "products": len(product_rows),
        "offers_raw": len(all_pairs),
        "offers_deduped": len({(s_, p_) for s_, p_, _ in all_pairs}),
        "products_with_offer": len({p_ for _, p_, _ in all_pairs}),
        "duplicates": len(extra),
        "neighbourhoods": len(NEIGHBOURHOODS),
        "categories": len(CATEGORIES),
        "floor_rate": round(truth["floor"] / max(1, truth["mall"]), 3),
        "unit_rate": round(truth["unit"] / max(1, truth["mall"]), 3),
        "mall_rate": round(truth["mall"] / max(1, truth["addresses"]), 3),
        "seed": seed,
        "snapshot": SNAPSHOT.isoformat(),
    })
    (out_dir / "synthetic_truth.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    return truth


def main() -> int:
    ap = argparse.ArgumentParser(description="generate a schema-faithful synthetic dataset")
    ap.add_argument("--out", default="../data")
    ap.add_argument("--shops", type=int, default=1200)
    ap.add_argument("--products", type=int, default=30_000)
    ap.add_argument("--offers", type=int, default=60_000)
    ap.add_argument("--seed", type=int, default=20261013)
    ap.add_argument("--full", action="store_true", help="real cardinalities (6,476/225,903/331,506)")
    args = ap.parse_args()

    truth = generate(Path(args.out), args.shops, args.products, args.offers, args.seed, args.full)
    print(json.dumps(truth, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
