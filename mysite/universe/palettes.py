"""
Color palette generation for celestial bodies.

Extracted from procedural_generation.py (issue #54) so palette policy has a
focused home separate from physical/orbital generation rules.

Both generators return dicts matching the `ColorPalette` dataclass shape in
`mysite.universe.models.celestial` ({main_color, hex_colors, pattern_name}),
which is how `PhysicalBody.color_palette` stores palettes as JSON.

Current palettes are deliberately simple: a single blackbody-approximation
color for stars and a dominant-composition color for planets/moons, both with
the UNIFORM pattern. Richer palettes (banded gas giants, multi-color
gradients, non-uniform patterns) are tracked separately — see issue #54's
follow-up ticket rather than a TODO in this module.
"""

from typing import Any, Dict


def generate_color_palette_from_temperature(temperature_k: float) -> Dict[str, Any]:
    """
    Generate a star's color palette from its effective temperature.

    Uses a coarse blackbody color approximation over the main-sequence
    temperature range: hotter stars render blue-white, cooler stars orange
    to red.
    """
    if temperature_k > 30000:
        main_color = "#9BB0FF"  # Blue-white (O-class)
    elif temperature_k > 10000:
        main_color = "#AABFFF"  # Blue (B-class)
    elif temperature_k > 7500:
        main_color = "#CAD7FF"  # Blue-white (A-class)
    elif temperature_k > 6000:
        main_color = "#FFF4E6"  # White (F-class)
    elif temperature_k > 5200:
        main_color = "#FFF8DC"  # Yellow-white (G-class)
    elif temperature_k > 3700:
        main_color = "#FFCC99"  # Orange (K-class)
    else:
        main_color = "#FF6B6B"  # Red (M-class)

    return {
        "main_color": main_color,
        "hex_colors": [main_color],
        "pattern_name": "UNIFORM",
    }


def generate_color_palette_from_composition(
    composition: Dict[str, Any], temperature_k: float
) -> Dict[str, Any]:
    """
    Generate a planet or moon's color palette from its surface composition.

    Picks a single dominant color by composition precedence: ocean water,
    then ice, then iron-rich rock, then generic rock. `temperature_k` is
    accepted for signature stability with the star generator but does not
    yet influence the palette.
    """
    if composition.get("water_coverage", 0) > 0.5:
        main_color = "#4A90E2"  # Blue (ocean)
    elif composition.get("ice_content", 0) > 0.3:
        main_color = "#E0F2F1"  # Light blue (ice)
    elif composition.get("iron_content", 0) > 0.4:
        main_color = "#8B4513"  # Brown (iron-rich)
    else:
        main_color = "#A0A0A0"  # Gray (rocky)

    return {
        "main_color": main_color,
        "hex_colors": [main_color],
        "pattern_name": "UNIFORM",
    }
