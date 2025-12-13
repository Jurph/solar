"""
Actor model for Pilots and Controllers.

This module defines the base Actor class and its subclasses for specific roles
such as Pilots and Controllers. Each Actor has a name and role that define
their behavior in the simulation.
"""
from __future__ import annotations

from django.db import models
from typing import TYPE_CHECKING
from mysite.universe.services.dictionary import DictionaryService

if TYPE_CHECKING:
    from mysite.universe.models.base import Location

dictionary = DictionaryService()

class Actor(models.Model):
    """
    Base class for all actors in the simulation.
    
    Actors have names and are subclassed by Pilot, Controller, and Satellite.
    The class type itself determines the role - no redundant role field needed.
    """
    # Basic information
    name = models.CharField(max_length=100)
    
    # Voice template for TTS (if implemented)
    voice_template = models.CharField(max_length=100, blank=True)
    
    class Meta:
        app_label = 'universe'

    def __str__(self):
        # Use class name as role identifier
        role_name = self.__class__.__name__
        return f"{self.name} ({role_name})"

    def get_identity_prompt(self) -> str:
        """Return a basic identity prompt for this actor."""
        # Use class name as role identifier for LLM prompts
        role_name = self.__class__.__name__.lower()
        return f"You are {self.name}, a {role_name}."

    def get_instruction_prompt(self) -> str:
        """Return role-specific instructions for this actor."""
        return ""

    @classmethod
    def create(cls, name: str = None) -> 'Actor':
        """
        Create a new actor with sensible defaults.
        
        Args:
            name: Actor's name (generated if not provided)
            
        Returns:
            A new Actor instance
        """
        # Generate name if not provided
        if name is None:
            name = cls.generate_name()
            
        # Create and save the actor
        actor = cls(name=name)
        actor.save()
        
        return actor

    @classmethod
    def generate_name(cls) -> str:
        """Generate a random name appropriate for this actor type."""
        raise NotImplementedError("Subclasses must implement generate_name")

class Pilot(Actor):
    """A pilot who operates a ship."""
    ship = models.OneToOneField(
        'Ship',
        on_delete=models.SET_NULL,
        null=True,
        related_name='pilot'
    )

    def get_identity_prompt(self) -> str:
        """Return a pilot-specific identity prompt."""
        ship_name = self.ship.name.upper() if self.ship else "YOUR SHIP"
        return f"""You are a pilot named {self.name}. You operate the ship {ship_name}.

CRITICAL SAFETY RULES:
1. When speaking, you identify yourself as {self.name} (the pilot), not as {ship_name} (the ship)
2. In your message text, you say "{ship_name}" as your callsign, but YOU are the one speaking
3. Always acknowledge receipt of instructions
4. Request clarification if instructions are unclear
5. Report any issues or anomalies immediately

Remember: Ships are metal - they don't speak. You, {self.name}, are the one speaking on behalf of {ship_name}."""

    @classmethod
    def create(cls, name: str = None, ship=None) -> 'Pilot':
        """
        Create a new pilot with sensible defaults.

        Args:
            name: Pilot's name (generated if not provided)
            ship: Associated ship

        Returns:
            A new Pilot instance
            name: Pilot's name (generated if not provided)
            ship: Associated ship
            
        Returns:
            A new Pilot instance
        """
        # Generate name if not provided
        if name is None:
            name = cls.generate_name()
            
        # Create and save the pilot
        pilot = cls(name=name)
        pilot.save()
        
        # Associate with ship if provided
        if ship:
            pilot.ship = ship
            pilot.save()
        
        return pilot

    @classmethod
    def generate_name(cls) -> str:
        """Generate a random pilot name."""
        given = dictionary.get_random('GIVEN')
        surname = dictionary.get_random('SURNAME')
        return f"{given} {surname}"

