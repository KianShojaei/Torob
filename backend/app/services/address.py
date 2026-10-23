"""Address parser + in-mall guidance generator (master prompt §4.8, §4.9).

Regex-first and deterministic: no LLM is needed at request time, which keeps the
"contact" and "visit" flows fast and testable. Everything the parser is not sure
about is reported as *missing*, never guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.etl.normalize import fold, to_ascii_digits, to_persian_digits

MALL_MARKERS = ("پاساژ", "مجتمع", "مرکز خرید", "بازار", "برج", "مال", "پلازا", "سنتر")
_MALL_RE = re.compile(
    r"(?:پاساژ|مجتمع(?:\s+تجاری)?|مرکز\s+خرید|بازار|برج|پلازا|سنتر|مال)\s+"
    r"(?P<name>[\u0600-\u06ff0-9a-zA-Z\s\-]{2,40}?)"
    r"(?=\s*(?:،|,|\.|$|طبقه|واحد|مغازه|پلاک|همکف|زیرزمین|نبش|خیابان|کوچه|بلوار|میدان|پاساژ|مجتمع|بازار))"
)

FLOOR_WORDS = {
    "همکف": "همکف",
    "زیرزمین": "زیرزمین",
    "اول": "1",
    "دوم": "2",
    "سوم": "3",
    "چهارم": "4",
    "پنجم": "5",
    "ششم": "6",
    "هفتم": "7",
    "هشتم": "8",
    "نهم": "9",
    "دهم": "10",
}
_NEGATIVE_FLOOR_WORDS = {"یک": "1", "دو": "2", "سه": "3", "چهار": "4", "پنج": "5"}
_FLOOR_RE = re.compile(
    r"(?:طبقه|ط\.)\s*(?P<v>همکف|زیرزمین|(?:منفی|منهای)\s*(?:\d+|یک|دو|سه|چهار|پنج)|"
    r"[\u06f0-\u06f9\d]{1,2}|اول|دوم|سوم|چهارم|پنجم|ششم|هفتم|هشتم|نهم|دهم)"
)
_UNIT_RE = re.compile(
    r"(?:واحد|مغازه|پلاک|دکان)\s*(?:شماره\s*)?(?P<v>[\u06f0-\u06f9\d]{1,5})"
)

_FLOOR_RE = re.compile(
    r"(?:طبقه|ط\.)\s*(?P<v>همکف|زیرزمین|(?:منفی|منهای)\s*(?:\d+|یک|دو|سه|چهار|پنج)|"
    r"[\u06f0-\u06f9\d]{1,2}|اول|دوم|سوم|چهارم|پنجم|ششم|هفتم|هشتم|نهم|دهم)"
)
_LANDMARK_RES = [
    re.compile(r"(?P<v>نبش\s+[^،,.]{2,40})"),
    re.compile(r"(?P<v>(?:بعد|قبل)\s+از\s+[^،,.]{2,40})"),
    re.compile(r"(?P<v>[^،,.]{2,30}\s+به\s+[^،,.]{2,30}\s+رسیده)"),
    re.compile(r"(?P<v>(?:تقاطع|چهارراه|میدان)\s+[^،,.]{2,30})"),
]
_STREET_RE = re.compile(r"(?P<v>(?:خیابان|بلوار|کوچه|بزرگراه|جاده)\s+[^،,.]{2,40})")


@dataclass
class AddressParts:
    mall_name: str | None = None
    mall_key: str | None = None          # normalized, used for clustering
    floor: str | None = None
    unit: str | None = None
    unit_kind: str | None = None         # واحد | مغازه | پلاک
    landmark: str | None = None
    street: str | None = None
    confidence: float = 0.0
    missing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "mall_name": self.mall_name,
            "floor": self.floor,
            "unit": self.unit,
            "unit_kind": self.unit_kind,
            "landmark": self.landmark,
            "street": self.street,
            "confidence": round(self.confidence, 2),
            "missing": self.missing,
        }


def _norm_floor(raw: str) -> str:
    v = to_ascii_digits(raw).strip()
    v = re.sub(r"\s+", " ", v)
    if v in FLOOR_WORDS:
        return FLOOR_WORDS[v]
    m = re.match(r"(?:منفی|منهای)\s*(\d+)", v)
    if m:
        return f"منفی {to_ascii_digits(m.group(1))}"
    m = re.match(r"(?:منفی|منهای)\s*(یک|دو|سه|چهار|پنج)", v)
    if m:
        return f"منفی {_NEGATIVE_FLOOR_WORDS[m.group(1)]}"
    return v


def mall_key(name: str | None) -> str | None:
    """Normalized key for grouping shops inside the same mall."""
    if not name:
        return None
    k = fold(name)
    for marker in MALL_MARKERS:
        k = k.replace(fold(marker), " ")
    k = re.sub(r"[^\w\u0600-\u06ff]+", " ", k)
    k = re.sub(r"\s+", " ", k).strip()
    return k or None


def parse_address(address: str | None) -> AddressParts:
    text = to_ascii_digits((address or "").strip())
    parts = AddressParts()
    if not text:
        parts.missing = ["آدرس"]
        return parts

    m = _MALL_RE.search(text)
    if m:
        raw_name = re.sub(r"\s+", " ", m.group("name")).strip(" -،,")
        matched = re.sub(r"\s+", " ", m.group(0))
        marker = matched[: len(matched) - len(m.group("name"))].strip() or matched.split()[0]
        # keep Persian digits for display
        parts.mall_name = f"{marker} {to_persian_digits(raw_name)}".strip()
        parts.mall_key = mall_key(raw_name)

    m = _FLOOR_RE.search(text)
    if m:
        parts.floor = _norm_floor(m.group("v"))

    m = _UNIT_RE.search(text)
    if m:
        parts.unit = to_ascii_digits(m.group("v"))
        kind = m.group(0).split()[0]
        parts.unit_kind = kind if kind in ("واحد", "مغازه", "پلاک", "دکان") else "واحد"

    for rx in _LANDMARK_RES:
        lm = rx.search(text)
        if lm:
            parts.landmark = re.sub(r"\s+", " ", lm.group("v")).strip(" ،,")
            break

    st = _STREET_RE.search(text)
    if st:
        parts.street = re.sub(r"\s+", " ", st.group("v")).strip(" ،,")

    found = sum(
        1 for v in (parts.mall_name, parts.floor, parts.unit, parts.landmark) if v
    )
    if parts.mall_name:
        parts.confidence = min(0.95, 0.30 + 0.25 + 0.15 * bool(parts.floor) + 0.20 * bool(parts.unit))
    else:
        parts.confidence = min(0.6, 0.10 + 0.15 * found + 0.10 * bool(parts.street))

    if not parts.mall_name:
        parts.missing.append("نام پاساژ")
    if not parts.floor:
        parts.missing.append("طبقه")
    if not parts.unit:
        parts.missing.append("واحد")
    return parts


def find_it_text(parts: AddressParts, shop_name: str | None = None) -> dict:
    """The "how to find it" card. Only states what is known (§4.9)."""
    known: list[str] = []
    if parts.mall_name:
        known.append(parts.mall_name)
    if parts.floor:
        known.append(f"طبقه {parts.floor}")
    if parts.unit:
        known.append(f"{parts.unit_kind or 'واحد'} {parts.unit}")

    if parts.mall_name and parts.floor and parts.unit:
        title = "، ".join(known)
        detail = (
            f"وارد {parts.mall_name} شوید، به طبقه {parts.floor} بروید و "
            f"{parts.unit_kind or 'واحد'} {parts.unit} را پیدا کنید."
        )
    elif parts.mall_name and (parts.floor or parts.unit):
        title = "، ".join(known)
        detail = f"در {parts.mall_name} هست. " + (
            f"طبقه {parts.floor} را پیدا کنید. " if parts.floor else ""
        ) + (
            f"{parts.unit_kind or 'واحد'} {parts.unit} مشخص است." if parts.unit else
            "شماره واحد ثبت نشده؛ از نگهبان یا فروشنده بپرسید."
        )
    elif parts.mall_name:
        title = parts.mall_name
        detail = (
            "فقط نام پاساژ ثبت شده. طبقه و واحد نامشخص است؛ "
            "بهتر است قبل از رفتن از فروشنده بپرسید."
        )
    elif parts.street:
        title = parts.street
        detail = "آدرس پاساژ ثبت نشده؛ از روی خیابان و پلاک مسیریابی کنید."
    else:
        title = "آدرس دقیق ثبت نشده"
        detail = "این فروشگاه آدرس قابل استناد ندارد؛ حتماً قبل از رفتن تماس بگیرید."

    ask_sentence = None
    if not (parts.floor and parts.unit):
        shop = shop_name or "این فروشگاه"
        ask_sentence = f"سلام، {shop} در این پاساژ کجاست؟ طبقه و واحدش را می‌فرمایید؟"

    return {
        "title": title,
        "detail": detail,
        "known": known,
        "missing": parts.missing,
        "confidence": round(parts.confidence, 2),
        "ask_sentence": ask_sentence,
        "landmark": parts.landmark,
    }
