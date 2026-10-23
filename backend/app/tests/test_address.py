from app.services.address import find_it_text, mall_key, parse_address


def test_full_mall_address():
    p = parse_address(
        "خیابان جمهوری، نبش شیخ هادی، پاساژ علاءالدین ۲، طبقه ۶، واحد ۶۲۲"
    )
    assert p.mall_name == "پاساژ علاءالدین ۲"
    assert p.floor == "6"
    assert p.unit == "622"
    assert p.unit_kind == "واحد"
    assert p.landmark and "نبش" in p.landmark
    assert p.confidence >= 0.8
    assert p.missing == []


def test_floor_words_and_negative_floor():
    assert parse_address("پاساژ آلتون، طبقه همکف، واحد ۱۲").floor == "همکف"
    assert parse_address("مجتمع تجاری نور، طبقه منفی یک، مغازه ۵").floor == "منفی 1"
    assert parse_address("پاساژ گلستان، طبقه سوم").floor == "3"


def test_missing_parts_are_reported_not_invented():
    p = parse_address("تهران، خیابان ولیعصر، کوچه بهار")
    assert p.mall_name is None
    assert "طبقه" in p.missing and "واحد" in p.missing
    card = find_it_text(p)
    assert card["ask_sentence"]
    assert "نامشخص" in card["detail"] or "ثبت نشده" in card["detail"]


def test_find_it_card_is_specific_when_known():
    p = parse_address("پاساژ بوشهری، طبقه ۲، واحد ۷")
    card = find_it_text(p)
    assert card["title"] == "پاساژ بوشهری، طبقه 2، واحد 7"
    assert "طبقه 2" in card["detail"]
    assert card["ask_sentence"] is None


def test_mall_key_groups_variants():
    a = mall_key("پاساژ علاءالدین ۲")
    b = mall_key("علاءالدین 2")
    c = mall_key("پاساژ  علاالدین")
    assert a == b
    assert a != c  # spelling variant is intentionally NOT merged (precision first)


def test_digits_are_ascii_normalized():
    p = parse_address("پاساژ آلتون، طبقه ۲، واحد ۱۴")
    assert p.floor == "2"
    assert p.unit == "14"


def test_empty_address():
    p = parse_address(None)
    assert p.confidence == 0.0
    assert p.missing == ["آدرس"]
