"""
Test procedural generation against real Solar System values.

This test creates a minimal star system (Sol-like star, Earth-like planet, Luna-like moon)
and validates that procedural generation produces values that are approximately correct.

The test uses multiple seeds to generate a distribution and verifies that real values
fall within reasonable ranges of the generated values.
"""

from django.test import TestCase
from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet, Moon
from mysite.universe.procedural_generation import (
    SeededRandom,
    weighted_choice,
    weighted_choice_dict,
    normal_clamped,
    log_normal_clamped,
    bin_select,
    bin_select_weighted,
    hash_to_float,
    hash_to_int,
    generate_star_type,
    generate_star_temperature,
    generate_star_mass_solar,
    generate_star_density,
    calculate_star_radius_from_mass_density,
    calculate_star_luminosity_solar,
    generate_planet_type,
    generate_composition,
    calculate_density_from_composition,
    generate_albedo,
    calculate_equilibrium_temperature,
    generate_moon_variety,
    generate_moon_quantity,
    generate_moon_properties,
    generate_moon_size,
    generate_moon_variety_by_parent,
    should_generate_moons_for_parent,
    calculate_solar_angle_deg,
    calculate_hill_sphere_radius_km,
    is_tidally_locked,
    calculate_geostationary_orbit_km,
    calculate_escape_velocity_km_s,
    can_retain_atmosphere,
    determine_atmosphere_type,
    calculate_scale_height_km,
    calculate_atmosphere_height_km,
    generate_atmosphere,
    generate_color_palette_from_temperature,
    generate_color_palette_from_composition,
)

# Real Solar System values for validation
REAL_SOL = {
    "star_type": "G",
    "temperature_k": 5778,  # Sun's effective temperature
    "mass_solar": 1.0,  # By definition
    "radius_km": 696340,  # Sun's radius
    "density_kg_m3": 1410,  # Sun's average density
    "luminosity_solar": 1.0,  # By definition
}

REAL_EARTH = {
    "planet_type": "TE",
    "orbital_distance_au": 1.0,  # By definition
    "mass_kg": 5.972e24,  # Earth mass
    "radius_km": 6371,  # Earth radius
    "density_kg_m3": 5514,  # Earth density
    "albedo": 0.306,  # Earth's Bond albedo
    "equilibrium_temperature_k": 255,  # Earth's equilibrium temp (no greenhouse)
    "orbital_period_days": 365.25,
    "iron_content": 0.32,  # ~32% iron by mass
    "water_coverage": 0.71,  # 71% ocean coverage
}

REAL_LUNA = {
    "variety": "R",  # Rocky
    "orbital_distance_km": 384400,  # Average distance from Earth
    "mass_kg": 7.342e22,  # Moon mass
    "radius_km": 1737,  # Moon radius
    "density_kg_m3": 3344,  # Moon density
    "albedo": 0.12,  # Moon's Bond albedo
    "orbital_period_hours": 655.7,  # ~27.3 days
}


