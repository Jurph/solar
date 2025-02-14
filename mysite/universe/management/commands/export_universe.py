import click
from django.core.management.base import BaseCommand
from universe.export_xml import UniverseExporter
import os
from typing import Optional

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
        
        # Check if file exists and handle --force
        if os.path.exists(output_path) and not options['force']:
            if not click.confirm(f'File {output_path} exists. Overwrite?'):
                self.stdout.write('Export cancelled.')
                return

        try:
            exporter = UniverseExporter()
            
            # Handle selective exports
            if options['galaxy']:
                xml_content = exporter.export_single_galaxy(options['galaxy'])
            elif options['system']:
                xml_content = exporter.export_single_system(options['system'])
            else:
                xml_content = exporter.export_universe()

            # Handle formatting options
            if options['compact']:
                xml_content = exporter.compact_output(xml_content)
                
            # Add template documentation if requested
            if options['template']:
                xml_content = exporter.add_template_docs(xml_content)
            
            # Write the file
            with click.open_file(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
                
            self.stdout.write(
                self.style.SUCCESS(f'Universe exported successfully to {output_path}')
            )
            
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f'Error exporting universe: {str(e)}')
            )