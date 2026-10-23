"""Seller contact simulator + channel adapters (master prompt §6.5).

Design notes
------------
* **Stateless scheduling.** A thread stores ``timeout_at`` and ``persona``; the
  reply text is generated lazily when the client polls. No background worker is
  needed, which keeps the single-container deployment simple and restart-safe.
* **Time compression.** ``DEMO_TIME_SCALE`` maps one simulated minute to
  ``60/scale`` real seconds, so a 5-minute demo can show a reply, a timeout and a
  failover.
* **Honesty.** The UI always shows a "شبیه‌سازی" badge; ``SimulatedChannel`` never
  claims to be a real shop and no real message is ever sent.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Protocol

from app.config import settings
from app.db.engine import connection, write_connection
from app.etl.normalize import to_persian_digits
from app.services.hours import TEHRAN, open_status, parse_week
from app.simulator.parser import ParsedReply, parse_reply
from app.simulator.persona import CLOSING, OPENING, Persona, persona_for

STATUS_FLOW = ("draft", "sent", "delivered", "replied", "no_reply", "confirmed",
               "out_of_stock", "needs_followup")


# --------------------------------------------------------------------------- #
# channels
# --------------------------------------------------------------------------- #
class SellerChannel(Protocol):
    kind: str

    def send(self, shop_name: str, phone: str | None, message: str) -> dict: ...


class SimulatedChannel:
    """Default channel: the message goes into our own inbox and a persona answers."""

    kind = "simulated"

    def send(self, shop_name: str, phone: str | None, message: str) -> dict:
        return {"kind": self.kind, "delivered": True, "real_message_sent": False}


class LinkChannel:
    """Deep-link channel for the (fake) phone numbers — clearly labelled as demo."""

    kind = "link"

    def __init__(self, base: str = "tel") -> None:
        self.base = base

    def send(self, shop_name: str, phone: str | None, message: str) -> dict:
        digits = (phone or "").replace("۰", "0")
        if self.base == "wa":
            url = f"https://wa.me/{digits}?text={message[:200]}"
        elif self.base == "bale":
            url = f"https://ble.ir/{digits}"
        else:
            url = f"tel:{digits}"
        return {"kind": f"link:{self.base}", "url": url, "delivered": False,
                "real_message_sent": False, "demo": True}


def get_channel(kind: str = "simulated") -> SellerChannel:
    return {"simulated": SimulatedChannel(),
            "wa": LinkChannel("wa"),
            "bale": LinkChannel("bale"),
            "tel": LinkChannel("tel")}.get(kind, SimulatedChannel())


# --------------------------------------------------------------------------- #
# reply rendering (templates — the LLM may replace this, never the facts)
# --------------------------------------------------------------------------- #
def _fmt_toman(value: float | None) -> str:
    if value is None:
        return "قیمت نامشخص"
    return to_persian_digits(f"{int(value):,}") + " تومان"


def render_reply(persona: Persona, *, product_title: str, recorded_price: float | None,
                 in_stock: bool, confirmed_price: float | None, hours: dict,
                 intent: str, closed_now: bool, opens_at: str | None = None) -> str:
    import random

    rng = random.Random(persona.seed)
    style = persona.style
    parts: list[str] = [rng.choice(OPENING[style])]

    if closed_now:
        nxt = f" از ساعت {to_persian_digits(opens_at)}" if opens_at else " در ساعت کاری"
        parts.append(f"الان بسته‌ایم؛{nxt} پاسخ می‌دهیم.")
        if persona.answers_hours and hours:
            parts.append("ساعت کاری‌مان را در پروفایل هم ثبت کرده‌ایم.")

    if intent in ("price", "price_stock", "all"):
        if in_stock:
            if confirmed_price and recorded_price and abs(confirmed_price - recorded_price) > 1:
                parts.append(f"قیمت فعلی {_fmt_toman(confirmed_price)} است "
                             f"(قیمت ثبت‌شده {_fmt_toman(recorded_price)} بود).")
            elif confirmed_price:
                parts.append(f"قیمت {_fmt_toman(confirmed_price)} است.")
            elif recorded_price:
                parts.append(f"قیمت همان {_fmt_toman(recorded_price)} است.")
        else:
            parts.append("این مدل فعلاً موجود نیست.")

    if intent in ("stock", "price_stock", "all"):
        if in_stock:
            parts.append("موجود داریم.")
        elif intent not in ("price",):
            parts.append("موجود تمام شده.")

    if intent == "hours" and not closed_now:
        parts.append("ساعت کاری ما در پروفایل ثبت شده، همان است.")

    if persona.prefers_phone and rng.random() < 0.5:
        parts.append("برای هماهنگی بهتر است تماس بگیرید.")
    if persona.prefers_in_person and rng.random() < 0.5:
        parts.append("بیایید حضوری ببینید، انتخاب بهتری می‌کنید.")
    if persona.will_ask_back and rng.random() < 0.6:
        question = rng.choice([
            "چه رنگی مد نظرتان است؟",
            "سایز یا مدل دقیق را دارید؟",
            "تا چه سقف بودجه‌ای?",
        ])
        parts.append(question)

    closing = rng.choice(CLOSING[style])
    if closing:
        parts.append(closing)
    return " ".join(p.strip() for p in parts if p).strip()


# --------------------------------------------------------------------------- #
# persistence helpers
# --------------------------------------------------------------------------- #
def _now() -> datetime:
    return datetime.now(TEHRAN)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=TEHRAN)
    except ValueError:
        return None


def _add_message(conn, thread_id: str, role: str, body: str, meta: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO contact_messages (thread_id, role, body, created_at, meta) VALUES (?,?,?,?,?)",
        (thread_id, role, body, _iso(_now()),
         json.dumps(meta, ensure_ascii=False) if meta else None))


def _shop_and_offer(shop_id: str, product_id: str | None):
    with connection() as conn:
        shop = conn.execute("SELECT * FROM shops WHERE id=?", (shop_id,)).fetchone()
        offer = None
        product = None
        if product_id:
            offer = conn.execute(
                "SELECT o.*, p.title, p.brand FROM offers o JOIN products p ON p.id=o.product_id "
                "WHERE o.shop_id=? AND o.product_id=?", (shop_id, product_id)).fetchone()
            product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    return shop, offer, product


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def _reply_delay_seconds(persona: Persona) -> float | None:
    """Persona delay is in *simulated* seconds; compress by DEMO_TIME_SCALE.

    Returns ``None`` for personas that never answer.
    """
    if persona.responsiveness == "never" or persona.delay_seconds <= 0:
        return None
    return min(persona.delay_seconds / max(1.0, settings.demo_time_scale),
               settings.contact_timeout_seconds - 1)


def ask(shop_id: str, product_id: str | None, intent: str = "price_stock",
        message: str | None = None, channel: str = "simulated") -> dict:
    shop, offer, product = _shop_and_offer(shop_id, product_id)
    if not shop:
        raise ValueError("shop_not_found")

    age_days = offer["age_days"] if offer else None
    persona = persona_for(shop_id, shop["name"], age_days, bool(shop["hours_known"]))
    week = parse_week(json.loads(shop["weekly_hours"]) if shop["weekly_hours"] else {})
    status = open_status(week, _now())
    title = product["title"] if product else "این محصول"
    recorded = offer["price"] if offer and offer["price_valid"] else None

    default_text = {
        "price": f"سلام، قیمت امروز «{title}» چقدر است؟",
        "stock": f"سلام، «{title}» موجود دارید؟",
        "hours": "سلام، تا چه ساعتی باز هستید؟",
        "price_stock": f"سلام، «{title}» موجود است و قیمت امروز چند؟",
        "all": f"سلام، «{title}» موجود است؟ قیمت امروز چند؟ تا چه ساعتی باز هستید؟",
    }.get(intent, f"سلام، درباره‌ی «{title}» یک سؤال داشتم.")
    body = (message or default_text).strip()

    conn_kind = channel
    ch = get_channel(conn_kind)
    phone = None
    try:
        contacts = json.loads(shop["contacts"] or "[]")
        phone = contacts[0].get("display_number") if contacts else None
    except json.JSONDecodeError:
        pass
    transport = ch.send(shop["name"], phone, body)

    thread_id = f"th_{uuid.uuid4().hex[:16]}"
    now = _now()
    delay = _reply_delay_seconds(persona)
    # a shop that is closed right now is slower to answer, sometimes never
    if status.state == "closed" and persona.responsiveness != "instant":
        if (persona.seed % 100) < 45:
            delay = None
        elif delay is not None:
            delay = min(delay * 1.6, settings.contact_timeout_seconds - 1)

    reply_at = now + timedelta(seconds=delay) if delay is not None else None
    timeout_at = now + timedelta(seconds=settings.contact_timeout_seconds)

    with write_connection() as conn:
        conn.execute(
            """INSERT INTO contact_threads
               (id, shop_id, product_id, intent, message, status, created_at, sent_at,
                reply_at, timeout_at, persona, parsed)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (thread_id, shop_id, product_id, intent, body, "sent", _iso(now), _iso(now),
             _iso(reply_at) if reply_at else None, _iso(timeout_at),
             json.dumps(persona.as_dict(), ensure_ascii=False), None))
        _add_message(conn, thread_id, "user", body,
                     {"channel": transport.get("kind"), "demo": True})
        if transport.get("url"):
            _add_message(conn, thread_id, "system",
                         "لینک کانال واقعی آماده شد (شماره‌های دیتاست نمایشی‌اند).",
                         transport)

    return {
        "thread_id": thread_id,
        "status": "sent",
        "shop_id": shop_id,
        "product_id": product_id,
        "intent": intent,
        "message": body,
        "channel": transport,
        "simulated": transport.get("kind") == "simulated",
        "sent_at": _iso(now),
        "reply_at": _iso(reply_at) if reply_at else None,
        "timeout_at": _iso(timeout_at),
        "expected_reply_seconds": round(delay, 1) if delay is not None else None,
        "will_reply": delay is not None,
        "persona_hint": {"responsiveness": persona.responsiveness, "style": persona.style},
    }


