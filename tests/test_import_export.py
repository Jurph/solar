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
        pprint(counts)        # Optionally, you can also assert at least one system is imported.
        self.assertGreater(StarSystem.objects.count(), 0, "Expected at least one star system.")
        self.assertGreater(Planet.objects.count(), 0, "Expected at least one planet.")
        self.assertGreater(Moon.objects.count(), 0, "Expected at least one moon.")

    def test_import_export_roundtrip(self):
        """
        Export the imported universe to test_output.xml and compare it line by line
        with the original test_universe.xml.
        """
        # Define input and output file path
        input_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        output_file = os.path.join(settings.BASE_DIR, "xml", "test_output.xml")

        # Export the universe using our exporter (it should write to test_output.xml)
        exporter = UniverseExporter()
        xml_content = exporter.export_universe()
        with open(output_file, "w", encoding="utf-8") as f:
                f.write(xml_content)

        # Read both files and normalize by stripping trailing whitespace
        with open(input_file, "r", encoding="utf-8") as f:
            original_lines = [line.rstrip() for line in f.readlines()]

        with open(output_file, "r", encoding="utf-8") as f:
            exported_lines = [line.rstrip() for line in f.readlines()]

        # Compare the files line by line
        for idx, (orig, exp) in enumerate(zip(original_lines, exported_lines)):
            self.assertEqual(
                orig,
                exp,
                f"Difference on line {idx + 1}:\nExpected: {orig}\nGot:      {exp}"
            ) 

        # First, ensure the file lengths match
        self.assertEqual(
            len(original_lines),
            len(exported_lines),
            "The number of lines in the original and exported XML files differ."
        )
    
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
            "Object counts should be identical after second import (idempotency)"
        )
        
        # Verify names are the same (no duplicates)
        for obj_type in names_after_first:
            self.assertEqual(
                sorted(names_after_first[obj_type]),
                sorted(names_after_second[obj_type]),
                f"{obj_type} names should be identical after second import"
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
            "First and second import should produce same counts"
        )
        self.assertEqual(
            counts_list[1],
            counts_list[2],
            "Second and third import should produce same counts"
        )
        
        # All names should be identical
        for obj_type in names_list[0]:
            self.assertEqual(
                sorted(names_list[0][obj_type]),
                sorted(names_list[1][obj_type]),
                f"{obj_type} names should match between first and second import"
            )
            self.assertEqual(
                sorted(names_list[1][obj_type]),
                sorted(names_list[2][obj_type]),
                f"{obj_type} names should match between second and third import"
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
        stars_with_props = Star.objects.exclude(
            mass_kg__isnull=True
        ).exclude(
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
                    f"Star {star_name} mass should be identical after re-import"
                )
            if star_after.radius_km:
                self.assertEqual(
                    star_after.radius_km,
                    props["radius_km"],
                    f"Star {star_name} radius should be identical after re-import"
                )
            if star_after.temperature_k:
                self.assertEqual(
                    star_after.temperature_k,
                    props["temperature_k"],
                    f"Star {star_name} temperature should be identical after re-import"
                )