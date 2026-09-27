import temp_convert
import weather


def test_new_name_works():
    assert temp_convert.fahrenheit_to_celsius(212) == 100
    assert temp_convert.freezing_c() == 0


def test_call_sites_updated():
    assert weather.describe(20) == "freezing"
    assert weather.describe(80) == "above freezing"


def test_old_name_is_gone():
    assert not hasattr(temp_convert, "f_to_c"), (
        "f_to_c must be renamed to fahrenheit_to_celsius, no alias may remain")
