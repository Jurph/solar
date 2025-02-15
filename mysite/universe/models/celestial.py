from django.db import models
from django.utils.translation import gettext_lazy as _
from .base import Location

class Galaxy(Location):
    def save(self, *args, **kwargs):
        self.scale = self.Scale.GALAXY
        super().save(*args, **kwargs)

class StarSystem(Location):
    orbits = models.ForeignKey(
        Galaxy,
        on_delete=models.CASCADE,
        related_name='star_systems'
    )
    
    def save(self, *args, **kwargs):
        self.scale = self.Scale.STARSYSTEM
        super().save(*args, **kwargs)

class Star(Location):
    orbits = models.ForeignKey(
        StarSystem,
        on_delete=models.CASCADE,
        related_name='stars'
    )
    startype = models.CharField(max_length=10, default="G2V")
    starmagnitude = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=4.31
    )
    
    def save(self, *args, **kwargs):
        self.scale = self.Scale.STAR
        super().save(*args, **kwargs)

class Planet(Location):
    class PlanetType(models.TextChoices):
        MESOPLANET = 'MP', _('Mesoplanet')
        SILICATE = 'SI', _('Silicate')
        TERRESTRIAL = 'TE', _('Terrestrial')
        SUPEREARTH = 'SE', _('Super-earth')
        CTHONIAN = 'CT', _('Cthonian')
        ICEGIANT = 'IG', _('Ice Giant')
        GASGIANT = 'GG', _('Gas Giant')
        ASTEROIDBELT = 'AB', _('Asteroid Belt')

    orbits = models.ForeignKey(
        Star,
        on_delete=models.CASCADE,
        related_name='planets'
    )
    planettype = models.CharField(
        max_length=2,
        choices=PlanetType.choices,
        default=PlanetType.TERRESTRIAL
    )
    
    def save(self, *args, **kwargs):
        self.scale = self.Scale.PLANET
        super().save(*args, **kwargs)

class Moon(Location):
    orbits = models.ForeignKey(
        Planet,
        on_delete=models.CASCADE,
        related_name='moons'
    )
    
    def save(self, *args, **kwargs):
        self.scale = self.Scale.MOON
        super().save(*args, **kwargs)