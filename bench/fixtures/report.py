def format_cents(cents):
    return "$" + str(cents // 100) + "." + str(cents % 100).zfill(2)


def render(cents):
    return "Total: " + format_cents(cents)
