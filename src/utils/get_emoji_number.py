from typing import List

emoji_by_number: List[str] = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]


def get_emoji_number(number: int) -> str:
    result: List[str] = []
    while number > 0:
        number, mod = divmod(number, 10)
        result.append(emoji_by_number[mod])

    result.reverse()
    string = "".join(result)
    return string
