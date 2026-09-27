import typing

import geometry


def test_area_rect_annotated_and_correct():
    hints = typing.get_type_hints(geometry.area_rect)
    assert "width" in hints
    assert "height" in hints
    assert "return" in hints
    assert geometry.area_rect(2, 3) == 6


def test_area_circle_annotated_and_correct():
    hints = typing.get_type_hints(geometry.area_circle)
    assert "radius" in hints
    assert "return" in hints
    assert abs(geometry.area_circle(1) - 3.141592653589793) < 1e-9


def test_perimeter_rect_annotated_and_correct():
    hints = typing.get_type_hints(geometry.perimeter_rect)
    assert "width" in hints
    assert "height" in hints
    assert "return" in hints
    assert geometry.perimeter_rect(2, 3) == 10


def test_scale_annotated_and_correct():
    hints = typing.get_type_hints(geometry.scale)
    assert "value" in hints
    assert "factor" in hints
    assert "return" in hints
    assert geometry.scale(2, 2.5) == 5.0