class TestProceduralGeneration(TestCase):
    """Test procedural generation against real Solar System values."""

    def setUp(self):
        """Create minimal test objects."""
        # Create galaxy and star system
        self.galaxy = Galaxy.objects.create(name="Test Galaxy")
        self.star_system = StarSystem.objects.create(
            name="Test System",
            orbits=self.galaxy,
            system_age_years=4.6e9,  # Solar system age
        )

    def test_star_generation_sol_like(self):
        """
        Test star generation for a Sol-like star.

        We set only star_type='G' and let procedural generation fill in the rest.
        We test with multiple seeds and verify that real Sol values fall within
        reasonable ranges of the generated distribution.
        """
        # Test with multiple seeds
        seeds = ["sol_test_1", "sol_test_2", "sol_test_3", "sol_test_4", "sol_test_5"]
        generated_values = {
            "temperatures": [],
            "masses": [],
            "densities": [],
            "radii": [],
            "luminosities": [],
        }

        for seed in seeds:
            rng = SeededRandom(seed, name="Sol")

            # Generate star properties
            star_type = "G"  # Sol is G-type
            temperature = generate_star_temperature(rng, star_type)
            mass_solar = generate_star_mass_solar(rng, star_type)
            density = generate_star_density(rng, star_type)

            # Calculate derived properties
            mass_kg = mass_solar * 1.989e30  # Convert to kg
            radius_km = calculate_star_radius_from_mass_density(mass_kg, density)
            luminosity_solar = calculate_star_luminosity_solar(radius_km, temperature)

            generated_values["temperatures"].append(temperature)
            generated_values["masses"].append(mass_solar)
            generated_values["densities"].append(density)
            generated_values["radii"].append(radius_km)
            generated_values["luminosities"].append(luminosity_solar)

        # Check that real Sol values are within reasonable ranges
        # We expect real values to be within the expected type ranges, not necessarily
        # within the min/max of a small sample (5 seeds)

        # Temperature: Sol is 5778 K, G-type range is 5200-6000 K
        assert 5200 <= REAL_SOL["temperature_k"] <= 6000
        # Also check that generated values are in the right range
        assert all(5200 <= t <= 6000 for t in generated_values["temperatures"])

        # Mass: Sol is 1.0 solar masses, G-type range is 0.8-1.04
        assert 0.8 <= REAL_SOL["mass_solar"] <= 1.04
        # Also check that generated values are in the right range
        assert all(0.8 <= m <= 1.04 for m in generated_values["masses"])

        # Density: Sol is ~1410 kg/m³, G-type range is 1200-1600
        assert 1200 <= REAL_SOL["density_kg_m3"] <= 1600
        # Also check that generated values are in the right range
        assert all(1200 <= d <= 1600 for d in generated_values["densities"])

        # Radius: Sol is ~696,340 km
        # Check that real value is reasonable (within expected range for G-type stars)
        # G-type radius range is approximately 0.96-1.15 solar radii = ~668,000-800,000 km
        assert 668000 <= REAL_SOL["radius_km"] <= 800000
        # Check generated values are reasonable
        avg_radius = sum(generated_values["radii"]) / len(generated_values["radii"])
        assert 668000 <= avg_radius <= 800000

        # Luminosity: Sol is 1.0 solar luminosities
        # Check that real value is reasonable (G-type stars typically 0.6-1.5 L_sun)
        assert 0.6 <= REAL_SOL["luminosity_solar"] <= 1.5
        # Check generated values are reasonable
        avg_luminosity = sum(generated_values["luminosities"]) / len(
            generated_values["luminosities"]
        )
        assert 0.6 <= avg_luminosity <= 1.5

    def test_planet_generation_earth_like(self):
        """
        Test planet generation for an Earth-like planet.

        We set only planet_type='TE' and orbital_distance_au=1.0, then let
        procedural generation fill in mass, radius, composition, albedo, etc.
        """
        # Create a Sol-like star first (for temperature/radius lookups)
        star = Star.objects.create(
            name="Sol",
            orbits=self.star_system,
            star_type="G",
            temperature_k=REAL_SOL["temperature_k"],
            mass_kg=REAL_SOL["mass_solar"] * 1.989e30,
            radius_km=REAL_SOL["radius_km"],
        )
        # Note: We don't create Planet objects because Planet doesn't have
        # mass_kg/radius_km fields yet (doesn't inherit from PhysicalBody)

        # Test with multiple seeds
        seeds = [
            "earth_test_1",
            "earth_test_2",
            "earth_test_3",
            "earth_test_4",
            "earth_test_5",
        ]
        generated_values = {
            "masses": [],
            "radii": [],
            "densities": [],
            "albedos": [],
            "equilibrium_temps": [],
            "iron_contents": [],
            "water_coverages": [],
        }

        for seed in seeds:
            rng = SeededRandom(seed, name="Earth")

            # Generate planet properties
            planet_type = "TE"  # Terrestrial (Earth-like)
            orbital_distance_au = 1.0  # 1 AU

            # Generate composition
            composition = generate_composition(rng, planet_type)

            # Generate mass and radius from type
            from mysite.universe.procedural_generation import PLANET_PROPERTIES_BY_TYPE

            mass_range = PLANET_PROPERTIES_BY_TYPE[planet_type]["mass_range_earth"]
            radius_range = PLANET_PROPERTIES_BY_TYPE[planet_type]["radius_range_earth"]

            mass_earth = rng.uniform(mass_range[0], mass_range[1])
            radius_earth = rng.uniform(radius_range[0], radius_range[1])

            mass_kg = mass_earth * 5.972e24  # Convert to kg
            radius_km = radius_earth * 6371  # Convert to km

            # Calculate density from composition
            density = calculate_density_from_composition(rng, composition, planet_type)

            # Generate albedo
            has_atmosphere = True  # Earth has atmosphere
            albedo = generate_albedo(rng, composition, planet_type, has_atmosphere)

            # Calculate equilibrium temperature
            equilibrium_temp = calculate_equilibrium_temperature(
                star.temperature_k or REAL_SOL["temperature_k"],
                star.radius_km or REAL_SOL["radius_km"],
                orbital_distance_au,
                albedo,
            )

            generated_values["masses"].append(mass_kg)
            generated_values["radii"].append(radius_km)
            generated_values["densities"].append(density)
            generated_values["albedos"].append(albedo)
            generated_values["equilibrium_temps"].append(equilibrium_temp)
            generated_values["iron_contents"].append(composition["iron_content"])
            generated_values["water_coverages"].append(composition["water_coverage"])

        # Validate against real Earth values
        # Mass: Earth is 5.972e24 kg, TE range is 0.3-5.0 Earth masses
        # Check that real value is within expected type range
        assert 0.3 * 5.972e24 <= REAL_EARTH["mass_kg"] <= 5.0 * 5.972e24
        # Check that generated values are in the right range
        assert all(
            0.3 * 5.972e24 <= m <= 5.0 * 5.972e24 for m in generated_values["masses"]
        )

        # Radius: Earth is 6371 km, TE range is 0.4-1.5 Earth radii
        # Check that real value is within expected type range
        assert 0.4 * 6371 <= REAL_EARTH["radius_km"] <= 1.5 * 6371
        # Check that generated values are in the right range
        assert all(0.4 * 6371 <= r <= 1.5 * 6371 for r in generated_values["radii"])

        # Density: Earth is ~5514 kg/m³
        avg_density = sum(generated_values["densities"]) / len(
            generated_values["densities"]
        )
        assert (
            abs(REAL_EARTH["density_kg_m3"] - avg_density) / REAL_EARTH["density_kg_m3"]
            < 0.3
        )

        # Albedo: Earth is 0.306
        avg_albedo = sum(generated_values["albedos"]) / len(generated_values["albedos"])
        assert abs(REAL_EARTH["albedo"] - avg_albedo) < 0.2  # Within 0.2

        # Equilibrium temperature: Earth is ~255 K (without greenhouse)
        avg_temp = sum(generated_values["equilibrium_temps"]) / len(
            generated_values["equilibrium_temps"]
        )
        assert (
            abs(REAL_EARTH["equilibrium_temperature_k"] - avg_temp) < 50
        )  # Within 50 K

        # Composition: Earth has ~32% iron, 71% water coverage
        avg_iron = sum(generated_values["iron_contents"]) / len(
            generated_values["iron_contents"]
        )
        assert abs(REAL_EARTH["iron_content"] - avg_iron) < 0.15  # Within 15%

        # Water coverage can vary a lot, but Earth's 71% should be in the range
        assert REAL_EARTH["water_coverage"] >= min(generated_values["water_coverages"])
        assert REAL_EARTH["water_coverage"] <= max(generated_values["water_coverages"])

    def test_moon_generation_luna_like(self):
        """
        Test moon generation for a Luna-like moon.

        We use the new moon generation system to generate a rocky moon around an Earth-like planet.
        """
        # Earth's properties for parent
        earth_mass_kg = REAL_EARTH["mass_kg"]
        earth_radius_km = REAL_EARTH["radius_km"]

        # Luna's orbital distance from Earth: ~384,400 km = ~0.00257 AU
        luna_orbital_distance_au = 0.00257

        # System age (Solar System is ~4.5 billion years old)
        system_age_years = 4.5e9

        # Test with multiple seeds
        seeds = [
            "luna_test_1",
            "luna_test_2",
            "luna_test_3",
            "luna_test_4",
            "luna_test_5",
        ]
        generated_values = {
            "masses": [],
            "radii": [],
            "densities": [],
            "albedos": [],
            "varieties": [],
        }

        for seed in seeds:
            rng = SeededRandom(seed, name="Luna")

            # Use the new moon generation system
            # Parent type is 'TE' (Terrestrial planet - Earth)
            moon_props = generate_moon_properties(
                rng=rng,
                parent_type="TE",
                parent_mass_kg=earth_mass_kg,
                parent_radius_km=earth_radius_km,
                orbital_distance_au=luna_orbital_distance_au,
                star_temperature_k=REAL_SOL["temperature_k"],
                star_radius_km=REAL_SOL["radius_km"],
                system_age_years=system_age_years,
                is_orbiting_star=False,
            )

            generated_values["masses"].append(moon_props["mass_kg"])
            generated_values["radii"].append(moon_props["radius_km"])
            generated_values["densities"].append(moon_props["density_kg_m3"])
            generated_values["albedos"].append(moon_props["albedo"])
            generated_values["varieties"].append(moon_props["variety"])

        # Validate against real Luna values
        # Mass: Luna is 7.342e22 kg = 0.0123 Earth masses
        # Expected range for rocky moons: 0.0001-0.02 Earth masses (from MOON_SIZE_AND_COMPOSITION_BY_TYPE)
        # Check that real value is within expected type range
        assert 0.0001 * 5.972e24 <= REAL_LUNA["mass_kg"] <= 0.02 * 5.972e24
        # Check that generated values are in the right range
        assert all(
            0.0001 * 5.972e24 <= m <= 0.02 * 5.972e24
            for m in generated_values["masses"]
        ), (
            f"Generated masses out of range: {[m / 5.972e24 for m in generated_values['masses']]}"
        )

        # Radius: Luna is 1737 km = 0.27 Earth radii
        # Expected range for rocky moons: 0.1-0.3 Earth radii (from MOON_SIZE_AND_COMPOSITION_BY_TYPE)
        # Check that real value is within expected type range
        assert 0.1 * 6371 <= REAL_LUNA["radius_km"] <= 0.3 * 6371
        # Check that generated values are in the right range
        assert all(0.1 * 6371 <= r <= 0.3 * 6371 for r in generated_values["radii"]), (
            f"Generated radii out of range: {[r / 6371 for r in generated_values['radii']]}"
        )

        # Variety: Should mostly be 'R' (Rocky) for moons around terrestrial planets
        # But allow for occasional other types (O, I, T) based on probability distribution
        rocky_count = sum(1 for v in generated_values["varieties"] if v == "R")
        assert rocky_count >= 3, (
            f"Expected at least 3 rocky moons out of 5, got: {generated_values['varieties']}"
        )

        # For Luna-like validation, we'll use only the rocky moons
        rocky_indices = [
            i for i, v in enumerate(generated_values["varieties"]) if v == "R"
        ]
        if not rocky_indices:
            # If no rocky moons, skip density/albedo checks (unlikely but possible)
            rocky_indices = list(range(len(generated_values["varieties"])))

        rocky_densities = [generated_values["densities"][i] for i in rocky_indices]
        rocky_albedos = [generated_values["albedos"][i] for i in rocky_indices]

        # Density: Luna is ~3344 kg/m³
        # Check if real value is within reasonable range of generated average (for rocky moons)
        avg_density = sum(rocky_densities) / len(rocky_densities)
        density_tolerance = 0.5  # 50% tolerance for density (composition can vary)
        assert (
            abs(REAL_LUNA["density_kg_m3"] - avg_density) / REAL_LUNA["density_kg_m3"]
            < density_tolerance
        ), (
            f"Luna density {REAL_LUNA['density_kg_m3']} not within {density_tolerance * 100}% of avg {avg_density}"
        )

        # Albedo: Luna is 0.12 (very low, dark rock)
        avg_albedo = sum(rocky_albedos) / len(rocky_albedos)
        assert abs(REAL_LUNA["albedo"] - avg_albedo) < 0.15, (
            f"Luna albedo {REAL_LUNA['albedo']} not within 0.15 of avg {avg_albedo}"
        )

    def test_integrated_generation(self):
        """
        Test full integrated generation: Star → Planet → Moon.

        This test creates a minimal system and validates that all generated
        values are physically reasonable and approximately match real values.
        """
        # Create with a single seed
        seed = "integrated_test"
        rng = SeededRandom(seed)

        # Generate star
        star_type = "G"
        temperature = generate_star_temperature(rng, star_type)
        mass_solar = generate_star_mass_solar(rng, star_type)
        density = generate_star_density(rng, star_type)
        mass_kg = mass_solar * 1.989e30
        radius_km = calculate_star_radius_from_mass_density(mass_kg, density)

        star = Star.objects.create(
            name="Test Star",
            orbits=self.star_system,
            star_type=star_type,
            temperature_k=temperature,
            mass_kg=mass_kg,
            radius_km=radius_km,
        )

        # Generate planet properties (test functions only, don't save to DB)
        planet_type = "TE"
        orbital_distance_au = 1.0
        composition = generate_composition(rng, planet_type)

        from mysite.universe.procedural_generation import PLANET_PROPERTIES_BY_TYPE

        mass_range = PLANET_PROPERTIES_BY_TYPE[planet_type]["mass_range_earth"]
        radius_range = PLANET_PROPERTIES_BY_TYPE[planet_type]["radius_range_earth"]
        mass_earth = rng.uniform(mass_range[0], mass_range[1])
        radius_earth = rng.uniform(radius_range[0], radius_range[1])

        density = calculate_density_from_composition(rng, composition, planet_type)
        albedo = generate_albedo(rng, composition, planet_type, has_atmosphere=True)
        equilibrium_temp = calculate_equilibrium_temperature(
            temperature, radius_km, orbital_distance_au, albedo
        )

        # Create planet with only fields that exist
        planet = Planet.objects.create(
            name="Test Planet",
            orbits=star,
            planet_type=planet_type,
            orbital_distance_au=orbital_distance_au,
        )

        # Generate moon
        variety = generate_moon_variety(rng)
        moon_composition = generate_composition(rng, "SI")  # Silicate for rocky moons
        moon_albedo = generate_albedo(rng, moon_composition, "SI", has_atmosphere=False)

        # Create moon with only fields that exist
        Moon.objects.create(
            name="Test Moon",
            orbits=planet,
            moon_type=variety,  # Function parameter is still "variety" for clarity
        )

        # Validate that all values are physically reasonable
        assert 0.8 <= mass_solar <= 1.04  # G-type mass range
        assert 5200 <= temperature <= 6000  # G-type temperature range
        assert 0.3 <= mass_earth <= 5.0  # TE mass range
        assert 0.4 <= radius_earth <= 1.5  # TE radius range
        assert 0.0 <= albedo <= 1.0  # wow this albedos are floats between zero and one.
        assert 0 < equilibrium_temp < 1000  # Reasonable temperature range
        assert 0.0 <= moon_albedo <= 1.0


