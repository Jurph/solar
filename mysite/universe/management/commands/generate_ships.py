from django.core.management.base import BaseCommand
from mysite.universe.models.ship import Ship

class Command(BaseCommand):
    help = 'Generate test ships throughout the universe'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=10,
                          help='Number of ships to generate')

    def handle(self, *args, **options):
        ship_count = options['count']
        
        for i in range(ship_count):
            ship = Ship.create()  # Uses our new factory method
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created ship: {ship} at {ship.current_location.name} carrying {ship.cargo}'
                )
            )