"""
Dialogue service for generating dialogue chains using particle-based system.

Orchestrates dialogue generation by:
1. Selecting appropriate dialogue chains based on maneuver type
2. Creating particles for each step in the chain
3. Generating dialogue messages using LLM with structured outputs
4. Converting messages to DialogueEvents
"""
import random
from typing import List, Dict, Any, Optional, Tuple
from .dialogue.base import DialogueParticle
from .dialogue.factory import ParticleFactory
from mysite.universe.models.actor import Actor
from mysite.universe.models.event import NavigationEvent
from mysite.universe.schemas.dialogue_schema import DialogueMessage
from mysite.universe.services.llm_service import LLMService


class DialogueService:
    """
    Service for generating dialogue chains from navigation events.
    
    Uses particle-based system to generate complete dialogue sequences
    upfront, rather than one message at a time. Supports variable-length
    chains (3-step, 4-step, 5-step) with weighted selection.
    
    Usage:
        dialogue_service = DialogueService(llm_service)
        messages = dialogue_service.generate_chain_from_nav_event(
            nav_event=nav_event,
            pilot=pilot,
            controller=controller,
            nav_context={...}
        )
    """
    
    def __init__(self, llm_service: LLMService):
        """
        Initialize DialogueService.
        
        Args:
            llm_service: LLMService instance for generating dialogue
        """
        self.llm_service: LLMService = llm_service
        self.particle_factory: ParticleFactory = ParticleFactory()
    
    def build_prompt(
        self,
        particle: DialogueParticle,
        previous_dialogue: Optional[DialogueMessage] = None,
    ) -> Tuple[str, str]:
        """
        Build system and user prompts from a dialogue particle.
        
        Args:
            particle: DialogueParticle instance to build prompts from
            previous_dialogue: Optional previous dialogue message for context
            
        Returns:
            Tuple of (system_prompt, user_prompt) strings
        """
        # Get previous dialogue text if available
        previous_text = previous_dialogue.message if previous_dialogue else None
        
        # Build user prompt data
        prompt_data = particle.build_user_prompt_data(previous_dialogue=previous_text)
        
        # Format user prompt
        user_prompt = particle.format_user_prompt(prompt_data)
        
        # System prompt is static (same for all particles)
        system_prompt = particle.SYSTEM_PROMPT
        
        return (system_prompt, user_prompt)
    
    def generate_dialogue(
        self,
        particle: DialogueParticle,
        previous_dialogue: Optional[DialogueMessage] = None,
        temperature: Optional[float] = None,
        max_retries: int = 3,
    ) -> DialogueMessage:
        """
        Generate a single dialogue message from a particle.
        
        Uses structured outputs to ensure valid DialogueMessage JSON.
        Retries on validation failures (e.g., missing recipient identification).
        
        Args:
            particle: DialogueParticle instance
            previous_dialogue: Optional previous dialogue message for context
            temperature: Optional temperature override
            max_retries: Maximum number of retries on validation failure
            
        Returns:
            DialogueMessage instance with generated dialogue
            
        Raises:
            ValueError: If validation fails after max_retries attempts
        """
        import json
        import logging
        
        logger = logging.getLogger('dialogue_service')
        
        # All particles now use procedural greetings
        # Generate procedural greeting prefix (inherited from base class or overridden)
        greeting = particle.generate_procedural_greeting()
        
        # Get known values from particle - don't let LLM guess these
        sender_callsign = particle.get_sender_callsign()
        recipient_callsign = particle.recipient
        role = particle.get_role()
        
        # Minimal schema - only ask LLM for the message content
        # We already know role, sender, and recipient from the particle
        format_schema = {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The dialogue content (no callsigns or greetings)"
                }
            },
            "required": ["message"]
        }
        
        # Build prompts (LLM will generate just the message content, no greeting)
        system_prompt, user_prompt = self.build_prompt(particle, previous_dialogue)
        
        
        # You might be tempted to make amendments to the system or user prompt here.
        # But that would be terrible, because the developer is expecting to find the 
        # ENTIRE system prompt in its authoritative home location, without the Good Idea Fairy
        # coming along and sprinkling lard all over it, bloating the prompt, and misinforming 
        # the developer - who is reading the authoritative system_prompt assignment block - 
        # about the actual system prompt. We don't create secondary code paths! We make the intended
        # primary code path work as intended, in one place. 
        
        # Prepare messages for LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        # Retry loop for validation failures
        for attempt in range(max_retries + 1):
            # Call LLM with structured outputs
            response_json = self.llm_service.chat(
                messages=messages,
                temperature=temperature,
                use_structured_output=True,
                format=format_schema,
            )
            
            # Parse response and build DialogueMessage with known values
            try:
                response_dict = json.loads(response_json)
                message_content = response_dict.get("message", "").strip()
                
                # Strip any callsigns LLM might have included despite instructions
                if sender_callsign in message_content.upper():
                    message_content = message_content.replace(sender_callsign, "").replace(sender_callsign.lower(), "")
                if recipient_callsign.upper() in message_content.upper():
                    message_content = message_content.replace(recipient_callsign, "").replace(recipient_callsign.lower(), "")
                message_content = " ".join(message_content.split())
                
                # Build full message with procedural greeting
                full_message = f"{greeting} {message_content}"
                
                # Build DialogueMessage with known values from particle
                dialogue_msg = DialogueMessage(
                    role=role,
                    speaker_callsign=sender_callsign,
                    recipient_callsign=recipient_callsign,
                    message=full_message,
                )
                return dialogue_msg
            except Exception as e:
                # Validation error - retry if attempts remaining
                if attempt < max_retries:
                    logger.debug(
                        f"Dialogue validation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Response: {response_json[:200]}... Retrying..."
                    )
                    continue
                else:
                    # Final attempt failed - raise the error
                    logger.error(
                        f"Dialogue validation failed after {max_retries + 1} attempts. "
                        f"Final response: {response_json}"
                    )
                    raise
    
    def _select_next_particle_type(self, probabilities: Dict[str, float]) -> Optional[str]:
        """
        Select next particle type based on probabilities.
        
        Uses weighted random selection. If probabilities sum to < 1.0,
        remaining probability represents chance that chain ends.
        
        Args:
            probabilities: Dict mapping particle types to probabilities
            
        Returns:
            Selected particle type string, or None if chain ends
        """
        if not probabilities:
            return None
        
        # Normalize probabilities (handle case where sum < 1.0)
        total = sum(probabilities.values())
        if total == 0:
            return None
        
        # Random selection
        r = random.random() * total
        cumulative = 0.0
        
        for particle_type, prob in probabilities.items():
            cumulative += prob
            if r <= cumulative:
                return particle_type
        
        # If we get here, probabilities sum to < 1.0 and random value exceeded sum
        # This means chain ends (no next particle)
        return None
    
    def _determine_actor_and_recipient(
        self,
        particle_type: str,
        pilot: Actor,
        controller: Actor,
    ) -> Tuple[Actor, str]:
        """
        Determine actor and recipient for a particle type.
        
        Args:
            particle_type: Particle type string (e.g., "request", "response")
            pilot: Pilot actor
            controller: Controller actor
            
        Returns:
            Tuple of (actor, recipient_callsign)
        """
        # Normalize to lowercase for consistent matching
        particle_type = particle_type.lower() if particle_type else ""
        
        # Requests, acknowledgments, readbacks, holding come from pilot
        if particle_type in ["request", "holding", "acknowledgment", "readback"]:
            actor = pilot
            recipient = controller.name.upper()
        # Responses come from controller
        elif particle_type in ["response", "hold_response", "adjusted_response"]:
            actor = controller
            recipient = pilot.ship.name.upper() if hasattr(pilot, 'ship') and pilot.ship else pilot.name.upper()
        else:
            # Fallback: assume pilot
            actor = pilot
            recipient = controller.name.upper()
        
        return (actor, recipient)
    
    def generate_chain_iteratively(
        self,
        initial_particle: DialogueParticle,
        pilot: Actor,
        controller: Actor,
        nav_context: Dict[str, Any],
        temperature: Optional[float] = None,
    ) -> List[Tuple[DialogueMessage, float]]:
        """
        Generate a dialogue chain iteratively using particle-driven probabilities.
        
        Starts with an initial particle, then uses each particle's probabilities
        to determine the next step. Continues until a particle signals chain end
        (empty probabilities or delay_until_next returns None).
        
        Args:
            initial_particle: Starting DialogueParticle instance
            pilot: Pilot actor
            controller: Controller actor
            nav_context: Navigation context dictionary
            temperature: Optional temperature override
            
        Returns:
            List of (DialogueMessage, cumulative_time_offset) tuples.
            Times are relative to chain start (0.0).
        """
        messages_with_timing: List[Tuple[DialogueMessage, float]] = []
        cumulative_time = 0.0
        current_particle: Optional[DialogueParticle] = initial_particle
        previous_dialogue: Optional[DialogueMessage] = None
        
        while current_particle:
            # Generate dialogue message from current particle
            dialogue_msg = self.generate_dialogue(
                particle=current_particle,
                previous_dialogue=previous_dialogue,
                temperature=temperature,
            )
            
            # Store with cumulative time offset
            messages_with_timing.append((dialogue_msg, cumulative_time))
            
            # Get delay until next event
            delay = current_particle.get_delay_until_next()
            if delay is None:
                break  # Chain ends here
            
            # Advance cumulative time
            cumulative_time += delay
            
            # Get probabilities for next particle
            probabilities = current_particle.get_next_particle_probabilities()
            next_particle_type = self._select_next_particle_type(probabilities)
            
            if next_particle_type is None:
                break  # Chain ends (probabilities sum to < 1.0)
            
            # Determine actor and recipient for next particle
            actor, recipient = self._determine_actor_and_recipient(
                next_particle_type,
                pilot,
                controller,
            )
            
            # Create next particle
            current_particle = self.particle_factory.create_particle(
                particle_type=next_particle_type,
                actor=actor,
                recipient=recipient,
                nav_context=nav_context,
            )
            
            previous_dialogue = dialogue_msg
        
        return messages_with_timing
    
    def generate_chain_from_nav_event(
        self,
        nav_event: NavigationEvent,
        pilot: Actor,
        controller: Actor,
        nav_context: Dict[str, Any],
        temperature: Optional[float] = None,
    ) -> List[Tuple[DialogueMessage, float]]:
        """
        Generate a dialogue chain from a NavigationEvent using iterative particle-driven generation.
        
        Creates an initial request particle based on maneuver type, then generates
        the complete dialogue sequence iteratively using particle probabilities.
        
        Args:
            nav_event: NavigationEvent to generate dialogue for
            pilot: Pilot actor
            controller: Controller actor
            nav_context: Navigation context dictionary
            temperature: Optional temperature override
            
        Returns:
            List of (DialogueMessage, cumulative_time_offset) tuples.
            Times are relative to chain start (0.0).
        """
        # Get maneuver type from nav_event
        maneuver_type = nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else str(nav_event.maneuver)
        
        # Create initial request particle based on maneuver type
        initial_particle = self.particle_factory.create_particle(
            particle_type=maneuver_type,  # e.g., "launch", "circularize"
            actor=pilot,
            recipient=controller.name.upper(),
            nav_context=nav_context,
        )
        
        # Generate chain iteratively
        return self.generate_chain_iteratively(
            initial_particle=initial_particle,
            pilot=pilot,
            controller=controller,
            nav_context=nav_context,
            temperature=temperature,
        )

