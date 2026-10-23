import json
import re
from openai import OpenAI

from backend.app.config import settings
from backend.app.db.repo import recommend_models
from backend.app.services.ranking import find_stores_for_product
from backend.app.etl.normalizer import normalize_persian, to_persian_digits
from backend.app.etl.price_rules import format_price_toman

KNOWN_BRANDS_MAP = {
    "شیائومی": "شیائومی", "شیایومی": "شیائومی", "شیاومی": "شیائومی", "شیومی": "شیائومی",
    "xiaomi": "شیائومی", "ردمی": "شیائومی", "پوکو": "شیائومی", "هایلو": "شیائومی", "qcy": "شیائومی",
    "سامسونگ": "سامسونگ", "سامسنگ": "سامسونگ", "samsung": "سامسونگ",
    "اپل": "اپل", "apple": "اپل", "آیفون": "اپل", "ایفون": "اپل", "ایرپاد": "اپل",
    "سونی": "سونی", "sony": "سونی", "انکر": "انکر", "anker": "انکر",
    "لنوو": "لنوو", "lenovo": "لنوو", "ایسوس": "ایسوس", "asus": "ایسوس",
    "اچ پی": "اچ پی", "hp": "اچ پی", "داهوا": "داهوا", "هایک ویژن": "هایک ویژن",
}

def llm_resolve_fuzzy_query(raw_message: str) -> dict:
    api_key = settings.LLM_API_KEY
    if not api_key or api_key == "your_boxapi_key_here" or len(api_key) < 8:
        return {}
    try:
        client = OpenAI(api_key=api_key, base_url=settings.LLM_BASE_URL, timeout=4.0)
        prompt = (
            f"کاربر در فروشگاه‌یاب تهران نوشته: «{raw_message}»\n"
            "اگر غلط املایی دارد آن را اصلاح کن و فقط یک JSON خالص با کلیدهای زیر برگردان:\n"
            '{"category": "گوشی موبایل | هدفون بی سیم | لپ تاپ | ساعت هوشمند | دوربین مدار بسته | پاوربانک", '
            '"brand": "شیائومی | سامسونگ | اپل | لنوو | ایسوس | سونی | انکر | null", '
            '"usage": "باتری قوی | دوربین عکاسی | گیمینگ | اقتصادی | مکالمه | null"}'
        )
        resp = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.0,
        )
        txt = (resp.choices[0].message.content or "").strip()
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except Exception:
        pass
    return {}

