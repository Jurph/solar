"""
Procedural generation utilities for the universe system.

This module provides seeded random number generation and helper methods
for generating universe properties deterministically. It's designed to be
importable from anywhere in the codebase for consistent, reproducible generation.

Key Features:
- Seeded random number generation (deterministic)
- Weighted choices (for star types, planet types, etc.)
- Distribution helpers (normal, uniform, log-normal)
- Bin selection (discrete ranges)
- Deterministic hashing (for name-based entropy)
- Celestial body generation (stars, planets, moons)
- Orbital mechanics calculations
"""

import hashlib
import random
import math
from typing import List, Tuple, Optional, Dict, Any, Union


class SeededRandom:
    """
    Wrapper around random.Random that provides deterministic generation
    based on a seed and optional name-based entropy.
    """
    
    def __init__(self, seed: Union[int, str], name: Optional[str] = None):
        """
        Initialize seeded random number generator.
        
        Args:
            seed: Base seed value (int or string)
            name: Optional name to add entropy (hashed and combined with seed)
        """
        if isinstance(seed, str):
            # Convert string seed to int
            seed = int(hashlib.md5(seed.encode()).hexdigest(), 16) % (2**31)
        
        # Add name-based entropy if provided
        if name:
            name_hash = int(hashlib.md5(name.encode()).hexdigest(), 16) % (2**31)
            seed = (seed + name_hash) % (2**31)
        
        self.rng = random.Random(seed)
        self._seed = seed
    
    def uniform(self, a: float, b: float) -> float:
        """Generate uniform random float in [a, b)."""
        return self.rng.uniform(a, b)
    
    def randint(self, a: int, b: int) -> int:
        """Generate random integer in [a, b] (inclusive)."""
        return self.rng.randint(a, b)
    
    def choice(self, seq: List[Any]) -> Any:
        """Choose random element from sequence."""
        return self.rng.choice(seq)
    
    def choices(self, population: List[Any], weights: Optional[List[float]] = None, k: int = 1) -> List[Any]:
        """Choose k elements with replacement, optionally weighted."""
        return self.rng.choices(population, weights=weights, k=k)
    
    def gauss(self, mu: float, sigma: float) -> float:
        """Generate normal (Gaussian) distribution."""
        return self.rng.gauss(mu, sigma)
    
    def lognormvariate(self, mu: float, sigma: float) -> float:
        """Generate log-normal distribution."""
        return self.rng.lognormvariate(mu, sigma)
    
    def triangular(self, low: float, high: float, mode: Optional[float] = None) -> float:
        """Generate triangular distribution."""
        if mode is None:
            mode = (low + high) / 2
        return self.rng.triangular(low, mode, high)
    
    def betavariate(self, alpha: float, beta: float) -> float:
        """Generate beta distribution (useful for 0-1 bounded values)."""
        return self.rng.betavariate(alpha, beta)
    
    def expovariate(self, lambd: float) -> float:
        """Generate exponential distribution."""
        return self.rng.expovariate(lambd)


def weighted_choice(rng: SeededRandom, items: List[Any], weights: List[float]) -> Any:
    """
    Choose an item from a list based on weights.
    
    Args:
        rng: SeededRandom instance
        items: List of items to choose from
        weights: List of weights (must match length of items)
    
    Returns:
        Selected item
    """
    if len(items) != len(weights):
        raise ValueError(f"Items ({len(items)}) and weights ({len(weights)}) must have same length")
    
    return rng.choices(items, weights=weights, k=1)[0]


def weighted_choice_dict(rng: SeededRandom, choices_dict: Dict[Any, float]) -> Any:
    """
    Choose an item from a dictionary where values are weights.
    
    Args:
        rng: SeededRandom instance
        choices_dict: Dictionary mapping items to weights
    
    Returns:
        Selected item (key from dictionary)
    """
    items = list(choices_dict.keys())
    weights = list(choices_dict.values())
    return weighted_choice(rng, items, weights)


def normal_clamped(rng: SeededRandom, mu: float, sigma: float, min_val: float, max_val: float) -> float:
    """
    Generate normal distribution clamped to [min_val, max_val].
    
    Args:
        rng: SeededRandom instance
        mu: Mean
        sigma: Standard deviation
        min_val: Minimum value
        max_val: Maximum value
    
    Returns:
        Clamped value
    """
    value = rng.gauss(mu, sigma)
    return max(min_val, min(max_val, value))


def log_normal_clamped(rng: SeededRandom, mu: float, sigma: float, min_val: float, max_val: float) -> float:
    """
    Generate log-normal distribution clamped to [min_val, max_val].
    
    Useful for properties that span orders of magnitude (mass, radius, etc.).
    
    Args:
        rng: SeededRandom instance
        mu: Mean of underlying normal distribution
        sigma: Standard deviation of underlying normal distribution
        min_val: Minimum value
        max_val: Maximum value
    
    Returns:
        Clamped value
    """
    value = rng.lognormvariate(mu, sigma)
    return max(min_val, min(max_val, value))


def bin_select(rng: SeededRandom, bins: List[Tuple[float, float]]) -> float:
    """
    Select a value from a bin (discrete range).
    
    Args:
        rng: SeededRandom instance
        bins: List of (min, max) tuples defining bins
    
    Returns:
        Random value from a randomly selected bin
    """
    bin_min, bin_max = rng.choice(bins)
    return rng.uniform(bin_min, bin_max)


def bin_select_weighted(rng: SeededRandom, bins: List[Tuple[float, float]], weights: List[float]) -> float:
    """
    Select a value from a weighted bin.
    
    Args:
        rng: SeededRandom instance
        bins: List of (min, max) tuples defining bins
        weights: List of weights for each bin
    
    Returns:
        Random value from a weighted-selected bin
    """
    bin_min, bin_max = weighted_choice(rng, bins, weights)
    return rng.uniform(bin_min, bin_max)


