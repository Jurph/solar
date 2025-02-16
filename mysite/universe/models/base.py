from django.db import models
from typing import Optional
from django.utils.translation import gettext_lazy as _
# Contains the base "Location" model that we can use to instantiate other stuff

class Location(models.Model):
    name = models.CharField(max_length=64, default="DEFAULT")

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

    def __str__(self):
        return self.name
