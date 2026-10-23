import hashlib
import json
import time
import uuid
from datetime import datetime

from backend.app.config import settings
from backend.app.db.repo import get_conn, search_products, normalize_realistic_price
from backend.app.services.ranking import find_stores_for_product
from backend.app.etl.normalizer import to_persian_digits
from backend.app.etl.price_rules import format_price_toman
from backend.app.etl.hours_engine import TEHRAN_TZ

def get_shop_persona(shop_id: str, product_id: str = "") -> dict:
    h = int(hashlib.md5(f"{shop_id}:{product_id}".encode("utf-8")).hexdigest()[:8], 16)
    mod = h % 100
    if mod < 55:
        behavior = "in_stock"
        delay_real_seconds = 1.5 + (h % 3)
    elif mod < 80:
        behavior = "out_of_stock"
        delay_real_seconds = 2.0 + (h % 2)
    else:
        behavior = "no_reply"
        delay_real_seconds = 9999.0
    return {
        "behavior": behavior,
        "delay_real_seconds": delay_real_seconds,
    }

def start_seller_contacts(
    shop_ids: list[str],
    product_id: str,
    intent: str = "all",
    custom_message: str | None = None,
    proposed_price_toman: int | None = None,
) -> list[dict]:
    conn = get_conn()
    prod = conn.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
    p_title = prod["persian_title"] if prod else "محصول موردنظر"
    cat_name = prod["category_name"] if prod else ""

    now_ts = time.time()
    timeout_secs = settings.CONTACT_TIMEOUT_SECONDS
    created_convs = []

    for idx, s_id in enumerate(shop_ids):
        shop = conn.execute("SELECT * FROM shops WHERE shop_id = ?", (s_id,)).fetchone()
        offer = conn.execute(
            "SELECT * FROM offers WHERE shop_id = ? AND product_id = ? LIMIT 1",
            (s_id, product_id),
        ).fetchone()
        if not shop:
            continue

        if len(shop_ids) >= 3:
            if idx == 0:
                forced_behavior = "in_stock"
                delay_s = 1.5
            elif idx == 1:
                forced_behavior = "out_of_stock"
                delay_s = 2.5
            else:
                forced_behavior = "no_reply"
                delay_s = 9999.0
        else:
            persona = get_shop_persona(s_id, product_id)
            forced_behavior = persona["behavior"]
            delay_s = persona["delay_real_seconds"]
            if intent == "negotiate_price":
                forced_behavior = "in_stock"
                delay_s = 1.6

        conv_id = "conv_" + uuid.uuid4().hex[:10]
        raw_rec_price = offer["price_toman"] if offer else (prod["min_valid_price"] if prod else 4_500_000)
        base_price = normalize_realistic_price(raw_rec_price, cat_name, p_title) or 4_500_000

        floor_info = shop["floor"] or "همکف"
        unit_info = shop["unit"] or "۱۲"

        if intent == "negotiate_price" and proposed_price_toman:
            target_p = proposed_price_toman
            user_msg = custom_message or (
                f"سلام وقت بخیر، درباره «{p_title}» پیام می‌دم. کف قیمت منصفانه بازار در فروشگاه‌های تهران حدود {format_price_toman(target_p)} هست. "
                f"اگر امروز حضوری خدمت برسم، امکانش هست با همین قیمت {format_price_toman(target_p)} فاکتور کنید؟"
            )
            agreed_price = int(round(((base_price * 0.35 + target_p * 0.65)) / 10000.0) * 10000)
            confirmed_price = min(base_price, agreed_price)
            reply_text = (
                f"سلام، برای خرید حضوری امروز به احترام شما قیمت رو اصلاح کردیم و با قیمت نهایی {format_price_toman(confirmed_price)} (با گارانتی اصلی) تقدیم می‌کنیم. "
                f"تا ساعت ۲۱ در طبقه {floor_info}، واحد {unit_info} منتظر حضور شما هستیم."
            )
        else:
            user_msg = custom_message or (
                f"سلام وقت بخیر، آیا «{p_title}» الان برای خرید حضوری موجوده و قیمت روزش چنده؟ ساعت کاری و واحد دقیق داخل پاساژ رو هم لطفاً می‌فرمایید؟"
            )
            confirmed_price = base_price
            reply_text = (
                f"سلام، بله «{p_title}» موجود و آماده تحویل حضوری است. "
                f"قیمت روز با گارانتی معتبر {format_price_toman(confirmed_price)} است. "
                f"امروز تا ساعت ۲۱ هستیم (طبقه {floor_info}، واحد {unit_info})."
            )

        if forced_behavior == "in_stock":
            parsed = {
                "in_stock": True,
                "confirmed_price_toman": confirmed_price,
                "hours_info": "امروز تا ساعت ۲۱:۰۰ باز است",
                "unit_info": f"طبقه {floor_info}، واحد {unit_info}",
                "negotiated": intent == "negotiate_price",
                "Simulated": True,
            }
            replied_at = now_ts + delay_s
        elif forced_behavior == "out_of_stock":
            reply_text = f"سلام، متأسفانه موجودی «{p_title}» امروز تمام شده است."
            parsed = {
                "in_stock": False,
                "confirmed_price_toman": None,
                "hours_info": None,
                "unit_info": None,
                "Simulated": True,
            }
            replied_at = now_ts + delay_s
        else:
            reply_text = None
            parsed = {
                "in_stock": None,
                "confirmed_price_toman": None,
                "hours_info": None,
                "Simulated": True,
            }
            replied_at = None

        conn.execute(
            """
            INSERT INTO conversations
            (conversation_id, shop_id, product_id, intent, status, user_message, seller_reply, parsed_result_json, created_at, replied_at, timeout_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conv_id,
                s_id,
                product_id,
                intent,
                "delivered",
                user_msg,
                reply_text,
                json.dumps(parsed, ensure_ascii=False),
                now_ts,
                replied_at,
                now_ts + timeout_secs,
            ),
        )
        created_convs.append({
            "conversation_id": conv_id,
            "shop_id": s_id,
            "shop_name": shop["name"],
            "product_id": product_id,
            "status": "delivered",
            "user_message": user_msg,
            "simulation_badge_fa": "شبیه‌سازی دمو",
        })

    conn.commit()
    conn.close()
    return created_convs

def poll_conversations(
    conversation_ids: list[str],
    user_lat: float | None = None,
    user_lon: float | None = None,
) -> dict:
    if not conversation_ids:
        return {"conversations": [], "alternatives": []}

    conn = get_conn()
    now_ts = time.time()
    now_tehran_str = to_persian_digits(datetime.now(TEHRAN_TZ).strftime("%H:%M"))

    placeholders = ",".join("?" for _ in conversation_ids)
    rows = conn.execute(
        f"""
        SELECT c.*, s.name as shop_name, s.location_label, s.guide_summary_fa, s.lat, s.lon,
               p.persian_title, o.offer_id
        FROM conversations c
        JOIN shops s ON c.shop_id = s.shop_id
        JOIN products p ON c.product_id = p.product_id
        LEFT JOIN offers o ON o.shop_id = c.shop_id AND o.product_id = c.product_id
        WHERE c.conversation_id IN ({placeholders})
        """,
        conversation_ids,
    ).fetchall()

    results = []
    failed_shop_ids = set()
    target_product_id = None

    for r in rows:
        d = dict(r)
        target_product_id = d["product_id"]
        parsed = json.loads(d["parsed_result_json"]) if d.get("parsed_result_json") else {}
        status = d["status"]

        if d["replied_at"] and now_ts >= d["replied_at"]:
            if parsed.get("in_stock") is True:
                status = "confirmed"
                conn.execute(
                    """
                    UPDATE offers
                    SET availability_status = 'confirmed_in_stock',
                        confirmed_price_toman = ?,
                        confirmed_at = ?
                    WHERE shop_id = ? AND product_id = ?
                    """,
                    (parsed.get("confirmed_price_toman"), now_tehran_str, d["shop_id"], d["product_id"]),
                )
            elif parsed.get("in_stock") is False:
                status = "out_of_stock"
                failed_shop_ids.add(d["shop_id"])
                conn.execute(
                    """
                    UPDATE offers
                    SET availability_status = 'confirmed_out_of_stock',
                        confirmed_at = ?
                    WHERE shop_id = ? AND product_id = ?
                    """,
                    (now_tehran_str, d["shop_id"], d["product_id"]),
                )
        elif d["replied_at"] is None and now_ts >= d["timeout_at"]:
            status = "no_reply"
            failed_shop_ids.add(d["shop_id"])

        if status != d["status"]:
            conn.execute(
                "UPDATE conversations SET status = ? WHERE conversation_id = ?",
                (status, d["conversation_id"]),
            )

        secs_left = max(0, int(round(d["timeout_at"] - now_ts))) if status == "delivered" else 0

        results.append({
            "conversation_id": d["conversation_id"],
            "offer_id": d.get("offer_id"),
            "lat": d.get("lat"),
            "lon": d.get("lon"),
            "shop_id": d["shop_id"],
            "shop_name": d["shop_name"],
            "location_label": d["location_label"],
            "guide_summary_fa": d["guide_summary_fa"],
            "product_id": d["product_id"],
            "product_title": d["persian_title"],
            "status": status,
            "status_label_fa": {
                "delivered": f"در انتظار پاسخ ({to_persian_digits(secs_left)} ثانیه)",
                "confirmed": "تأیید موجودی و قیمت روز",
                "out_of_stock": "ناموجود (اعلام فروشنده)",
                "no_reply": "عدم پاسخگویی (Timeout)",
            }.get(status, status),
            "user_message": d["user_message"],
            "seller_reply": d["seller_reply"] if status in ("confirmed", "out_of_stock") else None,
            "parsed_result": parsed if status in ("confirmed", "out_of_stock") else None,
            "confirmed_price_fa": format_price_toman(parsed.get("confirmed_price_toman")) if status == "confirmed" else None,
            "seconds_until_timeout": secs_left,
            "simulation_badge_fa": "شبیه‌سازی دمو",
        })

    conn.commit()
    conn.close()

    alternatives = []
    similar_models = []
    if failed_shop_ids and target_product_id:
        alt_res = find_stores_for_product(
            target_product_id, user_lat=user_lat, user_lon=user_lon, limit=10
        )
        contacted_ids = {r["shop_id"] for r in results}
        for st in alt_res["stores"]:
            if st["shop_id"] not in contacted_ids and st["availability_status"] != "confirmed_out_of_stock":
                st["alternative_reason_fa"] = "جایگزین خودکار (موجود در فروشگاه دیگر نزدیک شما)"
                alternatives.append(st)
                if len(alternatives) >= 3:
                    break

        conn2 = get_conn()
        p_row = conn2.execute("SELECT * FROM products WHERE product_id = ?", (target_product_id,)).fetchone()
        conn2.close()
        if p_row:
            sim_search = search_products(query=p_row["category_name"], limit=4)
            for sm in sim_search["products"]:
                if sm["product_id"] != target_product_id:
                    sm["alternative_badge_fa"] = "مدل مشابه (نه دقیقاً همان کالا)"
                    similar_models.append(sm)

    return {
        "conversations": results,
        "has_failures": bool(failed_shop_ids),
        "replacement_stores": alternatives,
        "similar_models": similar_models[:3],
    }
