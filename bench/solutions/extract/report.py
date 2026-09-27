from money_fmt import format_cents


def render(cents):
    return "Total: " + format_cents(cents)
