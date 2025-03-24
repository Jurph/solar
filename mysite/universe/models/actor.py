
"""
Actor model for Pilots and Controllers.

This module defines the base Actor class and its subclasses for specific roles
such as Pilots and Controllers. Each Actor has a name and role that define
their behavior in the simulation.
"""
from django.db import models
from typing import List, Optional, Dict
from enum import Enum
from dataclasses import dataclass
import json
from mysite.universe.services.dictionary import DictionaryService

dictionary = DictionaryService()

class Actor(models.Model):
    """
    Base class for all actors in the simulation.
    
    Actors have names and roles that can be used to generate appropriate
    dialogue and behavior in the simulation.
    """
    class Role(str, Enum):
        PILOT = "PILOT"
        CONTROLLER = "CONTROLLER"
        SATELLITE = "SATELLITE"
        
    # Basic information
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=[(r.value, r.name) for r in Role])
    
    # Voice template for TTS (if implemented)
    voice_template = models.CharField(max_length=100, blank=True)
    
    class Meta:
        app_label = 'universe'

    def __str__(self):
        return f"{self.name} ({self.role})"

    def get_identity_prompt(self) -> str:
        """Return a basic identity prompt for this actor."""
        return f"You are {self.name}, a {self.role}."

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
        return f"""You are a pilot named {self.name}.

CRITICAL SAFETY RULES:
1. Always identify yourself and your ship when speaking
2. Always acknowledge receipt of instructions
3. Request clarification if instructions are unclear
4. Report any issues or anomalies immediately"""

    @classmethod
    def create(cls, name: str = None, ship: Optional['Ship'] = None) -> 'Pilot':
        """
        Create a new pilot with sensible defaults.
        
        Args:
            name: Pilot's name (generated if not provided)
            ship: Associated ship
            
        Returns:
            A new Pilot instance
        """
        # Generate name if not provided
        if name is None:
            name = cls.generate_name()
            
        # Create and save the pilot
        pilot = cls(name=name, role=Actor.Role.PILOT)
        pilot.save()
        
        # Associate with ship if provided
        if ship:
            pilot.ship = ship
            pilot.save()
        
        return pilot

    @classmethod
    def generate_name(cls) -> str:
        """Generate a random pilot name."""
        given = dictionary.get_random('GIVEN_NAME')
        surname = dictionary.get_random('SURNAME')
        return f"{given} {surname}"

class Controller(Actor):
    """A space traffic controller at a specific location."""
    
    location = models.OneToOneField(
        'Location',
        on_delete=models.SET_NULL,
        null=True,
        related_name='controller'
    )
    
    def get_identity_prompt(self) -> str:
        """Return a controller-specific identity prompt."""
        return f"""You are a space traffic controller at {self.name}.

CRITICAL SAFETY RULES:
1. Always identify yourself and your station when speaking
2. Give clear, unambiguous instructions
3. Maintain awareness of all traffic in your sector
4. Prioritize safety over efficiency
5. Verify readback of critical instructions"""

    @classmethod
    def create(cls, name: str = None, location: 'Location' = None) -> 'Controller':
        """
        Create a new controller with sensible defaults.
        
        Args:
            name: Controller's name (generated if not provided)
            location: The Location this controller is responsible for
            
        Returns:
            A new Controller instance
        """
        # Generate name if not provided
        if name is None:
            name = cls.generate_name()
            
        # Create and save the controller
        controller = cls(name=name, role=Actor.Role.CONTROLLER, location=location)
        controller.save()
        
        return controller

    @classmethod
    def generate_name(cls) -> str:
        """Generate a random controller name."""
        return f"{dictionary.get_random('LOCATION')} Control"

class Satellite(Actor):
    """An automated satellite that can relay messages."""
    
    def get_identity_prompt(self) -> str:
        """Return a satellite-specific identity prompt."""
        return f"""You are an automated relay satellite named {self.name}.

CRITICAL SAFETY RULES:
1. Always identify yourself when relaying messages
2. Maintain neutral, professional tone
3. Report any communication issues immediately"""

    @classmethod
    def create(cls, name: str = None) -> 'Satellite':
        """
        Create a new satellite with sensible defaults.
        
        Args:
            name: Satellite's name (generated if not provided)
            
        Returns:
            A new Satellite instance
        """
        if name is None:
            name = cls.generate_name()
            
        satellite = cls(name=name, role=Actor.Role.SATELLITE)
        satellite.save()
        
        return satellite

    @classmethod
    def generate_name(cls) -> str:
        """Generate a random satellite name."""
        return f"Relay {dictionary.get_random('GREEK_LETTER')} {dictionary.get_random('NUMBER')}"