import re

ARABIC_TO_PERSIAN = str.maketrans({
    "ي": "ی", "ى": "ی", "ئ": "ی", "ك": "ک", "ؤ": "و",
    "إ": "ا", "أ": "ا", "ٱ": "ا", "ة": "ه", "ۀ": "ه",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
})

DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670\u0640]")
ZWNJ_RE = re.compile(r"[\u200c\u200d\u200e\u200f]+")
MULTI_SPACE_RE = re.compile(r"\s+")

PHONETIC_TYPO_MAP = [
    (r"\bشیا(?:ی|ئ)?ومی\b|\bشیومی\b|\bشیاومی\b|\bشیائومی\b", "شیایومی"),
    (r"\bسامسنگ\b|\bسمسونگ\b", "سامسونگ"),
    (r"\bهنسفری\b|\bهندفری\b|\bهنزفری\b", "هندزفری"),
    (r"\bایر\s*پاد\b|\bایرپادز\b", "ایرپاد"),
    (r"\bپاور\s*بانک\b", "پاوربانک"),
    (r"\bلپتاپ\b|\bلب\s*تاپ\b|\bلبتاپ\b", "لپ تاپ"),
    (r"\bمکبوک\b", "مک بوک"),
    (r"\bاسمارتواچ\b", "اسمارت واچ"),
    (r"\bمداربسته\b", "مدار بسته"),
    (r"\bهایکویژن\b", "هایک ویژن"),
    (r"\bکیوسیوای\b|\bکیو\s*سی\s*وای\b", "qcy"),
]

def to_ascii_digits(text: str) -> str:
    return text.translate(ARABIC_TO_PERSIAN) if text else ""

def normalize_persian(text: str | None) -> str:
    if not text or text == "null":
        return ""
    s = str(text).translate(ARABIC_TO_PERSIAN)
    s = DIACRITICS_RE.sub("", s)
    s = ZWNJ_RE.sub(" ", s)
    s = s.lower()
    s = MULTI_SPACE_RE.sub(" ", s).strip()
    for pattern, repl in PHONETIC_TYPO_MAP:
        s = re.sub(pattern, repl, s)
    return s

def to_persian_digits(val: str | int | float) -> str:
    return str(val).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