def extract_natural_intent(message: str, context: dict) -> dict:
    msg_norm = normalize_persian(message)

    detected_budget = context.get("max_budget")
    if not detected_budget:
        m_mio = re.search(r"(?:تا|حداکثر|زیر|حدود|بودجه|قیمت)?\s*(\d+(?:\.\d+)?)\s*(?:میلیون|ملیون|تومن|تومان)", msg_norm)
        if m_mio:
            val = float(m_mio.group(1))
            if val <= 300:
                detected_budget = int(val * 1_000_000)

    detected_brand = context.get("brand")
    if not detected_brand:
        for k, canonical_b in KNOWN_BRANDS_MAP.items():
            if re.search(rf"\b{re.escape(k)}\b", msg_norm) and k not in ("آیفون", "ایفون", "ایرپاد"):
                detected_brand = canonical_b
                break

    inst_mode = context.get("installment_mode") or "any"
    if inst_mode == "any":
        if any(w in msg_norm for w in ["قسطی حضوری", "قسطی تایید"]):
            inst_mode = "confirmed_only"
        elif any(w in msg_norm for w in ["قسطی", "اقساط", "اقساطی", "اعتباری", "ترب پی", "اسنپ پی"]):
            inst_mode = "all_installment"

    travel_mode = context.get("travel_mode") or "car"
    if any(w in msg_norm for w in ["مترو", "با مترو"]):
        travel_mode = "metro"
    elif any(w in msg_norm for w in ["پیاده", "با پای پیاده"]):
        travel_mode = "walk"

    sort_by = context.get("sort_by") or "best"
    if any(w in msg_norm for w in ["ارزون", "ارزان", "کمترین قیمت", "خوش قیمت"]):
        sort_by = "cheapest"
    elif any(w in msg_norm for w in ["نزدیک", "نزدیک ترین"]):
        sort_by = "nearest"
    elif any(w in msg_norm for w in ["الان باز", "باز باشه"]):
        sort_by = "open"

    usage_hint = context.get("usage_hint")
    if not usage_hint:
        if any(w in msg_norm for w in ["باتری", "باطری", "باتریش", "باطریش", "شارژدهی"]):
            usage_hint = "باتری قوی"
        elif any(w in msg_norm for w in ["عکاسی", "دوربین", "دوربینش"]):
            usage_hint = "دوربین عکاسی"
        elif any(w in msg_norm for w in ["ورزش", "ورزشی", "باشگاه"]):
            usage_hint = "ورزشی"
        elif any(w in msg_norm for w in ["گیمینگ", "بازی", "سخت افزار"]):
            usage_hint = "5g"
        elif any(w in msg_norm for w in ["مکالمه", "تماس"]):
            usage_hint = "مکالمه"
        elif any(w in msg_norm for w in ["نویز", "anc"]):
            usage_hint = "anc"
        elif any(w in msg_norm for w in ["مهندسی", "برنامه نویسی"]):
            usage_hint = "مهندسی"
        elif any(w in msg_norm for w in ["دانشجویی", "روزمره", "اقتصادی"]):
            usage_hint = "اقتصادی"

    clean_q = msg_norm
    clean_q = re.sub(r"(?:تا|حداکثر|زیر|حدود|بودجه|قیمت)?\s*\d+(?:\.\d+)?\s*(?:میلیون|ملیون|تومن|تومان)", " ", clean_q)
    for fw in [
        "سلام", "آقا", "اقا", "من", "یه", "یک", "میخوام", "می خوام", "میخواهم", "بخرم",
        "نمیدونم", "نمی دونم", "چه", "مدلی", "کدوم", "مناسب", "خوبه", "پیشنهاد", "بده",
        "لطفا", "با", "قیمت", "حداکثر", "تهران", "فروشگاه", "مغازه", "واسه", "برای",
        "قسطی", "اقساطی", "حضوری", "ارزون", "ارزان", "نزدیک", "مترو", "پیاده"
    ]:
        clean_q = re.sub(rf"\b{fw}\b", " ", clean_q)
    clean_q = " ".join(clean_q.split()).strip()

    if not any(w in clean_q for w in ["هدفون", "هندزفری", "ایرپاد", "گوشی", "موبایل", "لپ تاپ", "ساعت", "دوربین", "پاوربانک"]):
        llm_guess = llm_resolve_fuzzy_query(message)
        if llm_guess.get("category"):
            clean_q = llm_guess["category"]
        if not detected_brand and llm_guess.get("brand") and llm_guess["brand"] != "null":
            detected_brand = llm_guess["brand"]
        if not usage_hint and llm_guess.get("usage") and llm_guess["usage"] != "null":
            usage_hint = llm_guess["usage"]

    if not clean_q:
        clean_q = "هدفون بی سیم"

    base_cat_q = clean_q
    if detected_brand:
        for k, v in KNOWN_BRANDS_MAP.items():
            if v == detected_brand:
                base_cat_q = re.sub(rf"\b{re.escape(k)}\b", " ", base_cat_q).strip()
    if not base_cat_q:
        base_cat_q = clean_q

    return {
        "raw_message": message,
        "clean_query": clean_q,
        "base_category_query": base_cat_q,
        "brand": detected_brand,
        "max_budget": detected_budget,
        "installment_mode": inst_mode,
        "installment_only": inst_mode != "any",
        "travel_mode": travel_mode,
        "sort_by": sort_by,
        "usage_hint": usage_hint,
    }

