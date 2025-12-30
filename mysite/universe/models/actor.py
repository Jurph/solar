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
        cls.assign_audio_profile(actor)
        return actor

    @classmethod
    def assign_audio_profile(cls, actor: 'Actor'):
        """
        Ensure the actor has an AudioProfile with a voice_template if available.
        Base Actor uses a simple default (no room tone).
        """
        from mysite.universe.models.audio_profile import AudioProfile
        import random
        import glob
        from pathlib import Path
        from django.core.exceptions import ObjectDoesNotExist

        base_dir = Path(__file__).resolve().parents[3]
        generated_dir = base_dir / "audio" / "voices" / "generated"

        try:
            profile = actor.audio_profile
        except ObjectDoesNotExist:
            profile = None
        profile = profile or AudioProfile.create_default_for_actor(actor)

        # Only assign voice_template if not already set (idempotent)
        vp = profile.get_voice_params() or {}
        if not vp.get("voice_template"):
            candidates = sorted(glob.glob(str(generated_dir / "*.wav")))
            if candidates:
                voice_path = random.choice(candidates)
                voice_template = Path(voice_path).stem
                profile.set_voice_template(voice_template)

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
1. Flight protocol is handled procedurally. You do not need to identify yourself or your ship.
2. As a pilot, you defer to the controller's judgment; you REQUEST, but you never APPROVE.
3. When you receive instructions, you CONFIRM that you have received them by reading back the relevant details. 

