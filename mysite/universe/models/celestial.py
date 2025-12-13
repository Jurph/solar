from dataclasses import dataclass, asdict
from typing import List, Optional
from django.db import models
from django.utils.translation import gettext_lazy as _
from .base import Location
from .scale import Scale  # Use the enhanced Scale class


@dataclass
class ColorPalette:
    """
    Dataclass for storing color palette information.
    Used by Star, Planet, and Moon for visual rendering.
    """
    main_color: str  # Primary hex color (e.g., "#FF0000")
    hex_colors: List[str]  # List of hex color strings for gradients/patterns
    pattern_name: str  # Pattern type from PatternType enum
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ColorPalette':
        """Create from dictionary (JSON deserialization)."""
        return cls(
            main_color=data.get('main_color', '#FFFFFF'),
            hex_colors=data.get('hex_colors', []),
            pattern_name=data.get('pattern_name', 'UNIFORM')
        )


class Celestial(Location):
    """
    Abstract base model for all celestial bodies (Star, Planet, Moon).
    This is the common parent that provides basic celestial properties.
    """
    
    class Meta:
        abstract = True


class PhysicalBody(Celestial):
    """
    Abstract base model for celestial bodies with physical properties.
    Inherits from Celestial, which inherits from Location.
    Provides mass, radius, and color palette properties.
    This is the level shared by Star, Planet, and Moon (through OrbitalBody).
    """
    
    class PatternType(models.TextChoices):
        UNIFORM = 'UNIFORM', _('Uniform')
        BANDED = 'BANDED', _('Banded')
        SPLOTCHED = 'SPLOTCHED', _('Splotched')
        SWIRLED = 'SWIRLED', _('Swirled')
        SPOTS = 'SPOTS', _('Spots')
        STRIPED = 'STRIPED', _('Striped')
    
    # Mass properties (consequences of type)
    mass_kg = models.FloatField(
        null=True,
        blank=True,
        help_text="Mass in kilograms"
    )
    
    mass_solar = models.FloatField(
        null=True,
        blank=True,
        help_text="Mass in solar masses (calculated from mass_kg)"
    )
    
    # Radius properties (consequences of type)
    radius_km = models.FloatField(
        null=True,
        blank=True,
        help_text="Radius in kilometers"
    )
    
    radius_solar = models.FloatField(
        null=True,
        blank=True,
        help_text="Radius in solar radii (calculated from radius_km)"
    )
    
    # Density (can be calculated from mass/radius)
    density_kg_m3 = models.FloatField(
        null=True,
        blank=True,
        help_text="Density in kg/m³"
    )
    
    # Thermal properties
    albedo = models.FloatField(
        null=True,
        blank=True,
        help_text="Bond albedo (0.0-1.0)"
    )
    
    equilibrium_temperature_k = models.FloatField(
        null=True,
        blank=True,
        help_text="Equilibrium temperature in Kelvin (calculated from star distance/albedo)"
    )
    
    # Orbital properties (for Planet and Moon, null for Star)
    orbital_distance_km = models.FloatField(
        null=True,
        blank=True,
        help_text="Semi-major axis in km (for moons)"
    )
    
    orbital_period_days = models.FloatField(
        null=True,
        blank=True,
        help_text="Orbital period in Earth days"
    )
    
    orbital_period_hours = models.FloatField(
        null=True,
        blank=True,
        help_text="Orbital period in hours (for moons)"
    )
    
    orbital_eccentricity = models.FloatField(
        null=True,
        blank=True,
        default=0.0,
        help_text="Orbital eccentricity (0.0=circular, 0.0-1.0=elliptical)"
    )
    
    orbital_inclination_deg = models.FloatField(
        null=True,
        blank=True,
        help_text="Orbital inclination in degrees (tilt relative to reference plane)"
    )
    
    rotation_period_hours = models.FloatField(
        null=True,
        blank=True,
        help_text="Rotation period (day length) in hours"
    )
    
    axial_tilt_deg = models.FloatField(
        null=True,
        blank=True,
        help_text="Axial tilt in degrees (rotation axis tilt)"
    )
    
    is_tidally_locked = models.BooleanField(
        default=False,
        help_text="Whether the body is tidally locked to its parent"
    )
    
    # Color palette: JSONField storing ColorPalette dataclass
    # Optional for now - concrete classes will generate this later
    color_palette = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="ColorPalette dataclass as JSON: {main_color, hex_colors, pattern_name}"
    )
    
    class Meta:
        abstract = True
    
    def calculate_mass_solar(self):
        """Calculate mass in solar masses from mass_kg."""
        if self.mass_kg is None:
            return None
        # Solar mass = 1.989 × 10^30 kg
        SOLAR_MASS_KG = 1.989e30
        return self.mass_kg / SOLAR_MASS_KG
    
    def calculate_radius_solar(self):
        """Calculate radius in solar radii from radius_km."""
        if self.radius_km is None:
            return None
        # Solar radius = 696,340 km
        SOLAR_RADIUS_KM = 696340.0
        return self.radius_km / SOLAR_RADIUS_KM
    
    def get_color_palette(self) -> Optional[ColorPalette]:
        """Get ColorPalette dataclass from JSONField."""
        if not self.color_palette:
            return None
        return ColorPalette.from_dict(self.color_palette)
    
    def set_color_palette(self, palette: ColorPalette):
        """Store ColorPalette dataclass as JSONField."""
        self.color_palette = palette.to_dict()
    
    def save(self, *args, **kwargs):
        """Auto-calculate alternative units on save."""
        if self.mass_kg is not None and self.mass_solar is None:
            self.mass_solar = self.calculate_mass_solar()
        if self.radius_km is not None and self.radius_solar is None:
            self.radius_solar = self.calculate_radius_solar()
        super().save(*args, **kwargs)

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
    system_age_years = models.FloatField(
        null=True,
        blank=True,
        help_text="System age in years (derived from seed, shared by all bodies in system)"
    )

    def save(self, *args, **kwargs):
        if not self.scale:
            self.scale = Scale.STARSYSTEM
        super().save(*args, **kwargs)

