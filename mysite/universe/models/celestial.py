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
    def from_dict(cls, data: dict) -> "ColorPalette":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            main_color=data.get("main_color", "#FFFFFF"),
            hex_colors=data.get("hex_colors", []),
            pattern_name=data.get("pattern_name", "UNIFORM"),
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
        UNIFORM = "UNIFORM", _("Uniform")
        BANDED = "BANDED", _("Banded")
        SPLOTCHED = "SPLOTCHED", _("Splotched")
        SWIRLED = "SWIRLED", _("Swirled")
        SPOTS = "SPOTS", _("Spots")
        STRIPED = "STRIPED", _("Striped")

    # Mass properties (consequences of type)
    mass_kg = models.FloatField(null=True, blank=True, help_text="Mass in kilograms")

    mass_solar = models.FloatField(
        null=True,
        blank=True,
        help_text="Mass in solar masses (calculated from mass_kg)",
    )

    # Radius properties (consequences of type)
    radius_km = models.FloatField(
        null=True, blank=True, help_text="Radius in kilometers"
    )

    radius_solar = models.FloatField(
        null=True,
        blank=True,
        help_text="Radius in solar radii (calculated from radius_km)",
    )

    # Density (can be calculated from mass/radius)
    density_kg_m3 = models.FloatField(
        null=True, blank=True, help_text="Density in kg/m³"
    )

    # Thermal properties
    albedo = models.FloatField(null=True, blank=True, help_text="Bond albedo (0.0-1.0)")

    equilibrium_temperature_k = models.FloatField(
        null=True,
        blank=True,
        help_text="Equilibrium temperature in Kelvin (calculated from star distance/albedo)",
    )

    # Orbital properties (for Planet and Moon, null for Star)
    orbital_distance_km = models.FloatField(
        null=True, blank=True, help_text="Semi-major axis in km (for moons)"
    )

    orbital_period_days = models.FloatField(
        null=True, blank=True, help_text="Orbital period in Earth days"
    )

    orbital_period_hours = models.FloatField(
        null=True, blank=True, help_text="Orbital period in hours (for moons)"
    )

    orbital_eccentricity = models.FloatField(
        null=True,
        blank=True,
        default=0.0,
        help_text="Orbital eccentricity (0.0=circular, 0.0-1.0=elliptical)",
    )

    orbital_inclination_deg = models.FloatField(
        null=True,
        blank=True,
        help_text="Orbital inclination in degrees (tilt relative to reference plane)",
    )

    rotation_period_hours = models.FloatField(
        null=True, blank=True, help_text="Rotation period (day length) in hours"
    )

    axial_tilt_deg = models.FloatField(
        null=True, blank=True, help_text="Axial tilt in degrees (rotation axis tilt)"
    )

    is_tidally_locked = models.BooleanField(
        default=False, help_text="Whether the body is tidally locked to its parent"
    )

    # Color palette: JSONField storing ColorPalette dataclass
    # Optional for now - concrete classes will generate this later
    color_palette = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="ColorPalette dataclass as JSON: {main_color, hex_colors, pattern_name}",
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

    def get_atmosphere(self):
        """
        Get the Atmosphere object for this body, if it exists.

        Returns:
            Atmosphere instance or None
        """
        from .physics import Atmosphere
        from django.contrib.contenttypes.models import ContentType

        try:
            content_type = ContentType.objects.get_for_model(self.__class__)
            return Atmosphere.objects.filter(
                content_type=content_type, object_id=self.pk
            ).first()
        except Exception:
            return None

    def get_min_safe_orbit_km(self) -> float:
        """
        Calculate minimum safe orbital altitude above surface.

        Rules:
        - If atmosphere exists: min_altitude = 1.5 * atmosphere_height_km (rounded to 10km)
        - If no atmosphere: min_altitude = radius_km * 0.01 (rounded up to 10km)

        Returns:
            Minimum safe orbit altitude in km (rounded to nearest 10km)
        """
        import math

        atmosphere = self.get_atmosphere()
        if atmosphere and atmosphere.atmosphere_height_km:
            min_alt = 1.5 * atmosphere.atmosphere_height_km
        elif self.radius_km:
            min_alt = self.radius_km * 0.01
        else:
            # Fallback: assume 100km minimum
            min_alt = 100.0

        # Round to nearest 10km
        return math.ceil(min_alt / 10.0) * 10.0

    def get_leo_band_altitude_km(self, lane_number: int = None) -> float:
        """
        Get a LEO (Low Earth Orbit) band altitude in 10km increments.

        Lanes are spaced 10km apart starting from min_safe_orbit.
        Lane numbers range from 1 to 50.

        Args:
            lane_number: Lane number (1-50). If None, randomly selects one.

        Returns:
            Altitude in km for the selected lane
        """
        import random

        min_alt = self.get_min_safe_orbit_km()

        if lane_number is None:
            lane_number = random.randint(1, 50)
        else:
            lane_number = max(1, min(50, lane_number))

        return min_alt + (lane_number * 10.0)

    def get_launch_apogee_km(self, target_circular_orbit_km: float) -> float:
        """
        Calculate launch apogee altitude (slightly above target circularization orbit).

        Args:
            target_circular_orbit_km: Target circular orbit altitude

        Returns:
            Launch apogee altitude (target + 10-50km buffer)
        """
        import random

        buffer = random.uniform(10.0, 50.0)
        apogee = target_circular_orbit_km + buffer

        # Ensure apogee is above atmosphere if one exists
        atmosphere = self.get_atmosphere()
        if atmosphere and atmosphere.atmosphere_height_km:
            min_apogee = atmosphere.atmosphere_height_km + 20.0  # Safety margin
            apogee = max(apogee, min_apogee)

        return round(apogee, 1)

    def get_safe_entry_angle_deg(self) -> float:
        """
        Calculate safe atmospheric entry angle based on atmosphere properties.

        Uses a simplified model based on:
        - Atmosphere height (affects entry interface)
        - Surface pressure (affects deceleration)
        - Scale height (affects density gradient)

        Typical safe entry angles: 5-10 degrees
        Too steep (>10°): excessive heating
        Too shallow (<5°): skip out of atmosphere

        Returns:
            Safe entry angle in degrees (5-10 range)
        """
        import random
        import math

        atmosphere = self.get_atmosphere()
        if not atmosphere or not atmosphere.atmosphere_height_km:
            # Airless body: entry angle less critical, use wider range
            return random.uniform(3.0, 8.0)

        # Base angle on atmospheric properties
        # Higher pressure = can handle steeper entry (more drag)
        # Higher scale height = more gradual density change = can handle steeper entry
        base_angle = 6.5  # Earth-like default

        if atmosphere.surface_pressure_bar:
            # Higher pressure allows steeper entry
            # Earth = 1.0 bar, Venus = 92 bar, Mars = 0.006 bar
            pressure_factor = min(
                1.0, math.log10(max(0.01, atmosphere.surface_pressure_bar) + 1.0) / 2.0
            )
            base_angle += pressure_factor * 2.0  # Add up to 2 degrees for high pressure

        if atmosphere.scale_height_km:
            # Higher scale height = more gradual = steeper entry possible
            # Earth = ~8.5km, Mars = ~11km
            scale_factor = min(1.0, (atmosphere.scale_height_km - 5.0) / 10.0)
            base_angle += scale_factor * 1.5  # Add up to 1.5 degrees

        # Add small random variation (±0.5 degrees)
        entry_angle = base_angle + random.uniform(-0.5, 0.5)

        # Clamp to safe range
        return max(5.0, min(10.0, entry_angle))

    def get_geostationary_altitude_km(self) -> Optional[float]:
        """
        Calculate the altitude of a geostationary orbit above the surface.

        A geostationary orbit has a period equal to the body's rotation period.
        Formula: r = (G·M·T² / 4π²)^(1/3), altitude = r − radius.

        Returns:
            Altitude in km above surface, or None if required data is missing.
        """
        import math

        if not (self.mass_kg and self.radius_km and self.rotation_period_hours):
            return None

        G = 6.674e-11  # m³ kg⁻¹ s⁻²
        M = self.mass_kg  # kg
        T = self.rotation_period_hours * 3600.0  # seconds

        r_meters = (G * M * T**2 / (4 * math.pi**2)) ** (1 / 3)
        r_km = r_meters / 1000.0
        altitude_km = r_km - self.radius_km

        return altitude_km if altitude_km > 0 else None

    def get_low_orbit_altitude_km(self) -> float:
        """
        Return a practical low-orbit altitude above the surface.

        Uses twice the minimum safe orbit altitude, giving clearance above
        the atmosphere and typical debris belts.

        Returns:
            Low-orbit altitude in km.
        """
        return self.get_min_safe_orbit_km() * 2.0


