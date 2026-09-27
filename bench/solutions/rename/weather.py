import temp_convert


def describe(f):
    c = temp_convert.fahrenheit_to_celsius(f)
    if c <= 0:
        return "freezing"
    return "above freezing"
