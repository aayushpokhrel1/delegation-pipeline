import calc


def test_subtract_exists_and_works():
    assert calc.subtract(5, 3) == 2
    assert calc.subtract(0, 4) == -4
