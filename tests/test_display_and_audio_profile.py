from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from mysite.universe.models.actor import Actor, Controller, Pilot, Satellite
from mysite.universe.models.audio_profile import AudioProfile
from mysite.universe.models.base import Location
from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet
from mysite.universe.models.physics import Atmosphere
from mysite.universe.models.scale import Scale
from mysite.universe.models.ship import Ship
from mysite.universe.models.station import Station
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


class TestDisplayHelpers(TestCase):
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

    def test_get_atmosphere_data_returns_defaults_when_missing(self):
        galaxy = Galaxy.objects.create(name="G", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(name="S", orbits=galaxy)
        star = Star.objects.create(name="Star", orbits=system, star_type="G")
        planet = Planet.objects.create(name="P", orbits=star, planet_type="TE", orbital_distance_au=1.0)

        data = get_atmosphere_data(planet, Planet)
        assert data["has_atmosphere"] is False
        assert data["atmosphere_type"] is None

    def test_get_atmosphere_data_returns_values_when_present(self):
        galaxy = Galaxy.objects.create(name="G2", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(name="S2", orbits=galaxy)
        star = Star.objects.create(name="Star2", orbits=system, star_type="G")
        planet = Planet.objects.create(name="P2", orbits=star, planet_type="TE", orbital_distance_au=1.0)

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

    def test_surface_composition_hints(self):
        assert get_surface_composition_hint(planet_type="GG") == "No solid surface"
        assert get_surface_composition_hint(planet_type="AB") == "Rocky fragments"
        assert get_surface_composition_hint(planet_type="CT") == "Exposed rocky core"
        assert get_surface_composition_hint(planet_type="MP") == "Small rocky body"
        assert get_surface_composition_hint(planet_type="TE", density_kg_m3=6000) == "Dense rocky surface"
        assert get_surface_composition_hint(planet_type="TE", density_kg_m3=4000) == "Rocky surface"
        assert get_surface_composition_hint(planet_type="TE", density_kg_m3=2000) == "Light rocky/icy surface"
        assert get_surface_composition_hint(planet_type="TE") == "Rocky surface"
        assert get_surface_composition_hint(moon_type="I") == "Ice/water surface"
        assert get_surface_composition_hint(moon_type="O", density_kg_m3=1500) == "Ice/water surface with organic compounds"
        assert get_surface_composition_hint(moon_type="O", density_kg_m3=3000) == "Organic-rich surface"
        assert get_surface_composition_hint(moon_type="T") == "Earth-like surface (potentially habitable)"
        assert get_surface_composition_hint(moon_type="R", density_kg_m3=4500) == "Dense rocky surface"
        assert get_surface_composition_hint(moon_type="R", density_kg_m3=3500) == "Rocky surface"
        assert get_surface_composition_hint(moon_type="R") == "Rocky surface"
        assert get_surface_composition_hint() is None


class TestAudioProfileDefaults(TestCase):
    def setUp(self):
        self.loc = Location.objects.create(name="Dock", scale=Scale.STATION)

    def test_create_default_for_satellite(self):
        sat = Satellite.create(name="Test Navsat")
        profile = AudioProfile.create_default_for_actor(sat)
        assert profile.actor == sat
        assert profile.params["static"]["intensity"] == 0.0
        assert profile.params["room_tone"]["enabled"] is False

    def test_create_default_for_controller(self):
        controller = Controller.create(name="Dock Control", location=self.loc)
        profile = AudioProfile.create_default_for_actor(controller)
        assert profile.params["room_tone"]["reverb_room_size_hint"] == "large"
        assert profile.params["room_tone"]["engine_rumble_intensity"] == 0.0
        assert profile.params["static"]["intensity"] == 0.1

    def test_create_default_for_pilot_ship_size_influences_static(self):
        # small ship => lower static, higher rumble freq
        small_ship = Ship.objects.create(name="S", current_location=self.loc, size=Ship.Size.SMALL)
        pilot_small = Pilot.create(name="Pilot S", ship=small_ship)
        profile_small = AudioProfile.create_default_for_actor(pilot_small)
        assert profile_small.params["static"]["intensity"] == 0.03
        assert profile_small.params["room_tone"]["engine_rumble_base_freq_hz"] == 80.0

        # large ship => higher static, lower rumble freq
        large_ship = Ship.objects.create(name="L", current_location=self.loc, size=Ship.Size.LARGE)
        pilot_large = Pilot.create(name="Pilot L", ship=large_ship)
        profile_large = AudioProfile.create_default_for_actor(pilot_large)
        assert profile_large.params["static"]["intensity"] == 0.08
        assert profile_large.params["room_tone"]["engine_rumble_base_freq_hz"] == 40.0

        # medium ship defaults are stable
        medium_ship = Ship.objects.create(name="M", current_location=self.loc, size=Ship.Size.MEDIUM)
        pilot_medium = Pilot.create(name="Pilot M", ship=medium_ship)
        profile_medium = AudioProfile.create_default_for_actor(pilot_medium)
        assert profile_medium.params["static"]["intensity"] == 0.05
        assert profile_medium.params["room_tone"]["engine_rumble_base_freq_hz"] == 60.0

    def test_create_default_for_unknown_actor_type_uses_minimal(self):
        actor = Actor.objects.create(name="Mystery")
        profile = AudioProfile.create_default_for_actor(actor)
        assert profile.params["room_tone"]["enabled"] is False
        assert profile.params["static"]["intensity"] == 0.0

    def test_audio_profile_param_accessors(self):
        sat = Satellite.create(name="Accessor Sat")
        profile = AudioProfile.create_default_for_actor(sat)
        assert isinstance(profile.get_room_tone_params(), dict)
        assert isinstance(profile.get_static_params(), dict)
        assert isinstance(profile.get_quindar_params(), dict)
        assert isinstance(profile.get_voice_params(), dict)

    def test_audio_profile_str_includes_actor_name(self):
        sat = Satellite.create(name="Stringy Sat")
        profile = AudioProfile.create_default_for_actor(sat)
        assert "Stringy Sat" in str(profile)

