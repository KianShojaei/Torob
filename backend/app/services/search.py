"""Hybrid product search (master prompt §5.2).

Lexical retrieval runs in SQLite FTS5 (BM25) over the folded title/brand/category
/key-specs, then re-ranks in Python with:

* phrase coverage of the user's tokens (synonyms expanded)
* category / brand filters and budget fit
* availability signal (number of selling shops) and price sanity

No embeddings are shipped: they would add hundreds of MB and a model download at
boot, and the prompt explicitly allows "otherwise rely on LLM query-understanding
→ structured filters". The LLM path feeds structured filters into this function.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field

from app.db.engine import connection
from app.etl.normalize import expand_tokens, fold, tokens
from app.etl.taxonomy import ALL_CATEGORY_NAMES, CATEGORY_BY_NAME

FTS_SAFE = re.compile(r"[^\w\u0600-\u06ff\s]+")


@dataclass
class ProductFilters:
    category: str | None = None
    brand: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    in_stock_only: bool = True
    limit: int = 12


@dataclass
class ProductHit:
    id: str
    title: str
    brand: str | None
    category: str | None
    image: str | None
    price_min: float | None
    price_median: float | None
    price_max: float | None
    shop_count: int
    offer_count: int
    key_specs: dict
    score: float = 0.0
    matched: list[str] = field(default_factory=list)


def _fts_query(text: str) -> str:
    toks = [t for t in tokens(text) if len(t) > 1]
    if not toks:
        return ""
    expanded: list[str] = []
    for t in toks:
        variants = sorted(expand_tokens([t]))
        # cap the fan-out so a single token cannot dominate the query
        expanded.extend(FTS_SAFE.sub("", v) for v in variants[:4] if FTS_SAFE.sub("", v))
    uniq = list(dict.fromkeys(expanded))
    return " OR ".join(f'"{u}"' for u in uniq[:24])


def _like_query(text: str) -> str:
    toks = [t for t in tokens(text) if len(t) > 1][:4]
    return toks[0] if toks else ""


def _decode(row: sqlite3.Row) -> ProductHit:
    try:
        keys = json.loads(row["key_specs"] or "{}")
    except json.JSONDecodeError:
        keys = {}
    images = []
    try:
        images = json.loads(row["image_urls"] or "[]")
    except json.JSONDecodeError:
        pass
    return ProductHit(
        id=row["id"], title=row["title"], brand=row["brand"], category=row["category"],
        image=images[0] if images else None,
        price_min=row["price_min"], price_median=row["price_median"],
        price_max=row["price_max"], shop_count=row["shop_count"],
        offer_count=row["offer_count"], key_specs=keys,
    )


def _rank(hit: ProductHit, query_tokens: list[str], filters: ProductFilters) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0

    folded_title = fold(hit.title)
    if query_tokens:
        covered = [t for t in query_tokens if t in folded_title]
        coverage = len(covered) / len(query_tokens)
        score += 3.0 * coverage
        if coverage >= 0.75:
            reasons.append("عنوان دقیقاً با جست‌وجوی شما می‌خواند")
        elif covered:
            reasons.append(f"شامل «{covered[0]}»")

    # availability: more selling shops → easier to buy nearby
    shops = hit.shop_count or 0
    score += min(1.5, shops / 12)
    if shops >= 8:
        reasons.append(f"{shops} فروشگاه این محصول را دارند")

    # budget fit
    median = hit.price_median
    if filters.max_price and median:
        if median <= filters.max_price:
            score += 1.0
            reasons.append("داخل سقف بودجه‌ی شما")
        else:
            over = (median - filters.max_price) / filters.max_price
            score -= min(2.0, over * 3)
            reasons.append("بالاتر از بودجه‌ی شما")
    if filters.min_price and median and median < filters.min_price:
        score -= 0.5

    # exact category match beats a tangential one
    if filters.category and hit.category == filters.category:
        score += 1.2
        reasons.append(f"در دسته‌ی «{filters.category}»")
    if filters.brand and hit.brand and fold(filters.brand) == fold(hit.brand):
        score += 1.0
        reasons.append(f"برند {hit.brand}")

    # a product with no priced offer is not actionable
    if not hit.offer_count:
        score -= 3.0

    return score, reasons


def search_products(query: str, filters: ProductFilters | None = None) -> list[ProductHit]:
    filters = filters or ProductFilters()
    q_tokens = [t for t in tokens(query) if len(t) > 1 and t not in ("های", "برای")]
    fts = _fts_query(query)

    sql_base = """
        SELECT p.id, p.title, p.brand, p.category, p.image_urls, p.key_specs,
               p.offer_count, p.shop_count, p.price_min, p.price_median, p.price_max
        FROM products p {join}
        WHERE 1=1 {conds}
        ORDER BY {order}
        LIMIT ?
    """
    conds = ""
    params: list = []
    if filters.in_stock_only:
        conds += " AND p.offer_count > 0"
    if filters.category:
        conds += " AND p.category = ?"
        params.append(filters.category)
    if filters.brand:
        conds += " AND p.brand LIKE ?"
        params.append(f"%{filters.brand}%")
    if filters.max_price:
        conds += " AND (p.price_median IS NULL OR p.price_median <= ?)"
        params.append(filters.max_price * 1.15)

    hits: list[ProductHit] = []
    with connection() as conn:
        if fts:
            try:
                sql = sql_base.format(
                    join="JOIN products_fts f ON f.product_id = p.id",
                    conds=" AND products_fts MATCH ?" + conds,
                    order="bm25(products_fts)",
                )
                rows = conn.execute(sql, [fts, *params, filters.limit * 6]).fetchall()
                hits = [_decode(r) for r in rows]
            except sqlite3.OperationalError:
                hits = []

        if not hits:
            # fallback: trigram-ish LIKE over the folded title, then category scan
            like = _like_query(query)
            if like:
                sql = sql_base.format(
                    join="", conds=" AND p.title_folded LIKE ?" + conds,
                    order="p.offer_count DESC")
                rows = conn.execute(sql, [f"%{like}%", *params, filters.limit * 6]).fetchall()
                hits = [_decode(r) for r in rows]
            if not hits and not query.strip():
                sql = sql_base.format(join="", conds=conds, order="p.offer_count DESC")
                rows = conn.execute(sql, [*params, filters.limit * 6]).fetchall()
                hits = [_decode(r) for r in rows]

    ranked: list[ProductHit] = []
    for hit in hits:
        score, reasons = _rank(hit, q_tokens, filters)
        hit.score = round(score, 3)
        hit.matched = reasons
        ranked.append(hit)
    ranked.sort(key=lambda h: (-h.score, -(h.shop_count or 0)))
    return ranked[: filters.limit]


def get_product(product_id: str) -> ProductHit | None:
    with connection() as conn:
        row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not row:
        return None
    hit = _decode(row)
    hit.score = 1.0
    return hit


def get_products(product_ids: list[str]) -> list[ProductHit]:
    if not product_ids:
        return []
    placeholders = ",".join("?" for _ in product_ids)
    with connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM products WHERE id IN ({placeholders})", product_ids).fetchall()
    by_id = {r["id"]: _decode(r) for r in rows}
    return [by_id[p] for p in product_ids if p in by_id]


def similar_products(product_id: str, limit: int = 4) -> list[ProductHit]:
    """Same family/category, nearby price band — used for "similar models"."""
    base = get_product(product_id)
    if not base:
        return []
    conds = ["p.id != ?", "p.offer_count > 0"]
    params: list = [product_id]
    if base.category:
        conds.append("p.category = ?")
        params.append(base.category)
    if base.price_median:
        conds += ["p.price_median BETWEEN ? AND ?"]
        params += [base.price_median * 0.6, base.price_median * 1.6]
    sql = (
        "SELECT * FROM products p WHERE " + " AND ".join(conds) +
        " ORDER BY ABS(COALESCE(p.price_median, 0) - ?) ASC LIMIT ?"
    )
    params += [base.price_median or 0, limit]
    with connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_decode(r) for r in rows]


def categories() -> list[dict]:
    """Category chips, data-driven from the serving DB with counts."""
    with connection() as conn:
        rows = conn.execute(
            """SELECT category, COUNT(*) n, SUM(offer_count) offers
               FROM products WHERE category IS NOT NULL
               GROUP BY category ORDER BY offers DESC""").fetchall()
    out = []
    for r in rows:
        cat = CATEGORY_BY_NAME.get(r["category"])
        out.append({
            "name": r["category"],
            "products": r["n"],
            "offers": int(r["offers"] or 0),
            "key_specs": list(cat.key_specs) if cat else [],
            "family": list(cat.families[:3]) if cat else [],
        })
    known = {o["name"] for o in out}
    for name in ALL_CATEGORY_NAMES:
        if name not in known:
            out.append({"name": name, "products": 0, "offers": 0,
                        "key_specs": [], "family": []})
    return out


def suggest(query: str, limit: int = 6) -> list[str]:
    """Lightweight autocomplete over titles."""
    toks = tokens(query)
    if not toks:
        return []
    with connection() as conn:
        rows = conn.execute(
            """SELECT DISTINCT p.title FROM products p
               WHERE p.title_folded LIKE ? AND p.offer_count > 0
               ORDER BY p.offer_count DESC LIMIT ?""",
            (f"%{toks[-1]}%", limit),
        ).fetchall()
    return [r[0] for r in rows]
