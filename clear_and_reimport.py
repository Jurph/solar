#!/usr/bin/env python
"""Clear existing universe data and reimport with idempotent importer."""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.conf import settings
from django.db import connection
from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet, Moon
from mysite.universe.models.station import Station
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.models.navigation import UniverseGraph

# Nuclear option: Just delete the database file and recreate
db_path = str(settings.DATABASES['default']['NAME'])

if os.path.exists(db_path):
    print(f"Deleting database file: {db_path}")
    os.remove(db_path)
    print("Database deleted.")
else:
    print(f"Database file not found at: {db_path}")

print("Running migrations...")
os.system("cd mysite && python manage.py migrate")

print("Universe cleared. Importing from test_universe.xml...")
xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
importer = UniverseImporter(xml_file)
importer.import_universe()
UniverseGraph.get_instance().rebuild_graph()

print("Universe imported successfully!")
print(f"  Planets: {Planet.objects.count()}")
print(f"  Moons: {Moon.objects.count()}")
print(f"  Stations: {Station.objects.count()}")