class Galaxy(Location):
    ## https://en.wikipedia.org/wiki/Galaxy#Types_and_morphology
    galaxies = [
        ("CD", "Supergiant Elliptical Type cD"),
        ("DW", "Dwarf"),
        ("E0", "Elliptical - Sphere"),
        ("E7", "Elliptical - Elongated"),
        ("IR", "Irregular Type i"),
        ("IT", "Irregular Type ii"),
        ("LN", "Lenticular"),
        ("SB", "Barred Spiral"),
        ("SH", "Elliptical Shell"),
        ("SP", "Spiral Arm"),
        ("SS", "Superluminous Spiral"),
        ("UD", "Ultra Diffuse"),
    ]
    sizes = [
        ("D", "dwarf"),
        ("S", "small"),
        ("M", "medium"),
        ("L", "large"),
        ("X", "extra large"),
        ("G", "supergiant"),
    ]
    galaxy_type = models.CharField(max_length=2, choices=galaxies, default="SP")
    galaxy_size = models.CharField(max_length=1, choices=sizes, default="L")
    orbits = None

    def save(self, *args, **kwargs):
        # Location.scale defaults to Scale.STATION; for Celestial subclasses we must
        # override that default if caller didn't explicitly supply a scale.
        if not self.scale or self.scale == Scale.STATION:
            self.scale = Scale.GALAXY
        super().save(*args, **kwargs)


