# data/

The challenge CSVs go here. They are **never committed** (see `.gitignore`).

```
data/
├─ shops.csv
├─ products.csv
├─ offers.csv
└─ starcoach-dataset.zip   # optional, the original archive
```

Build the serving database:

```bash
cd backend && python -m app.etl.build --data ../data --db var/app.db
python -m app.etl.validate --db var/app.db       # invariants, also in CI
```

No dataset? Generate a schema-faithful demo set instead:

```bash
make synthetic && make data
```

Profile a real dataset first (shared markets, null rates, hours coverage):

```bash
python3 tools/profile_dataset.py data/
```

> **در محیط توسعه‌ی ابری** هاست `arvanstorage.ir` در دسترس نیست؛ فایل را از GitHub، پیوست چت یا
> لینک قابل دانلود دیگر برسانید. بدون داده هم `make synthetic` یک دیتاست نمایشی با همان ساختار
> می‌سازد.
