from django.core.management.base import BaseCommand
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.models import (
    Galaxy, StarSystem, Star, Planet, Moon, Station,
    Ship, BerthAssignment, Pilot, Controller
)
import os

class Command(BaseCommand):
    """Import a universe from an XML file."""
    help = "Import a universe from XML file"

    def add_arguments(self, parser):
        parser.add_argument("xml_file", type=str, help="Path to XML file to import")
        parser.add_argument("--dry-run", action="store_true", help="Validate XML without making changes")
        parser.add_argument("--clear", action="store_true", help="Clear existing universe data before import")

    def count_existing_objects(self):
        return {
            "galaxies": Galaxy.objects.count(),
            "systems": StarSystem.objects.count(),
            "stars": Star.objects.count(),
            "planets": Planet.objects.count(),
            "moons": Moon.objects.count(),
            "stations": Station.objects.count(),
        }

    def handle(self, *args, **options):
        xml_path = options["xml_file"]

        if not os.path.exists(xml_path):
            self.stderr.write(self.style.ERROR(f"File not found: {xml_path}"))
            return

        existing = self.count_existing_objects()
        total_existing = sum(existing.values())
        self.stdout.write("Current universe contains:")
        for name, count in existing.items():
            self.stdout.write(f"  {count} {name}")
        self.stdout.write(f"Total: {total_existing} objects\n")

        try:
            importer = UniverseImporter(xml_path)
            new_counts = importer.count_objects()
            total_new = sum(new_counts.values())

            self.stdout.write("New universe will contain:")
            for name, count in new_counts.items():
                self.stdout.write(f"  {count} {name}")
            self.stdout.write(f"Total: {total_new} objects\n")

            if options["dry_run"]:
                if options["clear"]:
                    self.stdout.write("\nIn a real run with --clear, the following would occur:")
                    self.stdout.write(f"  1. Delete {total_existing} existing objects")
                    self.stdout.write(f"  2. Import {total_new} new objects")
                else:
                    self.stdout.write(f"\nIn a real run, this would import {total_new} new objects")
                self.stdout.write("Dry run complete. No changes were made.")
                return

            if options["clear"]:
                confirm = input("\nThis will delete the existing universe and import the new one. Continue? (y/N): ")
                if confirm.lower() != "y":
                    self.stdout.write("Import cancelled.")
                    return

                self.stdout.write("Clearing existing universe data...")
                # Delete dependent objects first (in dependency order)
                # BerthAssignment references Station
                berth_count = BerthAssignment.objects.count()
                if berth_count > 0:
                    self.stdout.write(f"  Deleting {berth_count} berth assignments...")
                    BerthAssignment.objects.all().delete()
                
                # Ship references Location with PROTECT - must delete before Location
                ship_count = Ship.objects.count()
                if ship_count > 0:
                    self.stdout.write(f"  Deleting {ship_count} ships...")
                    Ship.objects.all().delete()
                
                # Pilot references Ship with SET_NULL - delete explicitly for cleanliness
                pilot_count = Pilot.objects.count()
                if pilot_count > 0:
                    self.stdout.write(f"  Deleting {pilot_count} pilots...")
                    Pilot.objects.all().delete()
                
                # Controller references Location with SET_NULL - delete before Location
                controller_count = Controller.objects.count()
                if controller_count > 0:
                    self.stdout.write(f"  Deleting {controller_count} controllers...")
                    Controller.objects.all().delete()
                
                # Now delete celestial hierarchy (bottom-up: stations, moons, planets, stars, systems, galaxies)
                station_count = Station.objects.count()
                if station_count > 0:
                    self.stdout.write(f"  Deleting {station_count} stations...")
                    Station.objects.all().delete()
                
                moon_count = Moon.objects.count()
                if moon_count > 0:
                    self.stdout.write(f"  Deleting {moon_count} moons...")
                    Moon.objects.all().delete()
                
                planet_count = Planet.objects.count()
                if planet_count > 0:
                    self.stdout.write(f"  Deleting {planet_count} planets...")
                    Planet.objects.all().delete()
                
                star_count = Star.objects.count()
                if star_count > 0:
                    self.stdout.write(f"  Deleting {star_count} stars...")
                    Star.objects.all().delete()
                
                system_count = StarSystem.objects.count()
                if system_count > 0:
                    self.stdout.write(f"  Deleting {system_count} star systems...")
                    StarSystem.objects.all().delete()
                
                galaxy_count = Galaxy.objects.count()
                if galaxy_count > 0:
                    self.stdout.write(f"  Deleting {galaxy_count} galaxies...")
                    Galaxy.objects.all().delete()
                
                self.stdout.write("Universe cleared successfully.")

            self.stdout.write("Importing universe...")
            importer.import_universe()
            self.stdout.write(self.style.SUCCESS("Universe imported successfully"))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Error importing universe: {exc}"))