import os
from django.core.management.base import BaseCommand
from ...export_xml import UniverseExporter

class Command(BaseCommand):
    help = 'Export universe to XML file'

    def add_arguments(self, parser):
        parser.add_argument('output_file', type=str, help='Path to output XML file')
        parser.add_argument('--compact', action='store_true', 
                          help='Output without pretty printing')
        parser.add_argument('--galaxy', type=str,
                          help='Export only this specific galaxy')
        parser.add_argument('--system', type=str,
                          help='Export only this specific star system')
        parser.add_argument('--template', action='store_true',
                          help='Add commented examples and documentation')
        parser.add_argument('--force', '-f', action='store_true',
                          help='Overwrite existing file without asking')

    def handle(self, *args, **options):
        output_path = options['output_file']
        backup_path = None  # Initialize to None
        
        # Check if file exists
        if os.path.exists(output_path):
            if not options['force']:
                self.stderr.write(f'Error: File {output_path} already exists.')
                self.stderr.write('Use --force to overwrite existing file.')
                return
            else:
                # Even with force, let's make a backup
                backup_path = f"{output_path}.bak"
                i = 1
                while os.path.exists(backup_path):
                    backup_path = f"{output_path}.bak.{i}"
                    i += 1
                self.stdout.write(f'Creating backup at {backup_path}')
                os.rename(output_path, backup_path)

        try:
            exporter = UniverseExporter()
            
            # Count what we're about to export
            galaxy_filter = options.get('galaxy')
            system_filter = options.get('system')
            
            if galaxy_filter:
                self.stdout.write(f'Exporting galaxy: {galaxy_filter}')
            if system_filter:
                self.stdout.write(f'Exporting system: {system_filter}')
            
            # Generate the XML
            xml_content = exporter.export_universe()
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            self.stdout.write(self.style.SUCCESS(
                f'Universe exported successfully to {output_path}'
            ))
            if backup_path:  # Only mention backup if we created one
                self.stdout.write(f'Backup saved at {backup_path}')
                
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error exporting universe: {str(e)}'))
            # If we failed and have a backup, try to restore it
            if backup_path and os.path.exists(backup_path):
                os.rename(backup_path, output_path)
                self.stderr.write('Restored original file from backup')