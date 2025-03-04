"""
Actor model for Pilots and Controllers with personality traits and voice templates.

This module defines the Actor class, which represents characters in the simulation
such as Pilots and Controllers. Each Actor has a name, role, personality traits,
and a prompt that can be used for LLM-based dialogue generation.
"""

from django.db import models
import random
from typing import List
from ..services.dictionary import DictionaryService


class Actor(models.Model):
    """
    Base class for all character types in the simulation.
    
    Actors have names, roles, personality traits, and prompts that can be used
    for LLM-based dialogue generation. This class can be subclassed to create
    specific types of actors like Pilots and Controllers.
    """
    
    class Role(models.TextChoices):
        """Defines the possible roles an Actor can have."""
        PILOT = 'PILOT', 'Pilot'
        CONTROLLER = 'CONTROLLER', 'Controller'
        SATELLITE = 'SATELLITE', 'Satellite'
    
    # Basic information
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=Role.choices)
    
    # Personality traits (stored as comma-separated values)
    traits = models.CharField(max_length=200, blank=True)
    years_of_experience = models.IntegerField(default=0)
    
    # Voice model configuration (for future TTS integration)
    voice_template = models.CharField(max_length=100, blank=True)
    
    # Prompt for LLM-based dialogue generation
    prompt_identity = models.TextField(blank=True)
    prompt_instructions = models.TextField(blank=True)    
    prompt = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"
    
    @property
    def traits_list(self) -> List[str]:
        """Returns the traits as a list of strings."""
        if not self.traits:
            return []
        return [trait.strip() for trait in self.traits.split(',')]
    
    @traits_list.setter
    def traits_list(self, traits: List[str]):
        """Sets the traits from a list of strings."""
        self.traits = ', '.join(traits)
    
    def build_prompt(self) -> str:
        """
        Builds and returns a prompt for LLM-based dialogue generation.
        """
        prompt_parts = [
            self.get_identity_prompt(),
            self.get_traits_prompt(),
            self.get_experience_prompt(),
            self.get_instruction_prompt()
        ]
        self.prompt = " ".join(filter(None, prompt_parts))
        return self.prompt

    def get_identity_prompt(self) -> str:
        """Return the identity prompt specific to the actor's role."""
        raise NotImplementedError("Subclasses should implement this method.")

    def get_instruction_prompt(self) -> str:
        """Return the instruction prompt specific to the actor's role."""
        raise NotImplementedError("Subclasses should implement this method.")

    def get_traits_prompt(self) -> str:
        """Return a formatted string of traits."""
        if self.traits_list:
            return f"You are {', '.join(self.traits_list)}."
        return ""

    def get_experience_prompt(self) -> str:
        """Return a formatted string of years of experience."""
        if self.years_of_experience > 0:
            return f"You have {self.years_of_experience} years of experience."
        return ""

    @classmethod
    def generate_name(cls) -> str:
        """Generate a random name using the dictionary service."""
        raise NotImplementedError("Subclasses should implement this method.")
    
    @classmethod
    def generate_traits(cls, num_traits: int = 2) -> List[str]:
        """Generate a list of random personality traits."""
        dictionary = DictionaryService()
        return dictionary.get_multiple('TRAIT', num_traits)
    
    @classmethod
    def generate_years_experience(cls) -> int:
        """Generate random years of experience between 1 and 30."""
        return random.randint(1, 30)
    
    @classmethod
    def create(cls, *, name: str = None, role: str = None, 
            traits: List[str] = None, years_of_experience: int = None) -> 'Actor':
        """
        Create a new Actor instance with sensible defaults.
        
        Args:
            name: Actor name (generated if not provided)
            role: Actor role (randomly selected if not provided)
            traits: List of personality traits (generated if not provided)
            years_of_experience: Years of experience (generated if not provided)
            
        Returns:
            The created and saved Actor instance.
        """
        if role is None:
            role = random.choice(cls.Role.choices)[0]
        
        if name is None:
            name = cls.generate_name()
        
        actor = cls(name=name, role=role)
        
        # Generate traits if not provided
        if traits is None:
            try:
                traits = cls.generate_traits()
            except Exception:
                # Fallback if 'TRAIT' wordlist is not available
                traits = ['professional']
        
        actor.traits_list = traits
        
        # Generate years of experience if not provided
        if years_of_experience is None:
            years_of_experience = cls.generate_years_experience()
        
        actor.years_of_experience = years_of_experience
        
        # Build the prompt
        actor.build_prompt()
        
        actor.save()
        return actor


