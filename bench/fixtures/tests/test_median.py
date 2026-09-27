import stats


def test_median_odd_length():
    assert stats.median([3, 1, 2]) == 2
    assert stats.median([5]) == 5


def test_median_even_length():
    assert stats.median([4, 1, 3, 2]) == 2.5
    assert stats.median([1, 2]) == 1.5


def test_mean_unchanged():
    assert stats.mean([1, 2, 3]) == 2


def test_median_empty_raises_valueerror():
    try:
        stats.median([])
    except ValueError:
        pass
    else:
        assert False, "median([]) must raise ValueError"
