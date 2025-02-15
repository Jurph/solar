from django.core.management.base import BaseCommand
from ...services.traffic_control import TrafficControlService

class Command(BaseCommand):
    help = 'Run the space traffic simulation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--duration',
            type=int,
            default=None,
            help='How long to run simulation (time units)'
        )
        parser.add_argument(
            '--ships-per-location',
            type=int,
            default=3,
            help='Number of ships to generate at each major location'
        )


    def handle(self, *args, **options):
        service = TrafficControlService()
        
        # Generate and register ships
        service.populate_universe(options['ships_per_location'])
            
        # Run simulation
        service.engine.run(duration=options['duration'])