class Star(PhysicalBody):
    """
    Star model inherits from PhysicalBody → Celestial → Location.
    Mass and radius are consequences of star_type.
    Color palette and pattern are generated from star properties.
    """
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
    temperature_k = models.FloatField(
        null=True,
        blank=True,
        help_text="Surface temperature in Kelvin"
    )

    def save(self, *args, **kwargs):
        if not self.scale:
            self.scale = Scale.STAR
        super().save(*args, **kwargs)

class Planet(PhysicalBody):
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
    orbital_distance_au = models.FloatField(
        null=True,
        blank=True,
        help_text="Semi-major axis in AU"
    )

    def save(self, *args, **kwargs):
        if not self.scale:
            self.scale = Scale.PLANET
        super().save(*args, **kwargs)

class Moon(PhysicalBody):
    class MoonType(models.TextChoices):
        ROCKY = 'R', _('Rocky')     # e.g. Luna, Deimos, Phobos - no atmosphere to speak of, dry 
        ICY = 'I', _('Icy')       # e.g. Europa, Ganymede, Callisto 
        ORGANIC = 'O', _('Organic')     # e.g. Titan, with a gaseous atmosphere and liquid water 
        TERRESTRIAL = 'T', _('Terrestrial') # e.g. "Earth-like" and therefore habitable; a special sub-class of "O" 
    
    orbits = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='moons'
    )
    
    moon_type = models.CharField(
        max_length=1,
        choices=MoonType.choices,
        default=MoonType.ROCKY,
        help_text="The primary composition/type of the moon"        
    )

    def save(self, *args, **kwargs):
        if not self.scale:
            self.scale = Scale.MOON
        super().save(*args, **kwargs)