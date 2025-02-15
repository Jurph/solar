from django.core.management.base import BaseCommand
from mysite.universe.services.ship_generator import ShipGenerator

class Command(BaseCommand):
    help = 'Generate test ships throughout the universe'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=10,
                          help='Number of ships to generate')

    def handle(self, *args, **options):
        ship_count = options['count']
        generator = ShipGenerator()
        
        for i in range(ship_count):
            ship = generator.generate_ship()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created ship: {ship} at {ship.current_location.name}'
                )
            )