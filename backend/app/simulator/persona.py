"""Deterministic seller personas (master prompt §6.5).

Every shop gets a stable persona derived from a hash of its id, so the same shop
always behaves the same way across restarts and demo runs. Persona dimensions:

* responsiveness — instant | minutes | slow | never  (~30% never)
* reliability     — in-stock probability, lower when the recorded price is stale
* price_drift     — unchanged | ±1–10%
* style           — formal | chatty | terse
* behaviours      — "closed now" auto-reply, "call me", "come in person", ask-back
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Persona:
    shop_id: str
    responsiveness: str      # instant | minutes | slow | never
    delay_seconds: int       # simulated delay before the first reply
    reliability: float       # 0..1 chance the product is in stock
    price_drift: float       # multiplier applied to the recorded price
    style: str               # formal | chatty | terse
    answers_hours: bool
    will_ask_back: bool
    prefers_phone: bool
    prefers_in_person: bool
    seed: int

    def as_dict(self) -> dict:
        return asdict(self)


def _rng(shop_id: str) -> random.Random:
    digest = hashlib.sha256(shop_id.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def persona_for(shop_id: str, shop_name: str | None = None,
                age_days: int | None = None, hours_known: bool = False) -> Persona:
    rng = _rng(shop_id)
    roll = rng.random()
    # delays are SIMULATED seconds; the demo clock divides by DEMO_TIME_SCALE
    if roll < 0.34:
        resp = "instant"
        delay = rng.randint(20, 55)          # ~1–3 real seconds at scale 20
    elif roll < 0.62:
        resp = "minutes"
        delay = rng.randint(120, 300)        # ~6–15 real seconds
    elif roll < 0.86:
        resp = "slow"
        delay = rng.randint(330, 600)        # ~16–30 real seconds
    else:
        resp = "never"
        delay = 0                            # no reply at all

    # stale prices correlate with unreliable listings (§6.5)
    base = 0.82 if (age_days is not None and age_days <= 7) else 0.58
    if age_days is None:
        base = 0.52
    reliability = max(0.15, min(0.97, base + rng.uniform(-0.12, 0.12)))

    drift_roll = rng.random()
    if drift_roll < 0.45:
        drift = 1.0
    elif drift_roll < 0.75:
        drift = 1 + rng.uniform(0.01, 0.10)
    else:
        drift = 1 - rng.uniform(0.01, 0.10)

    style = rng.choices(["formal", "chatty", "terse"], weights=[0.45, 0.35, 0.20])[0]
    return Persona(
        shop_id=shop_id,
        responsiveness=resp,
        delay_seconds=delay,
        reliability=round(reliability, 3),
        price_drift=round(drift, 4),
        style=style,
        answers_hours=rng.random() < (0.9 if hours_known else 0.55),
        will_ask_back=rng.random() < 0.22,
        prefers_phone=rng.random() < 0.12,
        prefers_in_person=rng.random() < 0.18,
        seed=rng.randint(0, 2**31 - 1),
    )


OPENING = {
    "formal": ["سلام، وقت بخیر.", "سلام، در خدمتم.", "وقت بخیر، بفرمایید."],
    "chatty": ["سلام سلام 🌹", "سلام، خوش آمدید.", "سلام رفیق، در خدمتم."],
    "terse": ["سلام.", "بله؟", "سلام، بفرمایید."],
}
CLOSING = {
    "formal": ["با احترام", "سپاس از تماس شما", "در خدمت شما هستیم"],
    "chatty": ["مرسی از پیامتون 🙏", "منتظرتونیم", "خوشحال می‌شیم ببینیمتون"],
    "terse": ["ممنون", "موفق باشید", ""],
}
