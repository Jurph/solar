from django.db import models
from django.utils.translation import gettext_lazy as _
from .base import Location
from .scale import Scale  # Use the enhanced Scale class

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
    galaxy_type = models.CharField(max_length=2, choices=galaxies, default='SP')
    galaxy_size = models.CharField(max_length=1, choices=sizes, default='L')
    orbits = None

    def save(self, *args, **kwargs):
        if not self.scale:  # If scale is not already set, then assign Galaxy scale.
            self.scale = Scale.GALAXY
        super().save(*args, **kwargs)

class StarSystem(Location):
    orbits = models.ForeignKey(
        Galaxy,
        on_delete=models.CASCADE,
        related_name='star_systems'
    )

    def save(self, *args, **kwargs):
        if not self.scale:
            self.scale = Scale.STARSYSTEM
        super().save(*args, **kwargs)

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
    orbits = models.ForeignKey(
        StarSystem,
        on_delete=models.CASCADE,
        related_name='stars'
    )
    star_type = models.CharField(max_length=10, default="G2V")
    star_magnitude = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=4.31
    )

    def save(self, *args, **kwargs):
        if not self.scale:
            self.scale = Scale.STAR
        super().save(*args, **kwargs)

class Planet(Location):
    class planetType(models.TextChoices):
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
    planet_type = models.CharField(
        max_length=2,
        choices=planetType.choices,
        default=planetType.TERRESTRIAL
    )

    def save(self, *args, **kwargs):
        if not self.scale:
            self.scale = Scale.PLANET
        super().save(*args, **kwargs)

class Moon(Location):
    VARIETIES = [
        ('R', 'Rocky'),     # e.g. Luna, Deimos, Phobos - no atmosphere to speak of, dry 
        ('I', 'Icy'),       # e.g. Europa, Ganymede, Callisto 
        ('O', 'Organic'),     # e.g. Titan, with a gaseous atmosphere and liquid water 
        ('T', 'Terrestrial') # e.g. "Earth-like" and therefore habitable; a special sub-class of "O" 
    ]
    orbits = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='moons'
    )
    
    variety = models.CharField(
        max_length=1,
        choices=VARIETIES,
        default='R',
        help_text="The primary composition of the moon"        
    )

    def save(self, *args, **kwargs):
        if not self.scale:
            self.scale = Scale.MOON
        super().save(*args, **kwargs)