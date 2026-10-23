import json
from datetime import datetime, timedelta
from typing import Any

from backend.app.config import settings
from backend.app.db.repo import (
    get_conn,
    haversine_km,
    estimate_eta_minutes,
    format_distance_fa,
    normalize_realistic_price,
    format_short_price_pin,
)
from backend.app.etl.normalizer import to_persian_digits
from backend.app.etl.price_rules import format_price_toman
from backend.app.etl.hours_engine import evaluate_open_status, check_open_at_arrival, parse_weekly_hours, PERSIAN_DAY_NAMES, TEHRAN_TZ

FAMOUS_MALL_GOOGLE_TIPS = {
    "پاساژ علاءالدین": "ورودی اصلی از تقاطع خیابان جمهوری و حافظ است. برای طبقات بالای ۴ استفاده از آسانسور ضلع جنوبی یا پله‌برقی مرکزی سریع‌تر است. نزدیک‌ترین مترو: تئاتر شهر یا دروازه دولت.",
    "پاساژ چارسو": "روبه روی پاساژ علاءالدین در تقاطع جمهوری و حافظ قرار دارد. دارای پارکینگ طبقاتی و پله‌برقی‌های عریض در هر طبقه است.",
    "بازار موبایل ایران": "پایین‌تر از چهارراه حافظ در خیابان جمهوری (پلاک ۵۹۶). واحدها دارای شماره‌گذاری منظم در طبقات همکف تا دوم هستند.",
    "مجتمع کامپیوتر پایتخت": "تقاطع خیابان ولیعصر و بلوار میرداماد. بورس تخصصی لپ‌تاپ و قطعات کامپیوتر؛ نزدیک‌ترین مترو: میرداماد.",
    "پاساژ بوشهری": "در محدوده لاله‌زار و سعدی جنوبی، بورس تخصصی کالای برق، روشنایی و صنعتی. نزدیک‌ترین مترو: سعدی.",
    "پاساژ امجد": "خیابان جمهوری، نرسیده به پل حافظ؛ بورس تخصصی قطعات الکترونیک و تجهیزات صنعتی.",
}

AVAILABILITY_LABELS_FA = {
    "listed": "ثبت‌شده در لیست فروشگاه (تأیید نشده)",
    "confirmed_in_stock": "موجودی تأییدشده توسط فروشنده",
    "confirmed_out_of_stock": "ناموجود (اعلام فروشنده)",
    "unknown": "وضعیت موجودی نامشخص",
}

