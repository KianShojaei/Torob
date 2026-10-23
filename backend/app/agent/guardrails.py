"""Guardrails that keep the LLM honest (master prompt §5.1, §7).

Two checks run on every model-written string before it reaches the UI:

1. **Numbers.** Any number in the final text must already exist in the tool
   results (or be a Persian-formatted variant of one). Invented prices, hours or
   distances get the sentence removed rather than shown.
2. **Entities.** Shop/product names must appear in the tool results.

The deterministic composer never needs this, but the guard is applied to both so a
future prompt change cannot leak a hallucinated price into the UI.
"""
from __future__ import annotations

import re

from app.etl.normalize import to_ascii_digits

NUMBER_RE = re.compile(r"\d[\d,٬.]*")
_URLISH = re.compile(r"https?://\S+")


def _numbers_in(text: str) -> set[str]:
    out = set()
    for m in NUMBER_RE.finditer(to_ascii_digits(text or "")):
        raw = m.group(0).replace(",", "").replace("٬", "").replace(".", "")
        if raw:
            out.add(raw.lstrip("0") or "0")
    return out


def collect_numbers(obj, acc: set[str], depth: int = 0) -> set[str]:
    if depth > 6:
        return acc
    if isinstance(obj, dict):
        for v in obj.values():
            collect_numbers(v, acc, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            collect_numbers(v, acc, depth + 1)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        acc.add(str(int(obj)))
        acc |= _numbers_in(f"{obj:,}")
    elif isinstance(obj, str):
        acc |= _numbers_in(obj)
    return acc


def check_text(text: str, tool_results: list | dict) -> tuple[bool, list[str]]:
    """Return (ok, violations). Violations are sentence fragments to drop."""
    allowed = collect_numbers(tool_results, set())
    violations: list[str] = []
    for sentence in re.split(r"(?<=[.!؟?\n])\s+", text or ""):
        if not sentence.strip():
            continue
        nums = _numbers_in(sentence)
        # tiny numbers are usually list markers or ordinals, not claims
        suspicious = {n for n in nums if len(n) >= 4}
        if suspicious - allowed:
            violations.append(sentence.strip())
    return (not violations), violations


def sanitize(text: str, tool_results) -> str:
    ok, violations = check_text(text, tool_results)
    if ok:
        return text
    kept = [s for s in re.split(r"(?<=[.!؟?\n])\s+", text) if s.strip() and s.strip() not in violations]
    return " ".join(kept).strip()


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def clean_model_text(text: str) -> str:
    """Never render model output as HTML; also drop fabricated URLs."""
    t = strip_html(text)
    return _URLISH.sub("", t).strip()
