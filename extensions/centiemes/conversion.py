"""Conversions de durées : heures:minutes, minutes, heures décimales et centièmes d'heure (1 h = 100 centièmes).

Sans Qt. Les durées sont des `Fraction` d'heures : aucune erreur d'arrondi cachée entre les formats
(1 minute = 5/3 de centième d'heure = 36 secondes divisées par 60). L'arrondi n'a lieu qu'à l'affichage.
"""

import re
from fractions import Fraction

CLOCK_COLON = re.compile(r"^(?P<h>\d+):(?P<m>\d{1,2})(?::(?P<s>\d{1,2}))?$")
CLOCK_LETTER = re.compile(r"^(?P<h>\d+)\s*h\s*(?:(?P<m>\d{1,2})\s*(?:min|m)?)?$")
NUMBER = re.compile(r"^\d+(?:\.\d+)?$")


class ParseError(ValueError):
    """Message destiné à l'utilisateur."""


def _clean(text: str) -> str:
    return re.sub(r"[\s  ]+", " ", text.strip().lower())


def parse_clock(text: str) -> Fraction:
    """`1:30`, `1:30:15`, `1h30`, `1 h 30`, `1h`, `0:45` → heures."""
    cleaned = _clean(text)
    match = CLOCK_COLON.match(cleaned.replace(" ", "")) or CLOCK_LETTER.match(cleaned)
    if not match:
        raise ParseError("Format attendu : 1:30 ou 1h30")
    parts = match.groupdict()
    hours, minutes, seconds = (int(parts.get(key) or 0) for key in ("h", "m", "s"))
    if minutes > 59 or seconds > 59:
        raise ParseError("Minutes et secondes : de 0 à 59")
    return Fraction(hours) + Fraction(minutes, 60) + Fraction(seconds, 3600)


def parse_number(text: str) -> Fraction:
    """Nombre positif, virgule ou point décimal, espaces ignorés (`1 275,5`)."""
    cleaned = _clean(text).replace(" ", "").replace(",", ".")
    if not NUMBER.match(cleaned):
        raise ParseError("Nombre attendu, par exemple 1,5")
    return Fraction(cleaned)


def format_decimal(value: Fraction, places: int) -> str:
    """Arrondi à `places` décimales (demi vers le haut), virgule, zéros inutiles retirés."""
    scaled = value * 10**places
    rounded = int(scaled + Fraction(1, 2)) if scaled >= 0 else -int(-scaled + Fraction(1, 2))
    integer, fraction = divmod(abs(rounded), 10**places)
    text = str(integer)
    if places and fraction:
        text += "," + str(fraction).rjust(places, "0").rstrip("0")
    return ("-" if rounded < 0 else "") + text


def to_clock(hours: Fraction) -> str:
    """`H:MM`, arrondi à la minute la plus proche."""
    total = int(hours * 60 + Fraction(1, 2))
    return f"{total // 60}:{total % 60:02d}"


def to_minutes(hours: Fraction) -> str:
    return format_decimal(hours * 60, 2)


def to_decimal_hours(hours: Fraction) -> str:
    return format_decimal(hours, 4)


def to_centiemes(hours: Fraction) -> str:
    return format_decimal(hours * 100, 2)


def exact(hours: Fraction) -> str:
    """`1 h 29 min 59 s` : la durée à la seconde près (utile quand `H:MM` est arrondi)."""
    total = int(hours * 3600 + Fraction(1, 2))
    return f"{total // 3600} h {total % 3600 // 60:02d} min {total % 60:02d} s"


def total(durations: list[Fraction]) -> Fraction:
    return sum(durations, Fraction(0))


def dump(hours: Fraction) -> str:
    """Forme texte exacte, pour l'enregistrement."""
    return f"{hours.numerator}/{hours.denominator}"


def load(text: str) -> Fraction | None:
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None
    return value if value >= 0 else None
