from django.db import models
from .scale import Scale, OrderedScale  # Import the enhanced Scale class
# Contains the base "Location" model that we can use to instantiate other stuff

class Location(models.Model):
    name = models.CharField(max_length=255, unique=True)
    # orbits = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE)

    # Use the enhanced Scale class for assigning and comparing scales.
    # The field stores a two-character string value, with choices defined in Scale.choices.
    scale = models.CharField(
        max_length=2,
        choices=Scale.choices,
        default=Scale.STATION,
    )

    @property
    def ordered_scale(self):
        return OrderedScale(self.scale)

    def __str__(self):
        return self.name

    def get_concrete_instance(self):
        """
        Returns the concrete (i.e. most specific) instance of this Location.
        If this instance is already concrete (not just a Location),
        it simply returns self. Otherwise, it attempts to re-fetch the object using
        each known subclass. (This incurs extra queries, so you might want to cache the result.)
        """
        if self.__class__.__name__ != "Location":
            return self

        from .station import Station
        from .celestial import Moon, Planet, Star, StarSystem, Galaxy

        for subclass in (Station, Moon, Planet, Star, StarSystem, Galaxy):
            try:
                instance = subclass.objects.get(pk=self.pk)
                if instance.__class__.__name__ != "Location":
                    return instance
            except subclass.DoesNotExist:
                continue
        return self

    def get_type_name(self) -> str:
        """
        Returns the real (concrete) class name as a string.
        """
        return self.get_concrete_instance().__class__.__name__

    @classmethod
    def create(cls, **kwargs):
        """
        Factory method to create a new Location (or a subclass thereof). Uses the
        Django model manager to create the new instance and returns
        its concrete instance.
        """
        instance = cls.objects.create(**kwargs)
        return instance.get_concrete_instance()

    def may_have_station(self):
        """
        Determines if this location may have a space station.
        Typically applies for locations at the STAR, PLANET, or MOON scales.
        """
        return self.scale in {Scale.STAR, Scale.PLANET, Scale.MOON}

    def can_dock(self):
        """
        Determines if this location is a space station suitable for docking.
        """
        return self.scale == Scale.STATION

    def can_land(self):
        """
        Determines if this location supports landing, typically for PLANET or MOON scales.
        """
        return self.scale in {Scale.PLANET, Scale.MOON}

    def requires_launch_clearance(self) -> bool:
        """
        Indicates whether leaving this location requires launch clearance.
        (This could be based on special scale values, for example.)
        """
        return self.scale in {Scale.PLANET, Scale.MOON, Scale.Station} 

    def requires_docking_clearance(self) -> bool:
        """
        Indicates whether arriving at this location requires docking clearance.
        """
        return self.scale == Scale.STATION
