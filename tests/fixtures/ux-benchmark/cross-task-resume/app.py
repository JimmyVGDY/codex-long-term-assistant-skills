def parse_count(value):
    result = int(value)
    if result < 0:
        raise ValueError("negative count")
    return result
