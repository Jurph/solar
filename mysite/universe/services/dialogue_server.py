"""
Dialogue service for generating dialogue chains using particle-based system.

Orchestrates dialogue generation by:
1. Selecting appropriate dialogue chains based on maneuver type
2. Creating particles for each step in the chain
3. Generating dialogue messages using LLM with structured outputs
4. Converting messages to DialogueEvents
"""
from typing import List, Dict, Any, Optional, Tuple
from .dialogue.base import DialogueParticle
from .dialogue.chain import DialogueChain, ChainSelector
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
        self.chain_selector: ChainSelector = ChainSelector()
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
        
        # Get JSON schema for structured outputs
        format_schema = DialogueMessage.model_json_schema()
        
        # Build prompts
        system_prompt, user_prompt = self.build_prompt(particle, previous_dialogue)
        
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
            
            # Parse response into DialogueMessage
            try:
                response_dict = json.loads(response_json)
                dialogue_msg = DialogueMessage.model_validate(response_dict)
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
    
    def generate_chain(
        self,
        chain: DialogueChain,
        pilot: Actor,
        controller: Actor,
        nav_context: Dict[str, Any],
        temperature: Optional[float] = None,
    ) -> List[DialogueMessage]:
        """
        Generate a complete dialogue chain from a DialogueChain.
        
        Iterates through chain steps, creates appropriate particles,
        and generates dialogue messages in sequence.
        
        Args:
            chain: DialogueChain defining the sequence of particle types
            pilot: Pilot actor
            controller: Controller actor
            nav_context: Navigation context dictionary
            temperature: Optional temperature override
            
        Returns:
            List of DialogueMessage instances in chain order
        """
        messages: List[DialogueMessage] = []
        previous_dialogue: Optional[DialogueMessage] = None
        
        for step_type in chain.steps:
            # Determine actor based on step type
            # Requests come from pilot, responses from controller
            if step_type in ["request", "holding", "acknowledgment", "readback"]:
                actor = pilot
                recipient = controller.name.upper()
            elif step_type in ["response", "hold_response", "adjusted_response"]:
                actor = controller
                recipient = pilot.ship.name.upper() if hasattr(pilot, 'ship') and pilot.ship else pilot.name.upper()
            else:
                # Fallback: assume pilot
                actor = pilot
                recipient = controller.name.upper()
            
            # Create particle for this step
            particle = self.particle_factory.create_particle(
                particle_type=step_type,
                actor=actor,
                recipient=recipient,
                nav_context=nav_context,
            )
            
            # Generate dialogue message
            dialogue_msg = self.generate_dialogue(
                particle=particle,
                previous_dialogue=previous_dialogue,
                temperature=temperature,
            )
            
            messages.append(dialogue_msg)
            previous_dialogue = dialogue_msg
        
        return messages
    
    def generate_chain_from_nav_event(
        self,
        nav_event: NavigationEvent,
        pilot: Actor,
        controller: Actor,
        nav_context: Dict[str, Any],
        temperature: Optional[float] = None,
    ) -> List[DialogueMessage]:
        """
        Generate a dialogue chain from a NavigationEvent.
        
        Entry point for chain generation. Selects appropriate chain based on
        maneuver type, then generates the complete dialogue sequence.
        
        Args:
            nav_event: NavigationEvent to generate dialogue for
            pilot: Pilot actor
            controller: Controller actor
            nav_context: Navigation context dictionary
            temperature: Optional temperature override
            
        Returns:
            List of DialogueMessage instances in chain order
        """
        # Get maneuver type from nav_event
        maneuver_type = nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else str(nav_event.maneuver)
        
        # Select chain based on maneuver type
        chain = self.chain_selector.select_chain(maneuver_type)
        
        # Generate chain
        return self.generate_chain(
            chain=chain,
            pilot=pilot,
            controller=controller,
            nav_context=nav_context,
            temperature=temperature,
        )

