import csv
import json
import os
import sqlite3
import time
from collections import defaultdict
from pathlib import Path

from backend.app.etl.normalizer import normalize_persian
from backend.app.etl.price_rules import validate_price, compute_price_age
from backend.app.etl.hours_engine import parse_weekly_hours
from backend.app.etl.address_parser import parse_shop_address
from backend.app.etl.installment_parser import parse_payment_options
from backend.app.etl.product_enrichment import enrich_and_group_product

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DB_PATH = Path(os.getenv("SQLITE_DB_PATH", "./data/torob_assistant.db"))
SNAPSHOT_DATE = os.getenv("SNAPSHOT_DATE", "2026-10-13")

def clean_val(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if v == "" or v.lower() == "null":
        return None
    return v

def safe_json_loads(v: str | None, default):
    v = clean_val(v)
    if not v:
        return default
    try:
        res = json.loads(v)
        return res if res is not None else default
    except Exception:
        return default

def create_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.executescript("""
    PRAGMA journal_mode = WAL;
    PRAGMA synchronous = NORMAL;

    DROP TABLE IF EXISTS shops;
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS offers;
    DROP TABLE IF EXISTS neighborhoods;
    DROP TABLE IF EXISTS conversations;
    DROP TABLE IF EXISTS products_fts;

    CREATE TABLE shops (
        shop_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        name_normalized TEXT,
        is_real_name INTEGER DEFAULT 0,
        address TEXT,
        lat REAL,
        lon REAL,
        location_label TEXT,
        category_names_json TEXT,
        phone_display TEXT,
        instagram TEXT,
        website_url TEXT,
        has_installment INTEGER DEFAULT 0,
        installment_level TEXT DEFAULT 'none',
        installment_label_fa TEXT,
        installment_providers_json TEXT,
        installment_details_json TEXT,
        supports_fast_delivery TEXT,
        weekly_hours_json TEXT,
        has_hours INTEGER DEFAULT 0,
        mall_name TEXT,
        floor TEXT,
        unit TEXT,
        street_hint TEXT,
        is_in_mall INTEGER DEFAULT 0,
        address_confidence TEXT,
        guide_summary_fa TEXT,
        guide_steps_json TEXT,
        offers_count INTEGER DEFAULT 0
    );

    CREATE TABLE neighborhoods (
        location_label TEXT PRIMARY KEY,
        shop_count INTEGER,
        center_lat REAL,
        center_lon REAL
    );

    CREATE TABLE products (
        product_id TEXT PRIMARY KEY,
        persian_title TEXT NOT NULL,
        title_normalized TEXT NOT NULL,
        brand_name TEXT,
        category_name TEXT NOT NULL,
        category_normalized TEXT NOT NULL,
        model_token TEXT,
        product_group_id TEXT NOT NULL,
        is_approximate_group INTEGER DEFAULT 0,
        image_url TEXT,
        compact_specs_json TEXT,
        min_valid_price INTEGER,
        max_valid_price INTEGER,
        median_valid_price INTEGER,
        offer_count INTEGER DEFAULT 0,
        shop_count INTEGER DEFAULT 0
    );

    CREATE TABLE offers (
        offer_id TEXT PRIMARY KEY,
        shop_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        product_group_id TEXT NOT NULL,
        seller_title TEXT,
        description TEXT,
        price_toman INTEGER,
        price_status TEXT NOT NULL,
        last_price_changed_at TEXT,
        age_days INTEGER,
        price_age_bucket TEXT NOT NULL,
        price_age_label_fa TEXT NOT NULL,
        availability_status TEXT NOT NULL DEFAULT 'listed',
        confirmed_price_toman INTEGER,
        confirmed_at TEXT,
        warranty_json TEXT,
        warranty_label_fa TEXT,
        duplicate_count INTEGER DEFAULT 1
    );

    CREATE TABLE conversations (
        conversation_id TEXT PRIMARY KEY,
        shop_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        intent TEXT NOT NULL,
        status TEXT NOT NULL,
        user_message TEXT,
        seller_reply TEXT,
        parsed_result_json TEXT,
        created_at REAL NOT NULL,
        replied_at REAL,
        timeout_at REAL NOT NULL
    );

    CREATE INDEX idx_shops_location ON shops(location_label);
    CREATE INDEX idx_shops_installment ON shops(installment_level);
    CREATE INDEX idx_products_category ON products(category_normalized);
    CREATE INDEX idx_products_group ON products(product_group_id);
    CREATE INDEX idx_offers_product ON offers(product_id);
    CREATE INDEX idx_offers_group ON offers(product_group_id);
    CREATE INDEX idx_offers_shop ON offers(shop_id);

    CREATE VIRTUAL TABLE products_fts USING fts5(
        product_id UNINDEXED,
        title_normalized,
        category_normalized,
        brand_name
    );
    """)
    conn.commit()

def run_etl():
    t0 = time.time()
    shops_csv = DATA_DIR / "shops.csv"
    products_csv = DATA_DIR / "products.csv"
    offers_csv = DATA_DIR / "offers.csv"

    for p in (shops_csv, products_csv, offers_csv):
        if not p.exists():
            raise FileNotFoundError(f"Missing required dataset CSV: {p.resolve()}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    create_schema(conn)
    cur = conn.cursor()

    # ---------------- 1. Process shops.csv ----------------
    print("1/4 Loading & cleaning shops.csv ...")
    stats = {
        "shops_total": 0,
        "shops_with_instagram": 0,
        "shops_with_website": 0,
        "shops_real_name": 0,
        "shops_with_payment_options": 0,
        "shops_in_person_installment": 0,
        "shops_with_hours": 0,
        "hours_declared_days": 0,
        "hours_closed_days": 0,
        "hours_unsupported_days": 0,
        "shops_in_mall": 0,
    }
    loc_coords = defaultdict(list)
    shop_rows = []

    with open(shops_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["shops_total"] += 1
            shop_id = clean_val(row.get("shop_id"))
            name = clean_val(row.get("name")) or "فروشگاه بدون نام"
            address = clean_val(row.get("address"))
            lat = float(row["lat"]) if clean_val(row.get("lat")) else None
            lon = float(row["lon"]) if clean_val(row.get("lon")) else None
            loc_label = clean_val(row.get("location_label")) or "سایر مناطق"
            instagram = clean_val(row.get("instagram"))
            website = clean_val(row.get("website_url"))
            fast_del = clean_val(row.get("supports_fast_delivery")) or "unknown"

            if instagram:
                stats["shops_with_instagram"] += 1
            if website:
                stats["shops_with_website"] += 1
            is_real = 1 if (instagram or website) else 0
            stats["shops_real_name"] += is_real

            if lat and lon and loc_label:
                loc_coords[loc_label].append((lat, lon))

            contacts = safe_json_loads(row.get("contacts"), [])
            phone_display = "۰۲۱-۰۰۰۰۰۰۰۰"
            if isinstance(contacts, list) and contacts:
                phone_display = contacts[0].get("display_number") or phone_display

            pay_info = parse_payment_options(row.get("payment_options"))
            if pay_info["has_installment"]:
                stats["shops_with_payment_options"] += 1
            if pay_info["installment_level"] == "in_person":
                stats["shops_in_person_installment"] += 1

            wh = parse_weekly_hours(row.get("weekly_hours"))
            has_hours = 1 if wh else 0
            if has_hours:
                stats["shops_with_hours"] += 1
                for day_k, day_v in wh.items():
                    if isinstance(day_v, dict):
                        st = day_v.get("status")
                        if st == "declared":
                            stats["hours_declared_days"] += 1
                        elif st == "closed":
                            stats["hours_closed_days"] += 1
                        elif st == "unsupported":
                            stats["hours_unsupported_days"] += 1

            addr_parsed = parse_shop_address(address, loc_label)
            if addr_parsed["is_in_mall"]:
                stats["shops_in_mall"] += 1

            shop_rows.append((
                shop_id,
                name,
                normalize_persian(name),
                is_real,
                address,
                lat,
                lon,
                loc_label,
                clean_val(row.get("category_names")) or "[]",
                phone_display,
                instagram,
                website,
                1 if pay_info["has_installment"] else 0,
                pay_info["installment_level"],
                pay_info["label_fa"],
                json.dumps(pay_info["providers"], ensure_ascii=False),
                json.dumps(pay_info["details"], ensure_ascii=False),
                fast_del,
                json.dumps(wh, ensure_ascii=False),
                has_hours,
                addr_parsed["mall_name"],
                addr_parsed["floor"],
                addr_parsed["unit"],
                addr_parsed["street_hint"],
                1 if addr_parsed["is_in_mall"] else 0,
                addr_parsed["confidence"],
                addr_parsed["guide_summary_fa"],
                json.dumps(addr_parsed["guide_steps_fa"], ensure_ascii=False),
                0
            ))

    cur.executemany("""
        INSERT INTO shops VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, shop_rows)

    # Rule 10: Neighborhood anchors
    nb_rows = []
    for loc_label, coords in loc_coords.items():
        avg_lat = sum(c[0] for c in coords) / len(coords)
        avg_lon = sum(c[1] for c in coords) / len(coords)
        nb_rows.append((loc_label, len(coords), avg_lat, avg_lon))
    cur.executemany("INSERT INTO neighborhoods VALUES (?,?,?,?)", nb_rows)
    conn.commit()

    # ---------------- 2. Process offers.csv first to deduplicate & aggregate ----------------
    print("2/4 Loading & deduplicating offers.csv ...")
    stats["offers_raw_total"] = 0
    stats["offers_invalid_price"] = 0
    dedup_offers = {}  # (shop_id, product_id) -> dict

    with open(offers_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["offers_raw_total"] += 1
            offer_id = clean_val(row.get("offer_id"))
            shop_id = clean_val(row.get("shop_id"))
            product_id = clean_val(row.get("product_id"))
            price_val, price_status = validate_price(row.get("price_toman"))
            if price_status == "unknown":
                stats["offers_invalid_price"] += 1
            last_changed = clean_val(row.get("last_price_changed_at"))
            seller_title = clean_val(row.get("seller_title"))
            description = clean_val(row.get("description"))
            warranty_raw = clean_val(row.get("warranty"))

            key = (shop_id, product_id)
            if key not in dedup_offers:
                dedup_offers[key] = {
                    "offer_id": offer_id,
                    "shop_id": shop_id,
                    "product_id": product_id,
                    "seller_title": seller_title,
                    "description": description,
                    "price_toman": price_val,
                    "price_status": price_status,
                    "last_price_changed_at": last_changed,
                    "warranty_raw": warranty_raw,
                    "duplicate_count": 1,
                }
            else:
                # Rule 4: Keep offer with latest last_price_changed_at (tie -> lowest valid price)
                existing = dedup_offers[key]
                existing["duplicate_count"] += 1
                ex_ts = existing["last_price_changed_at"] or ""
                new_ts = last_changed or ""
                replace = False
                if new_ts > ex_ts:
                    replace = True
                elif new_ts == ex_ts:
                    if price_val is not None and (existing["price_toman"] is None or price_val < existing["price_toman"]):
                        replace = True
                if replace:
                    dedup_offers[key].update({
                        "offer_id": offer_id,
                        "seller_title": seller_title,
                        "description": description,
                        "price_toman": price_val,
                        "price_status": price_status,
                        "last_price_changed_at": last_changed,
                        "warranty_raw": warranty_raw,
                    })

    stats["offers_unique_pairs"] = len(dedup_offers)
    stats["offers_duplicate_pairs_removed"] = stats["offers_raw_total"] - stats["offers_unique_pairs"]

    # Aggregate product offer stats
    prod_prices = defaultdict(list)
    prod_offer_counts = defaultdict(int)
    shop_offer_counts = defaultdict(int)

    for (s_id, p_id), o in dedup_offers.items():
        prod_offer_counts[p_id] += 1
        shop_offer_counts[s_id] += 1
        if o["price_toman"] is not None:
            prod_prices[p_id].append(o["price_toman"])

    stats["shops_with_offers"] = len(shop_offer_counts)

    # ---------------- 3. Process products.csv ----------------
    print("3/4 Loading & enriching products.csv ...")
    stats["products_total"] = 0
    prod_group_map = {}
    batch_products = []
    batch_fts = []

    with open(products_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["products_total"] += 1
            p_id = clean_val(row.get("product_id"))
            p_title = clean_val(row.get("persian_title")) or "محصول بدون عنوان"
            brand = clean_val(row.get("brand_name"))
            cat = clean_val(row.get("category_name")) or "سایر دسته‌ها"
            model_raw = clean_val(row.get("model"))
            imgs = safe_json_loads(row.get("image_urls"), [])
            first_img = imgs[0] if (isinstance(imgs, list) and imgs) else None

            enriched = enrich_and_group_product(
                p_id, p_title, brand, model_raw, cat, row.get("specs")
            )
            prod_group_map[p_id] = enriched["product_group_id"]

            prices = sorted(prod_prices.get(p_id, []))
            min_p = prices[0] if prices else None
            max_p = prices[-1] if prices else None
            med_p = prices[len(prices) // 2] if prices else None
            o_cnt = prod_offer_counts.get(p_id, 0)

            batch_products.append((
                p_id,
                p_title,
                enriched["title_normalized"],
                enriched["brand_resolved"],
                cat,
                normalize_persian(cat),
                enriched["model_resolved"],
                enriched["product_group_id"],
                1 if enriched["is_approximate_group"] else 0,
                first_img,
                enriched["compact_specs_json"],
                min_p,
                max_p,
                med_p,
                o_cnt,
                o_cnt
            ))
            batch_fts.append((
                p_id,
                enriched["title_normalized"],
                normalize_persian(cat),
                normalize_persian(enriched["brand_resolved"]),
            ))

            if len(batch_products) >= 10000:
                cur.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch_products)
                cur.executemany("INSERT INTO products_fts VALUES (?,?,?,?)", batch_fts)
                batch_products.clear()
                batch_fts.clear()

    if batch_products:
        cur.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch_products)
        cur.executemany("INSERT INTO products_fts VALUES (?,?,?,?)", batch_fts)
    conn.commit()

    # ---------------- 4. Insert deduplicated offers ----------------
    print("4/4 Writing enriched offers & updating shop counts ...")
    batch_offers = []
    for (s_id, p_id), o in dedup_offers.items():
        age_info = compute_price_age(o["last_price_changed_at"], SNAPSHOT_DATE)
        w_obj = safe_json_loads(o["warranty_raw"], {})
        w_label = "گارانتی نامشخص"
        if isinstance(w_obj, dict) and w_obj:
            prov = w_obj.get("provider")
            months = w_obj.get("period_months")
            desc = w_obj.get("description")
            if prov and months:
                w_label = f"گارانتی {months} ماهه ({prov})"
            elif prov:
                w_label = f"گارانتی ({prov})"
            elif desc:
                w_label = desc

        batch_offers.append((
            o["offer_id"],
            s_id,
            p_id,
            prod_group_map.get(p_id, p_id),
            o["seller_title"],
            o["description"],
            o["price_toman"],
            o["price_status"],
            o["last_price_changed_at"],
            age_info["age_days"],
            age_info["bucket"],
            age_info["label_fa"],
            "listed",
            None,
            None,
            o["warranty_raw"],
            w_label,
            o["duplicate_count"]
        ))
        if len(batch_offers) >= 10000:
            cur.executemany("INSERT INTO offers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch_offers)
            batch_offers.clear()

    if batch_offers:
        cur.executemany("INSERT INTO offers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch_offers)

    # Update shop offer counts
    cur.executemany(
        "UPDATE shops SET offers_count = ? WHERE shop_id = ?",
        [(cnt, s_id) for s_id, cnt in shop_offer_counts.items()]
    )
    conn.commit()
    conn.close()

    elapsed = round(time.time() - t0, 2)
    stats["elapsed_seconds"] = elapsed
    print("\n================ ETL VALIDATION REPORT ================")
    for k, v in stats.items():
        print(f"  {k:32s}: {v:,}" if isinstance(v, int) else f"  {k:32s}: {v}")
    print("=======================================================\n")
    return stats

if __name__ == "__main__":
    run_etl()
