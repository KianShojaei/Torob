"""Query understanding → structured need (master prompt §5.3 tool 1).

Deterministic Persian parsing runs first and is always available (degraded mode).
When an LLM is configured, its JSON output may refine the same structure; the
deterministic values win on conflicts because they are auditable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from app.etl.normalize import fold, to_ascii_digits
from app.etl.taxonomy import CATEGORIES, CATEGORY_BY_KEY, CATEGORY_BY_NAME, key_specs_for


@dataclass
class Need:
    query: str = ""
    category: str | None = None
    brand: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    installment_only: bool = False
    radius_km: float | None = None
    neighborhood: str | None = None
    usage: str | None = None
    urgency: str | None = None
    open_now: bool = False
    intent: str = "search"          # search | compare | stores | contact | plan | hours
    key_specs: dict = field(default_factory=dict)
    sort: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


NUM_WORDS = {
    "یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6, "هفت": 7,
    "هشت": 8, "نه": 9, "ده": 10, "بیست": 20, "سی": 30, "پنجاه": 50,
    "صد": 100, "هزار": 1000,
}

BUDGET_RE = re.compile(
    r"(?:زیر|کمتر از|حداکثر|تا|نهایتا|نهایتاً|بودجه(?:‌ام| ام)?|قیمتش?)\s*"
    r"(?P<num>[\d۰-۹.,٬]+)\s*(?P<scale>میلیون|ملیون|هزار|تومن|تومان|ت)?",
    re.IGNORECASE,
)
RANGE_RE = re.compile(
    r"(?P<a>[\d۰-۹.,٬]+)\s*(?:تا|-)\s*(?P<b>[\d۰-۹.,٬]+)\s*(?P<scale>میلیون|هزار)?"
)

CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "audio": ("هدفون", "هندزفری", "هدست", "اسپیکر", "ایرپاد", "هندز فری"),
    "mobile": ("گوشی", "موبایل", "smartphone"),
    "laptop": ("لپ تاپ", "لپتاپ", "نوت بوک", "نوتبوک", "لپ"),
    "tv": ("تلویزیون", "تی وی", "tv", "پروژکتور"),
    "fridge": ("یخچال", "فریزر", "ساید"),
    "home": ("لباسشویی", "لباس شویی", "ظرفشویی", "جاروبرقی", "جارو برقی",
             "مایکروویو", "مایکروفر", "اجاق", "چای ساز", "چایساز", "سرخ کن",
             "سرخ‌کن", "مخلوط کن", "اتو", "پنکه", "کولر", "آبگرمکن", "تصفیه آب"),
    "cctv": ("دوربین", "مداربسته", "cctv", "dvr"),
    "lighting": ("لامپ", "روشنایی", "ریسه", "هالوژن", "چراغ"),
    "electrical": ("سیم", "کابل", "کلید برق", "پریز", "محافظ"),
    "network": ("مودم", "روتر", "اکسس پوینت", "سوییچ", "وای فای", "وایفای"),
    "storage": ("هارد", "فلش", "ssd", "اس اس دی", "کارت حافظه", "حافظه"),
    "monitor": ("مانیتور", "نمایشگر"),
    "tablet": ("تبلت", "آیپد", "ایپد"),
    "wearable": ("ساعت هوشمند", "مچ بند", "مچ‌بند", "smartwatch"),
    "printer": ("پرینتر", "چاپگر", "اسکنر"),
    "shoes": ("کتونی", "کفش", "اسنیکرز", "کتانی"),
    "bags": ("کوله", "کیف", "ساک"),
}

BRAND_HINTS = ("سامسونگ", "اپل", "شیائومی", "سونی", "ال جی", "ال‌جی", "لنوو",
               "ایسوس", "ایسر", "دل", "اچ پی", "هواوی", "داهوا", "هایک",
               "تی پی لینک", "تی‌پی‌لینک", "مرکوسیس", "اسنوا", "بوش", "پاکشوما",
               "نایک", "آدیداس", "نیوبالانس", "پوما", "انکر", "جی بی ال")

INSTALLMENT_HINTS = ("قسطی", "اقساط", "قسط", "اعتباری", "چک", "وام", "bnpl", "اقساطی")
OPEN_HINTS = ("باز است", "بازن", "الان باز", "همین الان", "امروز")
NEAR_HINTS = ("نزدیک", "نزدیکم", "حوالی", "همین حوالی", "این طرف", "اینطرف")
CONTACT_HINTS = ("تماس", "زنگ", "بپرس", "سوال", "سؤال", "پیام", "چت کن",
                 "موجوده", "موجود هست", "قیمتش چنده", "قیمت چنده")
COMPARE_HINTS = ("مقایسه", "فرق", "تفاوت", "کدوم بهتر", "کدام بهتر")
PLAN_HINTS = ("برنامه سفر", "مسیر", "اول کجا", "ترتیب", "پلن", "برنامه خرید")


_BOUND_L = r"(?<![\u0600-\u06ff\w])"
_BOUND_R = r"(?![\u0600-\u06ff\w])"


def has_word(folded_text: str, word: str) -> bool:
    """Persian-safe whole-word test (\\b misbehaves with ZWNJ and Arabic script)."""
    w = fold(word)
    if not w:
        return False
    if len(w) <= 4:
        return re.search(_BOUND_L + re.escape(w) + _BOUND_R, folded_text) is not None
    return w in folded_text


def _to_number(raw: str) -> float | None:
    s = to_ascii_digits(raw).replace("٬", "").replace(",", "").replace("،", "")
    try:
        return float(s)
    except ValueError:
        return None


def _scale(value: float, unit: str | None) -> float:
    u = (unit or "").strip()
    if u in ("میلیون", "ملیون"):
        return value * 1_000_000
    if u == "هزار":
        return value * 1_000
    # "2.5" with a decimal point usually means million in Iranian speech
    if value < 1000 and "." in str(value):
        return value * 1_000_000
    if value < 1000:
        return value * 1_000_000  # "زیر ۳" → 3 million is the common reading
    return value


def extract_budget(text: str) -> tuple[float | None, float | None]:
    folded = to_ascii_digits(text)
    rng = RANGE_RE.search(folded)
    if rng:
        a = _to_number(rng.group("a"))
        b = _to_number(rng.group("b"))
        if a and b:
            scale = rng.group("scale")
            if scale:
                return _scale(a, scale), _scale(b, scale)
            return _scale(a, None), _scale(b, None)

    m = BUDGET_RE.search(folded)
    if m:
        num = _to_number(m.group("num"))
        if num is not None:
            value = _scale(num, m.group("scale"))
            if 100_000 <= value <= 5_000_000_000:
                return None, value
    return None, None


def detect_category(text: str) -> str | None:
    folded = fold(text)
    best: tuple[int, str] | None = None
    for key, hints in CATEGORY_HINTS.items():
        for h in hints:
            if fold(h) in folded:
                score = len(fold(h))
                if best is None or score > best[0]:
                    best = (score, key)
    if best:
        cat = CATEGORY_BY_KEY.get(best[1])
        return cat.name if cat else None
    # direct category name
    for cat in CATEGORIES:
        if fold(cat.name) in folded:
            return cat.name
    return None


def detect_brand(text: str) -> str | None:
    folded = fold(text)
    for b in sorted(BRAND_HINTS, key=len, reverse=True):
        if fold(b) in folded:
            return b.replace("‌", " ")
    return None


def detect_neighborhood(text: str, labels: list[str]) -> str | None:
    folded = fold(text)
    for label in sorted(labels, key=len, reverse=True):
        if fold(label) in folded:
            return label
    return None


def understand(query: str, *, neighborhoods: list[str] | None = None,
               default_category: str | None = None) -> Need:
    q = (query or "").strip()
    folded = fold(q)
    need = Need(query=q)

    need.budget_min, need.budget_max = extract_budget(q)
    need.category = detect_category(q) or default_category
    need.brand = detect_brand(q)
    need.installment_only = any(has_word(folded, h) for h in INSTALLMENT_HINTS)
    need.open_now = any(fold(h) in folded for h in OPEN_HINTS)

    if any(fold(h) in folded for h in CONTACT_HINTS):
        need.intent = "contact"
    elif any(fold(h) in folded for h in COMPARE_HINTS):
        need.intent = "compare"
    elif any(fold(h) in folded for h in PLAN_HINTS):
        need.intent = "plan"
    elif any(fold(h) in folded for h in ("فروشگاه", "مغازه", "کجا بخرم", "کجا هست", "کجا میتونم")):
        need.intent = "stores"

    radius = re.search(r"(\d{1,2})\s*(?:کیلومتر|کیلومتری|km)", folded)
    if radius:
        need.radius_km = float(radius.group(1))
    elif any(fold(h) in folded for h in NEAR_HINTS):
        need.radius_km = 4.0

    if neighborhoods:
        need.neighborhood = detect_neighborhood(q, neighborhoods)

    for usage in ("پیاده روی", "پیاده‌روی", "دویدن", "باشگاه", "بازی", "برنامه نویسی",
                  "برنامه‌نویسی", "اداری", "دانشجویی", "دانشجویی", "گیمینگ", "نقاشی"):
        if fold(usage) in folded:
            need.usage = usage
            break

    if any(fold(h) in folded for h in ("ارزان", "ارزون", "کمترین قیمت")):
        need.sort = "cheapest"
    elif any(fold(h) in folded for h in ("نزدیکترین", "نزدیک ترین")):
        need.sort = "nearest"
    elif any(fold(h) in folded for h in ("مطمئن", "معتبر", "بهترین")):
        need.sort = "trusted"

    # key specs mentioned directly, e.g. "رم ۸ گیگ" or "سایز ۴۲"
    if need.category:
        for spec in key_specs_for(need.category):
            if fold(spec) in folded:
                after = folded.split(fold(spec), 1)[1][:24]
                need.key_specs[spec] = after.strip()

    need.query = clean_query(q, need)
    return need


def clean_query(query: str, need: Need) -> str:
    """Strip filter words so lexical search sees the product words only."""
    q = query
    for pattern in (
        r"بین\s*[\d۰-۹.,٬]+\s*تا\s*[\d۰-۹.,٬]+\s*(?:میلیون|ملیون|هزار|تومن|تومان)?",
        r"زیر\s*[\d۰-۹.,٬]+\s*(?:میلیون|ملیون|هزار|تومن|تومان|ت)?",
        r"(?:کمتر از|حداکثر|نهایتا)\s*[\d۰-۹.,٬]+\s*(?:میلیون|هزار|تومن|تومان)?",
        r"(?<![\u0600-\u06ff\w])تا\s*[\d۰-۹.,٬]+\s*(?:میلیون|ملیون|هزار|تومن|تومان)",
        r"(?<![\u0600-\u06ff\w])(?:قسطی|اقساطی|اقساط|اعتباری|چک|وام|bnpl)(?![\u0600-\u06ff\w])",
        r"نزدیک(?:م|ترین)?|حوالی|این طرف|اینطرف",
        r"الان باز|باز است|بازن",
        r"میخوام|می‌خوام|میخواهم|می‌خواهم|دنبال|پیدا کنم|میگردم|می‌گردم|می\s*خوام",
        r"کجا\s*(?:می\s*تونی?م|بخرم|هست|پیدا)",
    ):
        q = re.sub(pattern, " ", q)
    q = re.sub(r"\s+", " ", q).strip(" ،,.")
    return q or need.category or query
