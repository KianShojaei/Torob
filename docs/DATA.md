# Data: what the challenge dataset actually contains, and how we treat it

> Source: Torob/Starcoach in-store dataset (CSV). The copy used in this repository is
> **synthetic but schema-faithful** — same columns, same pathologies, same rates — because the
> original archive was not reachable from the build environment.
> `/api/meta` always tells you which mode is running (`dataset_mode: "synthetic" | "real"`),
> and the UI shows the label in the home header.

---

## 1. Profile of the real snapshot

| Table | Rows | Key facts |
|---|---:|---|
| `shops.csv` | 6,476 | 4,473 with opening hours, 266 with `payment_options`, 19 malls, 30 neighbourhoods |
| `products.csv` | 225,903 | 3,428 distinct category strings, `brand_name` null for 74.5% |
| `offers.csv` | 331,506 | 20,315 duplicate `(shop, product)` pairs, 15,083 null prices |

What this means in practice:

* **Price is not a fact, it is a timestamped claim.** 4.5% of prices are missing and an unknown
  share are stale; `last_price_changed_at` alone does not prove stock.
* **`category_names` is a shop-level string array.** It is a *hint* about what a shop sells, never
  proof that a specific offer is in stock.
* **Hours are partially known and not normalized.** `unsupported` and missing day keys mean
  *unknown*, not *closed*.
* **Payment limits `0/0` mean "no information".** Treating them as "no limit" would fabricate
  installment offers.
* **Names are unreliable.** The dataset's shop names are demo values; looking them up elsewhere on
  the web would produce false facts. We never do.

---

## 2. ETL rules (implemented in `backend/app/etl/`)

| Rule | Implementation |
|---|---|
| `"null"` strings and empty cells → `None`; JSON parsed *safely* (broken → `None`, never a crash) | `services/normalize.py`, `etl/readers.py` |
| A price is valid only if `10_000 ≤ price ≤ 5_000_000_000` | `services/pricing.py::is_valid_price` |
| Duplicate `(shop, product)` offers → keep the most recently changed row | `etl/build.py` (`ROW_NUMBER() OVER (PARTITION BY shop_id, product_id …)`) |
| Availability is never inferred from price | `offers.price_valid` and `shops.*` stay separate columns all the way to the UI |
| Opening hours: cross-midnight, `unsupported` = unknown, Saturday-first week, `Asia/Tehran` | `services/hours.py` |
| Address: extract mall, floor, unit, landmark, street + a **confidence** score | `services/address.py` |
| Installment: `has_in_person_installment` only when a provider actually offers in-person installments; `0/0` limits ignored | `services/pricing.py`, `etl/enrich.py` |
| Product grouping: conservative `group_id` (same normalized title + brand + model) | `etl/enrich.py` |
| Search: FTS5 over folded titles + synonyms | `services/search.py`, `db/schema.py` |
| Cap 300 offers per shop (dataset contract) | `etl/build.py` |

### Derived labels shown in the UI

| Field | Values | Persian label |
|---|---|---|
| `price_age_bucket` | `fresh` < 7d · `recent` ≤ 30d · `old` ≤ 90d · `stale` > 90d | «تازه / چند روز پیش / قدیمی / کهنه» |
| `price_valid` | bool | «قیمت معتبر / قیمت نامعتبر» |
| `availability` | `listed` · `confirmed_in_stock` · `confirmed_out_of_stock` · `unknown` | «فقط در لیست / تأیید موجودی / ناموجود / نامشخص» |
| `open_state` at ETA | `open` · `closed` · `unknown` | «باز / بسته / نامشخص» |
| `installment_confirmed` | bool | «قسطی تأییدشده» / «نامشخص» |
| `addr_confidence` | 0…1 | «قطعیت آدرس» |

**Never** do we render a price without its age and availability label, and never do we convert
`unknown` into a positive statement.

---

## 3. Building

```bash
# real CSVs in ./data/{shops,products,offers}.csv
cd backend && python -m app.etl.build --data ../data --db var/app.db

# or a synthetic dataset with the same shape
python -m app.etl.synthetic --out ../data --shops 1200 --products 30000 --offers 60000
python -m app.etl.build --data ../data --db var/app.db

# invariants (also runs in CI)
python -m app.etl.validate --db var/app.db
```

Typical numbers from the demo build (1,200 shops / 30,000 products / ~47,500 offers):

```json
{ "shops": 1200, "products": 30000, "offers": 47514, "duplicates_removed": 2898,
  "usable_price_rate": 0.947, "malls": 19, "build_seconds": 10.5, "db_mb": 77 }
```

The ETL is **precomputed**: the container ships `app.db`, so cold start never runs it.
`validate` fails CI on: duplicates, cap300 violations, products without any offer, geo outside
Tehran, FTS index drift, implausible price validity, in-person installment > any installment.

---

## 4. Swapping in the real dataset

1. Drop the three CSVs into `data/` (the `.gitignore` excludes them; only `data/README.md` ships).
2. `make data` — the reader sniffs the header and maps Persian/English column names.
3. `python -m app.etl.validate` — expect `products_without_valid_price ≈ 6.7%`.
4. `make build && make serve` — `/api/meta` flips to `dataset_mode: "real"` automatically.

Nothing else changes: the UI and the agent read the same derived fields.
