import re

UNITS = (("h", 3600), ("m", 60), ("s", 1))


def parse_duration(text):
    text = text.strip()
    if not text:
        raise ValueError("empty duration")
    total = 0
    index = 0
    for unit, factor in UNITS:
        match = re.match(r"(\d+)" + unit, text[index:])
        if match:
            total += int(match.group(1)) * factor
            index += match.end()
    if index != len(text):
        raise ValueError("cannot parse duration: " + text)
    return total
