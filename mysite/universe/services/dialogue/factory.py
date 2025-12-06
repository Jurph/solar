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
    LaunchResponse,
    OrbitResponse,
    DepartureResponse,
    RadioAcknowledgment,
    RadioReadback,
    HoldResponse,
    Holding,
    AdjustedResponse,
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
    
    # Map maneuver types to response particle classes
    RESPONSE_PARTICLE_MAP: Dict[str, Type[DialogueParticle]] = {
        "launch": LaunchResponse,
        "direct_ascent": LaunchResponse,  # Direct ascent uses launch response
        "insertion": OrbitResponse,
        "circularize": OrbitResponse,
        "sublight": DepartureResponse,
        "hyperspace": DepartureResponse,  # Hyperspace uses departure response
        "hyperdrive": DepartureResponse,  # Hyperdrive uses departure response
        # "reentry": ReentryResponse,
        # "deorbit": DeorbitResponse,
        # "landing": LandingResponse,
        # Fallback for unspecified maneuvers
    }
    
    # Map generic particle types to particle classes
    PARTICLE_MAP: Dict[str, Type[DialogueParticle]] = {
        "response": RadioResponse,  # Fallback if maneuver type not found
        "acknowledgment": RadioAcknowledgment,
        "readback": RadioReadback,
        "hold_response": HoldResponse,
        "holding": Holding,
        "adjusted_response": AdjustedResponse,
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
        
        # For "response" type, check maneuver-specific response map
        if particle_type == "response":
            maneuver_type = nav_context.get("maneuver_type", "").lower()
            if maneuver_type in cls.RESPONSE_PARTICLE_MAP:
                particle_class = cls.RESPONSE_PARTICLE_MAP[maneuver_type]
                return particle_class(actor=actor, recipient=recipient, nav_context=nav_context)
            # Fallback to generic RadioResponse if maneuver not found
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

