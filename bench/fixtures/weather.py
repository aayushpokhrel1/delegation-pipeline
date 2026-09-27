import temp_convert


def describe(f):
    c = temp_convert.f_to_c(f)
    if c <= 0:
        return "freezing"
    return "above freezing"
