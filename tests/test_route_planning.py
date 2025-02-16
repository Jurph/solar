import os
from pprint import pprint
from django.conf import settings
from django.test import TestCase
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.models.celestial import Moon, Planet, Star, StarSystem, Galaxy
from mysite.universe.models.station import Station

class RoutePlanningTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Load the test universe from our XML fixture into the test database.
        Now our tests can assume a known environment with star systems, stars,
        planets, and moons.
        """
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        importer = UniverseImporter(xml_file)
        importer.import_universe()
    
    def test_route_planning_debug(self):
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
        pprint(counts)

        print("\n---- Detailed Star Systems ----")
        for system in StarSystem.objects.all():
            print(f"System: {system.name} (ID: {system.pk})")
            stars = system.stars.all()
            if stars:
                for star in stars:
                    print(f"  Star: {star.name} (ID: {star.pk})")
                    planets = star.planets.all()
                    if planets:
                        for planet in planets:
                            print(f"    Planet: {planet.name} (ID: {planet.pk})")
                    moons = star.moons.all()
                    if moons:
                        for moon in moons:
                            print(f"    Moon: {moon.name} (ID: {moon.pk})")
            else:
                print("  No stars found!")
        print("==== End Debug Info ====")

        # Optionally, you can also assert at least one system is imported.
        self.assertGreater(StarSystem.objects.count(), 0, "Expected at least one star system.")