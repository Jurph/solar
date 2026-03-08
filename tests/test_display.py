"""
Display helper function tests.

Tests formatting and calculation utilities for displaying
physical and astronomical data in the UI.
"""

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet
from mysite.universe.models.physics import Atmosphere
from mysite.universe.models.display import (
    format_number,
    format_distance_km,
    format_temperature_k,
    format_orbital_period_days,
    format_orbital_period_hours,
    format_rotation_period_hours,
    calculate_surface_gravity_ms2,
    format_surface_gravity,
    format_atmosphere_height,
    calculate_escape_velocity_ms,
    format_escape_velocity,
    calculate_orbital_velocity_ms,
    format_orbital_velocity,
    get_atmosphere_data,
    get_surface_composition_hint,
)


class TestDisplayFormatters(TestCase):
    """Test display formatting functions."""

    def test_formatters_handle_none(self):
        assert format_number(None) == "N/A"
        assert format_distance_km(None) == "N/A"
        assert format_temperature_k(None) == "N/A"
        assert format_orbital_period_days(None) == "N/A"
        assert format_orbital_period_hours(None) == "N/A"
        assert format_rotation_period_hours(None) == "N/A"
        assert format_surface_gravity(None) == "N/A"
        assert format_atmosphere_height(None) == "N/A"
        assert format_escape_velocity(None) == "N/A"
        assert format_orbital_velocity(None) == "N/A"

    def test_format_number_si_prefixes(self):
        assert format_number(999) == "999.00"
        assert format_number(1_000) == "1.00 kg"
        assert format_number(1_000_000) == "1.00 Mg"
        assert format_number(1e9) == "1.00 Gg"
        assert format_number(1e12) == "1.00 Tg"
        assert format_number(1e15) == "1.00 Pg"
        assert format_number(1e18) == "1.00 Eg"
        assert format_number(1e21) == "1.00 Zg"
        assert format_number(1e24) == "1.00 Yg"

    def test_format_distance_km_thresholds(self):
        assert format_distance_km(999) == "999.00 km"
        assert format_distance_km(1_000) == "1.00 km"
        assert format_distance_km(1_000_000) == "1.00 Mm"
        assert format_distance_km(1_000_000_000) == "1.00 Gm"

    def test_temperature_and_period_formatters(self):
        assert format_temperature_k(273.15) == "273 K (0°C)"
        assert "days (" in format_orbital_period_days(365.25)
        assert "hours (" in format_orbital_period_hours(24.0)
        assert "hours (" in format_rotation_period_hours(24.0)
        assert format_atmosphere_height(100.0) == "100.00 km"


class TestDisplayPhysicsCalculations(TestCase):
    """Test physics calculation functions."""

    def test_physics_calculations_return_none_when_missing(self):
        assert calculate_surface_gravity_ms2(None, 1.0) is None
        assert calculate_surface_gravity_ms2(1.0, None) is None
        assert calculate_escape_velocity_ms(None, 1.0) is None
        assert calculate_escape_velocity_ms(1.0, None) is None
        assert calculate_orbital_velocity_ms(None, 1.0) is None
        assert calculate_orbital_velocity_ms(1.0, None) is None

    def test_earth_like_gravity_and_escape_velocity_are_reasonable(self):
        g = calculate_surface_gravity_ms2(5.972e24, 6371)
        assert g is not None
        # within ~5% of Earth g (diagnostic but not overly strict)
        assert abs(g - 9.80665) / 9.80665 < 0.05
        assert "m/s²" in format_surface_gravity(g)

        v = calculate_escape_velocity_ms(5.972e24, 6371)
        assert v is not None
        assert 10_000 <= v <= 13_000
        assert "km/s" in format_escape_velocity(v)

        vo = calculate_orbital_velocity_ms(5.972e24, 6371)
        assert vo is not None
        assert 7_000 <= vo <= 9_000
        assert "km/s" in format_orbital_velocity(vo)


