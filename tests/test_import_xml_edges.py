"""
Targeted tests for uncovered branches in import_xml.py.

Covers:
- count_objects() (lines 24-32)
- galactic_z_ly in import_system() (line 64)
- planet update branch when already exists (lines 227-231)
- planet physical properties: orbital_distance_au, mass_kg, is_tidally_locked (229, 231, 258)
- planet atmosphere update branch when already exists (lines 305, 307, 309)
- moon atmosphere update branch when already exists (lines 315-337)
"""

import tempfile
import os

from django.test import TestCase

from mysite.universe.import_xml import UniverseImporter


# ---------------------------------------------------------------------------
# Minimal XML helpers
# ---------------------------------------------------------------------------

_XML_HEADER = '<?xml version="1.0" encoding="utf-8"?>'


def _minimal_galaxy(content: str) -> str:
    return f"""{_XML_HEADER}
<universe>
  <galaxy>
    <name>TestGalaxy</name>
    <type>spiral</type>
    <size>large</size>
    {content}
  </galaxy>
</universe>"""


def _system_with(content: str) -> str:
    return f"""
  <system>
    <name>TestSystem</name>
    {content}
    <star>
      <name>TestStar</name>
      <type>G</type>
      <magnitude>5.0</magnitude>
    </star>
  </system>"""


def _star_with_planet(planet_xml: str) -> str:
    return f"""
  <system>
    <name>PlanetSystem</name>
    <star>
      <name>PlanetStar</name>
      <type>G</type>
      <magnitude>5.0</magnitude>
      {planet_xml}
    </star>
  </system>"""


def _star_with_moon(moon_xml: str) -> str:
    return f"""
  <system>
    <name>MoonSystem</name>
    <star>
      <name>MoonStar</name>
      <type>G</type>
      <magnitude>5.0</magnitude>
      <planet>
        <name>MoonPlanet</name>
        <type>rocky</type>
        {moon_xml}
      </planet>
    </star>
  </system>"""


def _write_xml(content: str) -> str:
    """Write XML to a temp file and return the path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".xml", delete=False, encoding="utf-8"
    )
    tmp.write(content)
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# count_objects()
# ---------------------------------------------------------------------------


class TestCountObjects(TestCase):
    def test_counts_all_object_types(self):
        xml = _minimal_galaxy(_system_with("<galactic_x_ly>1.0</galactic_x_ly>"))
        path = _write_xml(xml)
        try:
            importer = UniverseImporter(path)
            counts = importer.count_objects()
        finally:
            os.unlink(path)

        self.assertIn("galaxies", counts)
        self.assertIn("systems", counts)
        self.assertIn("stars", counts)
        self.assertEqual(counts["galaxies"], 1)
        self.assertEqual(counts["systems"], 1)

    def test_counts_zero_when_empty(self):
        xml = f"{_XML_HEADER}<universe></universe>"
        path = _write_xml(xml)
        try:
            importer = UniverseImporter(path)
            counts = importer.count_objects()
        finally:
            os.unlink(path)
        self.assertEqual(counts["galaxies"], 0)
        self.assertEqual(counts["planets"], 0)


# ---------------------------------------------------------------------------
# galactic_z_ly in import_system()
# ---------------------------------------------------------------------------


class TestImportSystemGalacticZ(TestCase):
    def test_galactic_z_ly_is_imported(self):
        xml = _minimal_galaxy(
            _system_with(
                "<galactic_x_ly>1.0</galactic_x_ly>"
                "<galactic_y_ly>2.0</galactic_y_ly>"
                "<galactic_z_ly>3.5</galactic_z_ly>"
            )
        )
        path = _write_xml(xml)
        try:
            importer = UniverseImporter(path)
            importer.import_universe()
            from mysite.universe.models.celestial import StarSystem

            sys = StarSystem.objects.get(name="TestSystem")
            self.assertAlmostEqual(float(sys.galactic_z_ly), 3.5)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Planet update branch (already exists) + physical properties
# ---------------------------------------------------------------------------


_PLANET_FULL_XML = """
<planet>
  <name>FullPlanet</name>
  <type>rocky</type>
  <orbital_distance_au>1.0</orbital_distance_au>
  <mass_kg>5.972e24</mass_kg>
  <radius_km>6371.0</radius_km>
  <density_kg_m3>5515.0</density_kg_m3>
  <orbital_period_days>365.25</orbital_period_days>
  <rotation_period_hours>24.0</rotation_period_hours>
  <axial_tilt_deg>23.5</axial_tilt_deg>
  <is_tidally_locked>false</is_tidally_locked>
  <albedo>0.30</albedo>
  <equilibrium_temperature_k>255.0</equilibrium_temperature_k>
  <orbital_eccentricity>0.017</orbital_eccentricity>
  <orbital_inclination_deg>0.0</orbital_inclination_deg>