def hash_to_float(seed: Union[int, str], name: Optional[str] = None, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Generate deterministic float from seed and name hash.
    
    Useful for properties that should be deterministic based on name
    (e.g., same star name always generates same base properties).
    
    Args:
        seed: Base seed
        name: Name to hash (optional)
        min_val: Minimum output value
        max_val: Maximum output value
    
    Returns:
        Deterministic float in [min_val, max_val)
    """
    if isinstance(seed, str):
        seed = int(hashlib.md5(seed.encode()).hexdigest(), 16) % (2**31)
    
    if name:
        name_hash = int(hashlib.md5(name.encode()).hexdigest(), 16) % (2**31)
        combined = (seed + name_hash) % (2**31)
    else:
        combined = seed
    
    # Convert to float in range
    normalized = combined / (2**31)
    return min_val + (max_val - min_val) * normalized


def hash_to_int(seed: Union[int, str], name: Optional[str] = None, min_val: int = 0, max_val: int = 100) -> int:
    """
    Generate deterministic integer from seed and name hash.
    
    Args:
        seed: Base seed
        name: Name to hash (optional)
        min_val: Minimum output value
        max_val: Maximum output value (exclusive)
    
    Returns:
        Deterministic integer in [min_val, max_val)
    """
    float_val = hash_to_float(seed, name, min_val, max_val)
    return int(float_val)


# Star Type Generation
STAR_TYPE_WEIGHTS = {
    'O': 0.00003,  # Very rare
    'B': 0.0013,
    'A': 0.006,
    'F': 0.03,
    'G': 0.076,    # Sun-like
    'K': 0.121,
    'M': 0.764,    # Most common (red dwarfs)
}

STAR_TYPE_TEMPERATURE_RANGES = {
    'O': (30000, 50000),
    'B': (10000, 30000),
    'A': (7500, 10000),
    'F': (6000, 7500),
    'G': (5200, 6000),
    'K': (3700, 5200),
    'M': (2400, 3700),
}

STAR_TYPE_MASS_RANGES = {  # In solar masses
    'O': (16, 90),      # Baraffe et al. 2015
    'B': (2.1, 16),
    'A': (1.4, 2.1),
    'F': (1.04, 1.4),
    'G': (0.8, 1.04),   # Sun is 1.0
    'K': (0.45, 0.8),
    'M': (0.08, 0.45),  # Lower limit is hydrogen burning threshold
}

STAR_TYPE_DENSITY_RANGES = {  # In kg/m³ (average bulk density)
    'O': (10, 100),       # Large but diffuse - less dense than Sun
    'B': (50, 500),       # Still less dense than Sun typically
    'A': (200, 1000),     # Approaching solar density
    'F': (500, 1500),     # Around solar density
    'G': (1200, 1600),    # Sun is ~1410 kg/m³
    'K': (1500, 3000),    # Denser than Sun
    'M': (3000, 10000),   # Much denser (smaller, more compact)
}


def generate_star_type(rng: SeededRandom) -> str:
    """Generate star type based on weighted distribution."""
    return weighted_choice_dict(rng, STAR_TYPE_WEIGHTS)


def generate_star_temperature(rng: SeededRandom, star_type: str) -> float:
    """Generate temperature for given star type."""
    temp_min, temp_max = STAR_TYPE_TEMPERATURE_RANGES.get(star_type, (3000, 6000))
    return rng.uniform(temp_min, temp_max)


def generate_star_mass_solar(rng: SeededRandom, star_type: str) -> float:
    """Generate mass in solar masses for given star type."""
    mass_min, mass_max = STAR_TYPE_MASS_RANGES.get(star_type, (0.8, 1.2))
    return rng.uniform(mass_min, mass_max)


def generate_star_density(rng: SeededRandom, star_type: str) -> float:
    """Generate density in kg/m³ for given star type."""
    density_min, density_max = STAR_TYPE_DENSITY_RANGES.get(star_type, (1000, 2000))
    return log_normal_clamped(rng, math.log(density_min), 0.5, density_min, density_max)


def calculate_star_radius_from_mass_density(mass_kg: float, density_kg_m3: float) -> float:
    """
    Calculate star radius from mass and density.
    
    Uses: V = M/ρ and V = (4/3)πr³
    Therefore: r = (3M/(4πρ))^(1/3)
    
    Args:
        mass_kg: Star mass in kilograms
        density_kg_m3: Star density in kg/m³
    
    Returns:
        Star radius in kilometers
    """
    # Volume = mass / density
    volume_m3 = mass_kg / density_kg_m3
    
    # For a sphere: V = (4/3)πr³
    # Therefore: r = (3V/(4π))^(1/3)
    radius_m = (3 * volume_m3 / (4 * math.pi)) ** (1/3)
    
    # Convert to kilometers
    radius_km = radius_m / 1000
    
    return radius_km


# Planet Type Generation Based on Exoplanet Observations
# 
# References:
# - Seager et al. 2007: Mass-radius relationships showing composition zones
# - NASA Exoplanet Archive: ~5,000+ confirmed exoplanets show bimodal size distribution
# - Fulton et al. 2017: "Radius gap" at ~1.5-2.0 Earth radii (few planets exist here)
# - Petigura et al. 2022: Small planets (<1.4 R_Earth) peak around 1-2 Earth radii
# - Johnson et al. 2010: Giant planet occurrence increases with stellar metallicity
#
# Key observational facts from exoplanet data:
# 1. Super-Earths/mini-Neptunes (1.4-2.8 R_Earth) are the MOST COMMON exoplanets
# 2. There's a "radius valley" at ~1.5-2.0 R_Earth separating rocky from gas-rich planets
# 3. Neptune-sized planets (2-4 R_Earth) are surprisingly common
# 4. Jupiter-sized and larger are relatively rare (~1% of stars)
# 5. Most exoplanets orbit within 1 AU (detection bias, but real trend)

PLANET_TYPE_WEIGHTS_BY_DISTANCE = {
    # Very close to star (0.0-0.1 AU): Hot, volatile-stripped planets
    # Petigura et al. 2013: Close-in planets tend to be rocky or "hot Jupiters"
    # Hot Jupiters are rare (~1% of stars) but preferentially found here
    (0.0, 0.1): {
        'SI': 0.50,  # Silicate (small, stripped cores)
        'TE': 0.25,  # Terrestrial
        'CT': 0.10,  # Cthonian (stripped gas giant cores) - Batygin et al. 2016
        'GG': 0.10,  # Hot Jupiters (rare but concentrated here)
        'SE': 0.05,  # Super-earths can survive here
    },
    
    # Close orbits (0.1-0.5 AU): Mix of rocky and sub-Neptunes
    # Howard et al. 2012: Planet occurrence peaks for small planets at short periods
    (0.1, 0.5): {
        'TE': 0.35,  # Terrestrial planets common
        'SE': 0.40,  # Super-Earths most common (Fressin et al. 2013)
        'SI': 0.15,  # Smaller silicate planets
        'GG': 0.05,  # Some hot Jupiters
        'IG': 0.05,  # Mini-Neptunes
    },
    
    # Habitable zone analogs (0.5-1.5 AU): Peak of terrestrial/super-Earth
    # Dressing & Charbonneau 2015: Earth-sized planets common in HZ of M-dwarfs
    # Exoplanet data shows THIS is where most observed planets cluster
    (0.5, 1.5): {
        'TE': 0.35,  # Terrestrial (Earth-like)
        'SE': 0.45,  # Super-Earths MOST COMMON (data shows peak here)
        'SI': 0.10,  # Smaller rocky planets
        'IG': 0.05,  # Mini-Neptunes
        'GG': 0.05,  # Rare gas giants
    },
    
    # Outer terrestrial zone (1.5-3.0 AU): Transition zone
    # Gap between inner rocky planets and outer giants (like asteroid belt)
    (1.5, 3.0): {
        'TE': 0.20,  # Rocky planets rarer here
        'SE': 0.25,  # Super-Earths still present
        'IG': 0.25,  # Ice/mini-Neptunes more common
        'AB': 0.20,  # Asteroid belts form here (debris/planetesimals)
        'GG': 0.10,  # Gas giants start appearing
    },
    
    # Ice/gas giant zone (3.0-10.0 AU): Jupiter/Saturn analogs
    # Cumming et al. 2008: Giant planet frequency ~10-20% of stars
    # Most giants found between 1-10 AU (observational clustering)
    (3.0, 10.0): {
        'IG': 0.35,  # Ice giants common (Uranus/Neptune mass)
        'GG': 0.40,  # Gas giants (Jupiter/Saturn mass)
        'SE': 0.15,  # Some super-Earths can form here
        'AB': 0.10,  # Debris/asteroid analogs
    },
    
    # Outer gas giant zone (10.0-30.0 AU): Cold giants
    # Detection bias makes these harder to find, but they exist
    (10.0, 30.0): {
        'GG': 0.40,  # Cold gas giants
        'IG': 0.45,  # Ice giants dominant (Neptune-like)
        'AB': 0.15,  # Kuiper belt analogs
    },
    
    # Very distant (30.0+ AU): Kuiper belt / scattered disk analogs
    # Mostly small icy bodies, occasional rogue planets
    (30.0, float('inf')): {
        'AB': 0.50,  # Asteroid/Kuiper belt objects most common
        'IG': 0.30,  # Distant ice dwarfs
        'GG': 0.15,  # Rare distant giants
        'SI': 0.05,  # Scattered small bodies
    },
}

# Mass and radius ranges based on Seager et al. 2007 composition curves
# and observational data from exoplanet surveys
PLANET_PROPERTIES_BY_TYPE = {
    'SI': {  # Silicate planets (pure rock, no volatiles)
        'mass_range_earth': (0.1, 2.0),  # Smaller than Earth typically
        'radius_range_earth': (0.3, 1.3),  # Below Earth radius
        # Density calculated from composition (typically 3000-5500 kg/m³)
    },
    'TE': {  # Terrestrial (Earth-like: rock + some iron core)
        'mass_range_earth': (0.3, 3.0),  # Mercury to ~2x Earth
        'radius_range_earth': (0.4, 1.5),  # Data shows <1.5 R_E is rocky
        # Density calculated from composition (typically 4000-6000 kg/m³, Earth ~5500)
    },
    'SE': {  # Super-Earths (rocky but larger, possible thin H/He envelope)
        'mass_range_earth': (2.0, 10.0),  # Data shows peak at 1.4-2.8 R_E
        'radius_range_earth': (1.5, 2.5),  # Above radius gap, below mini-Neptunes
        # Density calculated from composition (typically 3500-5500 kg/m³)
    },
    'CT': {  # Cthonian planets (stripped gas giant cores)
        'mass_range_earth': (5.0, 50.0),  # Massive but small radius
        'radius_range_earth': (1.0, 2.0),  # Dense, compact
        # Density calculated from composition (typically 8000-15000 kg/m³, very high)
    },
    'IG': {  # Ice giants (rock/ice core + H/He envelope)
        'mass_range_earth': (10.0, 50.0),  # Neptune ~17, Uranus ~14.5 Earth masses
        'radius_range_earth': (2.5, 6.0),  # Data shows 3-6 R_E range
        # Density calculated from composition (typically 1000-2000 kg/m³, mostly gas)
    },
    'GG': {  # Gas giants (massive H/He atmosphere)
        'mass_range_earth': (50.0, 5000.0),  # Jupiter ~318, can go much higher
        'radius_range_earth': (8.0, 15.0),  # Jupiter ~11 R_E, Saturn ~9 R_E
        # Density calculated from composition (typically 400-1700 kg/m³, very low)
    },
    'AB': {  # Asteroid belt (not a planet, collection of debris)
        'mass_range_earth': (0.0001, 0.01),  # Negligible mass
        'radius_range_earth': (0.01, 0.1),  # Small bodies
        # Density calculated from composition (typically 2000-3000 kg/m³, rocky/icy)
    },
}


def generate_planet_type(rng: SeededRandom, orbital_distance_au: float, 
                        star_type: str = 'G') -> str:
    """
    Generate planet type based on orbital distance using observational exoplanet data.
    
    Based on NASA Exoplanet Archive statistics showing:
    - Small planets (1-2 R_Earth) are most common
    - "Radius gap" at 1.5-2.0 R_Earth (Fulton gap)
    - Hot Jupiters rare (~1%) but concentrated close-in
    - Super-Earths/mini-Neptunes dominate overall population
    
    Args:
        rng: SeededRandom instance
        orbital_distance_au: Orbital distance in AU
        star_type: Star spectral type (affects giant planet frequency)
    
    Returns:
        Planet type code (SI, TE, SE, CT, IG, GG, AB)
    """
    # Find appropriate distance range
    for (dist_min, dist_max), weights in PLANET_TYPE_WEIGHTS_BY_DISTANCE.items():
        if dist_min <= orbital_distance_au < dist_max:
            # Adjust for star type
            # Johnson et al. 2010: Metal-rich stars have more gas giants
            # Laughlin et al. 2004: M-dwarfs have fewer gas giants
            adjusted_weights = weights.copy()
            
            if star_type in ['M', 'K']:  # Cooler stars
                # Reduce gas giant probability, increase rocky planets
                if 'GG' in adjusted_weights:
                    gg_weight = adjusted_weights['GG']
                    adjusted_weights['GG'] *= 0.5  # Half as many giants
                    # Redistribute to terrestrials
                    adjusted_weights['TE'] = adjusted_weights.get('TE', 0) + gg_weight * 0.3
                    adjusted_weights['SE'] = adjusted_weights.get('SE', 0) + gg_weight * 0.2
            
            return weighted_choice_dict(rng, adjusted_weights)
    
    # Fallback for very distant planets
    return weighted_choice_dict(rng, {'AB': 0.5, 'IG': 0.3, 'GG': 0.2})


# Composition Generation
COMPOSITION_RANGES_BY_TYPE = {
    'SI': {  # Silicate
        'iron_content': (0.3, 0.6),
        'ice_content': (0.0, 0.05),
        'has_methane': False,
        'has_sulfur': (0.0, 0.1),
        'water_coverage': (0.0, 0.0),
        'carbon_content': (0.0, 0.05),
        'organic_haze': (0.0, 0.0),
    },
    'TE': {  # Terrestrial
        'iron_content': (0.2, 0.4),
        'ice_content': (0.0, 0.1),
        'has_methane': False,
        'has_sulfur': (0.0, 0.2),
        'water_coverage': (0.0, 0.9),
        'carbon_content': (0.0, 0.1),
        'organic_haze': (0.0, 0.1),
    },
    'SE': {  # Super-earth
        'iron_content': (0.15, 0.35),
        'ice_content': (0.0, 0.15),
        'has_methane': False,
        'has_sulfur': (0.0, 0.15),
        'water_coverage': (0.0, 0.9),
        'carbon_content': (0.0, 0.15),
        'organic_haze': (0.0, 0.2),
    },
    'CT': {  # Cthonian (stripped gas giant core)
        'iron_content': (0.4, 0.7),  # High iron (exposed core)
        'ice_content': (0.0, 0.05),
        'has_methane': False,
        'has_sulfur': (0.0, 0.1),
        'water_coverage': (0.0, 0.0),
        'carbon_content': (0.0, 0.1),
        'organic_haze': (0.0, 0.0),
    },
    'IG': {  # Ice Giant
        'iron_content': (0.05, 0.15),
        'ice_content': (0.3, 0.7),
        'has_methane': True,
        'has_sulfur': (0.0, 0.05),
        'water_coverage': (0.0, 0.0),
        'carbon_content': (0.1, 0.3),
        'organic_haze': (0.0, 0.1),
    },
    'GG': {  # Gas Giant
        'iron_content': (0.0, 0.1),
        'ice_content': (0.0, 0.2),
        'has_methane': True,
        'has_sulfur': (0.0, 0.05),
        'water_coverage': (0.0, 0.0),
        'carbon_content': (0.05, 0.2),
        'organic_haze': (0.0, 0.05),
    },
    'AB': {  # Asteroid belt (debris)
        'iron_content': (0.1, 0.4),
        'ice_content': (0.0, 0.3),
        'has_methane': False,
        'has_sulfur': (0.0, 0.2),
        'water_coverage': (0.0, 0.0),
        'carbon_content': (0.0, 0.1),
        'organic_haze': (0.0, 0.0),
    },
}


def generate_composition(rng: SeededRandom, planet_type: str) -> Dict[str, Any]:
    """
    Generate composition values for a planet/moon based on type.
    
    Args:
        rng: SeededRandom instance
        planet_type: Planet type code (SI, TE, SE, CT, IG, GG, AB)
    
    Returns:
        Dictionary with composition values
    """
    ranges = COMPOSITION_RANGES_BY_TYPE.get(planet_type, COMPOSITION_RANGES_BY_TYPE['TE'])
    
    composition = {}
    for key, value in ranges.items():
        if isinstance(value, bool):
            composition[key] = value
        elif isinstance(value, tuple):
            min_val, max_val = value
            composition[key] = rng.uniform(min_val, max_val)
        else:
            composition[key] = value
    
    return composition


def calculate_density_from_composition(rng: SeededRandom, composition: Dict[str, Any], 
                                      planet_type: str = None) -> float:
    """
    Calculate planet density from composition values.
    
    Uses weighted average of material densities based on composition fractions,
    then applies a random variation factor (±10-20%).
    
    Material densities (kg/m³):
    - Iron: ~7800 (iron core material)
    - Rock/silicate: ~3000-3500 (typical crust/mantle)
    - Ice (H2O): ~900-1000 (water ice)
    - Carbon: ~2000-2200 (graphite, organic compounds)
    - Gas (H2/He/methane): ~100-500 (atmospheric, very low density)
    - Water (liquid): ~1000 (surface water)
    
    Args:
        rng: SeededRandom instance for variation
        composition: Dictionary with composition values
        planet_type: Optional planet type for special cases (GG, IG have low density)
    
    Returns:
        Density in kg/m³
    """
    # Base material densities (kg/m³)
    DENSITY_IRON = 7800
    DENSITY_ROCK = 3250  # Average silicate rock
    DENSITY_ICE = 950
    DENSITY_WATER = 1000
    DENSITY_CARBON = 2100  # Graphite/organic
    
    iron_content = composition.get('iron_content', 0.0)
    ice_content = composition.get('ice_content', 0.0)
    water_coverage = composition.get('water_coverage', 0.0)
    carbon_content = composition.get('carbon_content', 0.0)
    has_methane = composition.get('has_methane', False)
    
    # For gas giants and ice giants, composition doesn't directly map to bulk density
    # They have massive atmospheres that dominate
    if planet_type in ['GG', 'IG']:
        # Gas giants: mostly H2/He atmosphere
        if planet_type == 'GG':
            base_density = 800  # Jupiter ~1326, Saturn ~687, but we'll use lower for variation
        else:  # IG
            base_density = 1500  # Neptune ~1638, Uranus ~1270
        # Core density from composition (for variation)
        core_density = (iron_content * DENSITY_IRON + 
                       (1.0 - iron_content) * DENSITY_ROCK)
        # Weighted average: mostly gas, some core
        bulk_density = (0.85 * base_density + 0.15 * core_density)
    else:
        # Rocky planets: calculate from material fractions
        # Remaining fraction after iron/ice/water/carbon is rock
        total_volatile = ice_content + water_coverage + carbon_content
        rock_fraction = max(0.0, 1.0 - iron_content - total_volatile)
        
        # Weighted average density
        bulk_density = (
            iron_content * DENSITY_IRON +
            rock_fraction * DENSITY_ROCK +
            ice_content * DENSITY_ICE +
            water_coverage * DENSITY_WATER +
            carbon_content * DENSITY_CARBON
        )
        
        # If has methane, add some gas component (reduces density)
        if has_methane:
            # Methane is a trace component, reduce density slightly
            bulk_density *= 0.95
    
    # Apply random variation (±10-20% depending on planet type)
    if planet_type == 'CT':
        # Cthonian planets: very dense, less variation
        variation = rng.uniform(-0.08, 0.08)  # ±8%
    elif planet_type in ['GG', 'IG']:
        # Gas/ice giants: more variation due to atmospheric composition
        variation = rng.uniform(-0.15, 0.15)  # ±15%
    else:
        # Rocky planets: moderate variation
        variation = rng.uniform(-0.12, 0.12)  # ±12%
    
    density = bulk_density * (1.0 + variation)
    
    # Clamp to reasonable physical limits
    min_density = 200  # Very low (gas giant)
    max_density = 20000  # Very high (exotic core material)
    
    return max(min_density, min(max_density, density))


# Moon Variety Generation
MOON_VARIETY_WEIGHTS = {
    'R': 0.6,  # Rocky (most common)
    'I': 0.25,  # Icy
    'O': 0.1,   # Organic
    'T': 0.05,  # Terrestrial (rare, habitable)
}


def generate_moon_variety(rng: SeededRandom) -> str:
    """Generate moon variety based on weighted distribution."""
    return weighted_choice_dict(rng, MOON_VARIETY_WEIGHTS)


# Orbital Properties
def calculate_orbital_period_days(orbital_distance_au: float, star_mass_kg: float) -> float:
    """
    Calculate orbital period using Kepler's third law.
    
    P² = (4π² / GM) * a³
    
    Args:
        orbital_distance_au: Semi-major axis in AU
        star_mass_kg: Star mass in kg
    
    Returns:
        Orbital period in days
    """
    G = 6.67430e-11  # Gravitational constant (m³/kg/s²)
    AU_TO_M = 1.496e11  # 1 AU in meters
    SECONDS_PER_DAY = 86400
    
    a_m = orbital_distance_au * AU_TO_M
    a_cubed = a_m ** 3
    
    # P² = (4π² / GM) * a³
    # P = sqrt((4π² / GM) * a³)
    period_seconds = math.sqrt((4 * math.pi**2 / (G * star_mass_kg)) * a_cubed)
    period_days = period_seconds / SECONDS_PER_DAY
    
    return period_days


def calculate_solar_angle_deg(system_age_years: float, orbital_period_days: float) -> float:
    """
    Calculate current orbital position (solar angle) in degrees.
    
    Args:
        system_age_years: System age in years
        orbital_period_days: Orbital period in days
    
    Returns:
        Solar angle in degrees (0-359)
    """
    orbital_period_years = orbital_period_days / 365.25
    revolutions = system_age_years / orbital_period_years
    angle_deg = (revolutions % 1.0) * 360.0
    return angle_deg


def calculate_hill_sphere_radius_km(planet_mass_kg: float, star_mass_kg: float, 
                                   orbital_distance_au: float, 
                                   eccentricity: float = 0.0) -> float:
    """
    Calculate Hill sphere radius (maximum stable orbit distance).
    
    Note: Stable orbits typically exist only within ~1/3 to 1/2 of Hill radius
    (Domingos et al. 2006).
    
    Args:
        planet_mass_kg: Planet mass in kg
        star_mass_kg: Star mass in kg
        orbital_distance_au: Semi-major axis in AU
        eccentricity: Orbital eccentricity (0 = circular)
    
    Returns:
        Hill sphere radius in km
    """
    AU_TO_KM = 1.496e8  # 1 AU in km
    
    orbital_distance_km = orbital_distance_au * AU_TO_KM
    
    # More accurate Hill sphere formula: r_H = a * (1 - e) * (m / (3*M))^(1/3)
    # For elliptical orbits, the Hill sphere size varies, so we use periapsis
    # (closest approach) which gives the minimum stable distance
    mass_ratio = planet_mass_kg / (3 * star_mass_kg)
    hill_radius_km = orbital_distance_km * (1 - eccentricity) * (mass_ratio ** (1/3))
    
    return hill_radius_km


def is_tidally_locked(orbital_distance_au: float, planet_mass_kg: float, 
                     planet_radius_km: float, star_mass_kg: float,
                     system_age_years: float) -> bool:
    """
    Estimate if planet is tidally locked to star.
    
    Based on tidal locking timescale (Murray & Dermott 1999):
    t_lock ≈ (ω * a^6 * I * Q) / (3 * G * M_star^2 * k_2 * R^5)
    
    Simplified: planets very close to star (<0.1 AU) are usually locked.
    
    Args:
        orbital_distance_au: Orbital distance in AU
        planet_mass_kg: Planet mass in kg
        planet_radius_km: Planet radius in km
        star_mass_kg: Star mass in kg
        system_age_years: System age in years
    
    Returns:
        True if likely tidally locked
    """
    # Simplified heuristic (full calculation requires Q, k2, moment of inertia)
    # Murray & Dermott 1999: t_lock ∝ a^6 / M_star^2
    
    # Very close planets (<0.05 AU) are almost certainly locked
    if orbital_distance_au < 0.05:
        return True
    
    # Close planets (0.05-0.15 AU) likely locked for old systems
    if orbital_distance_au < 0.15 and system_age_years > 1e9:  # 1 billion years
        return True
    
    # Moderate distance (0.15-0.5 AU) maybe locked for very old systems
    if orbital_distance_au < 0.5 and system_age_years > 5e9:  # 5 billion years
        # Also depends on planet mass (larger = harder to lock)
        earth_masses = planet_mass_kg / 5.972e24
        if earth_masses < 2.0:  # Small planets lock easier
            return True
    
    return False


def calculate_geostationary_orbit_km(planet_mass_kg: float, planet_radius_km: float, rotation_period_hours: float) -> float:
    """
    Calculate geostationary orbit altitude.
    
    Args:
        planet_mass_kg: Planet mass in kg
        planet_radius_km: Planet radius in km (not used in calculation, but kept for API consistency)
        rotation_period_hours: Rotation period in hours
    
    Returns:
        Geostationary orbit altitude in km (distance from planet center)
    """
    G = 6.67430e-11  # Gravitational constant
    KM_TO_M = 1000
    HOURS_TO_SECONDS = 3600
    
    rotation_period_s = rotation_period_hours * HOURS_TO_SECONDS
    
    # T = 2π * sqrt(r³ / GM)
    # r = (GM * T² / (4π²))^(1/3)
    r_m = ((G * planet_mass_kg * rotation_period_s**2) / (4 * math.pi**2)) ** (1/3)
    r_km = r_m / KM_TO_M
    
    return r_km


# Atmosphere Generation
# 
# References:
# - Zahnle & Catling 2017: Atmospheric evolution of terrestrial planets
# - Seager & Deming 2010: Exoplanet atmospheres composition and retention
# - Lopez & Fortney 2014: H/He envelope retention on super-Earths
# - Owen & Wu 2017: Atmospheric escape and the radius valley
# - Kasting et al. 1993: Habitable zones and atmospheric limits
#
# Key facts:
# 1. Atmosphere retention depends on escape velocity (v_esc = sqrt(2GM/R))
# 2. Jeans escape: molecules with thermal velocity > v_esc are lost
# 3. Rocky planets <0.5 Earth masses struggle to retain atmospheres
# 4. Super-Earths can retain H/He if far enough from star (no photoevaporation)
# 5. Gas/ice giants always have thick H/He atmospheres by definition

# Mean molecular masses (amu) for different atmosphere types
ATMOSPHERE_MOLECULAR_MASSES = {
    'NONE': 0.0,
    'CO2_THIN': 43.0,    # Mostly CO₂ (44 amu) with trace N₂
    'CO2_THICK': 43.5,   # Almost pure CO₂
    'N2_O2': 29.0,       # Earth-like: 78% N₂ (28 amu) + 21% O₂ (32 amu)
    'N2': 28.0,          # Pure N₂
    'H2_HE': 2.3,        # 90% H₂ (2 amu) + 10% He (4 amu), like Jupiter
    'N2_CH4': 27.0,      # Titan-like: 95% N₂ + 5% CH₄ (16 amu)
    'SO2': 64.0,         # Volcanic SO₂ (64 amu)
    'H2O': 18.0,         # Steam atmosphere (rare, hot planets)
}

# Surface pressure ranges by atmosphere type (bars)
ATMOSPHERE_PRESSURE_RANGES = {
    'NONE': (0.0, 0.0),
    'CO2_THIN': (0.001, 0.02),    # Mars: 0.006 bar
    'CO2_THICK': (50, 100),        # Venus: 92 bar
    'N2_O2': (0.5, 1.5),           # Earth: 1.013 bar
    'N2': (0.3, 2.0),              # Titan: 1.45 bar
    'H2_HE': (0.1, 10),            # Gas giants: define "surface" at 1 bar typically
    'N2_CH4': (1.0, 2.0),          # Titan-like
    'SO2': (0.00001, 0.001),       # Very thin, volcanic
    'H2O': (1.0, 100),             # Steam atmospheres can be thick
}


def calculate_escape_velocity_km_s(mass_kg: float, radius_km: float) -> float:
    """
    Calculate escape velocity: v_esc = sqrt(2GM/R)
    
    Args:
        mass_kg: Body mass in kg
        radius_km: Body radius in km
    
    Returns:
        Escape velocity in km/s
    """
    G = 6.67430e-11  # m³/kg/s²
    radius_m = radius_km * 1000
    
    v_esc_m_s = math.sqrt(2 * G * mass_kg / radius_m)
    v_esc_km_s = v_esc_m_s / 1000
    
    return v_esc_km_s


def can_retain_atmosphere(escape_velocity_km_s: float, temperature_k: float, 
                         molecular_mass_amu: float) -> bool:
    """
    Determine if a body can retain an atmosphere with given molecular mass.
    
    Uses Jeans escape criterion: thermal velocity < escape velocity
    Thermal velocity: v_thermal = sqrt(3kT/m)
    
    Rule of thumb (Walker 1977): atmosphere retained if v_esc > 6 * v_thermal
    
    Args:
        escape_velocity_km_s: Escape velocity in km/s
        temperature_k: Surface temperature in K
        molecular_mass_amu: Mean molecular mass in amu
    
    Returns:
        True if atmosphere can be retained
    """
    if molecular_mass_amu == 0:
        return False
    
    k_B = 1.380649e-23  # Boltzmann constant (J/K)
    amu_to_kg = 1.66054e-27  # kg per amu
    
    molecular_mass_kg = molecular_mass_amu * amu_to_kg
    
    # Thermal velocity (m/s)
    v_thermal_m_s = math.sqrt(3 * k_B * temperature_k / molecular_mass_kg)
    v_thermal_km_s = v_thermal_m_s / 1000
    
    # Atmosphere retained if v_esc > 6 * v_thermal (Walker 1977)
    # Relaxed to 5x for game purposes (allows more marginal atmospheres)
    return escape_velocity_km_s > (5 * v_thermal_km_s)


def determine_atmosphere_type(rng: SeededRandom, planet_type: str, 
                              orbital_distance_au: float, 
                              escape_velocity_km_s: float,
                              temperature_k: float,
                              star_type: str = 'G') -> str:
    """
    Determine atmosphere type based on planet properties.
    
    Logic:
    1. Gas/ice giants ALWAYS have H2_HE (by definition)
    2. Very hot close-in planets lose volatiles → thin/no atmosphere
    3. Escape velocity determines what can be retained
    4. Distance from star affects photoevaporation and volatile delivery
    5. Temperature affects atmospheric chemistry
    
    Args:
        rng: SeededRandom instance
        planet_type: Planet type code
        orbital_distance_au: Distance from star in AU
        escape_velocity_km_s: Escape velocity in km/s
        temperature_k: Equilibrium temperature in K
        star_type: Star spectral type
    
    Returns:
        Atmosphere type string
    """
    # Gas and ice giants always have thick H2/He atmospheres
    if planet_type == 'GG':
        return 'H2_HE'
    
    if planet_type == 'IG':
        return 'H2_HE'  # Ice giants still have H2/He envelopes
    
    # Asteroid belts have no atmosphere
    if planet_type == 'AB':
        return 'NONE'
    
    # Cthonian planets (stripped cores) have lost their atmospheres
    if planet_type == 'CT':
        return 'NONE'
    
    # Rocky planets (SI, TE, SE) - more complex
    
    # Check if escape velocity is sufficient for ANY atmosphere
    # Earth's escape velocity: 11.2 km/s
    # Mars: 5.0 km/s (can barely retain CO2)
    # Moon: 2.4 km/s (no atmosphere)
    
    if escape_velocity_km_s < 3.0:
        # Too small to retain any significant atmosphere
        return 'NONE'
    
    # Very hot planets (T > 1500 K) - most volatiles lost
    if temperature_k > 1500:
        if escape_velocity_km_s > 8.0:
            # Massive enough to retain some heavy molecules
            return 'CO2_THIN'
        else:
            return 'NONE'
    
    # Hot planets (1000-1500 K) - steam atmospheres possible
    if temperature_k > 1000:
        if can_retain_atmosphere(escape_velocity_km_s, temperature_k, 18.0):  # H2O
            return 'H2O'
        else:
            return 'NONE'
    
    # Very close to star (<0.5 AU) - photoevaporation strips light atmospheres
    # Owen & Wu 2017: explains radius valley via atmospheric loss
    if orbital_distance_au < 0.5:
        # Can only retain heavy molecules (CO2, not H2/He or H2O)
        if can_retain_atmosphere(escape_velocity_km_s, temperature_k, 44.0):  # CO2
            if planet_type == 'SE':
                # Super-Earths close-in tend to have thick CO2 (runaway greenhouse)
                return 'CO2_THICK'
            else:
                return 'CO2_THIN'
        else:
            return 'NONE'
    
    # Moderate distance (0.5-2 AU) - habitable zone candidates
    if orbital_distance_au < 2.0:
        # Super-Earths can retain H2/He if massive enough
        if planet_type == 'SE' and escape_velocity_km_s > 15.0:
            # Lopez & Fortney 2014: SE can retain H/He envelopes
            if rng.uniform(0, 1) < 0.3:  # 30% chance of retaining primordial atmosphere
                return 'H2_HE'
        
        # Check for Earth-like N2/O2 (very rare without biology!)
        if planet_type == 'TE' and 0.8 < orbital_distance_au < 1.5:
            # In habitable zone, small chance of N2/O2 (implies life)
            if rng.uniform(0, 1) < 0.05:  # 5% chance - VERY rare
                return 'N2_O2'
        
        # Most common: CO2 or N2 atmospheres
        if can_retain_atmosphere(escape_velocity_km_s, temperature_k, 44.0):
            # Can retain CO2
            if temperature_k > 400:
                # Hot → thick CO2 (runaway greenhouse like Venus)
                return 'CO2_THICK'
            elif temperature_k > 250:
                # Temperate → thin CO2 or N2
                return 'N2' if rng.uniform(0, 1) < 0.4 else 'CO2_THIN'
            else:
                # Cold → thin CO2 (Mars-like)
                return 'CO2_THIN'
        elif can_retain_atmosphere(escape_velocity_km_s, temperature_k, 28.0):
            # Can retain N2 but not CO2 (unlikely but possible)
            return 'N2'
        else:
            return 'NONE'
    
    # Cold outer system (2-10 AU)
    if orbital_distance_au < 10.0:
        # Super-Earths can retain thick atmospheres
        if planet_type == 'SE':
            if escape_velocity_km_s > 12.0:
                return 'H2_HE'  # Mini-Neptune
            else:
                return 'N2_CH4'  # Titan-like
        
        # Terrestrial planets
        if can_retain_atmosphere(escape_velocity_km_s, temperature_k, 28.0):
            # N2 or N2/CH4 mix
            return 'N2_CH4' if temperature_k < 100 else 'N2'
        else:
            return 'NONE'
    
    # Very distant (>10 AU) - mostly no atmosphere or very thin
    if escape_velocity_km_s > 5.0:
        return 'N2_CH4'  # Pluto-like
    else:
        return 'NONE'


def calculate_scale_height_km(temperature_k: float, mean_molecular_mass_amu: float, 
                              surface_gravity_m_s2: float) -> float:
    """
    Calculate atmospheric scale height: H = kT / (μg)
    
    Scale height is the altitude over which pressure decreases by factor of e.
    
    Args:
        temperature_k: Atmospheric temperature in K
        mean_molecular_mass_amu: Mean molecular mass in amu
        surface_gravity_m_s2: Surface gravity in m/s²
    
    Returns:
        Scale height in km
    """
    k_B = 1.380649e-23  # Boltzmann constant (J/K)
    amu_to_kg = 1.66054e-27  # kg per amu
    
    if mean_molecular_mass_amu == 0 or surface_gravity_m_s2 == 0:
        return 0.0
    
    molecular_mass_kg = mean_molecular_mass_amu * amu_to_kg
    
    # H = kT / (μg)
    scale_height_m = (k_B * temperature_k) / (molecular_mass_kg * surface_gravity_m_s2)
    scale_height_km = scale_height_m / 1000
    
    return scale_height_km


def calculate_atmosphere_height_km(scale_height_km: float, 
                                   surface_pressure_bar: float) -> float:
    """
    Calculate atmosphere height (where pressure becomes negligible).
    
    Typically defined as 7-10 scale heights (pressure drops to ~0.001-0.00001 of surface).
    
    For thin atmospheres, use fewer scale heights.
    For thick atmospheres, use more.
    
    Args:
        scale_height_km: Atmospheric scale height in km
        surface_pressure_bar: Surface pressure in bars
    
    Returns:
        Atmosphere height in km
    """
    if scale_height_km == 0:
        return 0.0
    
    # Thin atmospheres: 5-7 scale heights
    if surface_pressure_bar < 0.01:
        return scale_height_km * 6
    
    # Medium atmospheres: 7-9 scale heights
    elif surface_pressure_bar < 10:
        return scale_height_km * 8
    
    # Thick atmospheres: 9-12 scale heights
    else:
        return scale_height_km * 10


def generate_atmosphere(rng: SeededRandom, planet_type: str, 
                       mass_kg: float, radius_km: float,
                       orbital_distance_au: float, temperature_k: float,
                       star_type: str = 'G') -> Dict[str, Any]:
    """
    Generate complete atmosphere properties for a planet.
    
    Args:
        rng: SeededRandom instance
        planet_type: Planet type code
        mass_kg: Planet mass in kg
        radius_km: Planet radius in km
        orbital_distance_au: Orbital distance in AU
        temperature_k: Equilibrium temperature in K
        star_type: Star spectral type
    
    Returns:
        Dictionary with atmosphere properties:
        - has_atmosphere (bool)
        - atmosphere_type (str)
        - mean_molecular_mass (float, amu)
        - surface_pressure_bar (float)
        - scale_height_km (float)
        - atmosphere_height_km (float)
    """
    # Calculate escape velocity
    escape_velocity_km_s = calculate_escape_velocity_km_s(mass_kg, radius_km)
    
    # Determine atmosphere type
    atmosphere_type = determine_atmosphere_type(
        rng, planet_type, orbital_distance_au, 
        escape_velocity_km_s, temperature_k, star_type
    )
    
    # Get mean molecular mass
    mean_molecular_mass = ATMOSPHERE_MOLECULAR_MASSES.get(atmosphere_type, 0.0)
    
    # No atmosphere case
    if atmosphere_type == 'NONE' or mean_molecular_mass == 0:
        return {
            'has_atmosphere': False,
            'atmosphere_type': 'NONE',
            'mean_molecular_mass': 0.0,
            'surface_pressure_bar': 0.0,
            'scale_height_km': 0.0,
            'atmosphere_height_km': 0.0,
        }
    
    # Generate surface pressure
    pressure_min, pressure_max = ATMOSPHERE_PRESSURE_RANGES.get(
        atmosphere_type, (0.5, 1.5)
    )
    surface_pressure_bar = rng.uniform(pressure_min, pressure_max)
    
    # Calculate surface gravity (needed for scale height)
    G = 6.67430e-11  # m³/kg/s²
    radius_m = radius_km * 1000
    surface_gravity_m_s2 = (G * mass_kg) / (radius_m ** 2)
    
    # Calculate scale height
    # Use temperature (could adjust for greenhouse effect, but equilibrium temp is fine)
    scale_height_km = calculate_scale_height_km(
        temperature_k, mean_molecular_mass, surface_gravity_m_s2
    )
    
    # Calculate atmosphere height
    atmosphere_height_km = calculate_atmosphere_height_km(
        scale_height_km, surface_pressure_bar
    )
    
    return {
        'has_atmosphere': True,
        'atmosphere_type': atmosphere_type,
        'mean_molecular_mass': mean_molecular_mass,
        'surface_pressure_bar': surface_pressure_bar,
        'scale_height_km': scale_height_km,
        'atmosphere_height_km': atmosphere_height_km,
    }


# Color Palette Generation (placeholder - will be expanded)
def generate_color_palette_from_temperature(temperature_k: float) -> Dict[str, Any]:
    """
    Generate color palette for a star based on temperature.
    
    TODO: Implement full color generation logic.
    For now, returns a basic structure.
    """
    # Blackbody color approximation
    if temperature_k > 30000:
        main_color = "#9BB0FF"  # Blue-white
    elif temperature_k > 10000:
        main_color = "#AABFFF"  # Blue
    elif temperature_k > 7500:
        main_color = "#CAD7FF"  # Blue-white
    elif temperature_k > 6000:
        main_color = "#FFF4E6"  # White
    elif temperature_k > 5200:
        main_color = "#FFF8DC"  # Yellow-white
    elif temperature_k > 3700:
        main_color = "#FFCC99"  # Orange
    else:
        main_color = "#FF6B6B"  # Red
    
    return {
        'main_color': main_color,
        'hex_colors': [main_color],
        'pattern_name': 'UNIFORM'
    }


def generate_color_palette_from_composition(composition: Dict[str, Any], temperature_k: float) -> Dict[str, Any]:
    """
    Generate color palette for a planet/moon based on composition.
    
    TODO: Implement full color generation logic based on composition variables.
    For now, returns a basic structure.
    """
    # Simple heuristic based on water and ice
    if composition.get('water_coverage', 0) > 0.5:
        main_color = "#4A90E2"  # Blue (ocean)
    elif composition.get('ice_content', 0) > 0.3:
        main_color = "#E0F2F1"  # Light blue (ice)
    elif composition.get('iron_content', 0) > 0.4:
        main_color = "#8B4513"  # Brown (iron-rich)
    else:
        main_color = "#A0A0A0"  # Gray (rocky)
    
    return {
        'main_color': main_color,
        'hex_colors': [main_color],
        'pattern_name': 'UNIFORM'
    }

