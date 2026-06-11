"""Regression tests for Solar issue #46.

These tests guard the Python 3.12-compatible Scale/TextChoices refactor:
Scale members must remain string codes for Django import/setup, while
OrderedScale keeps the existing ordering semantics.
"""

from django.test import TestCase

from mysite.universe.models.scale import OrderedScale, Scale


class TestScaleTextChoicesCompatibility(TestCase):
    """Regression coverage for the Scale enum refactor."""

    def test_scale_members_remain_string_codes(self):
        """Scale members keep two-character string values for TextChoices compatibility."""
        self.assertEqual(
            [member.value for member in Scale],
            ["GX", "SY", "SR", "PL", "MN", "SS"],
        )
        self.assertTrue(all(isinstance(member.value, str) for member in Scale))

    def test_ordered_scale_preserves_scale_ordering(self):
        """OrderedScale still sorts from smallest to largest scale."""
        ordered = [
            OrderedScale(Scale.STATION),
            OrderedScale(Scale.MOON),
            OrderedScale(Scale.PLANET),
            OrderedScale(Scale.STAR),
            OrderedScale(Scale.STARSYSTEM),
            OrderedScale(Scale.GALAXY),
        ]

        self.assertEqual(ordered, sorted(ordered))
        self.assertLess(OrderedScale(Scale.STATION), OrderedScale(Scale.PLANET))
        self.assertGreater(OrderedScale(Scale.GALAXY), OrderedScale(Scale.STAR))
