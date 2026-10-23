"""Strict parser for seller replies (master prompt §6.5).

The LLM (or the deterministic template) writes free Persian text; this module turns
it into typed facts. Regex is the reliable path; an optional LLM extractor can be
plugged in with a strict JSON schema, but the regex result always wins when both
exist to keep behaviour deterministic in the demo.

Extracted fields:
    in_stock           bool | None
    confirmed_price    int | None      (Toman)
    unit               str | None
    hours_info         str | None
    needs_followup     bool
    alternatives_mentioned bool
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

from app.etl.normalize import to_ascii_digits

OUT_PATTERNS = [
    r"موجود نیست", r"تموم شد", r"تمام شده", r"نداریم", r"ندارم", r"نمی‌آر(?:ه|د)",
    r"موجود نداریم", r"کالا نیست", r"نیست", r"سفارش(?:ی)? نیست",
]
IN_PATTERNS = [
    r"موجود(?:ه| است| هست| داریم| دارم)", r"داریم", r"دارم", r"هست", r"موجوده",
    r"بله\s*،?\s*موجود", r"قابل خرید",
]
CLOSED_PATTERNS = [
    r"بسته(?:‌ایم| ایم| است| هست)?", r"تعطیل", r"ساعت کاری(?:‌مان)?",
    r"فردا", r"از ساعت \d+",
]
PRICE_RE = re.compile(
    r"(?P<num>\d{1,3}(?:[,،٬]\d{3})+|\d{4,18})\s*(?P<unit>تومن|تومان|هزار تومن|میلیون)?"
)


@dataclass
class ParsedReply:
    in_stock: bool | None = None
    confirmed_price: int | None = None
    unit: str | None = None
    hours_info: str | None = None
    needs_followup: bool = False
    alternatives_mentioned: bool = False
    raw: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _normalize_digits(text: str) -> str:
    return to_ascii_digits(text)


def extract_price(text: str) -> int | None:
    """Highest plausible Toman amount in the reply, in 10k..5e9."""
    best: int | None = None
    for m in PRICE_RE.finditer(_normalize_digits(text)):
        raw = m.group("num").replace(",", "").replace("،", "").replace("٬", "")
        try:
            value = int(raw)
        except ValueError:
            continue
        unit = (m.group("unit") or "").strip()
        if unit in ("هزار تومن",):
            value *= 1000
        elif unit == "میلیون":
            value *= 1_000_000
        if 10_000 <= value <= 5_000_000_000:
            if best is None or value > best:
                best = value
    return best


def parse_reply(text: str) -> ParsedReply:
    out = ParsedReply(raw=text)
    folded = text.replace("\u200c", " ").replace("\u200f", "").replace("\u200e", "")
    lowered = folded.lower()

    if any(re.search(p, lowered) for p in CLOSED_PATTERNS):
        m = re.search(r"(?:ساعت|از)\s*([0-9۰-۹]{1,2}[:٫.][0-9۰-۹]{1,2}|\d{1,2})", folded)
        if m:
            out.hours_info = m.group(0).strip()
        elif "بسته" in lowered or "تعطیل" in lowered:
            out.hours_info = "الان بسته است"
        out.needs_followup = out.hours_info is not None

    if any(re.search(p, lowered) for p in OUT_PATTERNS):
        out.in_stock = False
    elif any(re.search(p, lowered) for p in IN_PATTERNS):
        out.in_stock = True

    price = extract_price(folded)
    if price is not None:
        out.confirmed_price = price
        out.unit = "تومان"

    if re.search(r"(?:فروشگاه|مغازه)\s+(?:دیگر|دیگه)|جای دیگه|آنلاین|ترب", folded):
        out.alternatives_mentioned = True

    return out
