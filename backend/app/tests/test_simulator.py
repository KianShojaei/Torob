from app.simulator.parser import extract_price, parse_reply
from app.simulator.persona import persona_for


def test_persona_is_deterministic():
    a = persona_for("shop_abc", age_days=3, hours_known=True)
    b = persona_for("shop_abc", age_days=3, hours_known=True)
    assert a == b
    c = persona_for("shop_xyz", age_days=3, hours_known=True)
    assert a.seed != c.seed or a.responsiveness != c.responsiveness


def test_stale_listing_lowers_reliability():
    fresh = [persona_for(f"shop_{i}", age_days=2).reliability for i in range(40)]
    stale = [persona_for(f"shop_{i}", age_days=200).reliability for i in range(40)]
    assert sum(stale) / len(stale) < sum(fresh) / len(fresh)


def test_parser_detects_out_of_stock():
    r = parse_reply("سلام، این مدل موجود نیست، تموم شده.")
    assert r.in_stock is False


def test_parser_detects_in_stock_and_price():
    r = parse_reply("سلام موجود داریم، قیمت ۲٬۴۵۰٬۰۰۰ تومان است.")
    assert r.in_stock is True
    assert r.confirmed_price == 2_450_000


def test_parser_detects_hours_followup():
    r = parse_reply("الان بسته‌ایم، از ساعت ۱۰ صبح باز هستیم.")
    assert r.needs_followup is True


def test_extract_price_ignores_small_numbers():
    assert extract_price("سایز ۴۲ موجود است") is None
    assert extract_price("قیمت 3,200,000 تومان") == 3_200_000


def test_extract_price_rejects_absurd_values():
    assert extract_price("کد 999999999999999999") is None
