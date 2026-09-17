import money


def test_money_stores_integer_cents():
    m = money.Money(10, 50)  # 10 dollars, 50 cents
    assert m.cents == 1050


def test_money_add_and_subtract():
    a = money.Money(1, 25)
    b = money.Money(0, 75)
    assert (a + b).cents == 200
    assert (a - b).cents == 50


def test_money_format():
    assert money.Money(3, 5).format() == "$3.05"
    assert money.Money(0, 0).format() == "$0.00"