def process_agent_chat(message: str, context: dict | None = None) -> dict:
    ctx = context or {}
    intent = extract_natural_intent(message, ctx)

    u_lat = ctx.get("lat", settings.DEFAULT_LAT)
    u_lon = ctx.get("lon", settings.DEFAULT_LON)
    neighborhood = ctx.get("neighborhood", "ALL")

    rec = recommend_models(
        category_or_query=intent["base_category_query"],
        usage_hint=intent["usage_hint"],
        max_price=intent["max_budget"],
        brand=intent["brand"],
        installment_only=intent["installment_only"],
        sort_by=intent["sort_by"],
        limit=6,
    )

    fallback_notice_fa = None

    if not rec["recommended_models"] and intent["brand"]:
        rec_no_brand = recommend_models(
            category_or_query=intent["base_category_query"],
            usage_hint=intent["usage_hint"],
            max_price=intent["max_budget"],
            brand=None,
            installment_only=intent["installment_only"],
            sort_by=intent["sort_by"],
            limit=6,
        )
        if rec_no_brand["recommended_models"]:
            rec = rec_no_brand
            budget_str = f" تا سقف {format_price_toman(intent['max_budget'])}" if intent["max_budget"] else ""
            fallback_notice_fa = (
                f"در دیتاست فعلی فروشگاه‌های تهران، «{intent['base_category_query']}» با برند **{intent['brand']}**{budget_str} موجود نیست؛ "
                f"اما بر اساس امتیازها و موجودی بازار، **بهترین جایگزین‌های هم‌رده** را برایتان آوردم:"
            )

    if not rec["recommended_models"] and intent["max_budget"]:
        rec_no_budget = recommend_models(
            category_or_query=intent["base_category_query"],
            usage_hint=intent["usage_hint"],
            max_price=None,
            brand=intent["brand"],
            installment_only=intent["installment_only"],
            sort_by="cheapest",
            limit=6,
        )
        if rec_no_budget["recommended_models"]:
            rec = rec_no_budget
            fallback_notice_fa = (
                f"مدلی دقیقاً زیر سقف {format_price_toman(intent['max_budget'])} ثبت نشده است؛ "
                f"اما **ارزان‌ترین و خوش‌قیمت‌ترین مدل‌های موجود** در بازار تهران به ترتیب زیر هستند:"
            )

    if not rec["recommended_models"]:
        rec = recommend_models("هدفون بی سیم", sort_by=intent["sort_by"], limit=6)
        fallback_notice_fa = (
            f"کالای «{message}» در دیتاست فعلی موجود نیست. محبوب‌ترین مدل‌های دارای موجودی حضوری در تهران:"
        )

    top_prod = rec["recommended_models"][0]
    stores_res = find_stores_for_product(
        product_id_or_group=top_prod["product_id"],
        user_lat=u_lat,
        user_lon=u_lon,
        neighborhood_filter=neighborhood,
        max_budget_toman=intent["max_budget"],
        installment_mode=intent["installment_mode"],
        travel_mode=intent["travel_mode"],
        sort_by=intent["sort_by"],
        limit=20,
    )

    if fallback_notice_fa:
        reply_fa = (
            f"{fallback_notice_fa}\n"
            f"پیشنهاد اول: **«{top_prod['persian_title']}»** (قیمت منصفانه: **{top_prod['fair_market_price_fa']}**) در **{to_persian_digits(stores_res['total_stores_found'])} فروشگاه**."
        )
    else:
        filter_notes = []
        if intent["brand"]:
            filter_notes.append(f"برند {intent['brand']}")
        if intent["max_budget"]:
            filter_notes.append(f"بودجه تا {format_price_toman(intent['max_budget'])}")
        if intent["sort_by"] == "cheapest":
            filter_notes.append("مرتب‌شده بر اساس خوش‌قیمت‌ترین")
        if intent["usage_hint"]:
            filter_notes.append(f"اولویت {intent['usage_hint']}")
        if intent["installment_only"]:
            filter_notes.append("خرید قسطی")

        cond_str = f" ({' • '.join(filter_notes)})" if filter_notes else ""
        reply_fa = (
            f"بر اساس درخواست شما{cond_str}، **{to_persian_digits(len(rec['recommended_models']))} مدل منطبق** پیدا شد. "
            f"بهترین گزینه **«{top_prod['persian_title']}»** با قیمت منصفانه **{top_prod['fair_market_price_fa']}** است که در **{to_persian_digits(stores_res['total_stores_found'])} فروشگاه تهران** عرضه می‌شود."
        )

    return {
        "reply_fa": reply_fa,
        "cards": [
            {"type": "recommendations", "data": rec},
            {"type": "stores", "data": stores_res},
        ],
        "detected_filters": {
            "query": intent["clean_query"],
            "brand": intent["brand"],
            "max_budget": intent["max_budget"],
            "installment_mode": intent["installment_mode"],
            "installment_only": intent["installment_only"],
            "travel_mode": intent["travel_mode"],
            "sort_by": intent["sort_by"],
            "usage_hint": intent["usage_hint"],
            "had_fallback": bool(fallback_notice_fa),
        },
    }
