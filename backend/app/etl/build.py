"""Build the serving database from the CSVs (master prompt §4, §4.13).

    python -m app.etl.build --data ../data --db var/app.db

Stages: read → clean → normalise → derive → aggregate → index.
Idempotent: the target file is rebuilt from scratch in a temp path and swapped in.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from app.db.schema import ALL_DDL, FTS_DDL
from app.etl.enrich import (
    extract_brand,
    extract_key_specs,
    extract_model,
    family_of,
    group_key,
    pick_primary_image,
    warranty_info,
)
from app.etl.normalize import clean_display, fold, tokens
from app.etl.readers import (
    ParseStats,
    clean,
    dataset_mode,
    find_dataset_file,
    open_csv,
    parse_bool_tristate,
    parse_float,
    parse_json,
)
from app.services.address import mall_key, parse_address
from app.services.hours import TEHRAN, is_hours_known, parse_week
from app.services.pricing import age_bucket, age_days, is_valid_price, price_stats

SNAPSHOT_DEFAULT = date(2026, 10, 13)


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-64000")
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    for stmt in ALL_DDL:
        conn.execute(stmt)


def _create_fts(conn: sqlite3.Connection) -> bool:
    try:
        for stmt in FTS_DDL:
            conn.execute(stmt)
        return True
    except sqlite3.OperationalError:
        return False


def _installment_flags(payment_options: list | None) -> tuple[int, int, list[str]]:
    """§3.1 rule: ``channel=in_person`` is confirmed; ``unknown`` is declared only.
    ``0/0`` limits mean "no limit info", never a real limit."""
    confirmed = 0
    declared = 0
    providers: list[str] = []
    for opt in payment_options or []:
        if not isinstance(opt, dict):
            continue
        name = str(opt.get("provider_name") or "").strip()
        if name and name not in providers:
            providers.append(name)
        channel = str(opt.get("channel") or "").lower()
        if channel == "in_person":
            confirmed = 1
        else:
            declared = 1
    return confirmed, (confirmed or declared), providers


def load_shops(conn: sqlite3.Connection, path: Path, stats: ParseStats) -> dict:
    rows = []
    mall_acc: dict[str, dict] = {}
    nb_acc: dict[str, list] = defaultdict(lambda: [0.0, 0.0, 0])
    covers = Counter()

    for row in open_csv(path):
        stats.rows += 1
        sid = clean(row.get("shop_id"))
        if not sid:
            continue
        name = clean_display(clean(row.get("name"))) or "فروشگاه بدون نام"
        address = clean_display(clean(row.get("address")))
        lat = parse_float(row.get("lat"), stats)
        lon = parse_float(row.get("lon"), stats)
        label = clean(row.get("location_label"))
        cats = parse_json(row.get("category_names"), stats) or []
        contacts = parse_json(row.get("contacts"), stats) or []
        payment = parse_json(row.get("payment_options"), stats) or []
        hours_raw = parse_json(row.get("weekly_hours"), stats)
        hours = parse_week(hours_raw if isinstance(hours_raw, dict) else None)
        hours_known = int(is_hours_known(hours))

        instagram = clean(row.get("instagram"))
        website = clean(row.get("website_url"))
        real_name = 1 if (instagram or website) else 0

        addr = parse_address(address)
        confirmed, any_installment, providers = _installment_flags(payment)

        if addr.mall_key:
            covers["mall"] += 1
            acc = mall_acc.setdefault(addr.mall_key, {
                "name": addr.mall_name, "lat_sum": 0.0, "lon_sum": 0.0,
                "n": 0, "cats": Counter(), "nbhd": Counter(),
            })
            if lat is not None and lon is not None:
                acc["lat_sum"] += lat
                acc["lon_sum"] += lon
                acc["n"] += 1
            for c in cats:
                acc["cats"][str(c)] += 1
            if label:
                acc["nbhd"][label] += 1
        if addr.floor:
            covers["floor"] += 1
        if addr.unit:
            covers["unit"] += 1
        if label and lat is not None and lon is not None:
            a = nb_acc[label]
            a[0] += lat
            a[1] += lon
            a[2] += 1

        rows.append((
            sid, name, real_name, address, lat, lon, label,
            json.dumps(cats, ensure_ascii=False),
            json.dumps(contacts, ensure_ascii=False),
            instagram, website,
            json.dumps(payment, ensure_ascii=False),
            confirmed, any_installment, json.dumps(providers, ensure_ascii=False),
            parse_bool_tristate(row.get("supports_fast_delivery")),
            json.dumps(hours_raw, ensure_ascii=False) if isinstance(hours_raw, dict) else None,
            hours_known,
            addr.mall_name, addr.mall_key, addr.floor, addr.unit, addr.unit_kind,
            addr.landmark, addr.street, addr.confidence,
            0, 0, None, None,
        ))

    conn.executemany(
        """INSERT OR REPLACE INTO shops (
            id,name,name_is_real,address,lat,lon,location_label,category_names,contacts,
            instagram,website_url,payment_options,has_in_person_installment,
            has_any_installment,installment_providers,supports_fast_delivery,weekly_hours,
            hours_known,mall_name,mall_key,floor,unit,unit_kind,landmark,street,
            addr_confidence,has_offers,offer_count,min_price,max_price
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )

    mall_rows = []
    for key, acc in mall_acc.items():
        n = acc["n"] or 1
        mall_rows.append((
            key, acc["name"], acc["lat_sum"] / n, acc["lon_sum"] / n,
            acc["n"] and 0 or 0,  # shop_count filled later
            json.dumps([c for c, _ in acc["cats"].most_common(8)], ensure_ascii=False),
            acc["nbhd"].most_common(1)[0][0] if acc["nbhd"] else None,
        ))
    conn.executemany(
        "INSERT OR REPLACE INTO malls (key,name,lat,lon,shop_count,categories,neighborhood) "
        "VALUES (?,?,?,?,?,?,?)", mall_rows)

    nb_rows = [
        (label, a[0] / a[2], a[1] / a[2], a[2])
        for label, a in nb_acc.items() if a[2] > 0
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO neighbourhoods (label,lat,lon,shop_count) VALUES (?,?,?,?)",
        nb_rows)

    return {
        "shops": len(rows),
        "real_shop_names": sum(r[2] for r in rows),
        "with_hours": sum(r[17] for r in rows),
        "with_installment_in_person": sum(r[12] for r in rows),
        "with_any_installment": sum(r[13] for r in rows),
        "malls": len(mall_rows),
        "neighbourhoods": len(nb_rows),
        "covers": dict(covers),
    }


