from money_fmt import format_cents


def line(cents):
    return "Amount due " + format_cents(cents)
