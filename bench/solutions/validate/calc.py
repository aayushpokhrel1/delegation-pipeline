"""Tiny arithmetic helpers used by the delegation benchmark fixtures."""


def add(a, b):
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("add expects numeric arguments")
    return a + b


def mul(a, b):
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("mul expects numeric arguments")
    return a * b
