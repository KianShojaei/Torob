import json

def parse_payment_options(raw_payment: str | list | None) -> dict:
    """
    Section 3.1 Installment Rule:
    - Two levels:
      1) 'in_person' -> 'قسطی حضوری تأییدشده'
      2) 'unknown' -> 'قسطی اعلام‌شده (نوع نامشخص)'
    - Empty [] -> no provider -> excluded by installment filter.
    - 0/0 or null min/max_price_toman -> treated as 'no limit info' (unknown), never as 0 limit.
    """
    if not raw_payment or raw_payment == "null":
        items = []
    elif isinstance(raw_payment, list):
        items = raw_payment
    else:
        try:
            items = json.loads(raw_payment)
            if not isinstance(items, list):
                items = []
        except Exception:
            items = []

    if not items:
        return {
            "has_installment": False,
            "installment_level": "none",
            "label_fa": "بدون سرویس قسطی ثبت‌شده",
            "providers": [],
            "details": []
        }

    providers = []
    has_in_person = False
    details = []

    for item in items:
        if not isinstance(item, dict):
            continue
        prov = item.get("provider_name") or "سرویس اقساطی"
        ch = item.get("channel") or "unknown"
        if prov not in providers:
            providers.append(prov)
        if ch == "in_person":
            has_in_person = True

        min_p = item.get("min_price_toman")
        max_p = item.get("max_price_toman")
        min_valid = int(min_p) if min_p not in (None, 0, "0", "null") else None
        max_valid = int(max_p) if max_p not in (None, 0, "0", "null") else None

        details.append({
            "provider_name": prov,
            "channel": ch,
            "channel_label_fa": "حضوری تأییدشده" if ch == "in_person" else "اعلام‌شده (نیاز به استعلام)",
            "min_price_toman": min_valid,
            "max_price_toman": max_valid,
        })

    if has_in_person:
        level = "in_person"
        label_fa = f"قسطی حضوری تأییدشده ({'، '.join(providers)})"
    else:
        level = "declared"
        label_fa = f"قسطی اعلام‌شده ({'، '.join(providers)})"

    return {
        "has_installment": True,
        "installment_level": level,
        "label_fa": label_fa,
        "providers": providers,
        "details": details,
    }
