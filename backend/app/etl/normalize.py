"""Persian text normalization (master prompt §4.2).

Two distinct outputs are needed:

* ``clean_display``  – safe to show to a human: trims, collapses whitespace,
  keeps Persian letters and Persian digits exactly as the seller wrote them.
* ``fold``           – aggressive folding for indexing/matching: unifies
  Arabic/Persian letter variants, ASCII-izes digits, removes ZWNJ/tatweel/
  diacritics, lowercases Latin and collapses whitespace.

Never index the display form, never display the folded form.
"""
from __future__ import annotations

import re
import unicodedata

# --- character maps -------------------------------------------------------

_AR_TO_FA = {
    "\u064a": "\u06cc",  # ي -> ی
    "\u0649": "\u06cc",  # ى -> ی
    "\u0643": "\u06a9",  # ك -> ک
    "\u0623": "\u0627",  # أ -> ا
    "\u0625": "\u0627",  # إ -> ا
    "\u0622": "\u0627",  # آ -> ا
    "\u0629": "\u0647",  # ة -> ه
    "\u06c0": "\u0647",  # ۀ -> ه
    "\u0624": "\u0648",  # ؤ -> و
    "\u0626": "\u06cc",  # ئ -> ی
}

_DIACRITICS = re.compile(r"[\u064b-\u065f\u0670\u0640]")  # harakat + tatweel
_ZWNJ = "\u200c"
_ZWJ = "\u200d"
_RTL_MARKS = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")
_WS = re.compile(r"\s+")

_DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

_TOKEN_RE = re.compile(r"[0-9a-z\u0600-\u06ff]+(?:[./-][0-9a-z\u0600-\u06ff]+)*")


def clean_display(value: str | None) -> str:
    """Human-facing cleanup: no content changes, only whitespace hygiene."""
    if not value:
        return ""
    s = unicodedata.normalize("NFC", str(value)).replace(_ZWJ, _ZWNJ)
    s = _RTL_MARKS.sub("", s)
    s = s.replace("\u00a0", " ")
    s = _WS.sub(" ", s).strip()
    return s


def fold(value: str | None) -> str:
    """Aggressive normalization used as the search key."""
    if not value:
        return ""
    s = unicodedata.normalize("NFC", str(value))
    s = _RTL_MARKS.sub("", s)
    s = _DIACRITICS.sub("", s)
    s = "".join(_AR_TO_FA.get(ch, ch) for ch in s)
    s = s.translate(_DIGIT_MAP)
    # ZWNJ and other joiners behave like a word separator for matching
    s = s.replace(_ZWNJ, " ").replace(_ZWJ, " ")
    s = s.lower()
    s = _WS.sub(" ", s).strip()
    return s


def to_ascii_digits(value: str) -> str:
    return (value or "").translate(_DIGIT_MAP)


def to_persian_digits(value: str) -> str:
    return (value or "").translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def tokens(value: str) -> list[str]:
    """Search tokens from a folded string, longest-first order preserved."""
    return [t for t in _TOKEN_RE.findall(fold(value)) if t]


# --- domain vocabulary ----------------------------------------------------

STOPWORDS = {
    "و", "یا", "از", "به", "با", "در", "که", "این", "آن", "را", "تا", "بر",
    "برای", "است", "هست", "بود", "شود", "کن", "کنم", "کنید", "می", "من",
    "من", "تو", "او", "ما", "شما", "های", "هایی", "هم", "یک", "چه", "چی",
    "کجا", "کدام", "چقدر", "چند", "خیلی", "یه", "یکی", "همین", "همان",
    "میخوام", "می‌خوام", "میخواهم", "می‌خواهم", "دنبال", "پیدا", "کنم",
}

# canonical term -> extra surface forms (all folded)
SYNONYMS: dict[str, tuple[str, ...]] = {
    "کتونی": ("کفش ورزشی", "اسنیکرز", "sneaker", "sneakers", "کفش رانینگ",
              "کفش پیاده روی", "کفش کتانی", "کتانی", "کفش"),
    "لپ تاپ": ("لپ تاپ", "لپتاپ", "نوت بوک", "نوتبوک", "laptop", "notebook"),
    "کتانی": ("کتونی", "کفش کتانی", "کفش ورزشی"),
    "گوشی": ("موبایل", "گوشی موبایل", "smartphone", "phone", "موبایل گوشی"),
    "یخچال": ("سردکن", "fridge", "refrigerator", "یخچال فریزر"),
    "ماشین لباسشویی": ("لباسشویی", "لباس شویی", "washing machine"),
    "تلویزیون": ("tv", "television", "تلویزیون هوشمند"),
    "هدفون": ("هدست", "headphone", "headphones", "ایرپاد", "earbuds"),
    "جاروبرقی": ("جارو برقی", "vacuum"),
    "مایکروویو": ("مایکروفر", "microwave"),
    "پنکه": ("فن", "fan"),
    "هارد": ("هارد دیسک", "hdd", "ssd", "اس اس دی"),
    "دوربین": ("دوربین مداربسته", "cctv", "cam"),
    "لامپ": ("لامپ led", "bulb", "ال ای دی"),
    "روتر": ("مودم", "router", "modem"),
}
_SYNONYM_INDEX: dict[str, set[str]] = {}
for _canon, _forms in SYNONYMS.items():
    _bucket = {fold(_canon), *(fold(f) for f in _forms)}
    for _f in _bucket:
        _SYNONYM_INDEX.setdefault(_f, set()).update(_bucket)

BRANDS = [
    "سامسونگ", "اپل", "شیائومی", "ال جی", "سونی", "داهوا", "هایک", "لنوو",
    "ایسوس", "اچ پی", "دل", "هواوی", "جی پلاس", "اسنوا", "کنوود", "امرسان",
    "پاکشوما", "بوش", "فیلیپس", "پاناسونیک", "اینتل", "ای ام دی", "امدی",
    "نایک", "آدیداس", "نیوبالانس", "پوما", "ریبوک", "کاله", "زرین",
]
_BRAND_INDEX = {fold(b) for b in BRANDS}


def expand_token(token: str) -> set[str]:
    """Return the token plus any known synonyms (folded)."""
    t = fold(token)
    out = {t}
    out.update(_SYNONYM_INDEX.get(t, set()))
    return out


def expand_tokens(tokens_in: list[str]) -> list[str]:
    seen: list[str] = []
    have: set[str] = set()
    for t in tokens_in:
        for v in sorted(expand_token(t)):
            if v not in have:
                have.add(v)
                seen.append(v)
    return seen


def is_brand(token: str) -> bool:
    return fold(token) in _BRAND_INDEX


def detect_brand(text: str) -> str | None:
    folded = fold(text)
    for b in BRANDS:
        if fold(b) in folded:
            return b
    return None
