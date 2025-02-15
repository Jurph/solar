"""
LocationGenerator service provides methods to generate or select valid location
objects for various operations. Currently, it supports returning a random Station
object for initializing ships.
"""

import random
from mysite.universe.models.station import Station

class LocationGenerator:
    """Service for generating or choosing valid location objects."""

    def get_random_station(self) -> Station:
        """Return a random available Station from the database.

        Raises:
            ValueError: If there are no Station objects in the database.
        """
        stations = list(Station.objects.all())
        if not stations:
            raise ValueError("No station locations available in the database.")
        return random.choice(stations) 