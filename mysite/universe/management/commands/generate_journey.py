from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from ...models import Ship, Location
from ...services.route_service import RouteService
from ...services.script_service import ScriptService

class Command(BaseCommand):
    help = 'Generate a radio script for moving a ship between locations'

    def add_arguments(self, parser):
        parser.add_argument('ship_id', type=int, help='ID of the ship to move')
        parser.add_argument('destination_id', type=int, help='ID of the destination')
        parser.add_argument('--move', action='store_true', 
                          help='Actually move the ship (default is just show script)')

    def handle(self, *args, **options):
        try:
            # Get objects
            ship = Ship.objects.get(pk=options['ship_id'])
            destination = Location.objects.get(pk=options['destination_id'])
            
            # Generate route and script
            route_service = RouteService()
            script_service = ScriptService()
            
            self.stdout.write(f"\nPlanning journey for {ship.name}")
            self.stdout.write(f"From: {ship.current_location.name}")
            self.stdout.write(f"To: {destination.name}\n")
            
            steps = route_service.plan_route(ship.current_location, destination)
            script = script_service.generate_journey_script(ship, steps)
            
            # Output the script
            for line in script:
                speaker = line.speaker
                if speaker == ship.name:
                    speaker = "SHIP"  # More readable than long ship names
                else:
                    speaker = "CONTROL"
                self.stdout.write(f"{speaker}: \"{line.message}\"")
            
            # Move the ship if requested
            if options['move']:
                ship.current_location = destination
                ship.save()
                self.stdout.write(
                    self.style.SUCCESS(f'\nShip {ship.name} moved to {destination.name}')
                )
            
        except ObjectDoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Unexpected error: {str(e)}'))