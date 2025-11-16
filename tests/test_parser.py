from src.utils import persian_to_ascii

def test_persian_to_ascii_digits():
    assert persian_to_ascii("۱۲۳۴۵۶۷۸۹۰") == "1234567890"
    assert persian_to_ascii("قیمت ۱,۲۳۴,۵۶۷ تومان") == "قیمت 1,234,567 تومان"