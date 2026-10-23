import re
from backend.app.etl.normalizer import to_ascii_digits, to_persian_digits

MALL_VARIANTS = {
    "علاالدین": "پاساژ علاءالدین",
    "علاءالدین": "پاساژ علاءالدین",
    "علالدین": "پاساژ علاءالدین",
    "علا الدین": "پاساژ علاءالدین",
    "چارسو": "پاساژ چارسو",
    "بوشهری": "پاساژ بوشهری",
    "امجد": "پاساژ امجد",
    "فراز": "پاساژ فراز",
    "کیان": "پاساژ کیان",
    "اتحادیه": "پاساژ اتحادیه",
    "بازار موبایل ایران": "بازار موبایل ایران",
    "پاساژ یگانه": "پاساژ یگانه",
    "پایتخت": "مجتمع کامپیوتر پایتخت",
    "ایران مال": "ایران مال",
    "تیراژه": "مرکز خرید تیراژه",
}

MALL_REGEX = re.compile(
    r"(?:پاساژ|مجتمع(?:\s+تجاری|\s+کامپیوتر)?|مرکز\s+خرید|برج|بازار(?:\s+بزرگ|\s+موبایل)?)\s+([آ-یa-zA-Z0-9\s‌]{2,25}?)(?=\s*(?:،|,|-|طبقه|واحد|پلاک|غرفه|$))"
)

FLOOR_REGEX = re.compile(
    r"طبقه\s*(همکف|زیرهمکف|منفی\s*یک|منفی\s*دو|منفی\s*\d+|اول|دوم|سوم|چهارم|پنجم|ششم|هفتم|[-+]?\d+)"
)

UNIT_REGEX = re.compile(
    r"(?:واحد|غرفه|پلاک)\s*([0-9a-zA-Z/\-]+)"
)

STREET_LANDMARK_REGEX = re.compile(
    r"((?:خیابان|بلوار|میدان|چهارراه|تقاطع|نبش|نرسیده به|روبروی|جنب)\s+[^،,\n]{3,45})"
)

def normalize_mall_name(raw_name: str) -> str:
    cleaned = raw_name.strip(" ،,-")
    for k, canonical in MALL_VARIANTS.items():
        if k in cleaned:
            return canonical
    if not any( cleaned.startswith(prefix) for prefix in ("پاساژ", "مجتمع", "مرکز خرید", "بازار", "برج") ):
        return f"پاساژ {cleaned}"
    return cleaned

def parse_shop_address(address: str | None, neighborhood: str | None = None) -> dict:
    """
    Rule 8 & Rule 9:
    Extract mall_name, floor, unit, street/landmark, confidence, and build Persian 'how to find it' card.
    Never hallucinate missing floors/units; explicitly mark as 'نامشخص' and suggest asking the store.
    """
    if not address or address == "null":
        return {
            "mall_name": None,
            "floor": None,
            "unit": None,
            "street_hint": None,
            "is_in_mall": False,
            "confidence": "low",
            "guide_summary_fa": "آدرس دقیق ثبت نشده است • لطفاً پیش از مراجعه با فروشگاه تماس بگیرید",
            "guide_steps_fa": ["آدرس متنی کامل در دسترس نیست؛ از فروشنده لوکیشن یا پلاک دقیق را بپرسید."],
        }

    addr_clean = to_ascii_digits(address)
    mall_name = None

    # Check known canonical variants first
    for variant, canonical in MALL_VARIANTS.items():
        if variant in addr_clean:
            mall_name = canonical
            break

    if not mall_name:
        m = MALL_REGEX.search(addr_clean)
        if m:
            mall_name = normalize_mall_name(m.group(0))

    floor_match = FLOOR_REGEX.search(addr_clean)
    floor = floor_match.group(1).strip() if floor_match else None

    unit_match = UNIT_REGEX.search(addr_clean)
    unit = unit_match.group(1).strip() if unit_match else None

    landmarks = STREET_LANDMARK_REGEX.findall(addr_clean)
    street_hint = "، ".join(landmarks[:2]) if landmarks else None

    is_in_mall = bool(mall_name or floor)
    
    # Confidence scoring
    if mall_name and floor and unit:
        confidence = "high"
    elif (mall_name and (floor or unit)) or (street_hint and unit):
        confidence = "medium"
    else:
        confidence = "low"

    # Build Rule 9 In-Mall Guide Text
    floor_display = to_persian_digits(floor) if floor else "نامشخص"
    unit_display = to_persian_digits(unit) if unit else "نامشخص"

    steps = []
    if neighborhood:
        steps.append(f"محدوده: محله {neighborhood}")
    if street_hint:
        steps.append(f"مسیر دسترسی: {to_persian_digits(street_hint)}")

    if is_in_mall:
        mall_label = mall_name or "پاساژ/مجتمع تجاری"
        summary = f"{mall_label}، طبقه {floor_display}، واحد {unit_display}"
        steps.append(f"وارد «{mall_label}» شوید.")
        if floor:
            steps.append(f"به طبقه {floor_display} بروید.")
        else:
            steps.append("طبقه دقیق در آدرس ثبت نشده است (نامشخص)؛ از اطلاعات پاساژ یا فروشنده بپرسید.")
        if unit:
            steps.append(f"واحد/پلاک {unit_display} را پیدا کنید.")
        else:
            steps.append("شماره واحد نامشخص است؛ پیش از مراجعه از فروشنده شماره واحد را استعلام کنید.")
    else:
        summary = f"{to_persian_digits(street_hint or address[:50])} • پلاک/واحد: {unit_display}"
        steps.append(f"آدرس سرراست خیابانی: {to_persian_digits(address)}")
        if not unit:
            steps.append("پلاک دقیق مشخص نیست؛ در صورت نیاز با فروشگاه هماهنگ کنید.")

    return {
        "mall_name": mall_name,
        "floor": floor_display if floor else None,
        "unit": unit_display if unit else None,
        "street_hint": to_persian_digits(street_hint) if street_hint else None,
        "is_in_mall": is_in_mall,
        "confidence": confidence,
        "guide_summary_fa": summary,
        "guide_steps_fa": steps,
    }
