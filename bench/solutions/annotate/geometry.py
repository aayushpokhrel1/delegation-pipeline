def area_rect(width: float, height: float) -> float:
    return width * height


def area_circle(radius: float) -> float:
    return 3.141592653589793 * radius * radius


def perimeter_rect(width: float, height: float) -> float:
    return 2 * (width + height)


def scale(value: float, factor: float) -> float:
    return value * factor
