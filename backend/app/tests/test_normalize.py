from app.etl.normalize import (
    clean_display,
    detect_brand,
    expand_token,
    fold,
    is_brand,
    to_ascii_digits,
    to_persian_digits,
    tokens,
)


def test_arabic_and_persian_letters_unify():
    assert fold("كتاب") == fold("کتاب")
    assert fold("بابك") == fold("بابک")
    assert fold("إيران") == fold("ایران")


def test_zwnj_becomes_separator_for_matching():
    assert fold("می‌خواهم") == "می خواهم"
    assert "می" in tokens("می‌خواهم کتونی")


def test_diacritics_and_tatweel_removed():
    assert fold("کِتابـــــ") == "کتاب"


def test_digits_ascii_and_back():
    assert to_ascii_digits("۱۲۳۴۵") == "12345"
    assert to_persian_digits("42") == "۴۲"
    assert fold("مدل ۱۲") == "مدل 12"


def test_clean_display_keeps_words_but_collapses_space():
    assert clean_display("  کفش   کتانی  ") == "کفش کتانی"
    assert clean_display(None) == ""


def test_synonyms_expand():
    got = expand_token("کتونی")
    assert "کفش ورزشی" in got
    assert "sneaker" in got


def test_english_lowercased():
    assert fold("iPhone 15 PRO") == "iphone 15 pro"


def test_brand_detection():
    assert is_brand("سامسونگ")
    assert detect_brand("گوشی سامسونگ گلکسی") == "سامسونگ"
    assert detect_brand("یک محصول عجیب") is None


def test_empty_inputs():
    assert fold(None) == ""
    assert tokens("") == []
