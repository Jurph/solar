from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from ...models import Ship, Location
from mysite.universe.services.route_server import RouteService
from mysite.universe.services.script_server import ScriptService
import random

class Command(BaseCommand):
    help = 'Generate a script for a random ship journey'

    def add_arguments(self, parser):
        parser.add_argument('--move', action='store_true', 
                          help='Actually move the ship (default is just show script)')
        parser.add_argument('--list', action='store_true',
                          help='List all ships and locations first')

    def handle(self, *args, **options):
        try:
            if options['list']:
                self.stdout.write("\nAvailable Ships:")
                for s in Ship.objects.all():
                    self.stdout.write(f"ID: {s.id} - {s.name} at {s.current_location.name}")
                
                self.stdout.write("\nAvailable Locations:")
                for l in Location.objects.all():
                    self.stdout.write(f"ID: {l.id} - {l.name}")
                
                self.stdout.write("\n")
                return

            # Get random ship and destination
            ships = list(Ship.objects.all())
            if not ships:
                raise ValueError("No ships available!")
            
            ship = random.choice(ships)
            
            locations = list(Location.objects.exclude(id=ship.current_location.id))
            if not locations:
                raise ValueError("No other locations available!")
            
            destination = random.choice(locations)
            
            # Generate route and script
            route_service = RouteService()
            script_service = ScriptService()
            
            self.stdout.write(self.style.SUCCESS(f"\nPlanning random journey for {ship.name}"))
            self.stdout.write(f"From: {ship.current_location.name}")
            self.stdout.write(f"To: {destination.name}\n")
            
            steps = route_service.plan_route(ship.current_location, destination)
            script = script_service.generate_journey_script(ship, steps)
            
            # Output the script
            for line in script:
                speaker = "SHIP" if line.speaker == ship.name else "CONTROL"
                self.stdout.write(f"{speaker}: \"{line.message}\"")
            
            # Move the ship if requested
            if options['move']:
                ship.current_location = destination
                ship.save()
                self.stdout.write(
                    self.style.SUCCESS(f'\nShip {ship.name} moved to {destination.name}')
                )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))

