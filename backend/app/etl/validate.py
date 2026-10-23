"""ETL validation report (master prompt §7).

Prints the counts that Section 3 documents and asserts the invariants the rest of
the app relies on. Exits non-zero when an invariant breaks, so CI fails loudly.

    python -m app.etl.validate --db var/app.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

TEHRAN_LAT = (35.55, 35.90)
TEHRAN_LNG = (51.10, 51.65)


def _scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def validate(db_path: Path) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    report: dict = {"db": str(db_path), "checks": [], "metrics": {}}

    shops = _scalar(conn, "SELECT COUNT(*) FROM shops")
    products = _scalar(conn, "SELECT COUNT(*) FROM products")
    offers = _scalar(conn, "SELECT COUNT(*) FROM offers")

    dups = _scalar(conn, """SELECT COUNT(*) FROM (
        SELECT shop_id, product_id FROM offers GROUP BY shop_id, product_id HAVING COUNT(*) > 1)""")
    # raw coverage: a product may legitimately have only null-priced offers
    products_without_offer = _scalar(
        conn, "SELECT COUNT(*) FROM products WHERE id NOT IN (SELECT product_id FROM offers)")
    products_without_price = _scalar(
        conn, "SELECT COUNT(*) FROM products WHERE price_median IS NULL")
    bad_geo = _scalar(conn, f"""SELECT COUNT(*) FROM shops
        WHERE lat IS NULL OR lon IS NULL
           OR lat NOT BETWEEN {TEHRAN_LAT[0]} AND {TEHRAN_LAT[1]}
           OR lon NOT BETWEEN {TEHRAN_LNG[0]} AND {TEHRAN_LNG[1]}""")
    hours_known = _scalar(conn, "SELECT COUNT(*) FROM shops WHERE hours_known = 1")
    installment_in_person = _scalar(
        conn, "SELECT COUNT(*) FROM shops WHERE has_in_person_installment = 1")
    installment_any = _scalar(
        conn, "SELECT COUNT(*) FROM shops WHERE has_any_installment = 1")
    malls = _scalar(conn, "SELECT COUNT(*) FROM malls")
    malls_multi = _scalar(conn, "SELECT COUNT(*) FROM malls WHERE shop_count > 1")
    valid_price_rate = _scalar(
        conn, "SELECT ROUND(AVG(price_valid), 4) FROM offers") or 0
    over_cap = _scalar(conn, """SELECT COUNT(*) FROM (
        SELECT shop_id FROM offers GROUP BY shop_id HAVING COUNT(*) > 300)""")
    fts_rows = _scalar(conn, "SELECT COUNT(*) FROM products_fts") \
        if _scalar(conn, "SELECT COUNT(*) FROM sqlite_master WHERE name='products_fts'") else 0

    report["metrics"] = {
        "shops": shops,
        "products": products,
        "offers": offers,
        "duplicate_pairs": dups,
        "products_without_offer": products_without_offer,
        "products_without_valid_price": products_without_price,
        "products_without_any_offer": products_without_offer,
        "shops_bad_geo": bad_geo,
        "shops_with_hours": hours_known,
        "shops_with_in_person_installment": installment_in_person,
        "shops_with_any_installment": installment_any,
        "malls": malls,
        "malls_with_2plus_shops": malls_multi,
        "valid_price_rate": valid_price_rate,
        "shops_over_cap300": over_cap,
        "fts_rows": fts_rows,
    }

    def check(name: str, ok: bool, detail: str = "") -> None:
        report["checks"].append({"check": name, "ok": bool(ok), "detail": detail})

    check("shops > 0", (shops or 0) > 0, str(shops))
    check("products > 0", (products or 0) > 0, str(products))
    check("offers > 0", (offers or 0) > 0, str(offers))
    check("no duplicate (shop, product) offers", dups == 0, str(dups))
    check("cap300 respected", over_cap == 0, str(over_cap))
    check("every product has >=1 offer row", products_without_offer == 0,
          f"{products_without_offer} without offers")
    check("priced coverage >= 90%", (products - (products_without_price or 0)) >= products * 0.90,
          f"{products_without_price} with no valid price")
    check("geo inside Tehran", (bad_geo or 0) <= max(1, (shops or 1) * 0.02),
          f"{bad_geo} out of range")
    check("hours parsed for some shops", (hours_known or 0) > 0, str(hours_known))
    check("installment flags derived", (installment_any or 0) > 0, str(installment_any))
    check("in-person installment <= any", (installment_in_person or 0) <= (installment_any or 0))
    check("price validity rate plausible", 0.80 <= valid_price_rate <= 1.0, str(valid_price_rate))
    check("mall clustering produced groups", (malls_multi or 0) > 0, str(malls_multi))
    check("FTS index matches products", fts_rows == products, f"{fts_rows}/{products}")

    report["ok"] = all(c["ok"] for c in report["checks"])
    conn.close()
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/app.db")
    ap.add_argument("--json-out", default="var/etl-validation.json")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"database not found: {db}", file=sys.stderr)
        return 2

    report = validate(db)
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nETL validation")
    print("-" * 52)
    for k, v in report["metrics"].items():
        print(f"  {k:38s} {v}")
    print("-" * 52)
    for c in report["checks"]:
        mark = "✓" if c["ok"] else "✗"
        print(f"  {mark} {c['check']} {('— ' + c['detail']) if c['detail'] else ''}")
    print("-" * 52)
    print("RESULT:", "PASS" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