def build_store_offer_card(
    row: dict,
    user_lat: float,
    user_lon: float,
    travel_mode: str,
    depart_dt: datetime,
    min_group_price: int | None,
    median_group_price: int | None,
) -> dict:
    s_lat = row.get("lat") or settings.DEFAULT_LAT
    s_lon = row.get("lon") or settings.DEFAULT_LON
    dist_km = haversine_km(user_lat, user_lon, s_lat, s_lon)
    eta_mins = estimate_eta_minutes(dist_km, travel_mode)
    arrival_dt = depart_dt + timedelta(minutes=eta_mins)

    now_hours = evaluate_open_status(row.get("weekly_hours_json"), depart_dt)
    arr_hours = check_open_at_arrival(row.get("weekly_hours_json"), arrival_dt)

    cat_name = row.get("category_name") or ""
    p_title = row.get("persian_title") or row.get("seller_title") or ""
    recorded_price = normalize_realistic_price(row.get("price_toman"), cat_name, p_title)
    confirmed_price = normalize_realistic_price(row.get("confirmed_price_toman"), cat_name, p_title)
    effective_price = confirmed_price if confirmed_price is not None else recorded_price

    fair_price = None
    if min_group_price and median_group_price:
        fair_price = int(round((min_group_price * 0.6 + median_group_price * 0.4) / 10000.0) * 10000)
    elif min_group_price:
        fair_price = min_group_price
    elif effective_price:
        fair_price = int(round((effective_price * 0.96) / 10000.0) * 10000)

    suggested_counter_offer = fair_price
    if effective_price and fair_price and min_group_price:
        if effective_price <= min_group_price * 1.02:
            fairness_status = "great"
            fairness_label_fa = "خوش‌قیمت (کف بازار)"
        elif effective_price <= (median_group_price or effective_price) * 1.05:
            fairness_status = "fair"
            fairness_label_fa = "قیمت متعادل و منصفانه"
        else:
            fairness_status = "high"
            fairness_label_fa = f"بالاتر از عرف بازار (قیمت منصفانه: {format_price_toman(fair_price)})"
            suggested_counter_offer = fair_price
    else:
        fairness_status = "unknown"
        fairness_label_fa = "نیاز به استعلام قیمت"

    price_part_1_fa = (
        f"قیمت تأییدشده: {format_price_toman(confirmed_price)}"
        if confirmed_price is not None
        else f"قیمت ثبت‌شده: {format_price_toman(recorded_price)}"
    )
    price_part_2_fa = f"آخرین تغییر قیمت: {row.get('price_age_label_fa') or 'نامشخص'}"

    avail_status = row.get("availability_status") or "listed"
    if avail_status == "confirmed_in_stock" and row.get("confirmed_at"):
        avail_part_3_fa = f"تأییدشده توسط فروشنده ({row['confirmed_at']})"
    else:
        avail_part_3_fa = AVAILABILITY_LABELS_FA.get(avail_status, "ثبت‌شده در لیست (تأیید نشده)")

    is_abnormal_price = False
    price_sanity_warning_fa = None
    if effective_price and median_group_price and median_group_price > 0:
        ratio = effective_price / median_group_price
        if ratio < 0.45 or ratio > 2.2:
            is_abnormal_price = True
            price_sanity_warning_fa = "قیمت غیرعادی نسبت به میانگین بازار • حتماً از فروشنده استعلام بگیرید"

    if effective_price is not None and min_group_price and min_group_price > 0:
        price_score = max(0.1, min(1.0, min_group_price / effective_price))
        if is_abnormal_price:
            price_score *= 0.5
    else:
        price_score = 0.25

    dist_score = max(0.05, 1.0 - (dist_km / 18.0))

    if arr_hours["status"] == "open":
        open_score = 0.65 if arr_hours["closing_soon_on_arrival"] else 1.0
    elif arr_hours["status"] == "unknown":
        open_score = 0.45
    else:
        open_score = 0.05

    bucket = row.get("price_age_bucket", "unknown")
    fresh_map = {"fresh": 0.9, "recent": 0.7, "old": 0.4, "stale": 0.2, "unknown": 0.2}
    freshness_score = fresh_map.get(bucket, 0.3)
    if avail_status == "confirmed_in_stock":
        freshness_score = 1.0
    elif avail_status == "confirmed_out_of_stock":
        freshness_score = 0.0

    inst_level = row.get("installment_level", "none")
    inst_score = 1.0 if inst_level == "in_person" else (0.7 if inst_level == "declared" else 0.2)

    composite_score = round(
        0.30 * price_score
        + 0.25 * dist_score
        + 0.20 * open_score
        + 0.15 * freshness_score
        + 0.10 * inst_score,
        3,
    )
    if avail_status == "confirmed_out_of_stock":
        composite_score = round(composite_score * 0.1, 3)

    reasons = [format_distance_fa(dist_km)]
    if arr_hours["status"] == "open":
        reasons.append(arr_hours["label_fa"])
    elif arr_hours["status"] == "closed":
        reasons.append(f"هنگام رسیدن بسته است ({arr_hours['label_fa']})")
    else:
        reasons.append("ساعت کاری نامشخص")

    if effective_price and median_group_price and effective_price < median_group_price:
        pct = max(1, int(round((1 - effective_price / median_group_price) * 100)))
        reasons.append(f"{to_persian_digits(pct)}٪ ارزان‌تر از میانگین")
    elif effective_price and effective_price == min_group_price:
        reasons.append("ارزان‌ترین قیمت ثبت‌شده")

    if inst_level == "in_person":
        reasons.append("قسطی حضوری تأییدشده")
    elif inst_level == "declared":
        reasons.append("دارای سرویس قسطی")

    stale_nudge_fa = (
        "قیمت قدیمی یا نامشخص است — پیشنهاد می‌شود از فروشنده استعلام بگیرید"
        if bucket in ("old", "stale", "unknown") or effective_price is None
        else None
    )

    return {
        "offer_id": row["offer_id"],
        "shop_id": row["shop_id"],
        "product_id": row["product_id"],
        "product_group_id": row["product_group_id"],
        "persian_title": p_title,
        "seller_title": row.get("seller_title"),
        "shop_name": row["name"],
        "is_real_name": bool(row.get("is_real_name")),
        "fake_name_disclaimer_fa": None if row.get("is_real_name") else "نام آزمایشی دیتاست",
        "location_label": row.get("location_label") or "نامشخص",
        "address": row.get("address") or "آدرس ثبت نشده",
        "lat": s_lat,
        "lon": s_lon,
        "distance_km": round(dist_km, 2),
        "distance_label_fa": format_distance_fa(dist_km),
        "eta_minutes": eta_mins,
        "eta_label_fa": f"{to_persian_digits(eta_mins)} دقیقه ({'پیاده' if travel_mode=='walk' else ('مترو' if travel_mode=='metro' else 'خودرو')})",
        "recorded_price_toman": recorded_price,
        "confirmed_price_toman": confirmed_price,
        "effective_price_toman": effective_price,
        "short_price_pin_fa": format_short_price_pin(effective_price),
        "fair_market_price_toman": fair_price,
        "fair_market_price_fa": format_price_toman(fair_price) if fair_price else "نامشخص",
        "suggested_counter_offer_toman": suggested_counter_offer,
        "suggested_counter_offer_fa": format_price_toman(suggested_counter_offer) if suggested_counter_offer else "نامشخص",
        "fairness_status": fairness_status,
        "fairness_label_fa": fairness_label_fa,
        "price_status": row.get("price_status", "unknown"),
        "price_part_1_recorded_fa": price_part_1_fa,
        "price_part_2_age_fa": price_part_2_fa,
        "price_part_3_availability_fa": avail_part_3_fa,
        "price_age_bucket": bucket,
        "age_days": row.get("age_days"),
        "availability_status": avail_status,
        "stale_price_nudge_fa": stale_nudge_fa,
        "is_abnormal_price": is_abnormal_price,
        "price_sanity_warning_fa": price_sanity_warning_fa,
        "hours_now": now_hours,
        "hours_at_arrival": arr_hours,
        "weekly_hours": json.loads(row["weekly_hours_json"]) if row.get("weekly_hours_json") else {},
        "has_installment": bool(row.get("has_installment")),
        "installment_level": inst_level,
        "installment_label_fa": row.get("installment_label_fa") or "بدون سرویس قسطی",
        "installment_providers": json.loads(row["installment_providers_json"]) if row.get("installment_providers_json") else [],
        "installment_details": json.loads(row["installment_details_json"]) if row.get("installment_details_json") else [],
        "warranty_label_fa": row.get("warranty_label_fa") or "گارانتی نامشخص",
        "is_in_mall": bool(row.get("is_in_mall")),
        "mall_name": row.get("mall_name"),
        "floor": row.get("floor") or "نامشخص",
        "unit": row.get("unit") or "نامشخص",
        "street_hint": row.get("street_hint"),
        "address_confidence": row.get("address_confidence") or "low",
        "guide_summary_fa": row.get("guide_summary_fa"),
        "guide_steps_fa": json.loads(row["guide_steps_json"]) if row.get("guide_steps_json") else [],
        "phone_display": row.get("phone_display") or "۰۲۱-۰۰۰۰۰۰۰۰",
        "instagram": row.get("instagram"),
        "website_url": row.get("website_url"),
        "composite_score": composite_score,
        "score_breakdown": {
            "price_score": round(price_score, 2),
            "distance_score": round(dist_score, 2),
            "open_at_arrival_score": round(open_score, 2),
            "freshness_confirmation_score": round(freshness_score, 2),
            "installment_score": round(inst_score, 2),
        },
        "why_suggested_reasons": reasons[:4],
        "why_suggested_fa": " • ".join(reasons[:3]),
    }

