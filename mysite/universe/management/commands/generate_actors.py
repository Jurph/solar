"""
Management command to generate and display sample actors.

This command demonstrates how to create Pilot and Controller instances
with procedurally generated names, traits, and prompts.
"""

from django.core.management.base import BaseCommand
from mysite.universe.models.actor import Pilot, Controller
from mysite.universe.models.base import Location
from mysite.universe.models.ship import Ship


class Command(BaseCommand):
    help = 'Generate and display sample actors (pilots and controllers)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=5,
            help='Number of each type of actor to generate'
        )
    
    def handle(self, *args, **options):
        count = options['count']
        
        self.stdout.write(self.style.SUCCESS(f"Generating {count} pilots and {count} controllers..."))
        
        # Generate pilots
        self.stdout.write(self.style.NOTICE("\n=== PILOTS ==="))
        for i in range(count):
            # Get or create a ship for the pilot
            ships = Ship.objects.all()
            ship = ships[i] if i < len(ships) else Ship.create()
            
            # Create a pilot
            pilot = Pilot.create(ship=ship)
            
            # Display pilot information
            self.stdout.write(f"\nPilot: {pilot.name}")
            self.stdout.write(f"Ship: {ship.name}")
            self.stdout.write(f"Traits: {pilot.traits}")
            self.stdout.write(f"Years of Experience: {pilot.years_of_experience}")
            self.stdout.write(f"Prompt: {pilot.prompt}")
        
        # Generate controllers
        self.stdout.write(self.style.NOTICE("\n=== CONTROLLERS ==="))
        for i in range(count):
            # Get or create a location for the controller
            locations = Location.objects.all()
            location = locations[i] if i < len(locations) else None
            
            if location is None:
                self.stdout.write(self.style.WARNING(f"No location available for controller {i+1}. Skipping."))
                continue
            
            # Create a controller
            controller = Controller.create(location=location)
            
            # Display controller information
            self.stdout.write(f"\nController: {controller.name}")
            self.stdout.write(f"Location: {location.name}")
            self.stdout.write(f"Traits: {controller.traits}")
            self.stdout.write(f"Years of Experience: {controller.years_of_experience}")
            self.stdout.write(f"Prompt: {controller.prompt}")
        
        self.stdout.write(self.style.SUCCESS("\nActor generation complete!")) 