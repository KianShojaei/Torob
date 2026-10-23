# پوشه‌ی داده

فایل‌های CSV دیتاست اینجا قرار می‌گیرند و **در گیت کامیت نمی‌شوند** (به `.gitignore` نگاه کنید).

```
data/
├─ shops.csv
├─ products.csv
├─ offers.csv
└─ starcoach-dataset.zip   # یا zip اصلی
```

سپس پروفایل بگیرید:

```bash
python3 tools/profile_dataset.py data/
```

> در محیط توسعه‌ی ابری، هاست `arvanstorage.ir` قابل دسترسی نیست. فایل را از طریق GitHub،
> پیوست چت، یا لینک قابل دانلود دیگر تحویل دهید.