class TestDisplayAtmosphereData(TestCase):
    """Test atmosphere data retrieval."""

    def test_get_atmosphere_data_returns_defaults_when_missing(self):
        galaxy = Galaxy.objects.create(name="G", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(name="S", orbits=galaxy)
        star = Star.objects.create(name="Star", orbits=system, star_type="G")
        planet = Planet.objects.create(
            name="P", orbits=star, planet_type="TE", orbital_distance_au=1.0
        )

        data = get_atmosphere_data(planet, Planet)
        assert data["has_atmosphere"] is False
        assert data["atmosphere_type"] is None

    def test_get_atmosphere_data_returns_values_when_present(self):
        galaxy = Galaxy.objects.create(name="G2", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(name="S2", orbits=galaxy)
        star = Star.objects.create(name="Star2", orbits=system, star_type="G")
        planet = Planet.objects.create(
            name="P2", orbits=star, planet_type="TE", orbital_distance_au=1.0
        )

        ct = ContentType.objects.get_for_model(Planet)
        Atmosphere.objects.create(
            content_type=ct,
            object_id=planet.id,
            atmosphere_type=Atmosphere.AtmosphereType.N2_O2,
            atmosphere_height_km=100.0,
            surface_pressure_bar=1.0,
            scale_height_km=8.0,
        )

        data = get_atmosphere_data(planet, Planet)
        assert data["has_atmosphere"] is True
        assert data["atmosphere_type"] == Atmosphere.AtmosphereType.N2_O2
        assert data["atmosphere_height_km"] == 100.0

    def test_atmosphere_str_includes_type_and_parent_body(self):
        """Atmosphere.__str__ returns a readable representation (physics.py line 57)."""
        galaxy = Galaxy.objects.create(name="G3", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(name="S3", orbits=galaxy)
        star = Star.objects.create(name="Star3", orbits=system, star_type="G")
        planet = Planet.objects.create(
            name="P3", orbits=star, planet_type="TE", orbital_distance_au=1.0
        )
        ct = ContentType.objects.get_for_model(Planet)
        atm = Atmosphere.objects.create(
            content_type=ct,
            object_id=planet.id,
            atmosphere_type=Atmosphere.AtmosphereType.CO2_THIN,
        )
        result = str(atm)
        self.assertIn("CO2_THIN", result)
        self.assertIn("P3", result)


class TestDisplaySurfaceComposition(TestCase):
    """Test surface composition hint generation."""

    def test_surface_composition_hints(self):
        assert get_surface_composition_hint(planet_type="GG") == "No solid surface"
        assert get_surface_composition_hint(planet_type="AB") == "Rocky fragments"
        assert get_surface_composition_hint(planet_type="CT") == "Exposed rocky core"
        assert get_surface_composition_hint(planet_type="MP") == "Small rocky body"
        assert (
            get_surface_composition_hint(planet_type="TE", density_kg_m3=6000)
            == "Dense rocky surface"
        )
        assert (
            get_surface_composition_hint(planet_type="TE", density_kg_m3=4000)
            == "Rocky surface"
        )
        assert (
            get_surface_composition_hint(planet_type="TE", density_kg_m3=2000)
            == "Light rocky/icy surface"
        )
        assert get_surface_composition_hint(planet_type="TE") == "Rocky surface"
        assert get_surface_composition_hint(moon_type="I") == "Ice/water surface"
        assert (
            get_surface_composition_hint(moon_type="O", density_kg_m3=1500)
            == "Ice/water surface with organic compounds"
        )
        assert (
            get_surface_composition_hint(moon_type="O", density_kg_m3=3000)
            == "Organic-rich surface"
        )
        assert (
            get_surface_composition_hint(moon_type="T")
            == "Earth-like surface (potentially habitable)"
        )
        assert (
            get_surface_composition_hint(moon_type="R", density_kg_m3=4500)
            == "Dense rocky surface"
        )
        assert (
            get_surface_composition_hint(moon_type="R", density_kg_m3=3500)
            == "Rocky surface"
        )
        assert get_surface_composition_hint(moon_type="R") == "Rocky surface"
        assert get_surface_composition_hint() is None
