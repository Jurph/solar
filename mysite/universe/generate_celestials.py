"""
Procedural generation utilities for celestial bodies.

This module provides seeded random number generation and helper methods
for generating celestial body properties deterministically.

Key Features:
- Seeded random number generation (deterministic)
- Weighted choices (for star types, planet types, etc.)
- Distribution helpers (normal, uniform, log-normal)
- Bin selection (discrete ranges)
- Deterministic hashing (for name-based entropy)
"""

import hashlib
import random
import math
from typing import List, Tuple, Optional, Dict, Any, Union
from dataclasses import dataclass


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

STAR_TYPE_RADIUS_RANGES = {  # In solar radii
    'O': (6.6, 10.0),
    'B': (1.8, 6.6),
    'A': (1.4, 1.8),
    'F': (1.15, 1.4),
    'G': (0.96, 1.15),
    'K': (0.7, 0.96),
    'M': (0.1, 0.7),
}

STAR_TYPE_DENSITY_RANGES = {  # In kg/m³
    'O': (0.1, 1.0),
    'B': (0.1, 10.0),
    'A': (0.1, 100.0),
    'F': (0.1, 1000.0),
    'G': (1000, 2000),
    'K': (2000, 5000),
    'M': (5000, 50000),
}


def generate_star_type(rng: SeededRandom) -> str:
    """Generate star type based on weighted distribution."""
    return weighted_choice_dict(rng, STAR_TYPE_WEIGHTS)


def generate_star_temperature(rng: SeededRandom, star_type: str) -> float:
    """Generate temperature for given star type."""
    temp_min, temp_max = STAR_TYPE_TEMPERATURE_RANGES.get(star_type, (3000, 6000))
    return rng.uniform(temp_min, temp_max)


def generate_star_radius_solar(rng: SeededRandom, star_type: str) -> float:
    """Generate radius in solar radii for given star type."""
    radius_min, radius_max = STAR_TYPE_RADIUS_RANGES.get(star_type, (0.5, 1.5))
    return rng.uniform(radius_min, radius_max)


def generate_star_density(rng: SeededRandom, star_type: str) -> float:
    """Generate density in kg/m³ for given star type."""
    density_min, density_max = STAR_TYPE_DENSITY_RANGES.get(star_type, (1000, 2000))
    return log_normal_clamped(rng, math.log(density_min), 0.5, density_min, density_max)


# Planet Type Generation
PLANET_TYPE_WEIGHTS_BY_DISTANCE = {
    # Distance ranges in AU
    (0.0, 0.5): {'SI': 0.7, 'TE': 0.3},  # Close to star: mostly silicate, some terrestrial
    (0.5, 1.5): {'TE': 0.6, 'SE': 0.3, 'SI': 0.1},  # Habitable zone: terrestrial/super-earth
    (1.5, 3.0): {'TE': 0.4, 'SE': 0.3, 'IG': 0.2, 'SI': 0.1},  # Outer terrestrial zone
    (3.0, 10.0): {'IG': 0.5, 'GG': 0.4, 'TE': 0.1},  # Ice/gas giant zone
    (10.0, 50.0): {'GG': 0.7, 'IG': 0.3},  # Outer gas giant zone
    (50.0, float('inf')): {'AB': 0.5, 'IG': 0.3, 'GG': 0.2},  # Kuiper belt / outer system
}


def generate_planet_type(rng: SeededRandom, orbital_distance_au: float) -> str:
    """
    Generate planet type based on orbital distance.
    
    Args:
        rng: SeededRandom instance
        orbital_distance_au: Orbital distance in AU
    
    Returns:
        Planet type code (SI, TE, SE, IG, GG, etc.)
    """
    # Find appropriate distance range
    for (dist_min, dist_max), weights in PLANET_TYPE_WEIGHTS_BY_DISTANCE.items():
        if dist_min <= orbital_distance_au < dist_max:
            return weighted_choice_dict(rng, weights)
    
    # Fallback for very distant planets
    return weighted_choice_dict(rng, {'GG': 0.5, 'IG': 0.3, 'AB': 0.2})


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
        'water_coverage': (0.0, 0.8),
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
}


def generate_composition(rng: SeededRandom, planet_type: str) -> Dict[str, Any]:
    """
    Generate composition values for a planet/moon based on type.
    
    Args:
        rng: SeededRandom instance
        planet_type: Planet type code (SI, TE, SE, IG, GG)
    
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


def calculate_hill_sphere_radius_km(planet_mass_kg: float, star_mass_kg: float, orbital_distance_au: float) -> float:
    """
    Calculate Hill sphere radius (maximum stable orbit distance).
    
    Args:
        planet_mass_kg: Planet mass in kg
        star_mass_kg: Star mass in kg
        orbital_distance_au: Orbital distance in AU
    
    Returns:
        Hill sphere radius in km
    """
    AU_TO_KM = 1.496e8  # 1 AU in km
    orbital_distance_km = orbital_distance_au * AU_TO_KM
    
    # r_H ≈ a * (m / (3*M))^(1/3)
    mass_ratio = planet_mass_kg / (3 * star_mass_kg)
    hill_radius_km = orbital_distance_km * (mass_ratio ** (1/3))
    
    return hill_radius_km


def calculate_geostationary_orbit_km(planet_mass_kg: float, planet_radius_km: float, rotation_period_hours: float) -> float:
    """
    Calculate geostationary orbit altitude.
    
    Args:
        planet_mass_kg: Planet mass in kg
        planet_radius_km: Planet radius in km
        rotation_period_hours: Rotation period in hours
    
    Returns:
        Geostationary orbit altitude in km (distance from planet center)
    """
    G = 6.67430e-11  # Gravitational constant
    KM_TO_M = 1000
    HOURS_TO_SECONDS = 3600
    
    planet_mass_kg_val = planet_mass_kg
    planet_radius_m = planet_radius_km * KM_TO_M
    rotation_period_s = rotation_period_hours * HOURS_TO_SECONDS
    
    # T = 2π * sqrt(r³ / GM)
    # r = (GM * T² / (4π²))^(1/3)
    r_m = ((G * planet_mass_kg_val * rotation_period_s**2) / (4 * math.pi**2)) ** (1/3)
    r_km = r_m / KM_TO_M
    
    return r_km


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

