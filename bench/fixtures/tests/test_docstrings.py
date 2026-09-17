import inspect

import strings


def test_every_function_has_a_docstring():
    fns = [f for _, f in inspect.getmembers(strings, inspect.isfunction)]
    assert fns, "no functions found in strings.py"
    missing = [f.__name__ for f in fns if not (f.__doc__ or "").strip()]
    assert not missing, f"missing docstrings: {missing}"
