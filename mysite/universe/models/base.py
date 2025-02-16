from django.db import models
from typing import Optional
from django.utils.translation import gettext_lazy as _
# Contains the base "Location" model that we can use to instantiate other stuff

class Location(models.Model):
    name = models.CharField(max_length=255)
    # orbits = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE)


    def get_concrete_instance(self):
        """
        Returns the concrete (i.e. most specific) instance of this Location.
        If this instance is already concrete (not just a Location),
        it simply returns self. Otherwise, we attempt to re-fetch the object using
        each known subclass. (This incurs extra queries, so you might want to cache the result.)
        """
        # If this object is already not a bare Location, return self.
        if self.__class__.__name__ != "Location":
            return self

        # Import the known subclasses.
        # (List them in order of priority, if needed.)
        from .station import Station
        from .celestial import Moon, Planet, Star, StarSystem, Galaxy

        for subclass in (Station, Moon, Planet, Star, StarSystem, Galaxy):
            try:
                # Try to get a concrete instance of this subclass with the same primary key.
                instance = subclass.objects.get(pk=self.pk)
                if instance.__class__.__name__ != "Location":
                    return instance
            except subclass.DoesNotExist:
                continue
        return self

    def get_type_name(self) -> str:
        """
        Returns a string with the real (concrete) class name.
        """
        return self.get_concrete_instance().__class__.__name__


    class Scale(models.TextChoices):
        GALAXY = 'GX', _('galaxy')
        STARSYSTEM = 'SY', _('star system')
        STAR = 'SR', _('star')
        PLANET = 'PL', _('planet')
        MOON = 'MN', _('moon')
        STATION = 'SS', _('space station')
    
    scale = models.CharField(
        max_length=2, 
        choices=Scale.choices,
        default=Scale.STATION
    )

    def may_have_station(self):
        return self.scale in{
            self.scale.STAR,
            self.scale.PLANET,
            self.scale.MOON            
        }

    def can_dock(self):
        return self.scale in{
            self.scale.STATION,
        }

    def can_land(self):
        return self.scale in{
            self.scale.PLANET,
            self.scale.MOON,
        }

    def requires_launch_clearance(self) -> bool:
        """Whether this location requires launch clearance to depart"""
        return self.scale == 'SF'

    def requires_docking_clearance(self) -> bool:
        """Whether this location requires docking clearance to arrive"""
        return self.scale == 'SS'

    def get_control_station(self) -> Optional['Station']:
        """Get the control station responsible for this location"""
        from .station import Station  # Avoid circular import
        return Station.objects.filter(
            orbits=self,
            name__icontains='Control'
        ).first()

    def get_concrete_instance(self):
        """
        Returns the concrete (i.e. most specific) instance of this Location.
        If this instance is already concrete (not just a Location),
        it simply returns self. Otherwise, we attempt to re-fetch the object using
        each known subclass. (This incurs extra queries, so you might want to cache the result.)
        """
        # If this object is already not a bare Location, return self.
        if self.__class__.__name__ != "Location":
            return self

        # Import the known subclasses.
        # (List them in order of priority, if needed.)
        from .station import Station
        from .celestial import Moon, Planet, Star, StarSystem, Galaxy

        for subclass in (Station, Moon, Planet, Star, StarSystem, Galaxy):
            try:
                # Try to get a concrete instance of this subclass with the same primary key.
                instance = subclass.objects.get(pk=self.pk)
                if instance.__class__.__name__ != "Location":
                    return instance
            except subclass.DoesNotExist:
                continue
        return self

    def get_type_name(self) -> str:
        """
        Returns a string with the real (concrete) class name.
        """
        return self.get_concrete_instance().__class__.__name__

    def __str__(self):
        return self.name