def _materialize_reply(thread_row) -> dict | None:
    """Generate the seller's answer if the scheduled moment has passed."""
    reply_at = _parse_iso(thread_row["reply_at"])
    if reply_at is None or _now() < reply_at:
        return None
    persona_raw = thread_row["persona"]
    persona = Persona(**json.loads(persona_raw)) if persona_raw else None
    if persona is None:
        return None

    shop, offer, product = _shop_and_offer(thread_row["shop_id"], thread_row["product_id"])
    if not shop:
        return None
    week = parse_week(json.loads(shop["weekly_hours"]) if shop["weekly_hours"] else {})
    now = _now()
    status = open_status(week, now)
    closed_now = status.state == "closed"

    import random
    rng = random.Random(persona.seed ^ 0x5F5F)

    # a closed shop still answers "we are closed" for hours questions
    in_stock = rng.random() < persona.reliability
    if status.state == "unknown":
        in_stock = rng.random() < (persona.reliability - 0.08)
    recorded = offer["price"] if offer and offer["price_valid"] else None
    confirmed = round(recorded * persona.price_drift / 10_000) * 10_000 if recorded else None
    if confirmed and rng.random() < 0.08:
        confirmed = None  # "قیمت را باید چک کنم"

    text = render_reply(
        persona,
        product_title=(product["title"] if product else "محصول"),
        recorded_price=recorded,
        in_stock=in_stock,
        confirmed_price=confirmed if in_stock else None,
        hours=json.loads(shop["weekly_hours"]) if shop["weekly_hours"] else {},
        intent=thread_row["intent"],
        closed_now=closed_now and thread_row["intent"] in ("hours", "all", "price_stock"),
        opens_at=status.opens_at,
    )
    parsed: ParsedReply = parse_reply(text)
    if closed_now and thread_row["intent"] == "hours":
        parsed.hours_info = parsed.hours_info or "الان بسته است"

    if parsed.in_stock is False:
        new_status = "out_of_stock"
    elif parsed.needs_followup:
        new_status = "needs_followup"
    else:
        new_status = "confirmed" if parsed.confirmed_price or parsed.in_stock else "replied"

    with write_connection() as conn:
        conn.execute(
            "UPDATE contact_threads SET status=?, replied_at=?, parsed=? WHERE id=?",
            (new_status, _iso(now), json.dumps(parsed.as_dict(), ensure_ascii=False),
             thread_row["id"]))
        _add_message(conn, thread_row["id"], "seller", text,
                     {"simulated": True, "parsed": parsed.as_dict()})

    return {
        "status": new_status,
        "body": text,
        "parsed": parsed.as_dict(),
        "replied_at": _iso(now),
    }


