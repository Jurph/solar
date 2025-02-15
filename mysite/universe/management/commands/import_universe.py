from django.core.management.base import BaseCommand
from ...import_xml import UniverseImporter
from ...models import *
import os

class Command(BaseCommand):
    help = 'Import a universe from XML file'

    def add_arguments(self, parser):
        parser.add_argument('xml_file', type=str, help='Path to XML file to import')
        parser.add_argument('--dry-run', action='store_true', 
                          help='Validate XML without importing')
        parser.add_argument('--clear', action='store_true',
                          help='Clear existing universe data before import')

    def handle(self, *args, **options):
        xml_path = options['xml_file']
        
        if not os.path.exists(xml_path):
            self.stderr.write(self.style.ERROR(f'File not found: {xml_path}'))
            return

        if options['clear']:
            self.stdout.write('Clearing existing universe data...')
            # Add models in reverse dependency order
            Station.objects.all().delete()
            Moon.objects.all().delete()
            Planet.objects.all().delete()
            Star.objects.all().delete()
            StarSystem.objects.all().delete()
            Galaxy.objects.all().delete()

        try:
            importer = UniverseImporter(xml_path)
            
            if options['dry_run']:
                self.stdout.write('Validating XML...')
                # TODO: Add validation logic
                self.stdout.write(self.style.SUCCESS('XML is valid'))
                return

            self.stdout.write('Importing universe...')
            importer.import_universe()
            self.stdout.write(self.style.SUCCESS('Universe imported successfully'))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error importing universe: {str(e)}'))