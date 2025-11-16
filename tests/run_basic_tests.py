from src.utils import persian_to_ascii, id_from_url

def run():
    assert persian_to_ascii("۱۲۳۴۵۶۷۸۹۰") == "1234567890"
    assert persian_to_ascii("قیمت ۱,۲۳۴ تومان") == "قیمت 1,234 تومان"
    assert id_from_url("https://divar.ir/v/sample/AbCd1234") == "AbCd1234"
    assert id_from_url("/v/xyz/Token987") == "Token987"
    print("Basic tests OK")

if __name__ == "__main__":
    run()