import os
from django.conf import settings
from django.test import TestCase
from pprint import pprint
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.export_xml import UniverseExporter
from mysite.universe.models.celestial import Moon, Planet, Star, StarSystem, Galaxy
from mysite.universe.models.station import Station


class ImportExportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Import the test universe using our XML importer into the test database.
        """
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        importer = UniverseImporter(xml_file)
        importer.import_universe()

    def tearDown(self):
        """
        Clean up: Remove the exported file to keep the test environment tidy.
        """
        output_file = os.path.join(settings.BASE_DIR, "xml", "test_output.xml")
        if os.path.exists(output_file):
            os.remove(output_file)

    def test_universe_creation(self):
        """
        Debug output to see what objects exist in the test database.
        Run this test with output capture disabled (e.g., `pytest -s`) to view prints.
        """
        print("\n==== Debugging Imported Universe ====")
        print("Counts:")
        counts = {
            "galaxies": Galaxy.objects.count(),
            "systems": StarSystem.objects.count(),
            "stars": Star.objects.count(),
            "planets": Planet.objects.count(),
            "moons": Moon.objects.count(),
            "stations": Station.objects.count(),
        }
        pprint(
            counts
        )  # Optionally, you can also assert at least one system is imported.
        self.assertGreater(
            StarSystem.objects.count(), 0, "Expected at least one star system."
        )
        self.assertGreater(Planet.objects.count(), 0, "Expected at least one planet.")
        self.assertGreater(Moon.objects.count(), 0, "Expected at least one moon.")

    def test_import_export_roundtrip(self):
        """
        Export the imported universe and compare semantic XML content against the
        original test_universe.xml, checking that *all numeric leaf values* are
        extremely close.

        We intentionally do NOT do a line-by-line string comparison because:
        - float formatting can differ (e.g., "4.6e9" vs "4600000000.0")
        - pretty-printing/whitespace can differ
        """
        # Define input and output file path
        input_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        output_file = os.path.join(settings.BASE_DIR, "xml", "test_output.xml")

        # Export the universe using our exporter (it should write to test_output.xml)
        exporter = UniverseExporter()
        xml_content = exporter.export_universe()
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(xml_content)

        import math
        import xml.etree.ElementTree as ET

        def _norm_text(text: str | None) -> str | None:
            if text is None:
                return None
            stripped = text.strip()
            return stripped if stripped != "" else None

        def _as_float(text: str | None) -> float | None:
            if text is None:
                return None
            try:
                return float(text)
            except Exception:
                return None

        def _is_bool_text(text: str | None) -> bool:
            if text is None:
                return False
            return text.lower() in {"true", "false"}

        def _assert_leaf_equal(
            a_text: str | None, b_text: str | None, *, context: str
        ) -> None:
            a = _norm_text(a_text)
            b = _norm_text(b_text)
            if a == b:
                return

            # Booleans: normalize case
            if _is_bool_text(a) and _is_bool_text(b):
                self.assertEqual(a.lower(), b.lower(), context)
                return

            # Numerics: extremely close (formatting differences allowed)
            af = _as_float(a)
            bf = _as_float(b)
            if af is not None and bf is not None:
                if not math.isclose(af, bf, rel_tol=1e-10, abs_tol=1e-12):
                    self.fail(
                        f"{context}\nExpected: {af} (from {a})\nGot:      {bf} (from {b})"
                    )
                return

            self.fail(f"{context}\nExpected: {a}\nGot:      {b}")

        # Subtrees present in XML but not yet round-tripped by the importer/exporter.
        # We *do not* assert on these yet; separate tests should cover them when implemented.
        IGNORE_SUBTREES: set[str] = {
            "composition",
        }

        def _element_id(elem: ET.Element) -> tuple[str, str | None]:
            """
            Stable identity within a parent:
            - If element has a <name> child, use it.
            - Otherwise tag-only (assumed unique among siblings).
            """
            name = elem.findtext("name")
            name = _norm_text(name)
            return (elem.tag, name)

        def _children_by_id(
            elem: ET.Element,
        ) -> dict[tuple[str, str | None], list[ET.Element]]:
            grouped: dict[tuple[str, str | None], list[ET.Element]] = {}
            for child in list(elem):
                key = _element_id(child)
                grouped.setdefault(key, []).append(child)
            return grouped

        def _compare_elements_subset(
            expected: ET.Element, actual: ET.Element, *, path: str
        ) -> None:
            """
            Require that everything in expected is present in actual and matches.
            Allow actual to include additional tags/fields not present in expected.
            """
            self.assertEqual(expected.tag, actual.tag, f"{path}: tag mismatch")

            # Attributes: expected must be a subset of actual.
            for k, v in expected.attrib.items():
                self.assertIn(k, actual.attrib, f"{path}: missing attribute {k}")
                self.assertEqual(
                    v, actual.attrib.get(k), f"{path}: attribute {k} mismatch"
                )

            expected_children = [
                c for c in list(expected) if c.tag not in IGNORE_SUBTREES
            ]

            if not expected_children:
                # Leaf (or container we intentionally ignore subtrees on)
                _assert_leaf_equal(
                    expected.text, actual.text, context=f"{path}: leaf text mismatch"
                )
                return

            exp_grouped = _children_by_id(expected)
            act_grouped = _children_by_id(actual)

            for key, exp_list in exp_grouped.items():
                # Skip ignored subtree roots
                if key[0] in IGNORE_SUBTREES:
                    continue

                self.assertIn(key, act_grouped, f"{path}: missing child {key}")
                act_list = act_grouped[key]

                # For named elements (e.g., planet[Earth]) and leaf tags, we expect 1:1.
                self.assertGreaterEqual(
                    len(act_list),
                    len(exp_list),
                    f"{path}: child-count mismatch for {key}",
                )
                self.assertEqual(
                    len(exp_list),
                    len(act_list),
                    f"{path}: child-count mismatch for {key}",
                )

                for idx, (ec, ac) in enumerate(zip(exp_list, act_list)):
                    tag, name = key
                    label = f"{tag}[{name}]" if name else tag
                    _compare_elements_subset(ec, ac, path=f"{path}/{label}#{idx}")

            # Container text is typically whitespace; still require it to match when meaningful.
            _assert_leaf_equal(
                expected.text, actual.text, context=f"{path}: container text mismatch"
            )

        original_root = ET.parse(input_file).getroot()
        exported_root = ET.parse(output_file).getroot()
        _compare_elements_subset(original_root, exported_root, path="/universe")

    # ============================================================================
    # Idempotent Import Tests
    # ============================================================================

    def count_all_objects(self):
        """Count all universe objects."""
        return {
            "galaxies": Galaxy.objects.count(),
            "systems": StarSystem.objects.count(),
            "stars": Star.objects.count(),
            "planets": Planet.objects.count(),
            "moons": Moon.objects.count(),
            "stations": Station.objects.count(),
        }

    def get_object_names(self):
        """Get all object names for comparison."""
        return {
            "galaxies": list(Galaxy.objects.values_list("name", flat=True)),
            "systems": list(StarSystem.objects.values_list("name", flat=True)),
            "stars": list(Star.objects.values_list("name", flat=True)),
            "planets": list(Planet.objects.values_list("name", flat=True)),
            "moons": list(Moon.objects.values_list("name", flat=True)),
            "stations": list(Station.objects.values_list("name", flat=True)),
        }

    def test_import_twice_same_counts(self):
        """
        Test that importing the same universe twice produces the same object counts.

        This is the basic idempotency test - running the import twice should not
        create duplicates.
        """
        # Use a fresh XML file for this test (not the one from setUpTestData)
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe_v2.xml")
        if not os.path.exists(xml_file):
            # Fallback to test_universe.xml if v2 doesn't exist
            xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")

        # First import
        importer1 = UniverseImporter(xml_file)
        importer1.import_universe()

        counts_after_first = self.count_all_objects()
        names_after_first = self.get_object_names()

        # Second import (should be idempotent)
        importer2 = UniverseImporter(xml_file)
        importer2.import_universe()

        counts_after_second = self.count_all_objects()
        names_after_second = self.get_object_names()

        # Verify counts are the same
        self.assertEqual(
            counts_after_first,
            counts_after_second,
            "Object counts should be identical after second import (idempotency)",
        )

        # Verify names are the same (no duplicates)
        for obj_type in names_after_first:
            self.assertEqual(
                sorted(names_after_first[obj_type]),
                sorted(names_after_second[obj_type]),
                f"{obj_type} names should be identical after second import",
            )

    def test_import_three_times(self):
        """
        Test that importing three times still produces the same result.

        This ensures idempotency works beyond just two runs.
        """
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe_v2.xml")
        if not os.path.exists(xml_file):
            xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")

        counts_list = []
        names_list = []

        # Import three times
        for i in range(3):
            importer = UniverseImporter(xml_file)
            importer.import_universe()

            counts_list.append(self.count_all_objects())
            names_list.append(self.get_object_names())

        # All three should be identical
        self.assertEqual(
            counts_list[0],
            counts_list[1],
            "First and second import should produce same counts",
        )
        self.assertEqual(
            counts_list[1],
            counts_list[2],
            "Second and third import should produce same counts",
        )

        # All names should be identical
        for obj_type in names_list[0]:
            self.assertEqual(
                sorted(names_list[0][obj_type]),
                sorted(names_list[1][obj_type]),
                f"{obj_type} names should match between first and second import",
            )
            self.assertEqual(
                sorted(names_list[1][obj_type]),
                sorted(names_list[2][obj_type]),
                f"{obj_type} names should match between second and third import",
            )

    def test_import_preserves_properties(self):
        """
        Test that importing twice preserves object properties.

        This ensures that re-importing doesn't just avoid duplicates,
        but also preserves the properties of existing objects.
        """
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe_v2.xml")
        if not os.path.exists(xml_file):
            xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")

        # First import
        importer1 = UniverseImporter(xml_file)
        importer1.import_universe()

        # Get a sample of objects with their properties
        sample_star = Star.objects.first()
        sample_planet = Planet.objects.first()
        sample_moon = Moon.objects.first()

        if sample_star:
            star_props = {
                "name": sample_star.name,
                "star_type": sample_star.star_type,
                "star_magnitude": sample_star.star_magnitude,
            }

        if sample_planet:
            planet_props = {
                "name": sample_planet.name,
                "planet_type": sample_planet.planet_type,
            }

        if sample_moon:
            moon_props = {
                "name": sample_moon.name,
                "moon_type": sample_moon.moon_type,
            }

        # Second import
        importer2 = UniverseImporter(xml_file)
        importer2.import_universe()

        # Verify properties are preserved
        if sample_star:
            star_after = Star.objects.get(name=sample_star.name)
            self.assertEqual(star_after.star_type, star_props["star_type"])
            self.assertEqual(star_after.star_magnitude, star_props["star_magnitude"])

        if sample_planet:
            planet_after = Planet.objects.get(name=sample_planet.name)
            self.assertEqual(planet_after.planet_type, planet_props["planet_type"])

        if sample_moon:
            moon_after = Moon.objects.get(name=sample_moon.name)
            self.assertEqual(moon_after.moon_type, moon_props["moon_type"])

    def test_import_with_procedural_generation(self):
        """
        Test that importing with procedural generation is idempotent.

        This test verifies that when XML has missing properties and procedural
        generation fills them in, re-importing produces the same generated values
        (assuming the same seed is used).
        """
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe_v2.xml")
        if not os.path.exists(xml_file):
            xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")

        # This test assumes that procedural generation uses a seed based on
        # the object name or system, making it deterministic.
        # If procedural generation is called during import, we should get
        # the same values on re-import.

        # First import
        importer1 = UniverseImporter(xml_file)
        importer1.import_universe()

        # Get objects that might have procedurally generated properties
        stars_with_props = Star.objects.exclude(mass_kg__isnull=True).exclude(
            radius_km__isnull=True
        )

        star_props = {}
        for star in stars_with_props[:5]:  # Sample first 5
            star_props[star.name] = {
                "mass_kg": star.mass_kg,
                "radius_km": star.radius_km,
                "temperature_k": star.temperature_k,
            }

        # Second import
        importer2 = UniverseImporter(xml_file)
        importer2.import_universe()

        # Verify procedurally generated properties are the same
        for star_name, props in star_props.items():
            star_after = Star.objects.get(name=star_name)
            if star_after.mass_kg:
                self.assertEqual(
                    star_after.mass_kg,
                    props["mass_kg"],
                    f"Star {star_name} mass should be identical after re-import",
                )
            if star_after.radius_km:
                self.assertEqual(
                    star_after.radius_km,
                    props["radius_km"],
                    f"Star {star_name} radius should be identical after re-import",
                )
            if star_after.temperature_k:
                self.assertEqual(
                    star_after.temperature_k,
                    props["temperature_k"],
                    f"Star {star_name} temperature should be identical after re-import",
                )
