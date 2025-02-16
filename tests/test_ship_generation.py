import string
from django.test import TestCase
from unittest.mock import patch
from mysite.universe.models.ship import Ship
from mysite.universe.models.base import Location
from mysite.universe.services.cargo_server import CargoService

class ShipGenerateNameTests(TestCase):
    def setUp(self):
        # Create a dummy station location so that Ship.create() can find it.
        # Assuming Location has a 'name' and a 'scale' field.
        self.station = Location.objects.create(
            name="Test Station",
            scale=Location.Scale.STATION  # Use the proper constant from Location.Scale
        )
        # Get the list of templates from the Ship model
        self.templates = Ship.NAME_TEMPLATES

    def make_expected(self, template):
        # Use Formatter to extract field names as done in the method
        formatter = string.Formatter()
        field_names = [field_name for _, field_name, _, _ in formatter.parse(template) if field_name]
        # For each field, the fake dictionary returns "TEST_<field>"
        return template.format(**{field: f"TEST_{field}" for field in field_names})

    @patch("mysite.universe.models.ship.random.choice")
    @patch("mysite.universe.services.dictionary.DictionaryService")
    def test_generate_name_templates(self, MockDictionaryService, mock_choice):
        # Setup the fake dictionary service: for every field, return "TEST_<field>"
        fake_instance = MockDictionaryService.return_value
        fake_instance.get_random.side_effect = lambda field: f"TEST_{field}"

        # For each template in the Ship model, validate name generation.
        for template in self.templates:
            # Force use of the specific template.
            mock_choice.return_value = template
            generated_name = Ship.generate_name()
            expected = self.make_expected(template)
            self.assertEqual(
                generated_name,
                expected,
                msg=f"Failed for template: {template}. Expected: {expected}, Got: {generated_name}"
            )

class ShipCreationTests(TestCase):
    def setUp(self):
        # Create a station location fixture necessary for Ship.create().
        self.station = Location.objects.create(
            name="Test Station",
            scale=Location.Scale.STATION
        )

    def test_create_ship_for_each_size(self):
        # Iterate over each size defined in the Ship model.
        sizes = [choice[0] for choice in Ship.Size.choices]
        for size in sizes:
            # The location is picked up by get_random_station (which will return self.station)
            ship = Ship.create(size=size)
            self.assertEqual(
                ship.size,
                size,
                msg=f"Ship created with size {ship.size} does not match expected size {size}."
            )
            self.assertIsNotNone(ship.cargo, msg="Ship cargo should not be None.")
            self.assertNotEqual(ship.cargo, "", msg="Ship cargo should not be an empty string.")

    def test_unload_and_reload_cargo(self):
        # Create a new ship and check its initial cargo.
        ship = Ship.create()
        original_cargo = ship.cargo
        self.assertIsNotNone(original_cargo, msg="Initial cargo should not be None.")

        # Unload the cargo – set it to None.
        ship.cargo = None
        ship.save()
        self.assertIsNone(ship.cargo, msg="After unloading, cargo should be set to None.")

        # Reload cargo using CargoService.
        cargo_service = CargoService()
        new_cargo = cargo_service.generate_cargo(ship)
        ship.cargo = new_cargo
        ship.save()

        self.assertIsNotNone(ship.cargo, msg="After reloading, cargo should not be None.")
        self.assertNotEqual(ship.cargo, "", msg="Reloaded cargo should not be an empty string.") 