def status(thread_id: str) -> dict | None:
    """Advance the thread state machine, then return the full conversation."""
    with connection() as conn:
        row = conn.execute("SELECT * FROM contact_threads WHERE id=?", (thread_id,)).fetchone()
    if not row:
        return None

    current = row["status"]
    timeout_at = _parse_iso(row["timeout_at"])
    now = _now()

    if current in ("sent", "delivered"):
        if timeout_at and now >= timeout_at:
            with write_connection() as conn:
                conn.execute("UPDATE contact_threads SET status='no_reply' WHERE id=?",
                             (thread_id,))
                _add_message(conn, thread_id, "system",
                             "فروشنده در بازه‌ی تعیین‌شده پاسخ نداد.")
        else:
            _materialize_reply(row)  # no-op until the scheduled moment

    with connection() as conn:
        row = conn.execute("SELECT * FROM contact_threads WHERE id=?", (thread_id,)).fetchone()
        messages = conn.execute(
            "SELECT role, body, created_at, meta FROM contact_messages "
            "WHERE thread_id=? ORDER BY id", (thread_id,)).fetchall()

    current = row["status"]
    parsed = None
    if row["parsed"]:
        try:
            parsed = json.loads(row["parsed"])
        except json.JSONDecodeError:
            parsed = None

    timeout_at = _parse_iso(row["timeout_at"])
    remaining = max(0, int((timeout_at - _now()).total_seconds())) if timeout_at else None
    return {
        "thread_id": thread_id,
        "shop_id": row["shop_id"],
        "product_id": row["product_id"],
        "intent": row["intent"],
        "status": current,
        "simulated": True,
        "sent_at": row["sent_at"],
        "replied_at": row["replied_at"],
        "timeout_at": row["timeout_at"],
        "seconds_remaining": remaining,
        "parsed": parsed,
        "messages": [
            {"role": m["role"], "body": m["body"], "created_at": m["created_at"],
             "meta": json.loads(m["meta"]) if m["meta"] else None}
            for m in messages
        ],
    }


def list_threads(limit: int = 20) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT id FROM contact_threads ORDER BY created_at DESC LIMIT ?",
            (limit,)).fetchall()
    out = []
    for r in rows:
        st = status(r["id"])
        if st:
            out.append({k: st[k] for k in ("thread_id", "shop_id", "product_id", "status",
                                           "sent_at", "replied_at", "parsed")})
    return out