class StarSystem(Location):
    """
    StarSystem represents a star system within a galaxy.

    Galactic coordinates (x, y, z) are stored in light-years relative to the
    galactic center. These enable:
    - Distance calculations between star systems
    - HYPERSPACE transit time calculations
    - Spatial visualization of the galaxy

    Coordinate system follows standard astronomical conventions:
    - Origin at galactic center
    - X-axis: direction toward galactic center from Sun's position
    - Y-axis: direction of galactic rotation
    - Z-axis: perpendicular to galactic plane (positive = north)
    """

    orbits = models.ForeignKey(
        Galaxy, on_delete=models.CASCADE, related_name="star_systems"
    )
    system_age_years = models.FloatField(
        null=True,
        blank=True,
        help_text="System age in years (derived from seed, shared by all bodies in system)",
    )
    galactic_x_ly = models.FloatField(
        null=True,
        blank=True,
        help_text="Galactic X coordinate in light-years (relative to galactic center)",
    )
    galactic_y_ly = models.FloatField(
        null=True,
        blank=True,
        help_text="Galactic Y coordinate in light-years (relative to galactic center)",
    )
    galactic_z_ly = models.FloatField(
        null=True,
        blank=True,
        help_text="Galactic Z coordinate in light-years (relative to galactic center, perpendicular to plane)",
    )

    def save(self, *args, **kwargs):
        # Location.scale defaults to Scale.STATION; for Celestial subclasses we must
        # override that default if caller didn't explicitly supply a scale.
        if not self.scale or self.scale == Scale.STATION:
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
        ("O", "O-Type Blue Supergiant"),
        ("B", "B-Type Blue Giant"),
        ("A", "A-Type White Star"),
        ("F", "F-Type White Star"),
        ("G", "G-Type Yellow Star"),
        ("K", "K-Type Yellow Star"),
        ("M", "M-Type Red Dwarf"),
        ("N", "M-Type Red Supergiant"),
    ]
    orbits = models.ForeignKey(
        StarSystem, on_delete=models.CASCADE, related_name="stars"
    )
    star_type = models.CharField(max_length=10, default="G2V")
    star_magnitude = models.DecimalField(max_digits=8, decimal_places=2, default=4.31)
    temperature_k = models.FloatField(
        null=True, blank=True, help_text="Surface temperature in Kelvin"
    )
    luminosity_solar = models.FloatField(
        null=True, blank=True, help_text="Luminosity in solar units (L☉)"
    )

    def save(self, *args, **kwargs):
        # Location.scale defaults to Scale.STATION; for Celestial subclasses we must
        # override that default if caller didn't explicitly supply a scale.
        if not self.scale or self.scale == Scale.STATION:
            self.scale = Scale.STAR
        super().save(*args, **kwargs)


class Planet(PhysicalBody):
    class planetType(models.TextChoices):
        MESOPLANET = "MP", _("Mesoplanet")
        SILICATE = "SI", _("Silicate")
        TERRESTRIAL = "TE", _("Terrestrial")
        SUPEREARTH = "SE", _("Super-earth")
        CTHONIAN = "CT", _("Cthonian")
        ICEGIANT = "IG", _("Ice Giant")
        GASGIANT = "GG", _("Gas Giant")
        ASTEROIDBELT = "AB", _("Asteroid Belt")

    orbits = models.ForeignKey(Star, on_delete=models.CASCADE, related_name="planets")
    planet_type = models.CharField(
        max_length=2, choices=planetType.choices, default=planetType.TERRESTRIAL
    )
    orbital_distance_au = models.FloatField(
        null=True, blank=True, help_text="Semi-major axis in AU"
    )

    def save(self, *args, **kwargs):
        # Location.scale defaults to Scale.STATION; for Celestial subclasses we must
        # override that default if caller didn't explicitly supply a scale.
        if not self.scale or self.scale == Scale.STATION:
            self.scale = Scale.PLANET
        super().save(*args, **kwargs)


class Moon(PhysicalBody):
    class MoonType(models.TextChoices):
        ROCKY = (
            "R",
            _("Rocky"),
        )  # e.g. Luna, Deimos, Phobos - no atmosphere to speak of, dry
        ICY = "I", _("Icy")  # e.g. Europa, Ganymede, Callisto
        ORGANIC = (
            "O",
            _("Organic"),
        )  # e.g. Titan, with a gaseous atmosphere and liquid water
        TERRESTRIAL = (
            "T",
            _("Terrestrial"),
        )  # e.g. "Earth-like" and therefore habitable; a special sub-class of "O"

    orbits = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="moons")

    moon_type = models.CharField(
        max_length=1,
        choices=MoonType.choices,
        default=MoonType.ROCKY,
        help_text="The primary composition/type of the moon",
    )

    def save(self, *args, **kwargs):
        # Location.scale defaults to Scale.STATION; for Celestial subclasses we must
        # override that default if caller didn't explicitly supply a scale.
        if not self.scale or self.scale == Scale.STATION:
            self.scale = Scale.MOON
        super().save(*args, **kwargs)
