def mean(values):
    return sum(values) / len(values)


def median(values):
    if not values:
        raise ValueError("median of an empty list is undefined")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2