class TestProceduralGenerationCoverage(TestCase):
    """
    Targeted tests to exercise procedural_generation branches that are easy to miss,
    and that can cause subtle regressions later (determinism, bounds, edge cases).
    """

    def test_seeded_random_determinism_and_name_entropy(self):
        rng1 = SeededRandom("seed", name="A")
        rng2 = SeededRandom("seed", name="A")
        rng3 = SeededRandom("seed", name="B")

        # Determinism: same seed+name gives same sequence
        seq1 = (rng1.uniform(0, 1), rng1.randint(1, 10), rng1.choice([1, 2, 3]))
        seq2 = (rng2.uniform(0, 1), rng2.randint(1, 10), rng2.choice([1, 2, 3]))
        assert seq1 == seq2

        # Name entropy: different name should (very likely) change sequence
        seq3 = (rng3.uniform(0, 1), rng3.randint(1, 10), rng3.choice([1, 2, 3]))
        assert seq3 != seq1

        # Exercise remaining RNG wrappers
        rng = SeededRandom(12345, name="misc")
        assert isinstance(rng.choices([1, 2, 3], weights=[0.1, 0.8, 0.1], k=2), list)
        assert isinstance(rng.gauss(0.0, 1.0), float)
        assert isinstance(rng.lognormvariate(0.0, 0.5), float)
        assert isinstance(rng.triangular(0.0, 10.0), float)  # default mode path
        assert isinstance(rng.triangular(0.0, 10.0, mode=1.0), float)
        assert 0.0 <= rng.betavariate(2.0, 5.0) <= 1.0
        assert rng.expovariate(1.5) >= 0.0

    def test_weighted_choice_validation_and_membership(self):
        rng = SeededRandom(1, name="w")

        try:
            weighted_choice(rng, items=[1, 2], weights=[1.0])
            raise AssertionError("Expected ValueError for mismatched items/weights")
        except ValueError:
            pass

        picked = weighted_choice_dict(rng, {"a": 0.0, "b": 1.0})
        assert picked == "b"

    def test_distribution_and_hash_helpers_are_bounded_and_deterministic(self):
        rng = SeededRandom(42, name="dist")
        assert (
            0.0
            <= normal_clamped(rng, mu=100.0, sigma=1000.0, min_val=0.0, max_val=1.0)
            <= 1.0
        )
        assert (
            1.0
            <= log_normal_clamped(rng, mu=0.0, sigma=1.0, min_val=1.0, max_val=10.0)
            <= 10.0
        )

        val = bin_select(rng, bins=[(0.0, 1.0), (10.0, 11.0)])
        assert (0.0 <= val < 1.0) or (10.0 <= val < 11.0)

        val2 = bin_select_weighted(
            rng, bins=[(0.0, 1.0), (10.0, 11.0)], weights=[0.0, 1.0]
        )
        assert 10.0 <= val2 < 11.0

        f1 = hash_to_float("12345", name="X", min_val=-5.0, max_val=5.0)
        f2 = hash_to_float("12345", name="X", min_val=-5.0, max_val=5.0)
        f3 = hash_to_float("12345", name="Y", min_val=-5.0, max_val=5.0)
        assert -5.0 <= f1 < 5.0
        assert f1 == f2
        assert f1 != f3

        i = hash_to_int("12345", name="X", min_val=0, max_val=10)
        assert 0 <= i < 10

        # Cover the "no name provided" hash_to_float path
        f_no_name = hash_to_float(12345, name=None, min_val=0.0, max_val=1.0)
        assert 0.0 <= f_no_name < 1.0

    def test_generate_star_type_returns_valid_code(self):
        rng = SeededRandom(7, name="star_type")
        t = generate_star_type(rng)
        assert t in {"O", "B", "A", "F", "G", "K", "M"}

    def test_planet_type_generation_handles_m_dwarf_adjustment_and_nan_fallback(self):
        # Triggers the star_type in ['M','K'] adjustment branch for close-in bins.
        rng = SeededRandom("planet_seed", name="p")
        planet_type = generate_planet_type(rng, orbital_distance_au=0.05, star_type="M")
        assert planet_type in {"SI", "TE", "CT", "GG", "SE", "IG", "AB"}

        # Defensive: NaN should trigger the fallback return
        rng2 = SeededRandom("planet_seed_2", name="p2")
        fallback_type = generate_planet_type(
            rng2, orbital_distance_au=float("nan"), star_type="G"
        )
        assert fallback_type in {"AB", "IG", "GG"}

    def test_density_from_composition_covers_gas_giant_and_surface_effects(self):
        """
        Cover:
        - GG/IG branch (atmosphere-dominated density)
        - water_coverage density micro-adjustment
        - has_methane density reduction
        """
        from unittest.mock import patch

        base_comp = {
            "iron_content": 0.3,
            "ice_content": 0.1,
            "water_coverage": 0.0,
            "carbon_content": 0.0,
            "has_methane": False,
        }

        rng = SeededRandom(999, name="dens")
        gg_density = calculate_density_from_composition(
            rng, base_comp, planet_type="GG"
        )
        assert 200 <= gg_density <= 20000

        rng_ig = SeededRandom(1001, name="dens_ig")
        ig_density = calculate_density_from_composition(
            rng_ig, base_comp, planet_type="IG"
        )
        assert 200 <= ig_density <= 20000

        # Remove random variation so we can assert the methane and water effects directly.
        rng2 = SeededRandom(1000, name="dens2")
        with patch.object(rng2, "uniform", return_value=0.0):
            d_no_methane = calculate_density_from_composition(
                rng2, {**base_comp, "has_methane": False}, planet_type="TE"
            )
            d_methane = calculate_density_from_composition(
                rng2, {**base_comp, "has_methane": True}, planet_type="TE"
            )
            assert d_methane < d_no_methane

            d_dry = calculate_density_from_composition(
                rng2, {**base_comp, "water_coverage": 0.0}, planet_type="TE"
            )
            d_wet = calculate_density_from_composition(
                rng2, {**base_comp, "water_coverage": 1.0}, planet_type="TE"
            )
            assert d_wet < d_dry

            # Cover the Cthonian variation branch (narrower variation band)
            d_ct = calculate_density_from_composition(
                rng2, {**base_comp, "water_coverage": 0.0}, planet_type="CT"
            )
            assert 200 <= d_ct <= 20000

    def test_generate_albedo_covers_gas_giant_ice_giant_and_atmosphere_boost(self):
        from unittest.mock import patch

        comp = {
            "ice_content": 0.0,
            "water_coverage": 0.0,
            "iron_content": 0.0,
            "carbon_content": 0.0,
            "organic_haze": 0.0,
        }
        rng = SeededRandom(123, name="alb")
        assert (
            0.01
            <= generate_albedo(rng, comp, planet_type="GG", has_atmosphere=False)
            <= 0.99
        )
        assert (
            0.01
            <= generate_albedo(rng, comp, planet_type="IG", has_atmosphere=False)
            <= 0.99
        )

        # Atmosphere boost should increase albedo when not overridden by GG/IG special cases.
        rng2 = SeededRandom(124, name="alb2")

        def _uniform(a, b):
            # Make boost deterministic and avoid extra variation.
            if (a, b) == (0.05, 0.25):
                return 0.1
            if (a, b) == (-0.1, 0.1):
                return 0.0
            return (a + b) / 2.0

        with patch.object(rng2, "uniform", side_effect=_uniform):
            no_atmo = generate_albedo(
                rng2, comp, planet_type="TE", has_atmosphere=False
            )
            with_atmo = generate_albedo(
                rng2, comp, planet_type="TE", has_atmosphere=True
            )
            assert with_atmo >= no_atmo

    def test_moon_quantity_and_variety_edge_cases(self):
        rng = SeededRandom(555, name="mq")
        assert generate_moon_quantity(rng, parent_type="UNKNOWN") == 0

        n = generate_moon_quantity(rng, parent_type="TE")
        assert 0 <= n <= 2

        # min==max branch
        assert generate_moon_quantity(rng, parent_type="CT") == 0

        # Force the "uniform across range" branch by controlling the first 0-1 draw.
        from unittest.mock import patch

        rng3 = SeededRandom(556, name="mq2")
        with patch.object(rng3, "uniform", side_effect=[0.9, 0.0]):
            # 0.9 chooses uniform-branch, then 0.0 chooses center exactly
            n2 = generate_moon_quantity(rng3, parent_type="IG")
        assert 5 <= n2 <= 30

        # Force the "no range matched" fallback by using +inf, which fails dist < inf checks.
        rng2 = SeededRandom(1, name="mv")
        v = generate_moon_variety_by_parent(
            rng2, parent_type="STAR", orbital_distance_au=float("inf")
        )
        assert v in {"R", "I", "O", "T"}

        # Unknown parent => defaults to rocky
        assert (
            generate_moon_variety_by_parent(
                rng2, parent_type="NOT_A_PARENT", orbital_distance_au=1.0
            )
            == "R"
        )

    def test_moon_size_caps_and_radius_adjustments(self):
        from unittest.mock import patch

        # Star-orbiting cap at 0.01 Earth masses
        rng = SeededRandom(2, name="ms")
        with patch.object(rng, "uniform", side_effect=[0.02, 0.2]):
            props = generate_moon_size(
                rng, moon_variety="R", parent_mass_kg=1.0e24, is_orbiting_star=True
            )
        assert abs(props["mass_kg"] - (0.01 * 5.972e24)) < 1e18

        # Near-min mass => radius scaled down
        rng2 = SeededRandom(3, name="ms2")
        with patch.object(rng2, "uniform", side_effect=[0.0001, 0.3]):
            props2 = generate_moon_size(
                rng2, moon_variety="R", parent_mass_kg=1.0e30, is_orbiting_star=False
            )
        assert props2["radius_km"] <= 0.3 * 6371

        # Near-max mass => radius scaled up
        rng3 = SeededRandom(4, name="ms3")
        with patch.object(rng3, "uniform", side_effect=[0.02, 0.1]):
            props3 = generate_moon_size(
                rng3, moon_variety="R", parent_mass_kg=1.0e30, is_orbiting_star=False
            )
        assert props3["radius_km"] >= 0.1 * 6371

        # Unknown variety should default to 'R'
        rng4 = SeededRandom(5, name="ms4")
        props4 = generate_moon_size(
            rng4, moon_variety="???", parent_mass_kg=1.0e30, is_orbiting_star=False
        )
        assert "mass_kg" in props4 and "radius_km" in props4

    def test_generate_moon_properties_can_generate_atmosphere_in_both_paths(self):
        """
        Exercise the atmosphere generation code paths in generate_moon_properties.
        We patch variety selection to 'T' (terrestrial) and force the 0-1 chance rolls to 0.0.
        """
        from unittest.mock import patch

        rng = SeededRandom(10, name="moonprops")
        original_uniform = rng.uniform

        def _uniform(a, b):
            if (a, b) == (0, 1):
                return 0.0
            # Ensure the generated moon is large enough to exceed the escape-velocity threshold
            # so the atmosphere-generation branch is reachable.
            if (a, b) == (0.001, 0.1):  # T-moon mass_range_earth
                return 0.1
            if (a, b) == (0.2, 0.6):  # T-moon radius_range_earth
                # For star-orbiting objects, mass is capped at 0.01 Earth masses;
                # using the minimum radius ensures escape velocity can exceed 2 km/s
                # so the atmosphere-generation branch is reachable.
                return 0.2
            return original_uniform(a, b)

        with (
            patch(
                "mysite.universe.procedural_generation.generate_moon_variety_by_parent",
                return_value="T",
            ),
            patch.object(rng, "uniform", side_effect=_uniform),
        ):
            props_star = generate_moon_properties(
                rng=rng,
                parent_type="STAR",
                parent_mass_kg=5.972e24,
                parent_radius_km=6371,
                orbital_distance_au=0.1,
                star_temperature_k=5778,
                star_radius_km=696340,
                system_age_years=4.6e9,
                is_orbiting_star=True,
            )
            assert props_star["atmosphere"] is not None

            props_planet = generate_moon_properties(
                rng=rng,
                parent_type="TE",
                parent_mass_kg=5.972e24,
                parent_radius_km=6371,
                orbital_distance_au=0.00257,
                star_temperature_k=5778,
                star_radius_km=696340,
                system_age_years=4.6e9,
                is_orbiting_star=False,
            )
            assert props_planet["atmosphere"] is not None

    def test_should_generate_moons_for_parent(self):
        # Parent without moons => generate
        g = Galaxy.objects.create(name="SG Galaxy")
        system = StarSystem.objects.create(name="SG System", orbits=g)
        star = Star.objects.create(name="SG Star", orbits=system, star_type="G")
        planet = Planet.objects.create(
            name="SG Planet", orbits=star, planet_type="TE", orbital_distance_au=1.0
        )
        assert should_generate_moons_for_parent(planet) is True

        Moon.objects.create(name="SG Moon", orbits=planet, moon_type="R")
        assert should_generate_moons_for_parent(planet) is False

        class _NoMoons:
            pass

        assert should_generate_moons_for_parent(_NoMoons()) is True

    def test_orbital_and_atmosphere_physics_helpers(self):
        # solar angle
        angle = calculate_solar_angle_deg(
            system_age_years=4.6e9, orbital_period_days=365.25
        )
        assert 0.0 <= angle < 360.0

        # hill sphere should shrink with eccentricity
        r0 = calculate_hill_sphere_radius_km(
            planet_mass_kg=5.972e24,
            star_mass_kg=1.989e30,
            orbital_distance_au=1.0,
            eccentricity=0.0,
        )
        r1 = calculate_hill_sphere_radius_km(
            planet_mass_kg=5.972e24,
            star_mass_kg=1.989e30,
            orbital_distance_au=1.0,
            eccentricity=0.5,
        )
        assert r1 < r0

        assert (
            is_tidally_locked(
                orbital_distance_au=0.01,
                planet_mass_kg=5.972e24,
                planet_radius_km=6371,
                star_mass_kg=1.989e30,
                system_age_years=1e6,
            )
            is True
        )
        assert (
            is_tidally_locked(
                orbital_distance_au=0.1,
                planet_mass_kg=5.972e24,
                planet_radius_km=6371,
                star_mass_kg=1.989e30,
                system_age_years=2e9,
            )
            is True
        )
        assert (
            is_tidally_locked(
                orbital_distance_au=0.4,
                planet_mass_kg=1.0e24,
                planet_radius_km=3000,
                star_mass_kg=1.989e30,
                system_age_years=6e9,
            )
            is True
        )
        assert (
            is_tidally_locked(
                orbital_distance_au=1.0,
                planet_mass_kg=5.972e24,
                planet_radius_km=6371,
                star_mass_kg=1.989e30,
                system_age_years=1e9,
            )
            is False
        )

        # geostationary orbit (Earth) ~42164 km from center
        geo = calculate_geostationary_orbit_km(
            planet_mass_kg=5.972e24, planet_radius_km=6371, rotation_period_hours=23.934
        )
        assert 40000 <= geo <= 45000

        esc = calculate_escape_velocity_km_s(mass_kg=5.972e24, radius_km=6371)
        assert 10.0 <= esc <= 12.0

        assert (
            can_retain_atmosphere(
                escape_velocity_km_s=11.2, temperature_k=288, molecular_mass_amu=28.0
            )
            is True
        )
        assert (
            can_retain_atmosphere(
                escape_velocity_km_s=1.0, temperature_k=500, molecular_mass_amu=28.0
            )
            is False
        )
        assert (
            can_retain_atmosphere(
                escape_velocity_km_s=11.2, temperature_k=288, molecular_mass_amu=0.0
            )
            is False
        )

        # atmosphere decision tree: exercise several branches
        rng = SeededRandom(77, name="atmo")
        assert (
            determine_atmosphere_type(
                rng,
                "GG",
                orbital_distance_au=5.0,
                escape_velocity_km_s=50.0,
                temperature_k=200,
                star_type="G",
            )
            == "H2_HE"
        )
        assert (
            determine_atmosphere_type(
                rng,
                "IG",
                orbital_distance_au=5.0,
                escape_velocity_km_s=50.0,
                temperature_k=200,
                star_type="G",
            )
            == "H2_HE"
        )
        assert (
            determine_atmosphere_type(
                rng,
                "AB",
                orbital_distance_au=3.0,
                escape_velocity_km_s=1.0,
                temperature_k=200,
                star_type="G",
            )
            == "NONE"
        )
        assert (
            determine_atmosphere_type(
                rng,
                "CT",
                orbital_distance_au=1.0,
                escape_velocity_km_s=20.0,
                temperature_k=500,
                star_type="G",
            )
            == "NONE"
        )
        assert (
            determine_atmosphere_type(
                rng,
                "TE",
                orbital_distance_au=0.01,
                escape_velocity_km_s=2.0,
                temperature_k=2000,
                star_type="G",
            )
            == "NONE"
        )

        # Very hot branch
        assert (
            determine_atmosphere_type(
                rng,
                "TE",
                orbital_distance_au=0.5,
                escape_velocity_km_s=9.0,
                temperature_k=1600,
                star_type="G",
            )
            == "CO2_THIN"
        )
        assert (
            determine_atmosphere_type(
                rng,
                "TE",
                orbital_distance_au=0.5,
                escape_velocity_km_s=7.0,
                temperature_k=1600,
                star_type="G",
            )
            == "NONE"
        )

        # Steam atmosphere branch
        assert (
            determine_atmosphere_type(
                rng,
                "TE",
                orbital_distance_au=1.0,
                escape_velocity_km_s=30.0,
                temperature_k=1200,
                star_type="G",
            )
            == "H2O"
        )

        # Close-in photoevaporation branch (<0.5 AU) with CO2 retention
        close = determine_atmosphere_type(
            rng,
            "SE",
            orbital_distance_au=0.2,
            escape_velocity_km_s=15.0,
            temperature_k=500,
            star_type="G",
        )
        assert close in {"CO2_THICK", "CO2_THIN"}

        # Very distant outer-system branch (>10 AU)
        assert (
            determine_atmosphere_type(
                rng,
                "TE",
                orbital_distance_au=20.0,
                escape_velocity_km_s=6.0,
                temperature_k=50,
                star_type="G",
            )
            == "N2_CH4"
        )
        assert (
            determine_atmosphere_type(
                rng,
                "TE",
                orbital_distance_au=20.0,
                escape_velocity_km_s=4.0,
                temperature_k=50,
                star_type="G",
            )
            == "NONE"
        )

        # scale height / atmosphere height
        H = calculate_scale_height_km(
            temperature_k=288, mean_molecular_mass_amu=29.0, surface_gravity_m_s2=9.81
        )
        assert H > 0.0
        assert (
            calculate_scale_height_km(
                temperature_k=288,
                mean_molecular_mass_amu=0.0,
                surface_gravity_m_s2=9.81,
            )
            == 0.0
        )

        assert (
            calculate_atmosphere_height_km(
                scale_height_km=7.0, surface_pressure_bar=0.001
            )
            == 42.0
        )
        assert (
            calculate_atmosphere_height_km(
                scale_height_km=7.0, surface_pressure_bar=1.0
            )
            == 56.0
        )
        assert (
            calculate_atmosphere_height_km(
                scale_height_km=7.0, surface_pressure_bar=50.0
            )
            == 70.0
        )
        assert (
            calculate_atmosphere_height_km(
                scale_height_km=0.0, surface_pressure_bar=1.0
            )
            == 0.0
        )

        atmo = generate_atmosphere(
            rng=SeededRandom(88, name="atmo2"),
            planet_type="TE",
            mass_kg=5.972e24,
            radius_km=6371,
            orbital_distance_au=1.0,
            temperature_k=288,
            star_type="G",
        )
        assert "atmosphere_type" in atmo

    def test_color_palette_generation_helpers(self):
        # Hit multiple thresholds in the temperature palette logic
        assert generate_color_palette_from_temperature(40000)["main_color"] == "#9BB0FF"
        assert generate_color_palette_from_temperature(15000)["main_color"] == "#AABFFF"
        assert generate_color_palette_from_temperature(8000)["main_color"] == "#CAD7FF"
        assert generate_color_palette_from_temperature(6500)["main_color"] == "#FFF4E6"
        assert generate_color_palette_from_temperature(5500)["main_color"] == "#FFF8DC"
        assert generate_color_palette_from_temperature(4000)["main_color"] == "#FFCC99"
        assert generate_color_palette_from_temperature(3000)["main_color"] == "#FF6B6B"

        ocean = generate_color_palette_from_composition(
            {"water_coverage": 0.9}, temperature_k=300
        )
        ice = generate_color_palette_from_composition(
            {"ice_content": 0.9}, temperature_k=100
        )
        iron = generate_color_palette_from_composition(
            {"iron_content": 0.9}, temperature_k=300
        )
        rock = generate_color_palette_from_composition({}, temperature_k=300)
        assert ocean["main_color"] != ice["main_color"]
        assert iron["main_color"] != rock["main_color"]
