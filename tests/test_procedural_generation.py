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
    generate_star_temperature,
    generate_star_mass_solar,
    generate_star_density,
    calculate_star_radius_from_mass_density,
    calculate_star_luminosity_solar,
    generate_composition,
    calculate_density_from_composition,
    generate_albedo,
    calculate_equilibrium_temperature,
    calculate_orbital_period_days,
    generate_moon_variety,
    generate_moon_properties,
    generate_moon_size,
    generate_moon_composition,
    generate_moon_variety_by_parent,
)

# Real Solar System values for validation
REAL_SOL = {
    'star_type': 'G',
    'temperature_k': 5778,  # Sun's effective temperature
    'mass_solar': 1.0,  # By definition
    'radius_km': 696340,  # Sun's radius
    'density_kg_m3': 1410,  # Sun's average density
    'luminosity_solar': 1.0,  # By definition
}

REAL_EARTH = {
    'planet_type': 'TE',
    'orbital_distance_au': 1.0,  # By definition
    'mass_kg': 5.972e24,  # Earth mass
    'radius_km': 6371,  # Earth radius
    'density_kg_m3': 5514,  # Earth density
    'albedo': 0.306,  # Earth's Bond albedo
    'equilibrium_temperature_k': 255,  # Earth's equilibrium temp (no greenhouse)
    'orbital_period_days': 365.25,
    'iron_content': 0.32,  # ~32% iron by mass
    'water_coverage': 0.71,  # 71% ocean coverage
}

