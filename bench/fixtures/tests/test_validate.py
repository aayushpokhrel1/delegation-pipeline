import pytest

import calc


def test_add_and_mul_still_work():
    assert calc.add(2, 3) == 5
    assert calc.mul(2, 3) == 6


def test_non_numeric_raises_typeerror():
    with pytest.raises(TypeError):
        calc.add("2", 3)
    with pytest.raises(TypeError):
        calc.mul(2, "3")
