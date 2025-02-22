from functools import total_ordering
from typing import Union
from django.db import models
from django.utils.translation import gettext as _

@total_ordering
class OrderedScale(str):
    ORDERING = {
        'SS': 1,
        'MN': 2,
        'PL': 3,
        'SR': 4,
        'SY': 5,
        'GX': 6,
    }

    def __new__(cls, value: Union[str, "OrderedScale"]) -> "OrderedScale":
        return super().__new__(cls, value)

    def __hash__(self) -> int:
        print(f"Hashing OrderedScale: {self}")
        return hash(str(self))

    def __lt__(self, other: Union[str, "OrderedScale"]) -> bool:
        print(f"Comparing {self} < {other}")
        if isinstance(other, (OrderedScale, str)):
            return self.ORDERING[str(self)] < self.ORDERING.get(str(other), 0)
        return NotImplemented

    def __eq__(self, other: Union[str, "OrderedScale"]) -> bool:
        print(f"Comparing {self} == {other}")
        if isinstance(other, (OrderedScale, str)):
            return self.ORDERING[str(self)] == self.ORDERING.get(str(other), 0)
        return NotImplemented

class Scale(models.TextChoices):
    """
    Enhanced Scale choices for Location.
    
    Each member has a two-character value (for XML import and storage) and a plain-English
    description. The underlying value is of type OrderedScale, so that scale comparisons
    (>, <, ==, etc.) can be made naturally.
    """
    GALAXY     = OrderedScale('GX'), _('galaxy')
    STARSYSTEM = OrderedScale('SY'), _('star system')
    STAR       = OrderedScale('SR'), _('star')
    PLANET     = OrderedScale('PL'), _('planet')
    MOON       = OrderedScale('MN'), _('moon')
    STATION    = OrderedScale('SS'), _('space station')
