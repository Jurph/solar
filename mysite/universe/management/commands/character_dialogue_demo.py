"""
Management command to demonstrate character-based dialogue between pilots and controllers.

Usage:
    python manage.py character_dialogue_demo
"""

import time
import random
from django.core.management.base import BaseCommand
from mysite.universe.services.llm_service import LLMService
from mysite.universe.models.navigation import ManeuverType

class Command(BaseCommand):
    help = 'Demonstrate character-based dialogue between pilots and controllers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            default="qwen2.5:1.5b",
            help='Specify the LLM model to use (default: qwen2.5:1.5b)',
        )
        parser.add_argument(
            '--scenario',
            type=str,
            choices=['departure', 'landing', 'emergency', 'random'],
            default='random',
            help='Specify the scenario type (default: random)',
        )
        parser.add_argument(
            '--turns',
            type=int,
            default=3,
            help='Number of conversation turns (default: 3)',
        )

    def handle(self, *args, **options):
        # Setup
        model_name = options['model']
        scenario = options['scenario']
        turns = options['turns']
        
        if scenario == 'random':
            scenario = random.choice(['departure', 'landing', 'emergency'])
        
        self.stdout.write(self.style.SUCCESS(f"Running {scenario} scenario with {model_name} for {turns} turns"))
        
        # Create LLM service
        try:
            llm = LLMService(model_name=model_name)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to initialize LLM service: {e}"))
            self.stdout.write(self.style.WARNING("Is Ollama running? Try starting it with 'ollama serve'"))
            return
        
        # Setup scenario parameters
        scenario_params = self._get_scenario_params(scenario)
        
        # Run the scenario
        self._run_scenario(llm, scenario_params, turns)
    
    def _get_scenario_params(self, scenario):
        """Set up parameters for the selected scenario."""
        # Common ship parameters
        ship_classes = [
            "Cargo Vessel", "Passenger Liner", "Research Vessel", 
            "Mining Hauler", "Courier", "Patrol Craft"
        ]
        ship_class = random.choice(ship_classes)
        
        ship_names = [
            "Stellar Horizon", "Pathfinder", "Aurora", "Constellation", 
            "Odyssey", "Polaris", "Orion's Pride", "Vanguard"
        ]
        ship_name = random.choice(ship_names)
        
        pilot_names = [
            "Captain Chen", "Captain Rodriguez", "Captain Sharma", 
            "Captain Kim", "Captain Patel", "Captain Okonkwo"
        ]
        pilot_name = random.choice(pilot_names)
        
        # Scenario-specific parameters
        if scenario == 'departure':
            controller_name = "Earth Orbital Control"
            controller_location = "Earth orbit"
            current_location = "Earth Spaceport"
            destination = "Mars Colony"
            cargo = "Medical supplies and equipment"
            maneuver = "departure"
            scenario_title = "Departure from Earth"
            situation = "You're preparing for departure from Earth to Mars Colony"
        
        elif scenario == 'landing':
            controller_name = "Mars Approach Control"
            controller_location = "Mars orbit"
            current_location = "Mars approach vector"
            destination = "Olympus City, Mars"
            cargo = "Scientific equipment and research samples"
            maneuver = "landing"
            scenario_title = "Landing on Mars"
            situation = "You're on final approach to Mars, preparing for landing"
        
        elif scenario == 'emergency':
            controller_name = "Luna Emergency Control"
            controller_location = "Lunar orbit"
            current_location = "Lunar space sector 7"
            destination = "Luna Base"
            cargo = "Critical life support components"
            maneuver = "emergency docking"
            scenario_title = "Emergency Docking at Luna Base"
            situation = "You're experiencing a minor life support malfunction and need emergency clearance"
        
        return {
            'ship_name': ship_name,
            'ship_class': ship_class,
            'pilot_name': pilot_name,
            'controller_name': controller_name,
            'controller_location': controller_location,
            'current_location': current_location,
            'destination': destination,
            'cargo': cargo,
            'maneuver': maneuver,
            'scenario_title': scenario_title,
            'situation': situation
        }
    
    def _run_scenario(self, llm, params, turns):
        """Run the dialogue scenario with the given parameters."""
        # Display scenario information
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS(f"SCENARIO: {params['scenario_title']}"))
        self.stdout.write("-"*80)
        self.stdout.write(f"Ship: {params['ship_name']} ({params['ship_class']})")
        self.stdout.write(f"Pilot: {params['pilot_name']}")
        self.stdout.write(f"Controller: {params['controller_name']}")
        self.stdout.write(f"Current Location: {params['current_location']}")
        self.stdout.write(f"Destination: {params['destination']}")
        self.stdout.write(f"Cargo: {params['cargo']}")
        self.stdout.write(f"Situation: {params['situation']}")
        self.stdout.write("="*80 + "\n")
        
        # Initial greeting from pilot
        self.stdout.write(self.style.SUCCESS("Starting conversation..."))
        time.sleep(1)
        
        pilot_greeting = llm.build_pilot_greeting(
            pilot_name=params['pilot_name'],
            ship_name=params['ship_name'],
            controller_name=params['controller_name'],
            maneuver=params['maneuver'],
            cargo=params['cargo']
        )
        
        self._print_message(params['ship_name'], pilot_greeting)
        
        # First controller response
        last_message = pilot_greeting
        
        # Conversation loop
        for i in range(turns):
            # Controller responds
            controller_response = llm.generate_in_character_response(
                character_type="controller",
                incoming_message=last_message,
                controller_name=params['controller_name'],
                controller_location=params['controller_location']
            )
            self._print_message(params['controller_name'], controller_response)
            last_message = controller_response
            
            # Pilot responds (unless we're at the last turn)
            if i < turns - 1:
                pilot_response = llm.generate_in_character_response(
                    character_type="pilot",
                    incoming_message=last_message,
                    pilot_name=params['pilot_name'],
                    ship_name=params['ship_name'],
                    ship_class=params['ship_class'],
                    cargo=params['cargo'],
                    current_location=params['current_location'],
                    destination=params['destination']
                )
                self._print_message(params['ship_name'], pilot_response)
                last_message = pilot_response
        
        # End scenario
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("End of conversation"))
        self.stdout.write("="*80)
    
    def _print_message(self, speaker, message):
        """Print a message with formatting and simulated typing."""
        self.stdout.write("\n")
        self.stdout.write(self.style.WARNING(f"{speaker}:"))
        
        # Simulate realistic typing effect
        for char in message:
            self.stdout.write(char, ending='')
            self.stdout.flush()
            time.sleep(0.005)  # Adjust for typing speed
        
        self.stdout.write("\n")
        time.sleep(0.5)  # Pause between messages 