from django.core.management.base import BaseCommand
from mysite.universe.models import Ship, Location
from mysite.universe.services.route_server import RouteService
from mysite.universe.services.llm_service import LLMService
import random

class Command(BaseCommand):
    help = 'Generate a narrative description for a random ship journey using LLM'

    def add_arguments(self, parser):
        parser.add_argument('--ship_id', type=int, help='Specific ship ID to use (optional)')
        parser.add_argument('--destination_id', type=int, help='Specific destination ID to use (optional)')
        parser.add_argument('--model', type=str, default='qwen2.5:0.5b', help='LLM model to use')
        parser.add_argument('--detailed', action='store_true', help='Generate more detailed descriptions')

    def handle(self, *args, **options):
        try:
            # Initialize services
            route_service = RouteService()
            llm_service = LLMService(model_name=options['model'])
            
            # Get ship (either specified or random)
            if options.get('ship_id'):
                ship = Ship.objects.get(id=options['ship_id'])
            else:
                ships = list(Ship.objects.all())
                if not ships:
                    raise ValueError("No ships available!")
                ship = random.choice(ships)
            
            # Get destination (either specified or random)
            if options.get('destination_id'):
                destination = Location.objects.get(id=options['destination_id'])
            else:
                destination = route_service.pick_random_destination(ship.current_location)
            
            # Generate the journey
            self.stdout.write(self.style.SUCCESS(f"\nPlanning journey for {ship.name}"))
            self.stdout.write(f"From: {ship.current_location.name}")
            self.stdout.write(f"To: {destination.name}\n")
            
            events = route_service.plan_route(ship.current_location, destination)
            
            # Display event table
            self.stdout.write(route_service.pretty_print_events(events))
            
            # Generate LLM description
            detail_level = "detailed" if options['detailed'] else "concise"
            self.stdout.write(self.style.SUCCESS(f"\nGenerating {detail_level} journey narrative..."))
            
            # Create prompt for the LLM
            system_prompt = f"""
            You are a space navigation AI that describes journeys between planets, moons, and stations.
            You use precise technical terminology while being engaging and descriptive.
            You focus on the physical sensations, visual elements, and technical details of space travel.
            Your descriptions should be {detail_level} and focus on the journey itself.
            """
            
            # Create a description of the journey for the LLM input
            journey_details = []
            for i, event in enumerate(events):
                origin = events[i-1].target.name if i > 0 else ship.current_location.name
                journey_details.append(f"{i+1}. {event.maneuver.name} from {origin} to {event.target.name} (Controller: {event.controller.name if event.controller else 'None'})")
            
            journey_text = "\n".join(journey_details)
            
            user_message = f"""
            Describe a journey for the ship '{ship.name}' with the following navigation events:
            
            {journey_text}
            
            The ship is carrying {ship.cargo} as cargo.
            """
            
            # Get response from LLM
            narrative = llm_service.generate_with_system_prompt(
                user_message=user_message,
                system_prompt=system_prompt,
                temperature=0.8,
                max_tokens=1024 if options['detailed'] else 512
            )
            
            # Print the narrative
            self.stdout.write(self.style.SUCCESS(f"\nJourney Narrative:"))
            self.stdout.write(narrative)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}')) 