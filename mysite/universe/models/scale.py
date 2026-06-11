from functools import total_ordering
from typing import Union

from django.db import models
from django.utils.translation import gettext as _


@total_ordering
class OrderedScale(int):
    ORDERING = {
        "SS": 1,
        "MN": 2,
        "PL": 3,
        "SR": 4,
        "SY": 5,
        "GX": 6,
    }

    def __new__(cls, value: Union[str, int, "OrderedScale"]) -> "OrderedScale":
        if isinstance(value, OrderedScale):
            return value
        if isinstance(value, str):
            try:
                numeric_value = cls.ORDERING[value]
            except KeyError:
                raise ValueError(f"Invalid scale code: {value}")
            return super().__new__(cls, numeric_value)
        return super().__new__(cls, value)

    def __str__(self) -> str:
        # Convert back to code for string representation
        for code, value in self.ORDERING.items():
            if value == self:
                return code
        return str(int(self))

    def __hash__(self) -> int:
        return hash(str(self))


class Scale(models.TextChoices):
    """
    Enhanced Scale choices for Location.

    Each member stores a two-character string code for the database / forms and a
    plain-English description for display. This keeps Django TextChoices happy on
    Python 3.12+, while ordering and numeric comparisons are handled by
    `OrderedScale`, which converts the stored code into a sortable int.
    """

    GALAXY = "GX", _("galaxy")
    STARSYSTEM = "SY", _("star system")
    STAR = "SR", _("star")
    PLANET = "PL", _("planet")
    MOON = "MN", _("moon")
    STATION = "SS", _("space station")
