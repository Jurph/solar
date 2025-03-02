from django.core.management.base import BaseCommand
from mysite.universe.models import Ship, Location
from mysite.universe.models.navigation import UniverseGraph  # Add this import
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
        parser.add_argument('--debug', action='store_true',
                        help='Show debug information')

    def handle(self, *args, **options):
        try:
            debug = options['debug']  # Get debug flag
            
            if options['list']:
                self._list_universe()
                return

            # Initialize universe graph
            if debug:
                self.stdout.write("\nInitializing Universe Graph...")
                
            universe = UniverseGraph.get_instance()
            universe.rebuild_graph()  # This will now show debug output from navigation.py

            # Get random ship and destination
            ships = list(Ship.objects.all())
            if not ships:
                raise ValueError("No ships available!")
            
            ship = random.choice(ships)
            locations = list(Location.objects.exclude(id=ship.current_location.id))
            if not locations:
                raise ValueError("No other locations available!")
            
            destination = random.choice(locations)
            
            if debug:
                self.stdout.write("\nSelected objects:")
                self.stdout.write(f"Ship: {ship.name} (ID: {ship.id})")
                self.stdout.write(f"Current location: {ship.current_location.name} (ID: {ship.current_location.id})")
                self.stdout.write(f"Destination: {destination.name} (ID: {destination.id})")
            
            # Generate route and script
            route_server = RouteService()  # Fixed naming convention
            script_server = ScriptService()
            
            self.stdout.write(self.style.SUCCESS(f"\nPlanning random journey for {ship.name}"))
            self.stdout.write(f"From: {ship.current_location.name}")
            self.stdout.write(f"To: {destination.name}\n")
            
            steps = route_server.plan_route(ship.current_location, destination)
            print(steps)
            
            if debug:
                self.stdout.write("\nNavigation steps:")
                for i, step in enumerate(steps, 1):
                    self.stdout.write(f"{i}. {step.maneuver.value} towards {step.target.name}")
            
            script = script_server.script_handler(ship, steps)
            script += '' # For now we just store the script; later on we'll push it as an event 
            
            # Move the ship if requested
            if options['move']:
                ship.current_location = destination
                ship.save()
                self.stdout.write(
                    self.style.SUCCESS(f'\nShip {ship.name} moved to {destination.name}')
                )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))

    def _list_universe(self):
        """Helper to list all ships and locations"""
        self.stdout.write("\nAvailable Ships:")
        for s in Ship.objects.all():
            self.stdout.write(f"ID: {s.id} - {s.name} at {s.current_location.name}")
        
        self.stdout.write("\nAvailable Locations:")
        for l in Location.objects.all():
            self.stdout.write(
                f"ID: {l.id} - {l.name} " + 
                f"(orbits: {l.orbits.name if l.orbits else 'nothing'})"
            )
        self.stdout.write("\n")