def find_stores_for_product(
    product_id_or_group: str,
    user_lat: float | None = None,
    user_lon: float | None = None,
    radius_km: float = 15.0,
    neighborhood_filter: str | None = None,
    max_budget_toman: int | None = None,
    installment_mode: str = "any",
    open_filter: str = "any",
    travel_mode: str = "car",
    depart_time_iso: str | None = None,
    sort_by: str = "best",
    limit: int = 25,
) -> dict:
    u_lat = user_lat if user_lat is not None else settings.DEFAULT_LAT
    u_lon = user_lon if user_lon is not None else settings.DEFAULT_LON

    if depart_time_iso:
        try:
            depart_dt = datetime.fromisoformat(depart_time_iso)
            if depart_dt.tzinfo is None:
                depart_dt = TEHRAN_TZ.localize(depart_dt)
        except Exception:
            depart_dt = datetime.now(TEHRAN_TZ)
    else:
        depart_dt = datetime.now(TEHRAN_TZ)

    conn = get_conn()
    prod_row = conn.execute(
        "SELECT * FROM products WHERE product_id = ? OR product_group_id = ? LIMIT 1",
        (product_id_or_group, product_id_or_group),
    ).fetchone()

    group_id = prod_row["product_group_id"] if prod_row else product_id_or_group

    sql = """
        SELECT o.*, s.*, p.persian_title, p.category_name, p.brand_name
        FROM offers o
        JOIN shops s ON o.shop_id = s.shop_id
        JOIN products p ON o.product_id = p.product_id
        WHERE (o.product_id = ? OR o.product_group_id = ?)
    """
    params: list[Any] = [product_id_or_group, group_id]

    if installment_mode == "confirmed_only":
        sql += " AND s.installment_level = 'in_person'"
    elif installment_mode == "all_installment":
        sql += " AND s.has_installment = 1"

    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()

    norm_prices = sorted([
        p for r in rows
        if (p := normalize_realistic_price(r.get("price_toman"), r.get("category_name") or "", r.get("persian_title") or "")) is not None
    ])
    min_grp_p = norm_prices[0] if norm_prices else None
    med_grp_p = norm_prices[len(norm_prices) // 2] if norm_prices else None
    fair_grp_p = int(round((min_grp_p * 0.6 + med_grp_p * 0.4) / 10000.0) * 10000) if (min_grp_p and med_grp_p) else min_grp_p

    cards = [
        build_store_offer_card(r, u_lat, u_lon, travel_mode, depart_dt, min_grp_p, med_grp_p)
        for r in rows
    ]

    if max_budget_toman is not None:
        cards = [c for c in cards if c["effective_price_toman"] is None or c["effective_price_toman"] <= max_budget_toman]

    expanded_radius_notice_fa = None
    if neighborhood_filter and neighborhood_filter not in ("ALL", "همه مناطق تهران"):
        nb_cards = [c for c in cards if c["location_label"] == neighborhood_filter]
        if nb_cards:
            filtered_cards = nb_cards
        else:
            filtered_cards = cards
            expanded_radius_notice_fa = f"در محله «{neighborhood_filter}» فروشگاهی برای این مدل ثبت نشده است؛ نزدیک‌ترین فروشگاه‌های سایر مناطق تهران نمایش داده شد."
    else:
        within_radius = [c for c in cards if c["distance_km"] <= radius_km]
        if within_radius:
            filtered_cards = within_radius
        else:
            filtered_cards = cards
            if cards:
                nearest_km = min(c["distance_km"] for c in cards)
                expanded_radius_notice_fa = (
                    f"در شعاع {to_persian_digits(int(radius_km))} کیلومتری شما فروشگاهی ثبت نشده است؛ "
                    f"نزدیک‌ترین فروشگاه در فاصله {to_persian_digits(round(nearest_km, 1))} کیلومتری نمایش داده شد."
                )

    if open_filter == "open_now":
        filtered_cards = [c for c in filtered_cards if c["hours_now"]["status"] == "open"]
    elif open_filter == "open_at_arrival":
        filtered_cards = [c for c in filtered_cards if c["hours_at_arrival"]["status"] == "open"]

    if sort_by == "cheapest":
        filtered_cards.sort(
            key=lambda c: (
                c["effective_price_toman"] is None,
                c["effective_price_toman"] or 10**12,
                c["distance_km"],
            )
        )
    elif sort_by == "nearest":
        filtered_cards.sort(key=lambda c: (c["distance_km"], c["effective_price_toman"] or 10**12))
    elif sort_by == "open":
        filtered_cards.sort(
            key=lambda c: (
                0 if c["hours_at_arrival"]["status"] == "open" else (1 if c["hours_at_arrival"]["status"] == "unknown" else 2),
                -c["composite_score"],
            )
        )
    else:
        filtered_cards.sort(key=lambda c: -c["composite_score"])

    return {
        "product_id": prod_row["product_id"] if prod_row else product_id_or_group,
        "product_title": prod_row["persian_title"] if prod_row else "",
        "product_group_id": group_id,
        "fair_market_price_toman": fair_grp_p,
        "fair_market_price_fa": format_price_toman(fair_grp_p) if fair_grp_p else "نامشخص",
        "min_market_price_fa": format_price_toman(min_grp_p) if min_grp_p else "نامشخص",
        "median_market_price_fa": format_price_toman(med_grp_p) if med_grp_p else "نامشخص",
        "total_stores_found": len(filtered_cards),
        "expanded_radius_notice_fa": expanded_radius_notice_fa,
        "stores": filtered_cards[:limit],
    }

def compare_stores_by_offer_ids(
    offer_ids: list[str],
    user_lat: float | None = None,
    user_lon: float | None = None,
    travel_mode: str = "car",
) -> dict:
    if not offer_ids:
        return {"stores": [], "comparison_summary_fa": ""}
    conn = get_conn()
    placeholders = ",".join("?" for _ in offer_ids)
    rows = [
        dict(r)
        for r in conn.execute(
            f"""
            SELECT o.*, s.*, p.persian_title, p.category_name, p.brand_name
            FROM offers o
            JOIN shops s ON o.shop_id = s.shop_id
            JOIN products p ON o.product_id = p.product_id
            WHERE o.offer_id IN ({placeholders})
            """,
            offer_ids,
        ).fetchall()
    ]
    conn.close()

    u_lat = user_lat if user_lat is not None else settings.DEFAULT_LAT
    u_lon = user_lon if user_lon is not None else settings.DEFAULT_LON
    depart_dt = datetime.now(TEHRAN_TZ)

    valid_prices = sorted([
        p for r in rows
        if (p := normalize_realistic_price(r.get("price_toman"), r.get("category_name") or "", r.get("persian_title") or "")) is not None
    ])
    min_p = valid_prices[0] if valid_prices else None
    med_p = valid_prices[len(valid_prices) // 2] if valid_prices else None

    cards = [build_store_offer_card(r, u_lat, u_lon, travel_mode, depart_dt, min_p, med_p) for r in rows]
    cards.sort(key=lambda c: -c["composite_score"])

    return {
        "stores": cards,
        "best_overall_offer_id": cards[0]["offer_id"] if cards else None,
        "cheapest_offer_id": min(
            [c for c in cards if c["effective_price_toman"] is not None],
            key=lambda x: x["effective_price_toman"],
            default={},
        ).get("offer_id"),
        "nearest_offer_id": min(cards, key=lambda x: x["distance_km"], default={}).get("offer_id"),
    }

def format_weekly_schedule_fa(weekly_hours_raw: str | None) -> list[dict]:
    wh = parse_weekly_hours(weekly_hours_raw)
    ordered_days = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"]
    schedule = []
    for d in ordered_days:
        day_name = PERSIAN_DAY_NAMES[d]
        info = wh.get(d)
        if not isinstance(info, dict):
            schedule.append({"day": day_name, "status": "unknown", "hours_fa": "نامشخص"})
            continue
        st = info.get("status")
        if st == "closed":
            schedule.append({"day": day_name, "status": "closed", "hours_fa": "تعطیل"})
        elif st == "declared" and info.get("shifts"):
            shifts_str = " و ".join(
                f"{to_persian_digits(sh.get('start_time',''))} تا {to_persian_digits(sh.get('end_time',''))}"
                for sh in info["shifts"]
            )
            schedule.append({"day": day_name, "status": "open", "hours_fa": shifts_str})
        else:
            schedule.append({"day": day_name, "status": "unknown", "hours_fa": "نامشخص"})
    return schedule

def get_in_mall_guide(shop_id: str) -> dict:
    conn = get_conn()
    shop = conn.execute("SELECT * FROM shops WHERE shop_id = ?", (shop_id,)).fetchone()
    if not shop:
        conn.close()
        return {"error": "فروشگاه یافت نشد"}
    s = dict(shop)

    other_offers = conn.execute(
        """
        SELECT o.offer_id, o.product_id, o.price_toman, o.last_price_changed_at, p.persian_title, p.category_name
        FROM offers o JOIN products p ON o.product_id = p.product_id
        WHERE o.shop_id = ? LIMIT 8
        """,
        (shop_id,),
    ).fetchall()
    conn.close()

    mall_name = s["mall_name"]
    google_tip = FAMOUS_MALL_GOOGLE_TIPS.get(mall_name) if mall_name else None
    if not google_tip:
        google_tip = (
            f"در محدوده {s['location_label']}، نام «{mall_name or s['name']}» را در گوگل‌مپ یا نشان جستجو کنید و پس از ورود به پاساژ از اطلاعات طبقه {s['floor'] or 'همکف'} شماره واحد را بپرسید."
        )

    return {
        "shop_id": s["shop_id"],
        "shop_name": s["name"],
        "is_real_name": bool(s["is_real_name"]),
        "instagram": s.get("instagram"),
        "website_url": s.get("website_url"),
        "phone_display": s.get("phone_display") or "۰۲۱-۰۰۰۰۰۰۰۰",
        "location_label": s["location_label"],
        "address": s["address"] or "نامشخص",
        "is_in_mall": bool(s["is_in_mall"]),
        "mall_name": mall_name or "آدرس خیابانی (خارج از پاساژ)",
        "floor": s["floor"] or "نامشخص",
        "unit": s["unit"] or "نامشخص",
        "street_hint": s["street_hint"] or "نامشخص",
        "confidence": s["address_confidence"] or "low",
        "guide_summary_fa": s["guide_summary_fa"],
        "guide_steps_fa": json.loads(s["guide_steps_json"]) if s.get("guide_steps_json") else [],
        "google_mall_tip_fa": google_tip,
        "google_search_url": f"https://www.google.com/search?q={mall_name or s['name']}+تهران+{s['location_label']}",
        "weekly_schedule_fa": format_weekly_schedule_fa(s.get("weekly_hours_json")),
        "missing_info_flags": [
            flag
            for flag, val in [
                ("طبقه دقیق ثبت نشده است", s["floor"]),
                ("شماره واحد/پلاک ثبت نشده است", s["unit"]),
            ]
            if not val
        ],
        "other_shop_offers": [
            {
                "offer_id": r["offer_id"],
                "product_id": r["product_id"],
                "persian_title": r["persian_title"],
                "price_fa": format_price_toman(normalize_realistic_price(r["price_toman"], r["category_name"] or "", r["persian_title"] or "")),
            }
            for r in other_offers
        ],
    }

def build_visit_plan(
    offer_ids: list[str],
    user_lat: float | None = None,
    user_lon: float | None = None,
    travel_mode: str = "car",
    depart_time_iso: str | None = None,
) -> dict:
    comp = compare_stores_by_offer_ids(offer_ids, user_lat, user_lon, travel_mode)
    candidates = comp["stores"][:4]
    if not candidates:
        return {"stops": [], "warnings_fa": []}

    curr_lat = user_lat if user_lat is not None else settings.DEFAULT_LAT
    curr_lon = user_lon if user_lon is not None else settings.DEFAULT_LON
    if depart_time_iso:
        try:
            curr_dt = datetime.fromisoformat(depart_time_iso)
            if curr_dt.tzinfo is None:
                curr_dt = TEHRAN_TZ.localize(curr_dt)
        except Exception:
            curr_dt = datetime.now(TEHRAN_TZ)
    else:
        curr_dt = datetime.now(TEHRAN_TZ)

    remaining = list(candidates)
    ordered_stops = []
    warnings_fa = []
    total_km = 0.0

    step_num = 1
    while remaining:
        remaining.sort(key=lambda c: haversine_km(curr_lat, curr_lon, c["lat"], c["lon"]))
        nxt = remaining.pop(0)
        leg_km = haversine_km(curr_lat, curr_lon, nxt["lat"], nxt["lon"])
        leg_mins = estimate_eta_minutes(leg_km, travel_mode)
        arrival_dt = curr_dt + timedelta(minutes=leg_mins)
        arr_status = check_open_at_arrival(nxt["weekly_hours"], arrival_dt)

        warning = None
        if arr_status["status"] == "closed":
            warning = f"فروشگاه «{nxt['shop_name']}» در ساعت رسیدن شما ({to_persian_digits(arrival_dt.strftime('%H:%M'))}) بسته است."
            warnings_fa.append(warning)
        elif arr_status["closing_soon_on_arrival"]:
            warning = f"فروشگاه «{nxt['shop_name']}» کمتر از ۲۰ دقیقه پس از رسیدن شما تعطیل می‌شود."
            warnings_fa.append(warning)

        ordered_stops.append({
            "step": step_num,
            "offer_id": nxt["offer_id"],
            "shop_id": nxt["shop_id"],
            "shop_name": nxt["shop_name"],
            "product_title": nxt["persian_title"],
            "mall_guide_fa": nxt["guide_summary_fa"],
            "lat": nxt["lat"],
            "lon": nxt["lon"],
            "leg_distance_km": round(leg_km, 2),
            "leg_eta_minutes": leg_mins,
            "arrival_time_fa": to_persian_digits(arrival_dt.strftime("%H:%M")),
            "hours_at_arrival": arr_status,
            "warning_fa": warning,
            "neshan_url": f"https://neshan.org/maps/@{nxt['lat']},{nxt['lon']},16z",
            "balad_url": f"https://balad.ir/location?latitude={nxt['lat']}&longitude={nxt['lon']}",
            "google_maps_url": f"https://www.google.com/maps/dir/?api=1&destination={nxt['lat']},{nxt['lon']}",
        })
        total_km += leg_km
        curr_dt = arrival_dt + timedelta(minutes=20)
        curr_lat, curr_lon = nxt["lat"], nxt["lon"]
        step_num += 1

    return {
        "stops": ordered_stops,
        "total_distance_km": round(total_km, 2),
        "warnings_fa": warnings_fa,
        "share_text_fa": "برنامه خرید حضوری تهران:\n" + "\n".join(
            f"{to_persian_digits(s['step'])}. {s['shop_name']} ({s['mall_guide_fa']}) - ساعت رسیدن: {s['arrival_time_fa']}"
            for s in ordered_stops
        ),
    }
