from django.core.management.base import BaseCommand
from mysite.universe.models import Ship, Location 
from mysite.universe.models.navigation import UniverseGraph  # Add this import
from mysite.universe.services.route_server import RouteService  
from mysite.universe.services.script_server import ScriptService
from mysite.universe.models.scale import Scale, OrderedScale
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
        parser.add_argument('--llm', action='store_true',
                        help='Use LLM to generate more natural dialogue')
        parser.add_argument('--model', type=str, default='qwen2.5:0.5b',
                        help='LLM model to use (default: qwen2.5:0.5b)')

    def handle(self, *args, **options):
        try:
            debug = options['debug']  # Get debug flag
            use_llm = options['llm']  # Get LLM flag
            model = options.get('model', 'qwen2.5:0.5b')  # Get model name
            
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
            
            destination = self.pick_random_destination(ship.current_location)
            
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
            
            events = route_server.random_journey(ship)
            
            self.stdout.write(self.style.SUCCESS(f"\nGenerated journey for {ship.name}:"))
            # Display journey table
            self.stdout.write(route_server.pretty_print_events(events))
            
            # Generate script with optional LLM enhancement
            if use_llm:
                self.stdout.write(self.style.SUCCESS(f"\nGenerating enhanced journey script with {model}..."))
                script = script_server.generate_llm_script(events, ship.name, ship.cargo)
            else:
                self.stdout.write(self.style.SUCCESS(f"\nJourney Script:"))
                script = script_server.generate_script(events)
            
            self.stdout.write(script)
            
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

    def pick_random_destination(self, excluding: Location, max_scale: Scale = None) -> Location:
        all_locations = list(Location.objects.exclude(id=excluding.id))
        eligible = [
            loc for loc in all_locations
            if not max_scale or self._scale_order_value(loc.scale) <= self._scale_order_value(max_scale)
        ]
        if not eligible:
            raise ValueError("No available destination in the universe matching criteria.")
        return random.choice(eligible)
    
    def _scale_order_value(self, scale: str) -> int:
        """Convert a Scale string to its OrderedScale integer value"""
        from mysite.universe.models.scale import OrderedScale
        return OrderedScale(scale)