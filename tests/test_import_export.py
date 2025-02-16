import os
from django.conf import settings
from django.test import TestCase
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.export_xml import UniverseExporter

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