Pay close attention to the examples and counterexamples provided. """

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
        cls.assign_audio_profile(pilot)
        return pilot

    @classmethod
    def generate_name(cls) -> str:
        """Generate a random pilot name."""
        given = dictionary.get_random('GIVEN')
        surname = dictionary.get_random('SURNAME')
        return f"{given} {surname}"

    @classmethod
    def assign_audio_profile(cls, actor: 'Pilot'):
        from mysite.universe.models.audio_profile import AudioProfile
        import random
        import glob
        from pathlib import Path
        from django.core.exceptions import ObjectDoesNotExist
        # project root (e.g., .../solar)
        base_dir = Path(__file__).resolve().parents[3]
        generated_dir = base_dir / "audio" / "voices" / "generated"

        try:
            profile = actor.audio_profile
        except ObjectDoesNotExist:
            profile = None
        profile = profile or AudioProfile.create_default_for_actor(actor)
        
        # Only assign voice_template if not already set (idempotent)
        vp = profile.get_voice_params() or {}
        if not vp.get("voice_template"):
            candidates = sorted(glob.glob(str(generated_dir / "*.wav")))
            if candidates:
                voice_path = random.choice(candidates)
                voice_template = Path(voice_path).stem
                profile.set_voice_template(voice_template)

        # Room tone based on ship size (always update - ship size may change)
        ship_size = 'medium'
        if hasattr(actor, 'ship') and actor.ship and actor.ship.size:
            ship_size = actor.ship.size.lower()
        if ship_size == 's' or 'small' in ship_size:
            rt = "room_tone_small"
        elif ship_size == 'l' or 'large' in ship_size or 'freighter' in ship_size:
            rt = "room_tone_large"
        else:
            rt = "room_tone_medium"
        profile.set_room_tone_preset(rt)

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
1. Give clear, unambiguous instructions
2. You APPROVE, AUTHORIZE, CONFIRM, and CLEAR - you rarely REQUEST anything
3. You are in a position of authority - pilots request, and then you approve"""

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
        cls.assign_audio_profile(controller)
        
        return controller

    @classmethod
    def assign_audio_profile(cls, actor: 'Controller'):
        from mysite.universe.models.audio_profile import AudioProfile
        import random
        import glob
        from pathlib import Path
        from django.core.exceptions import ObjectDoesNotExist
        base_dir = Path(__file__).resolve().parents[3]
        generated_dir = base_dir / "audio" / "voices" / "generated"

        try:
            profile = actor.audio_profile
        except ObjectDoesNotExist:
            profile = None
        profile = profile or AudioProfile.create_default_for_actor(actor)
        
        # Only assign voice_template if not already set (idempotent)
        vp = profile.get_voice_params() or {}
        if not vp.get("voice_template"):
            candidates = sorted(glob.glob(str(generated_dir / "*.wav")))
            if candidates:
                voice_path = random.choice(candidates)
                voice_template = Path(voice_path).stem
                profile.set_voice_template(voice_template)
        
        profile.set_room_tone_preset("room_tone_controller")

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
    
    location = models.ForeignKey(
        'Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='satellites',
        help_text="The Location (Planet, Moon, Star, StarSystem) this satellite orbits"
    )
    
    def get_response_message(self) -> str:
        """
        Get the pre-programmed response message for this satellite.
        
        Determines message dynamically based on satellite name/type.
        No database field needed - calculated on demand.
        
        Returns:
            Pre-programmed response message string.
        """
        name_lower = self.name.lower()
        
        # Default messages based on satellite type/name
        if "beacon" in name_lower or "nav" in name_lower:
            return "BEEP BOOP"
        elif "relay" in name_lower:
            return "<ENCODED NOISE>"
        else:
            # Generic default for other satellite types
            return "<BURST OF MODEM NOISE>"

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
            
        satellite = cls(name=name)
        satellite.save()
        cls.assign_audio_profile(satellite)
        
        return satellite

    @classmethod
    def assign_audio_profile(cls, actor: 'Satellite'):
        from mysite.universe.models.audio_profile import AudioProfile
        import random
        import glob
        from pathlib import Path
        from django.core.exceptions import ObjectDoesNotExist
        base_dir = Path(__file__).resolve().parents[3]
        generated_dir = base_dir / "audio" / "voices" / "generated"

        try:
            profile = actor.audio_profile
        except ObjectDoesNotExist:
            profile = None
        profile = profile or AudioProfile.create_default_for_actor(actor)
        
        # Only assign voice_template if not already set (idempotent)
        vp = profile.get_voice_params() or {}
        if not vp.get("voice_template"):
            candidates = sorted(glob.glob(str(generated_dir / "*.wav")))
            if candidates:
                voice_path = random.choice(candidates)
                voice_template = Path(voice_path).stem
                profile.set_voice_template(voice_template)
        # No room tone for satellites
        profile.set_room_tone_preset(None)

    @classmethod
    def generate_name(cls) -> str:
        """Generate a random satellite name."""
        return f"Relay {dictionary.get_random('GREEK_LETTER')} {dictionary.get_random('NUMBER')}"
    
    @classmethod
    def create_navigation_satellite(cls, location: 'Location' = None) -> 'Satellite':
        """
        Create a navigation satellite with proper naming.
        
        Navigation satellites are named after their star system (e.g., "Sol Navsat").
        Per design doc: "Some systems may not have a NavSat; if you choose a random star 
        and it has no NavSat, create the Actor"
        
        Args:
            location: Optional Location (StarSystem, Planet, etc.) to derive name from.
                     If None, picks a random StarSystem.
                     
        Returns:
            A new Satellite instance with navigation satellite naming
        """
        from mysite.universe.models.celestial import StarSystem
        from mysite.universe.services.location_service import find_star_system_for_location
        
        # Determine which star system to use
        star_system = None
        if location:
            star_system = find_star_system_for_location(location)
        
        # If no location provided or couldn't find system, pick a random one
        if not star_system:
            star_systems = list(StarSystem.objects.all())
            if star_systems:
                import random
                star_system = random.choice(star_systems)
            else:
                # Fallback if no star systems exist
                name = "Navigation Satellite"
                satellite = cls(name=name)
                satellite.save()
                return satellite
        
        # Generate name: "[STARSYSTEM] NAVSAT" (e.g., "Sol Navsat")
        name = f"{star_system.name} Navsat"
        
        # Create satellite with location set to the star system
        satellite = cls(name=name, location=star_system)
        satellite.save()
        return satellite