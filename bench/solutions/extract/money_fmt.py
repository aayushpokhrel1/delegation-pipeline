def format_cents(cents):
    return "$" + str(cents // 100) + "." + str(cents % 100).zfill(2)