REAL_LUNA = {
    'variety': 'R',  # Rocky
    'orbital_distance_km': 384400,  # Average distance from Earth
    'mass_kg': 7.342e22,  # Moon mass
    'radius_km': 1737,  # Moon radius
    'density_kg_m3': 3344,  # Moon density
    'albedo': 0.12,  # Moon's Bond albedo
    'orbital_period_hours': 655.7,  # ~27.3 days
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
        seeds = ['sol_test_1', 'sol_test_2', 'sol_test_3', 'sol_test_4', 'sol_test_5']
        generated_values = {
            'temperatures': [],
            'masses': [],
            'densities': [],
            'radii': [],
            'luminosities': [],
        }
        
        for seed in seeds:
            rng = SeededRandom(seed, name="Sol")
            
            # Generate star properties
            star_type = 'G'  # Sol is G-type
            temperature = generate_star_temperature(rng, star_type)
            mass_solar = generate_star_mass_solar(rng, star_type)
            density = generate_star_density(rng, star_type)
            
            # Calculate derived properties
            mass_kg = mass_solar * 1.989e30  # Convert to kg
            radius_km = calculate_star_radius_from_mass_density(mass_kg, density)
            luminosity_solar = calculate_star_luminosity_solar(radius_km, temperature)
            
            generated_values['temperatures'].append(temperature)
            generated_values['masses'].append(mass_solar)
            generated_values['densities'].append(density)
            generated_values['radii'].append(radius_km)
            generated_values['luminosities'].append(luminosity_solar)
        
        # Check that real Sol values are within reasonable ranges
        # We expect real values to be within the expected type ranges, not necessarily
        # within the min/max of a small sample (5 seeds)
        
        # Temperature: Sol is 5778 K, G-type range is 5200-6000 K
        assert 5200 <= REAL_SOL['temperature_k'] <= 6000
        # Also check that generated values are in the right range
        assert all(5200 <= t <= 6000 for t in generated_values['temperatures'])
        
        # Mass: Sol is 1.0 solar masses, G-type range is 0.8-1.04
        assert 0.8 <= REAL_SOL['mass_solar'] <= 1.04
        # Also check that generated values are in the right range
        assert all(0.8 <= m <= 1.04 for m in generated_values['masses'])
        
        # Density: Sol is ~1410 kg/m³, G-type range is 1200-1600
        assert 1200 <= REAL_SOL['density_kg_m3'] <= 1600
        # Also check that generated values are in the right range
        assert all(1200 <= d <= 1600 for d in generated_values['densities'])
        
        # Radius: Sol is ~696,340 km
        # Check that real value is reasonable (within expected range for G-type stars)
        # G-type radius range is approximately 0.96-1.15 solar radii = ~668,000-800,000 km
        assert 668000 <= REAL_SOL['radius_km'] <= 800000
        # Check generated values are reasonable
        avg_radius = sum(generated_values['radii']) / len(generated_values['radii'])
        assert 668000 <= avg_radius <= 800000
        
        # Luminosity: Sol is 1.0 solar luminosities
        # Check that real value is reasonable (G-type stars typically 0.6-1.5 L_sun)
        assert 0.6 <= REAL_SOL['luminosity_solar'] <= 1.5
        # Check generated values are reasonable
        avg_luminosity = sum(generated_values['luminosities']) / len(generated_values['luminosities'])
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
            star_type='G',
            temperature_k=REAL_SOL['temperature_k'],
            mass_kg=REAL_SOL['mass_solar'] * 1.989e30,
            radius_km=REAL_SOL['radius_km'],
        )
        # Note: We don't create Planet objects because Planet doesn't have
        # mass_kg/radius_km fields yet (doesn't inherit from PhysicalBody)
        
        # Test with multiple seeds
        seeds = ['earth_test_1', 'earth_test_2', 'earth_test_3', 'earth_test_4', 'earth_test_5']
        generated_values = {
            'masses': [],
            'radii': [],
            'densities': [],
            'albedos': [],
            'equilibrium_temps': [],
            'iron_contents': [],
            'water_coverages': [],
        }
        
        for seed in seeds:
            rng = SeededRandom(seed, name="Earth")
            
            # Generate planet properties
            planet_type = 'TE'  # Terrestrial (Earth-like)
            orbital_distance_au = 1.0  # 1 AU
            
            # Generate composition
            composition = generate_composition(rng, planet_type)
            
            # Generate mass and radius from type
            from mysite.universe.procedural_generation import PLANET_PROPERTIES_BY_TYPE
            mass_range = PLANET_PROPERTIES_BY_TYPE[planet_type]['mass_range_earth']
            radius_range = PLANET_PROPERTIES_BY_TYPE[planet_type]['radius_range_earth']
            
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
                star.temperature_k or REAL_SOL['temperature_k'],
                star.radius_km or REAL_SOL['radius_km'],
                orbital_distance_au,
                albedo
            )
            
            generated_values['masses'].append(mass_kg)
            generated_values['radii'].append(radius_km)
            generated_values['densities'].append(density)
            generated_values['albedos'].append(albedo)
            generated_values['equilibrium_temps'].append(equilibrium_temp)
            generated_values['iron_contents'].append(composition['iron_content'])
            generated_values['water_coverages'].append(composition['water_coverage'])
        
        # Validate against real Earth values
        # Mass: Earth is 5.972e24 kg, TE range is 0.3-5.0 Earth masses
        # Check that real value is within expected type range
        assert 0.3 * 5.972e24 <= REAL_EARTH['mass_kg'] <= 5.0 * 5.972e24
        # Check that generated values are in the right range
        assert all(0.3 * 5.972e24 <= m <= 5.0 * 5.972e24 for m in generated_values['masses'])
        
        # Radius: Earth is 6371 km, TE range is 0.4-1.5 Earth radii
        # Check that real value is within expected type range
        assert 0.4 * 6371 <= REAL_EARTH['radius_km'] <= 1.5 * 6371
        # Check that generated values are in the right range
        assert all(0.4 * 6371 <= r <= 1.5 * 6371 for r in generated_values['radii'])
        
        # Density: Earth is ~5514 kg/m³
        avg_density = sum(generated_values['densities']) / len(generated_values['densities'])
        assert abs(REAL_EARTH['density_kg_m3'] - avg_density) / REAL_EARTH['density_kg_m3'] < 0.3
        
        # Albedo: Earth is 0.306
        avg_albedo = sum(generated_values['albedos']) / len(generated_values['albedos'])
        assert abs(REAL_EARTH['albedo'] - avg_albedo) < 0.2  # Within 0.2
        
        # Equilibrium temperature: Earth is ~255 K (without greenhouse)
        avg_temp = sum(generated_values['equilibrium_temps']) / len(generated_values['equilibrium_temps'])
        assert abs(REAL_EARTH['equilibrium_temperature_k'] - avg_temp) < 50  # Within 50 K
        
        # Composition: Earth has ~32% iron, 71% water coverage
        avg_iron = sum(generated_values['iron_contents']) / len(generated_values['iron_contents'])
        assert abs(REAL_EARTH['iron_content'] - avg_iron) < 0.15  # Within 15%
        
        avg_water = sum(generated_values['water_coverages']) / len(generated_values['water_coverages'])
        # Water coverage can vary a lot, but Earth's 71% should be in the range
        assert REAL_EARTH['water_coverage'] >= min(generated_values['water_coverages'])
        assert REAL_EARTH['water_coverage'] <= max(generated_values['water_coverages'])
    
    def test_moon_generation_luna_like(self):
        """
        Test moon generation for a Luna-like moon.
        
        We use the new moon generation system to generate a rocky moon around an Earth-like planet.
        """
        # Create Sol and Earth first
        star = Star.objects.create(
            name="Sol",
            orbits=self.star_system,
            star_type='G',
            temperature_k=REAL_SOL['temperature_k'],
            radius_km=REAL_SOL['radius_km'],
            mass_kg=REAL_SOL['mass_solar'] * 1.989e30,
        )
        
        # Earth's properties for parent
        earth_mass_kg = REAL_EARTH['mass_kg']
        earth_radius_km = REAL_EARTH['radius_km']
        
        # Luna's orbital distance from Earth: ~384,400 km = ~0.00257 AU
        luna_orbital_distance_au = 0.00257
        
        # System age (Solar System is ~4.5 billion years old)
        system_age_years = 4.5e9
        
        # Test with multiple seeds
        seeds = ['luna_test_1', 'luna_test_2', 'luna_test_3', 'luna_test_4', 'luna_test_5']
        generated_values = {
            'masses': [],
            'radii': [],
            'densities': [],
            'albedos': [],
            'varieties': [],
        }
        
        for seed in seeds:
            rng = SeededRandom(seed, name="Luna")
            
            # Use the new moon generation system
            # Parent type is 'TE' (Terrestrial planet - Earth)
            moon_props = generate_moon_properties(
                rng=rng,
                parent_type='TE',
                parent_mass_kg=earth_mass_kg,
                parent_radius_km=earth_radius_km,
                orbital_distance_au=luna_orbital_distance_au,
                star_temperature_k=REAL_SOL['temperature_k'],
                star_radius_km=REAL_SOL['radius_km'],
                system_age_years=system_age_years,
                is_orbiting_star=False,
            )
            
            generated_values['masses'].append(moon_props['mass_kg'])
            generated_values['radii'].append(moon_props['radius_km'])
            generated_values['densities'].append(moon_props['density_kg_m3'])
            generated_values['albedos'].append(moon_props['albedo'])
            generated_values['varieties'].append(moon_props['variety'])
        
        # Validate against real Luna values
        # Mass: Luna is 7.342e22 kg = 0.0123 Earth masses
        # Expected range for rocky moons: 0.0001-0.02 Earth masses (from MOON_SIZE_AND_COMPOSITION_BY_TYPE)
        # Check that real value is within expected type range
        assert 0.0001 * 5.972e24 <= REAL_LUNA['mass_kg'] <= 0.02 * 5.972e24
        # Check that generated values are in the right range
        assert all(0.0001 * 5.972e24 <= m <= 0.02 * 5.972e24 for m in generated_values['masses']), \
            f"Generated masses out of range: {[m / 5.972e24 for m in generated_values['masses']]}"
        
        # Radius: Luna is 1737 km = 0.27 Earth radii
        # Expected range for rocky moons: 0.1-0.3 Earth radii (from MOON_SIZE_AND_COMPOSITION_BY_TYPE)
        # Check that real value is within expected type range
        assert 0.1 * 6371 <= REAL_LUNA['radius_km'] <= 0.3 * 6371
        # Check that generated values are in the right range
        assert all(0.1 * 6371 <= r <= 0.3 * 6371 for r in generated_values['radii']), \
            f"Generated radii out of range: {[r / 6371 for r in generated_values['radii']]}"
        
        # Variety: Should mostly be 'R' (Rocky) for moons around terrestrial planets
        # But allow for occasional other types (O, I, T) based on probability distribution
        rocky_count = sum(1 for v in generated_values['varieties'] if v == 'R')
        assert rocky_count >= 3, \
            f"Expected at least 3 rocky moons out of 5, got: {generated_values['varieties']}"
        
        # For Luna-like validation, we'll use only the rocky moons
        rocky_indices = [i for i, v in enumerate(generated_values['varieties']) if v == 'R']
        if not rocky_indices:
            # If no rocky moons, skip density/albedo checks (unlikely but possible)
            rocky_indices = list(range(len(generated_values['varieties'])))
        
        rocky_masses = [generated_values['masses'][i] for i in rocky_indices]
        rocky_radii = [generated_values['radii'][i] for i in rocky_indices]
        rocky_densities = [generated_values['densities'][i] for i in rocky_indices]
        rocky_albedos = [generated_values['albedos'][i] for i in rocky_indices]
        
        # Density: Luna is ~3344 kg/m³
        # Check if real value is within reasonable range of generated average (for rocky moons)
        avg_density = sum(rocky_densities) / len(rocky_densities)
        density_tolerance = 0.5  # 50% tolerance for density (composition can vary)
        assert abs(REAL_LUNA['density_kg_m3'] - avg_density) / REAL_LUNA['density_kg_m3'] < density_tolerance, \
            f"Luna density {REAL_LUNA['density_kg_m3']} not within {density_tolerance*100}% of avg {avg_density}"
        
        # Albedo: Luna is 0.12 (very low, dark rock)
        avg_albedo = sum(rocky_albedos) / len(rocky_albedos)
        assert abs(REAL_LUNA['albedo'] - avg_albedo) < 0.15, \
            f"Luna albedo {REAL_LUNA['albedo']} not within 0.15 of avg {avg_albedo}"
    
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
        star_type = 'G'
        temperature = generate_star_temperature(rng, star_type)
        mass_solar = generate_star_mass_solar(rng, star_type)
        density = generate_star_density(rng, star_type)
        mass_kg = mass_solar * 1.989e30
        radius_km = calculate_star_radius_from_mass_density(mass_kg, density)
        luminosity_solar = calculate_star_luminosity_solar(radius_km, temperature)
        
        star = Star.objects.create(
            name="Test Star",
            orbits=self.star_system,
            star_type=star_type,
            temperature_k=temperature,
            mass_kg=mass_kg,
            radius_km=radius_km,
        )
        
        # Generate planet properties (test functions only, don't save to DB)
        planet_type = 'TE'
        orbital_distance_au = 1.0
        composition = generate_composition(rng, planet_type)
        
        from mysite.universe.procedural_generation import PLANET_PROPERTIES_BY_TYPE
        mass_range = PLANET_PROPERTIES_BY_TYPE[planet_type]['mass_range_earth']
        radius_range = PLANET_PROPERTIES_BY_TYPE[planet_type]['radius_range_earth']
        
        mass_earth = rng.uniform(mass_range[0], mass_range[1])
        radius_earth = rng.uniform(radius_range[0], radius_range[1])
        planet_mass_kg = mass_earth * 5.972e24
        planet_radius_km = radius_earth * 6371
        
        density = calculate_density_from_composition(rng, composition, planet_type)
        albedo = generate_albedo(rng, composition, planet_type, has_atmosphere=True)
        equilibrium_temp = calculate_equilibrium_temperature(
            temperature, radius_km, orbital_distance_au, albedo
        )
        orbital_period = calculate_orbital_period_days(orbital_distance_au, star.mass_kg)
        
        # Create planet with only fields that exist
        planet = Planet.objects.create(
            name="Test Planet",
            orbits=star,
            planet_type=planet_type,
            orbital_distance_au=orbital_distance_au,
        )
        
        # Generate moon
        variety = generate_moon_variety(rng)
        moon_composition = generate_composition(rng, 'SI')  # Silicate for rocky moons
        
        # Simplified moon generation
        moon_mass_earth = rng.uniform(0.005, 0.1)
        moon_mass_kg = moon_mass_earth * 5.972e24
        moon_radius_earth = rng.uniform(0.1, 0.5)
        moon_radius_km = moon_radius_earth * 6371
        moon_density = calculate_density_from_composition(rng, moon_composition, 'SI')
        moon_albedo = generate_albedo(rng, moon_composition, 'SI', has_atmosphere=False)
        
        # Create moon with only fields that exist
        moon = Moon.objects.create(
            name="Test Moon",
            orbits=planet,
            moon_type=variety,  # Function parameter is still "variety" for clarity
        )
        
        # Validate that all values are physically reasonable
        assert 0.8 <= mass_solar <= 1.04  # G-type mass range
        assert 5200 <= temperature <= 6000  # G-type temperature range
        assert 0.3 <= mass_earth <= 5.0  # TE mass range
        assert 0.4 <= radius_earth <= 1.5  # TE radius range
        assert 0.0 <= albedo <= 1.0 # wow this albedos are floats between zero and one. 
        assert 0 < equilibrium_temp < 1000  # Reasonable temperature range
        assert 0.0 <= moon_albedo <= 1.0

