"""
Characterization tests for mysite.universe.palettes (issue #54).

These pin the palette contract that PhysicalBody.color_palette JSON storage
relies on: {main_color, hex_colors, pattern_name} with UNIFORM single-color
palettes, star colors keyed to blackbody temperature bands, and body colors
keyed to dominant composition.
"""

from django.test import SimpleTestCase

from mysite.universe.models.celestial import ColorPalette
from mysite.universe.palettes import (
    generate_color_palette_from_composition,
    generate_color_palette_from_temperature,
)


class StarPaletteTests(SimpleTestCase):
    def test_temperature_bands_map_to_spectral_colors(self):
        expected = [
            (40000, "#9BB0FF"),  # O-class blue-white
            (15000, "#AABFFF"),  # B-class blue
            (8000, "#CAD7FF"),  # A-class blue-white
            (6500, "#FFF4E6"),  # F-class white
            (5500, "#FFF8DC"),  # G-class yellow-white
            (4000, "#FFCC99"),  # K-class orange
            (3000, "#FF6B6B"),  # M-class red
        ]
        for temperature_k, color in expected:
            with self.subTest(temperature_k=temperature_k):
                palette = generate_color_palette_from_temperature(temperature_k)
                self.assertEqual(palette["main_color"], color)

    def test_band_boundaries_belong_to_the_cooler_band(self):
        # Thresholds are strict greater-than: an exact boundary temperature
        # renders as the cooler class.
        self.assertEqual(
            generate_color_palette_from_temperature(6000)["main_color"],
            "#FFF8DC",
            "6000K is G-class (yellow-white), not F-class",
        )
        self.assertEqual(
            generate_color_palette_from_temperature(3700)["main_color"],
            "#FF6B6B",
            "3700K is M-class (red), not K-class",
        )

    def test_palette_shape_round_trips_through_color_palette_dataclass(self):
        palette = generate_color_palette_from_temperature(5778)
        restored = ColorPalette.from_dict(palette)
        self.assertEqual(restored.main_color, palette["main_color"])
        self.assertEqual(restored.hex_colors, [palette["main_color"]])
        self.assertEqual(restored.pattern_name, "UNIFORM")


class BodyPaletteTests(SimpleTestCase):
    def test_composition_precedence_ocean_ice_iron_rock(self):
        cases = [
            ({"water_coverage": 0.9}, "#4A90E2"),  # ocean wins
            ({"ice_content": 0.9}, "#E0F2F1"),  # ice
            ({"iron_content": 0.9}, "#8B4513"),  # iron-rich
            ({}, "#A0A0A0"),  # bare rock fallback
        ]
        for composition, color in cases:
            with self.subTest(composition=composition):
                palette = generate_color_palette_from_composition(
                    composition, temperature_k=300
                )
                self.assertEqual(palette["main_color"], color)

    def test_water_outranks_ice_and_iron_when_all_present(self):
        palette = generate_color_palette_from_composition(
            {"water_coverage": 0.6, "ice_content": 0.9, "iron_content": 0.9},
            temperature_k=300,
        )
        self.assertEqual(palette["main_color"], "#4A90E2")

    def test_threshold_edges_do_not_trigger_dominant_color(self):
        # Thresholds are strict: exactly-at-threshold compositions fall through.
        palette = generate_color_palette_from_composition(
            {"water_coverage": 0.5, "ice_content": 0.3, "iron_content": 0.4},
            temperature_k=300,
        )
        self.assertEqual(palette["main_color"], "#A0A0A0")

    def test_palette_shape_round_trips_through_color_palette_dataclass(self):
        palette = generate_color_palette_from_composition(
            {"water_coverage": 0.9}, temperature_k=288
        )
        restored = ColorPalette.from_dict(palette)
        self.assertEqual(restored.main_color, palette["main_color"])
        self.assertEqual(restored.hex_colors, [palette["main_color"]])
        self.assertEqual(restored.pattern_name, "UNIFORM")