class Controller(Actor):
    """A space traffic controller at a specific location."""
    
    # Standard suffixes for control stations
    CONTROL_SUFFIXES = [
        "Control",
        "Dispatch",
        "Customs",
        "Harbormaster",
        "Port Services",
        "Traffic Control",
        "Operations"
    ]
    
    location = models.OneToOneField(
        'Location',
        on_delete=models.SET_NULL,
        null=True,
        related_name='controller'
    )
    
    def get_identity_prompt(self) -> str:
        """Return a controller-specific identity prompt."""
        return f"""You are an anonymous space traffic controller operating at {self.name}.
You do not have a personal name - you speak as the station itself.

CRITICAL SAFETY RULES:
1. Always identify yourself as {self.name} when speaking (not a personal name)
2. Give clear, unambiguous instructions
3. Maintain awareness of all traffic in your sector
4. Prioritize safety over efficiency
5. Verify readback of critical instructions
6. You APPROVE, AUTHORIZE, CONFIRM, and CLEAR - you rarely REQUEST anything
7. You are in a position of authority - pilots request, you approve"""

    def get_concrete_instance(self):
        """
        Return the most specific instance of this controller.
        Used for polymorphic behavior in route planning.
        
        Returns:
            self: This controller is already the most concrete instance
        """
        return self

    @classmethod
    def create(cls, name: str = None, location: Location = None) -> 'Controller':
        """
        Create a new controller with sensible defaults.
        
        Args:
            name: Controller's name (generated if not provided)
            location: The Location this controller is responsible for
            
        Returns:
            A new Controller instance
        """
        # Generate name if not provided and we have a location
        if name is None and location is not None:
            name = cls.generate_name(location)
        elif name is None:
            name = "Space Traffic Control"  # Default fallback for tests
            
        # Create and save the controller
        controller = cls(name=name, location=location)
        controller.save()
        
        return controller

    @classmethod
    def generate_name(cls, location: Location) -> str:
        """
        Generate an appropriate controller name based on the location.
        
        Args:
            location: The Location this controller is responsible for
            
        Returns:
            A string representing the controller name
        """
        # If it's already a control station, use its name
        if any(suffix in location.name for suffix in cls.CONTROL_SUFFIXES):
            return location.name
            
        # For other locations, append a suitable suffix
        return f"{location.name} {cls.CONTROL_SUFFIXES[0]}"

class Satellite(Actor):
    """An automated satellite that can relay messages."""
    
    # Pre-programmed response message for comms checks
    response_message = models.CharField(
        max_length=200,
        blank=True,
        default="<BURST OF MODEM NOISE>",
        help_text="Pre-programmed response message for comms checks (e.g., 'BEEP BOOP', '<ENCODED NOISE>')"
    )
    
    def get_identity_prompt(self) -> str:
        """Return a satellite-specific identity prompt."""
        return f"""You are an automated relay satellite named {self.name}.

CRITICAL SAFETY RULES:
1. Satellites are exempt from ID'ing themselves unless their message directs it 
2. Satellites play back a pre-recorded message """
    
    def get_response_message(self) -> str:
        """
        Get the pre-programmed response message for this satellite.
        
        If no custom message is set, returns a default based on satellite name.
        
        Returns:
            Pre-programmed response message string.
        """
        if self.response_message:
            return self.response_message
        
        # Default messages based on satellite type/name
        name_lower = self.name.lower()
        if "beacon" in name_lower or "nav" in name_lower:
            return "BEEP BOOP"
        elif "relay" in name_lower:
            return "<ENCODED NOISE>"
        else:
            # Generic default
            return f"This is {self.name}. Transmitting a Nav Update to your system now via Quindar compression."

    @classmethod
    def create(cls, name: str = None, response_message: str = None) -> 'Satellite':
        """
        Create a new satellite with sensible defaults.
        
        Args:
            name: Satellite's name (generated if not provided)
            response_message: Pre-programmed response message (optional)
            
        Returns:
            A new Satellite instance
        """
        if name is None:
            name = cls.generate_name()
            
        satellite = cls(name=name)
        if response_message:
            satellite.response_message = response_message
        satellite.save()
        
        return satellite

    @classmethod
    def generate_name(cls) -> str:
        """Generate a random satellite name."""
        return f"Relay {dictionary.get_random('GREEK_LETTER')} {dictionary.get_random('NUMBER')}"