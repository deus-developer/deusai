def format_number(number: int, n: int = 3) -> str:
    number_string = str(int(number))
    j = len(number_string) % n
    substrings = [number_string[n * i + j : n * (i + 1) + j] for i in range(len(number_string) // n)]
    if j != 0:
        substrings.insert(0, number_string[:j])
    return " ".join(substrings)


def format_number_padded(number: int, size: int, count: int):
    return format_number(number, size).rjust(count, " ")
