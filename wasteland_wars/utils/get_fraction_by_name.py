from wasteland_wars.constants import fractions_by_name
from wasteland_wars.enums import Fraction


def get_fraction_by_name(name: str) -> Fraction:
    return fractions_by_name.get(name, Fraction.UNKNOWN)
