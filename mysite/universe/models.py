from django.db import models
from django.core import serializers
from django.utils.translation import gettext_lazy as _

# Apparently turn on the Django before running this
# Can't believe you didn't turn on the Django, Dave.

# Define the Data Model 

class Location(models.Model):
    name = models.CharField(
        max_length=64, 
        default="DEFAULT"
        )
    orbits = None

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
        return self.Size in{
            self.Size.STAR,
            self.Size.PLANET,
            self.Size.MOON            
        }

    def can_dock(self):
        return self.Size in{
            self.Size.STATION,
        }

    def can_land(self):
        return self.Size in{
            self.Size.PLANET,
            self.Size.MOON,
        }

    def __str__(self):
        return self.name


class Galaxy(Location):
    ## https://en.wikipedia.org/wiki/Galaxy#Types_and_morphology
    galaxies = [
        ('CD', 'Supergiant Elliptical Type cD'),    
        ('DW', 'Dwarf'),
        ('E0', 'Elliptical - Sphere'),
        ('E7', 'Elliptical - Elongated'),
        ('IR', 'Irregular Type i'),
        ('IT', 'Irregular Type ii'),
        ('LN', 'Lenticular'),    
        ('SB', 'Barred Spiral'),
        ('SH', 'Elliptical Shell'),
        ('SP', 'Spiral Arm'),
        ('SS', 'Superluminous Spiral'),
        ('UD', 'Ultra Diffuse'),
    ]    
    sizes = [
        ('D', 'dwarf'),
        ('S', 'small'),
        ('M', 'medium'),
        ('L', 'large'),
        ('X', 'extra large'),
        ('G', 'supergiant'),
    ]    
    type = models.CharField(max_length=2,choices=galaxies)
    size = models.CharField(max_length=1,choices=sizes)
    orbits = None

class StarSystem(Location):
    # These are boring until we have binary stars 
    orbits = models.ForeignKey(Galaxy, on_delete=models.CASCADE, related_name="+")

class Star(Location):
    # othernames = TODO: figure out how to create a list of CharFields
    # TODO: expand this later - https://en.wikipedia.org/wiki/Stellar_classification
    stars = [
        ('O', 'O-Type Blue Supergiant'),
        ('B', 'B-Type Blue Giant'),
        ('A', 'A-Type White Star'),
        ('F', 'F-Type White Star'),                
        ('G', 'G-Type Yellow Star'),
        ('K', 'K-Type Yellow Star'),
        ('M', 'M-Type Red Dwarf'),
        ('N', 'M-Type Red Supergiant'),
    ]
    startype = models.CharField(max_length=2,choices=stars)
    starmagnitude = models.DecimalField(max_digits=8,decimal_places=2, default=4.31)
    orbits = models.ForeignKey(StarSystem, on_delete=models.CASCADE, related_name="Belongs")

class Planet(Location):
    # othernames = TODO: figure out how to create a list of CharFields
    # TODO: add complex planet variety
    orbits = models.ForeignKey(Star, on_delete=models.CASCADE, related_name="Orbiting")

class Moon(Location):
    # TODO: add complex satellite variety ("Rocky", "Barren", "Icy")
    orbits = models.ForeignKey(Planet, on_delete=models.CASCADE, related_name="Orbiting")

class Station(Location):
    orbits = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="orbiter")
    large_berths = models.PositiveSmallIntegerField(default=1)
    medium_berths = models.PositiveSmallIntegerField(default=2)
    small_berths = models.PositiveSmallIntegerField(default=8)