def load_products(conn: sqlite3.Connection, path: Path, stats: ParseStats) -> dict:
    rows = []
    for row in open_csv(path):
        stats.rows += 1
        pid = clean(row.get("product_id"))
        title = clean_display(clean(row.get("persian_title")))
        if not pid or not title:
            continue
        category = clean(row.get("category_name"))
        specs = parse_json(row.get("specs"), stats) or []
        images = parse_json(row.get("image_urls"), stats) or []
        brand = extract_brand(clean(row.get("brand_name")), title, specs if isinstance(specs, list) else [])
        model = extract_model(title, clean(row.get("model")), specs if isinstance(specs, list) else [])
        key_specs = extract_key_specs(category, specs if isinstance(specs, list) else [])
        gid = group_key(title, brand, model, category)
        fam = family_of(title, category)
        rows.append((
            pid, title, fold(title), len(title), brand, category, model,
            json.dumps(images if isinstance(images, list) else [], ensure_ascii=False),
            json.dumps(specs if isinstance(specs, list) else [], ensure_ascii=False),
            json.dumps(key_specs, ensure_ascii=False),
            gid, fam, 0, 0, None, None, None, None, None,
        ))
    conn.executemany(
        """INSERT OR REPLACE INTO products (
            id,title,title_folded,title_len,brand,category,model,image_urls,specs,
            key_specs,group_id,family,offer_count,shop_count,price_min,price_median,
            price_max,price_p25,price_p75
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    return {"products": len(rows)}


def load_offers(conn: sqlite3.Connection, path: Path, snapshot: date, stats: ParseStats) -> dict:
    """Dedupe on (shop_id, product_id) keeping the latest timestamp (§4.4)."""
    best: dict[tuple[str, str], tuple] = {}
    dup = 0
    raw = 0
    invalid = 0

    for row in open_csv(path):
        stats.rows += 1
        raw += 1
        shop = clean(row.get("shop_id"))
        pid = clean(row.get("product_id"))
        if not shop or not pid:
            continue
        price = parse_float(row.get("price_toman"), stats)
        changed = clean(row.get("last_price_changed_at"))
        changed_iso = None
        if changed:
            try:
                changed_iso = datetime.fromisoformat(changed.replace("Z", "+00:00")).isoformat()
            except ValueError:
                changed_iso = None
        key = (shop, pid)
        prev = best.get(key)
        if prev is not None:
            dup += 1
            prev_changed = prev[5] or ""
            if (changed_iso or "") <= prev_changed:
                continue
        if not is_valid_price(price):
            invalid += 1
        warranty_json, months = warranty_info(parse_json(row.get("warranty"), stats))
        days = age_days(changed_iso or changed, snapshot)
        bucket, _label = age_bucket(days)
        best[key] = (
            clean(row.get("offer_id")) or f"{shop}:{pid}",
            shop, pid, price, 1 if is_valid_price(price) else 0,
            changed_iso or changed, days, bucket,
            clean_display(clean(row.get("seller_title"))),
            fold(clean(row.get("seller_title"))),
            warranty_json, months,
        )

    rows = list(best.values())
    conn.executemany(
        """INSERT OR REPLACE INTO offers (
            id,shop_id,product_id,price,price_valid,last_changed_at,age_days,age_bucket,
            seller_title,seller_title_folded,warranty,warranty_months
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    return {
        "offers_raw": raw,
        "offers": len(rows),
        "duplicates": dup,
        "invalid_prices": invalid,
    }


def aggregate(conn: sqlite3.Connection) -> dict:
    t0 = time.time()
    # product price stats — single pass, no per-product query
    prices_by_product: dict[str, list[float]] = defaultdict(list)
    shops_by_product: dict[str, set[str]] = defaultdict(set)
    for pid, shop, price in conn.execute(
            "SELECT product_id, shop_id, price FROM offers WHERE price_valid=1"):
        prices_by_product[pid].append(price)
        shops_by_product[pid].add(shop)

    updates = []
    for pid, prices in prices_by_product.items():
        st = price_stats(prices) or {}
        updates.append((
            len(prices), len(shops_by_product[pid]), st.get("min"),
            st.get("median"), st.get("max"), st.get("p25"), st.get("p75"), pid,
        ))
    conn.executemany(
        """UPDATE products SET offer_count=?, shop_count=?, price_min=?, price_median=?,
           price_max=?, price_p25=?, price_p75=? WHERE id=?""", updates)

    # shop aggregates — grouped, one scan
    conn.execute(
        """CREATE TEMP TABLE shop_agg AS
           SELECT shop_id, COUNT(*) n, MIN(CASE WHEN price_valid=1 THEN price END) mn,
                  MAX(CASE WHEN price_valid=1 THEN price END) mx
           FROM offers GROUP BY shop_id"""
    )
    conn.execute(
        """UPDATE shops SET
             offer_count = COALESCE((SELECT n FROM shop_agg a WHERE a.shop_id = shops.id), 0),
             min_price   = (SELECT mn FROM shop_agg a WHERE a.shop_id = shops.id),
             max_price   = (SELECT mx FROM shop_agg a WHERE a.shop_id = shops.id)"""
    )
    conn.execute("UPDATE shops SET has_offers = CASE WHEN offer_count > 0 THEN 1 ELSE 0 END")
    conn.execute("DROP TABLE shop_agg")

    # mall shop counts — grouped, one scan
    conn.execute(
        """UPDATE malls SET shop_count = COALESCE(
             (SELECT c FROM (SELECT mall_key k, COUNT(*) c FROM shops
                             WHERE mall_key IS NOT NULL GROUP BY mall_key) m
              WHERE m.k = malls.key), 0)"""
    )
    conn.commit()
    return {"aggregate_seconds": round(time.time() - t0, 1)}


def build_fts(conn: sqlite3.Connection, available: bool) -> dict:
    if not available:
        return {"fts": False}
    conn.execute("DELETE FROM products_fts")
    batch = []
    n = 0
    for pid, title, brand, cat, specs in conn.execute(
            "SELECT id, title_folded, brand, category, key_specs FROM products"):
        spec_text = " ".join(str(v) for v in json.loads(specs or "{}").values())
        batch.append((pid, title, fold(brand), fold(cat), fold(spec_text)))
        if len(batch) >= 5000:
            conn.executemany("INSERT INTO products_fts VALUES (?,?,?,?,?)", batch)
            n += len(batch)
            batch.clear()
    if batch:
        conn.executemany("INSERT INTO products_fts VALUES (?,?,?,?,?)", batch)
        n += len(batch)
    conn.commit()
    conn.execute("INSERT INTO products_fts(products_fts) VALUES('optimize')")
    conn.commit()
    return {"fts": True, "fts_rows": n}


def build(data_dir: Path, db_path: Path, snapshot: date = SNAPSHOT_DEFAULT) -> dict:
    mode = dataset_mode(data_dir)
    shops_csv = find_dataset_file(data_dir, "shops")
    products_csv = find_dataset_file(data_dir, "products")
    offers_csv = find_dataset_file(data_dir, "offers")
    if not (shops_csv and products_csv and offers_csv):
        raise SystemExit(
            f"CSV files not found in {data_dir}. "
            "Run `make synthetic` for a demo dataset or place shops.csv, "
            "products.csv, offers.csv there."
        )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".building.db")
    for p in (tmp, Path(str(tmp) + "-wal"), Path(str(tmp) + "-shm")):
        if p.exists():
            p.unlink()

    conn = _connect(tmp)
    _create_schema(conn)
    fts_ok = _create_fts(conn)

    stats = {name: ParseStats() for name in ("shops", "products", "offers")}
    t0 = time.time()
    report = {"mode": mode, "snapshot": snapshot.isoformat()}

    report["shops"] = load_shops(conn, shops_csv, stats["shops"])
    conn.commit()
    report["products"] = load_products(conn, products_csv, stats["products"])
    conn.commit()
    report["offers"] = load_offers(conn, offers_csv, snapshot, stats["offers"])
    conn.commit()
    report.update(aggregate(conn))
    report.update(build_fts(conn, fts_ok))
    report["parse_stats"] = {k: v.as_dict() for k, v in stats.items()}
    report["seconds"] = round(time.time() - t0, 1)

    meta = {
        "mode": mode,
        "snapshot": snapshot.isoformat(),
        "built_at": datetime.now(TEHRAN).isoformat(),
        "counts": {
            "shops": report["shops"]["shops"],
            "products": report["products"]["products"],
            "offers": report["offers"]["offers"],
            "offers_raw": report["offers"]["offers_raw"],
            "duplicates": report["offers"]["duplicates"],
        },
    }
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('build', ?)",
                 (json.dumps(meta, ensure_ascii=False),))
    conn.commit()
    conn.execute("PRAGMA optimize")
    # rebuild the file densely: ~8 % smaller and faster to page in on a small container
    conn.execute("VACUUM")
    conn.close()

    if db_path.exists():
        db_path.unlink()
    os.replace(tmp, db_path)
    for suffix in ("-wal", "-shm"):
        p = Path(str(tmp) + suffix)
        if p.exists():
            p.unlink()

    report["db_path"] = str(db_path)
    report["db_mb"] = round(db_path.stat().st_size / 1e6, 1)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="build the serving database")
    ap.add_argument("--data", default="../data")
    ap.add_argument("--db", default="var/app.db")
    ap.add_argument("--snapshot", default=SNAPSHOT_DEFAULT.isoformat())
    args = ap.parse_args()

    report = build(Path(args.data), Path(args.db), date.fromisoformat(args.snapshot))
    out = Path("var/etl-report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "parse_stats"},
                     ensure_ascii=False, indent=2))
    print(f"report → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
