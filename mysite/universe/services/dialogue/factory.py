"""
Factory for creating dialogue particles dynamically.

Provides a centralized registry of all particle classes and factory methods
for creating particles based on maneuver type or particle type strings.
"""
from typing import Dict, Type, Any
from .base import DialogueParticle
from .particles import (
    LaunchRequest,
    CircularizationRequest,
    InsertionRequest,
    SublightRequest,
    DeorbitRequest,
    LandingRequest,
    GenericRequest,
    RadioResponse,
    RadioReadback,
    HoldResponse,
    Holding,
    CommsCheckRequest,
    SatelliteResponse,
    NavBroadcast,
    GratitudeParticle,
)
from mysite.universe.models.actor import Actor


class ParticleFactory:
    """
    Factory for creating dialogue particles.
    
    Maintains registries of particle classes mapped by:
    - Maneuver type (e.g., "launch" → LaunchRequest)
    - Generic particle type (e.g., "response" → RadioResponse)
    
    Usage:
        factory = ParticleFactory()
        particle = factory.create_particle(
            particle_type="launch",
            actor=pilot,
            recipient="MARS CONTROL",
            nav_context={...}
        )
    """
    
    # Map maneuver types to request particle classes
    REQUEST_PARTICLE_MAP: Dict[str, Type[DialogueParticle]] = {
        "launch": LaunchRequest,
        "circularize": CircularizationRequest,
        "insertion": InsertionRequest,
        "sublight": SublightRequest,
        "deorbit": DeorbitRequest,
        "landing": LandingRequest,
        # Fallback for unspecified maneuvers
        "generic": GenericRequest,
    }
    
    # Map generic particle types to particle classes
    PARTICLE_MAP: Dict[str, Type[DialogueParticle]] = {
        "response": RadioResponse,  # Used for all approvals (including after holds)
        "readback": RadioReadback,
        "hold_response": HoldResponse,
        "holding": Holding,
        "adjusted_response": RadioResponse,  # Same as response, just after a hold
        "comms_check": CommsCheckRequest,  # Pilot requesting comms check from satellite
        "satellite_response": SatelliteResponse,  # Satellite responding with pre-programmed message
        "nav_broadcast": NavBroadcast,  # Satellite navigation broadcast
        "gratitude": GratitudeParticle,  # Pilot thanking satellite for nav broadcast
    }
    
    @classmethod
    def create_particle(
        cls,
        particle_type: str,
        actor: Actor,
        recipient: str,
        nav_context: Dict[str, Any],
    ) -> DialogueParticle:
        """
        Create a dialogue particle based on particle type string.
        
        First checks REQUEST_PARTICLE_MAP (for maneuver-based requests),
        then checks PARTICLE_MAP (for generic particle types),
        finally falls back to GenericRequest if not found.
        
        Args:
            particle_type: String identifying particle type (e.g., "launch", "response")
            actor: The actor speaking (Pilot, Controller, etc.)
            recipient: The recipient callsign (e.g., "MARS CONTROL")
            nav_context: Navigation context dictionary
            
        Returns:
            DialogueParticle instance of the appropriate type.
            
        Raises:
            ValueError: If particle_type is empty or None.
        """
        if not particle_type:
            raise ValueError("particle_type cannot be empty or None")
        
        # Normalize particle type to lowercase
        particle_type = particle_type.lower()
        
        # Check request particle map first (maneuver-based requests)
        if particle_type in cls.REQUEST_PARTICLE_MAP:
            particle_class = cls.REQUEST_PARTICLE_MAP[particle_type]
            return particle_class(actor=actor, recipient=recipient, nav_context=nav_context)
        
        # For "response" type, always use RadioResponse (handles all maneuver types via nav_context)
        if particle_type == "response":
            return RadioResponse(actor=actor, recipient=recipient, nav_context=nav_context)
        
        # Check generic particle map (acknowledgment, readback, etc.)
        if particle_type in cls.PARTICLE_MAP:
            particle_class = cls.PARTICLE_MAP[particle_type]
            return particle_class(actor=actor, recipient=recipient, nav_context=nav_context)
        
        # Fallback to GenericRequest for unknown types
        return GenericRequest(actor=actor, recipient=recipient, nav_context=nav_context)
    
    @classmethod
    def register_request_particle(
        cls,
        maneuver_type: str,
        particle_class: Type[DialogueParticle],
    ) -> None:
        """
        Register a new request particle class for a maneuver type.
        
        Allows extending the factory with custom particle types at runtime.
        
        Args:
            maneuver_type: Maneuver type string (e.g., "plane_change")
            particle_class: DialogueParticle subclass to register
            
        Raises:
            TypeError: If particle_class is not a subclass of DialogueParticle.
        """
        if not issubclass(particle_class, DialogueParticle):
            raise TypeError(f"particle_class must be a subclass of DialogueParticle, got {type(particle_class)}")
        
        cls.REQUEST_PARTICLE_MAP[maneuver_type.lower()] = particle_class
    
    @classmethod
    def register_particle(
        cls,
        particle_type: str,
        particle_class: Type[DialogueParticle],
    ) -> None:
        """
        Register a new generic particle class.
        
        Allows extending the factory with custom particle types at runtime.
        
        Args:
            particle_type: Generic particle type string (e.g., "response")
            particle_class: DialogueParticle subclass to register
            
        Raises:
            TypeError: If particle_class is not a subclass of DialogueParticle.
        """
        if not issubclass(particle_class, DialogueParticle):
            raise TypeError(f"particle_class must be a subclass of DialogueParticle, got {type(particle_class)}")
        
        cls.PARTICLE_MAP[particle_type.lower()] = particle_class

