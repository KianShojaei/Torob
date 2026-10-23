"""Serving schema (master prompt §4.13).

SQLite is the shipped engine (the prompt's sanctioned "fallback mode"), chosen so a
single container on Liara can run with a persistent disk and no extra service.
All access goes through ``app.db.repository`` so a Postgres adapter can be added
without touching the API layer; the portable DDL for Postgres is in
``docs/schema.postgres.sql``.
"""
from __future__ import annotations

DDL = [
    # ---------- shops ----------
    """
    CREATE TABLE IF NOT EXISTS shops (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        name_is_real INTEGER NOT NULL DEFAULT 0,
        address TEXT,
        lat REAL,
        lon REAL,
        location_label TEXT,
        category_names TEXT,              -- JSON array
        contacts TEXT,                    -- JSON array
        instagram TEXT,
        website_url TEXT,
        payment_options TEXT,             -- JSON array
        has_in_person_installment INTEGER NOT NULL DEFAULT 0,
        has_any_installment INTEGER NOT NULL DEFAULT 0,
        installment_providers TEXT,       -- JSON array
        supports_fast_delivery TEXT,      -- true | false | unknown
        weekly_hours TEXT,                -- JSON object
        hours_known INTEGER NOT NULL DEFAULT 0,
        mall_name TEXT,
        mall_key TEXT,
        floor TEXT,
        unit TEXT,
        unit_kind TEXT,
        landmark TEXT,
        street TEXT,
        addr_confidence REAL NOT NULL DEFAULT 0,
        has_offers INTEGER NOT NULL DEFAULT 0,
        offer_count INTEGER NOT NULL DEFAULT 0,
        min_price REAL,
        max_price REAL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_shops_geo ON shops(lat, lon)",
    "CREATE INDEX IF NOT EXISTS idx_shops_label ON shops(location_label)",
    "CREATE INDEX IF NOT EXISTS idx_shops_mall ON shops(mall_key)",
    "CREATE INDEX IF NOT EXISTS idx_shops_offers ON shops(has_offers, offer_count)",
    # ---------- products ----------
    """
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        title_folded TEXT NOT NULL,
        title_len INTEGER NOT NULL DEFAULT 0,
        brand TEXT,
        category TEXT,
        model TEXT,
        image_urls TEXT,                  -- JSON array
        specs TEXT,                       -- JSON array {key,section,value}
        key_specs TEXT,                   -- JSON object {key: value}
        group_id TEXT,
        family TEXT,
        offer_count INTEGER NOT NULL DEFAULT 0,
        shop_count INTEGER NOT NULL DEFAULT 0,
        price_min REAL,
        price_median REAL,
        price_max REAL,
        price_p25 REAL,
        price_p75 REAL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)",
    "CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand)",
    "CREATE INDEX IF NOT EXISTS idx_products_group ON products(group_id)",
    "CREATE INDEX IF NOT EXISTS idx_products_offers ON products(offer_count DESC)",
    # ---------- offers ----------
    """
    CREATE TABLE IF NOT EXISTS offers (
        id TEXT PRIMARY KEY,
        shop_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        price REAL,
        price_valid INTEGER NOT NULL DEFAULT 0,
        last_changed_at TEXT,
        age_days INTEGER,
        age_bucket TEXT,
        seller_title TEXT,
        seller_title_folded TEXT,
        warranty TEXT,                    -- JSON
        warranty_months INTEGER,
        UNIQUE(shop_id, product_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_offers_product ON offers(product_id, price_valid, price)",
    "CREATE INDEX IF NOT EXISTS idx_offers_shop ON offers(shop_id)",
    "CREATE INDEX IF NOT EXISTS idx_offers_price ON offers(price_valid, price)",
    # ---------- malls ----------
    """
    CREATE TABLE IF NOT EXISTS malls (
        key TEXT PRIMARY KEY,
        name TEXT,
        lat REAL,
        lon REAL,
        shop_count INTEGER NOT NULL DEFAULT 0,
        categories TEXT,                  -- JSON array
        neighborhood TEXT
    )
    """,
    # ---------- neighbourhoods ----------
    """
    CREATE TABLE IF NOT EXISTS neighbourhoods (
        label TEXT PRIMARY KEY,
        lat REAL,
        lon REAL,
        shop_count INTEGER NOT NULL DEFAULT 0
    )
    """,
    # ---------- simulated seller conversation ----------
    """
    CREATE TABLE IF NOT EXISTS contact_threads (
        id TEXT PRIMARY KEY,
        shop_id TEXT NOT NULL,
        product_id TEXT,
        intent TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        sent_at TEXT,
        replied_at TEXT,
        reply_at TEXT,
        timeout_at TEXT,
        persona TEXT,                     -- JSON
        parsed TEXT                       -- JSON answer
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_threads_shop ON contact_threads(shop_id, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS contact_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id TEXT NOT NULL,
        role TEXT NOT NULL,               -- user | seller | system
        body TEXT NOT NULL,
        created_at TEXT NOT NULL,
        meta TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_messages_thread ON contact_messages(thread_id, id)",
    # ---------- analytics ----------
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        name TEXT NOT NULL,
        payload TEXT,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_events_name ON events(name, created_at)",
    """
    CREATE TABLE IF NOT EXISTS agent_runs (
        id TEXT PRIMARY KEY,
        session_id TEXT,
        state TEXT,
        tools TEXT,
        latency_ms INTEGER,
        provider TEXT,
        degraded INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        created_at TEXT NOT NULL
    )
    """,
]

# FTS5 is created separately because availability differs between builds.
FTS_DDL = [
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
        product_id UNINDEXED,
        title,
        brand,
        category,
        specs,
        tokenize = 'unicode61 remove_diacritics 2'
    )
    """,
]

META_DDL = [
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)",
]

ALL_DDL = DDL + META_DDL

TABLES_IN_ORDER = [
    "shops", "products", "offers", "malls", "neighbourhoods",
    "contact_threads", "contact_messages", "events", "agent_runs", "meta",
]
