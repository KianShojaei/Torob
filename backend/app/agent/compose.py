"""Persian copy generated **from tool results only** (§6.4).

The deterministic composer builds the assistant text out of the same JSON the UI
receives, so an offline run and an LLM run never disagree about facts. The LLM, when
enabled, may phrase things differently — but its output passes the same guardrail.
"""
from __future__ import annotations

from app.etl.normalize import to_persian_digits

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(value) -> str:
    return to_persian_digits(str(value))


def money(value: float | None) -> str:
    if value is None:
        return "نامشخص"
    return fa(f"{int(value):,}").replace(",", "٬") + " تومان"


def price_range(lo, hi) -> str:
    if lo is None and hi is None:
        return "قیمت نامشخص"
    if lo and hi and int(lo) != int(hi):
        return f"{money(lo)} تا {money(hi)}"
    return money(lo or hi)


def distance(km: float, minutes: int) -> str:
    if km is None or km < 0:
        return "فاصله نامشخص"
    if km < 1:
        return f"{fa(int(round(km * 1000 / 50) * 50))} متر"
    return f"{fa(f'{km:.1f}')} کیلومتر"


def open_phrase(state: str, closes_at: str | None, opens_at: str | None) -> str:
    if state == "open":
        return f"باز است تا {fa(closes_at)}" if closes_at else "باز است"
    if state == "closed":
        return f"بسته است؛ {fa(opens_at)} باز می‌شود" if opens_at else "بسته است"
    return "ساعت کاری نامشخص"


def search_summary(need, result: dict) -> str:
    n = result.get("count", 0)
    if not n:
        return (
            "برای این جست‌وجو محصولی پیدا نکردم؛ "
            "می‌توانم بودجه را باز کنم یا دسته‌ی نزدیک‌تری پیشنهاد بدهم."
        )
    parts = [f"{fa(n)} گزینه پیدا کردم"]
    if need.budget_max:
        parts.append(f"زیر {money(need.budget_max)}")
    parts.append("— برای دیدن فروشنده‌ها یکی را انتخاب کنید.")
    return " ".join(parts)


def recommend_summary(result: dict) -> str:
    models = result.get("models") or []
    if not models:
        return "مدلی برای این دسته پیدا نکردم؛ می‌توانم دسته‌ی دیگری را امتحان کنم."
    top = models[0]
    line = (
        f"{fa(len(models))} مدل پیشنهاد می‌کنم. "
        f"گزینه‌ی اول «{top['title']}» با میانه‌ی {money(top.get('price_median'))}"
        f" در {fa(top.get('shop_count') or 0)} فروشگاه."
    )
    if len(models) > 1:
        line += " دو گزینه‌ی دیگر را هم می‌بینید تا مقایسه کنید."
    return line


def stores_summary(result: dict, need) -> str:
    rows = result.get("stores") or []
    if not rows:
        return (
            "فروشنده‌ای با این فیلترها پیدا نشد. "
            "شعاع را بیشتر کنم یا سقف بودجه را بالا ببرم؟"
        )
    best = rows[0]
    parts = [f"{fa(len(rows))} فروشگاه پیدا کردم."]
    price = best.get("price")
    if best.get("price_valid") and price:
        parts.append(f"ارزان‌ترین {money(price)}")
        if best.get("price_age_label"):
            parts.append(f"(قیمت ثبت‌شده: {best['price_age_label']})")
        parts.append(".")
    if best.get("distance_km", -1) >= 0:
        parts.append(f"نزدیک‌ترین حدود {distance(best['distance_km'], best.get('travel_minutes', 0))} فاصله دارد.")
    closed = [r for r in rows if r.get("open_state") == "closed"]
    if closed and not result.get("filters", {}).get("open_now"):
        parts.append(f"{fa(len(closed))} فروشگاه الان بسته است؛ در کارت‌ها مشخص شده.")
    return " ".join(parts)


def contact_summary(shop_name: str, status: dict) -> str:
    st = status.get("status")
    parsed = status.get("parsed") or {}
    if st == "no_reply":
        return (
            f"«{shop_name}» پاسخ نداد. می‌توانم همین حالا فروشگاه‌های جایگزین نزدیک را "
            "پیشنهاد بدهم."
        )
    if parsed.get("in_stock") is False:
        return f"«{shop_name}» گفت این مدل موجود نیست. جایگزین پیشنهاد می‌کنم."
    if parsed.get("confirmed_price"):
        return (
            f"«{shop_name}» قیمت را {money(parsed['confirmed_price'])} تأیید کرد"
            + (" و موجودی را تأیید کرد." if parsed.get("in_stock") else ".")
        )
    if parsed.get("in_stock") is True:
        return f"«{shop_name}» موجود بودن را تأیید کرد؛ قیمت دقیق را ذکر نکرد."
    if parsed.get("hours_info"):
        return f"«{shop_name}» درباره‌ی ساعت کاری پاسخ داد: {parsed['hours_info']}"
    return f"پاسخ «{shop_name}» رسید؛ جزئیات در کارت گفت‌وگو آمده است."


def alternatives_summary(result: dict) -> str:
    same = result.get("same_product_elsewhere") or []
    similar = result.get("similar_products") or []
    parts = []
    if same:
        top = same[0]
        dist_text = distance(top.get("distance_km", -1), top.get("travel_minutes", 0))
        tail = (f" و در {dist_text} فاصله" if dist_text != "فاصله نامشخص" else "")
        parts.append(
            f"{fa(len(same))} فروشگاه دیگر همین محصول را دارند؛ "
            f"نزدیک‌ترین «{top['name']}» با {money(top.get('price'))}{tail}."
        )
    if similar:
        parts.append(f"{fa(len(similar))} مدل مشابه هم هست (نه همان محصول).")
    if not parts:
        parts.append("جایگزین نزدیکی پیدا نکردم؛ می‌توانم شعاع را بیشتر کنم.")
    return " ".join(parts)


def plan_summary(result: dict) -> str:
    stops = result.get("stops") or []
    if not stops:
        return "برای برنامه‌ی سفر حداقل یک فروشگاه انتخاب کنید."
    parts = [f"برنامه‌ی {fa(len(stops))} توقفی آماده است."]
    parts.append(
        "اول «" + stops[0]["shop_name"] + f"» ساعت {fa(stops[0]['arrival_time'])}.")
    warn = result.get("warnings") or []
    if warn:
        parts.append(f"{fa(len(warn))} هشدار ساعت کاری دارم؛ قبل از حرکت ببینید.")
    return " ".join(parts)


def mall_summary(detail: dict) -> str:
    guide = (detail.get("mall") or {}).get("guide") or {}
    if guide.get("title") and guide["title"] != "آدرس دقیق ثبت نشده":
        text = f"{guide['title']}."
        if guide.get("detail"):
            text += " " + guide["detail"]
        return text
    return "آدرس دقیق داخل پاساژ ثبت نشده؛ بهتر است قبل از رفتن از فروشنده بپرسید."


def clarify_question(need) -> str:
    if need.category and need.budget_max:
        return "دسته و بودجه را گرفتم. کاربری اصلی‌اش چیست؛ روزمره، حرفه‌ای یا هدیه؟"
    if need.category:
        return "سقف بودجه‌تان چقدر است تا گزینه‌های واقعی‌تر نشان بدهم؟"
    return "چه محصولی می‌خواهید و تا چه بودجه‌ای؟"
