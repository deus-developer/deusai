from wasteland_wars.constants import fractions_by_icon
from wasteland_wars.enums import Fraction


def get_fraction_by_emoji(emoji: str) -> Fraction:
    return fractions_by_icon.get(emoji, Fraction.UNKNOWN)