</planet>"""


class TestImportPlanetBranches(TestCase):
    def test_planet_physical_properties_imported(self):
        """All hasattr branches for planet physical properties are covered."""
        xml = _minimal_galaxy(_star_with_planet(_PLANET_FULL_XML))
        path = _write_xml(xml)
        try:
            importer = UniverseImporter(path)
            importer.import_universe()
            from mysite.universe.models.celestial import Planet

            planet = Planet.objects.get(name="FullPlanet")
            self.assertAlmostEqual(float(planet.orbital_distance_au), 1.0)
            self.assertAlmostEqual(float(planet.mass_kg), 5.972e24, delta=1e20)
        finally:
            os.unlink(path)

    def test_planet_update_branch_on_second_import(self):
        """Importing a planet that already exists hits the 'not created' update branch."""
        xml = _minimal_galaxy(_star_with_planet(_PLANET_FULL_XML))
        path = _write_xml(xml)
        try:
            # First import creates the planet
            UniverseImporter(path).import_universe()
            # Second import triggers the update branch
            UniverseImporter(path).import_universe()
            from mysite.universe.models.celestial import Planet

            self.assertEqual(Planet.objects.filter(name="FullPlanet").count(), 1)
        finally:
            os.unlink(path)

    def test_planet_is_tidally_locked_true(self):
        """is_tidally_locked=true is parsed and stored."""
        planet_xml = """
<planet>
  <name>TidalPlanet</name>
  <type>rocky</type>
  <is_tidally_locked>true</is_tidally_locked>
</planet>"""
        xml = _minimal_galaxy(_star_with_planet(planet_xml))
        path = _write_xml(xml)
        try:
            UniverseImporter(path).import_universe()
            from mysite.universe.models.celestial import Planet

            planet = Planet.objects.get(name="TidalPlanet")
            self.assertTrue(planet.is_tidally_locked)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Planet atmosphere update branch (already exists)
# ---------------------------------------------------------------------------

_PLANET_WITH_ATMO = """
<planet>
  <name>AtmoPlanet</name>
  <type>rocky</type>
  <atmosphere>
    <atmosphere_type>STANDARD</atmosphere_type>
    <atmosphere_height_km>100.0</atmosphere_height_km>
    <surface_pressure_bar>1.0</surface_pressure_bar>
    <scale_height_km>8.5</scale_height_km>
  </atmosphere>
</planet>"""


class TestImportPlanetAtmosphereBranches(TestCase):
    def test_atmosphere_update_branch_on_second_import(self):
        """Importing a planet+atmosphere twice hits the atmosphere 'not created' update."""
        xml = _minimal_galaxy(_star_with_planet(_PLANET_WITH_ATMO))
        path = _write_xml(xml)
        try:
            UniverseImporter(path).import_universe()
            UniverseImporter(path).import_universe()
            from mysite.universe.models.physics import Atmosphere
            from mysite.universe.models.celestial import Planet
            from django.contrib.contenttypes.models import ContentType

            planet = Planet.objects.get(name="AtmoPlanet")
            ct = ContentType.objects.get_for_model(Planet)
            atmo = Atmosphere.objects.get(content_type=ct, object_id=planet.id)
            self.assertEqual(atmo.atmosphere_type, "STANDARD")
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Moon atmosphere update branch (already exists)
# ---------------------------------------------------------------------------

_MOON_WITH_ATMO = """
<moon>
  <name>AtmoMoon</name>
  <moon_type>rocky</moon_type>
  <atmosphere>
    <atmosphere_type>THIN</atmosphere_type>
    <atmosphere_height_km>50.0</atmosphere_height_km>
    <surface_pressure_bar>0.01</surface_pressure_bar>
    <scale_height_km>11.0</scale_height_km>
  </atmosphere>
</moon>"""


class TestImportMoonAtmosphereBranches(TestCase):
    def test_moon_atmosphere_update_branch_on_second_import(self):
        """Importing a moon+atmosphere twice hits the moon atmosphere update branch."""
        xml = _minimal_galaxy(_star_with_moon(_MOON_WITH_ATMO))
        path = _write_xml(xml)
        try:
            UniverseImporter(path).import_universe()
            UniverseImporter(path).import_universe()
            from mysite.universe.models.physics import Atmosphere
            from mysite.universe.models.celestial import Moon
            from django.contrib.contenttypes.models import ContentType

            moon = Moon.objects.get(name="AtmoMoon")
            ct = ContentType.objects.get_for_model(Moon)
            atmo = Atmosphere.objects.get(content_type=ct, object_id=moon.id)
            self.assertEqual(atmo.atmosphere_type, "THIN")
        finally:
            os.unlink(path)