class Pilot(Actor):
    """
    Specialized Actor class for pilots.
    
    Pilots operate ships and communicate with controllers during navigation.
    """
    
    ship = models.OneToOneField('Ship', on_delete=models.SET_NULL, null=True, related_name='pilot')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = self.Role.PILOT
    
    def get_identity_prompt(self) -> str:
        return f"You are a pilot named {self.name}."

    def get_instruction_prompt(self) -> str:
        return ("You follow the rules of radio communication, keeping messages clear, concise, and professional. "
                "Always address the controller by their station (e.g. 'Control' or 'Mars Control') and then identify your ship by name before making a request. "
                "Keep each request simple and clear. Keep it short and to the point.")

    @classmethod
    def generate_name(cls) -> str:
        dictionary = DictionaryService()
        surname = dictionary.get_random('SURNAME')
        return f"Captain {surname}"

    @classmethod
    def create(cls, *, ship=None, **kwargs) -> 'Pilot':
        """
        Create a new Pilot instance with sensible defaults.
        
        Args:
            ship: The ship this pilot operates (optional)
            **kwargs: Other arguments to pass to Actor.create()
            
        Returns:
            The created and saved Pilot instance.
        """
        kwargs['role'] = cls.Role.PILOT
        kwargs['prompt_identity'] = f"You are a pilot named {kwargs['name']}."
        kwargs['prompt_instructions'] = """You follow the rules of radio communication, keeping messages clear, concise, and professional. 
                                Always address the controller by their station (e.g. 'Control' or 'Mars Control') and then identify your ship by name before making a request.
                                Keep each request simple and clear. Nobody but rookies improvises out here! Keep it short and to the point. 
                                On the other hand, superstitions die hard out here, and wishing someone 'good luck' or 'safe travels' is fine.
                                But **mostly**, be brief!!
                                You are here to safely get the mission done. 
                                """
        
        pilot = super().create(**kwargs)
        
        if ship:
            pilot.ship = ship
            pilot.save()
        
        return pilot


class Controller(Actor):
    """
    Specialized Actor class for controllers.
    
    Controllers manage traffic at stations, planets, or other locations.
    """
    
    location = models.ForeignKey('base.Location', on_delete=models.CASCADE, related_name='controllers')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = self.Role.CONTROLLER
    
    def get_identity_prompt(self) -> str:
        return "You are a space traffic controller."

    def get_instruction_prompt(self) -> str:
        return ("You strictly follow the rules of radio communication, keeping messages clear, concise, and professional. "
                "Always address the ship (not the pilot!) and then identify your station (e.g. 'Control' or 'Mars Control') before granting permission. "
                "Approvals are simple: 'Approved,' 'Cleared', 'Authorized', or 'Go for orbit'. Keep each approval simple and clear.")

    @classmethod
    def generate_name(cls) -> str:
        return ""

    @classmethod
    def create(cls, *, location=None, **kwargs) -> 'Controller':
        """
        Create a new Controller instance with sensible defaults.
        
        Args:
            location: The location this controller manages (required)
            **kwargs: Other arguments to pass to Actor.create()
            
        Returns:
            The created and saved Controller instance.
        """
        kwargs['role'] = cls.Role.CONTROLLER
        kwargs['prompt_identity'] = "You are a space traffic controller."
        kwargs['prompt_instructions'] = """You strictly follow the rules of radio communication, keeping messages clear, concise, and professional. 
                                Always address the ship (not the pilot!) and then identify your station (e.g. 'Control' or 'Mars Control') before granting permission.
                                Approvals are simple: "Approved," "Cleared", "Authorized", or even "Go for orbit". 
                                Keep each approval simple and clear. Nobody but rookies improvises out here! Keep it short and to the point. 
                                On the other hand, superstitions die hard out here, and wishing someone 'good luck' or 'safe travels' as they depart is fine.
                                But **mostly**, be brief!!
                                """
        controller = super().create(**kwargs)
        
        if location:
            controller.location = location
            controller.save()
        
        return controller


class Satellite(Actor):
    """
    Specialized Actor class for satellites.
    
    Satellites are for unit testing. They always say "BEEP BOOP" and that is all. 
    """
    
    location = models.ForeignKey('base.Location', on_delete=models.CASCADE, related_name='satellites')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = self.Role.SATELLITE
    
    def get_identity_prompt(self) -> str:
        return "You are an automated satellite with a simple embedded system."

    def get_instruction_prompt(self) -> str:
        return "You respond with 'BEEP BOOP' and nothing else."

    @classmethod
    def generate_name(cls) -> str:
        return ""

    @classmethod
    def create(cls, *, location=None, **kwargs) -> 'Satellite':
        # A satellite is a controller with a different prompt
        kwargs['role'] = cls.Role.SATELLITE
        kwargs['prompt_identity'] = "You are an automated satellite with a simple embedded system."
        kwargs['prompt_instructions'] = "You respond with 'BEEP BOOP' and nothing else."
        satellite = super().create(**kwargs)
        
        return satellite