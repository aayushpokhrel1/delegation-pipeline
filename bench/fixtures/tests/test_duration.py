import duration


def test_parse_duration_values():
    assert duration.parse_duration("1h30m") == 5400
    assert duration.parse_duration("45s") == 45
    assert duration.parse_duration("2h") == 7200
    assert duration.parse_duration("1h2m3s") == 3723


def test_parse_duration_returns_int():
    assert isinstance(duration.parse_duration("45s"), int)


def test_parse_duration_tolerates_whitespace():
    assert duration.parse_duration(" 90s ") == 90


def test_parse_duration_rejects_bad_input():
    for text in ("", "10", "5d", "abc"):
        try:
            duration.parse_duration(text)
        except ValueError:
            pass
        else:
            assert False, "parse_duration(%r) must raise ValueError" % (text,)
