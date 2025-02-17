"""
Provides an enhanced Scale implementation that preserves our two-character
text values (for XML import and database storage) and plain-English descriptions,
while also supporting comparison operators (<, <=, >, >=, ==, !=) via a custom ordering.

This is achieved by defining a custom string subclass, OrderedScale, that uses a
predefined mapping to determine ordering, then using OrderedScale as the value type
in our TextChoices enumeration.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from functools import total_ordering

@total_ordering
class OrderedScale(str):
    """
    A string subclass that supports ordering based on a custom mapping.
    
    The mapping defines the relative sizes of each scale:
    'SS' (space station) < 'MN' (moon) < 'PL' (planet) < 'SR' (star) < 'SY' (star system) < 'GX' (galaxy)
    """
    ORDERING = {
        'SS': 1,  # space station
        'MN': 2,  # moon
        'PL': 3,  # planet
        'SR': 4,  # star
        'SY': 5,  # star system
        'GX': 6,  # galaxy
    }

    def __new__(cls, value):
        # Create a new instance of OrderedScale as a string.
        obj = str.__new__(cls, value)
        return obj

    def __lt__(self, other):
        if isinstance(other, str):
            return OrderedScale.ORDERING.get(self, 0) < OrderedScale.ORDERING.get(other, 0)
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, str):
            return OrderedScale.ORDERING.get(self, 0) == OrderedScale.ORDERING.get(other, 0)
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
