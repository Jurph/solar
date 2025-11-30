from typing import List, Dict, Any, Optional, Union
from openai import OpenAI
from mysite.universe.models.actor import Actor
import yaml
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
import json
from ..schemas.dialogue_schema import (
    DialogueMessage,
    DialoguePrompt,
    DialogueContext,
    DialogueFormat,
    Role,
)

class LLMService:
    """
    A service for interacting with the Qwen2.5 model via Ollama.
    """

    def __init__(self, config_path: str = "llm.config", quiet_mode: bool = True):
        """
        Initialize the LLM service.
        
        The YAML config file should contain:
        - base_url: The base URL for the API (e.g., "http://localhost:11434/v1/")
        - api_key: The API key (e.g., "ollama")
        - model_name: The model name (e.g., "qwen2.5:0.5b")
        - temperature: Default temperature
        - max_tokens: Default maximum tokens
        
        Args:
            config_path: Path to the YAML config file
            quiet_mode: If True, suppress all stdout/stderr during API calls
        """
        self.quiet_mode = quiet_mode

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        self.client = OpenAI(
            base_url=config["api_base"],
            api_key=config["api_key"]
        )
        self.model_name = config["model_name"]
        self.temperature = config["temperature"]
        self.max_tokens = config["max_tokens"]

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Send a message to the LLM and get a response using the generate endpoint.

        Args:
            messages: List of message dictionaries with keys "role" and "content".
            temperature: Controls randomness (0-1).
            max_tokens: Maximum tokens in the response.
            system_prompt: Optionally, a system prompt that will override or be added
                            as the first message.

        Returns:
            The LLM's response text.
        """
        # If a system prompt is provided, add or replace a system message
        if system_prompt:
            if any(msg.get('role') == 'system' for msg in messages):
                messages = [
                    {'role': 'system', 'content': system_prompt} if msg.get('role') == 'system' else msg
                    for msg in messages
                ]
            else:
                messages = [{'role': 'system', 'content': system_prompt}] + messages

        # Extract system and user messages
        system_msg = next((msg['content'] for msg in messages if msg.get('role') == 'system'), None)
        user_msg = next((msg['content'] for msg in messages if msg.get('role') == 'user'), None)

        # Combine messages into a single prompt
        prompt = ""
        if system_msg:
            prompt += f"{system_msg}\n\n"
        if user_msg:
            prompt += user_msg

        try:
            # Debug output right before API call
            if not self.quiet_mode:
                print("\n=== FINAL PROMPT TO LLM ===")
                print("=== SYSTEM MESSAGE ===")
                print(system_msg)
                print("\n=== USER MESSAGE ===")
                print(user_msg)
                print("\n=== END PROMPT ===\n")

            # Optionally redirect stdout/stderr during API call
            if self.quiet_mode:
                f_stdout = io.StringIO()
                f_stderr = io.StringIO()
                
                with redirect_stdout(f_stdout), redirect_stderr(f_stderr):
                    completion = self.client.completions.create(
                        model=self.model_name,
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
            else:
                completion = self.client.completions.create(
                    model=self.model_name,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            return completion.choices[0].text.strip()
        except Exception as e:
            return f"Error communicating with LLM: {str(e)}"

    def generate_with_system_prompt(
        self,
        user_message: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        """
        Convenience method to generate text with a system prompt and user message.

        Args:
            user_message: The user's message.
            system_prompt: The system prompt to set context.
            temperature: Controls randomness (0-1).
            max_tokens: Maximum tokens in the response.

        Returns:
            The LLM's response text.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        return self.chat(messages, temperature=temperature, max_tokens=max_tokens)

    def get_actor_json_response(
        self,
        line: str,
        actor: Actor,
        context: Optional[List[Union[str, DialogueMessage]]] = None,
        temperature: Optional[float] = None,
        navigation_context: Optional[Dict] = None
    ) -> str:
        """
        Generate dialogue for an actor and return as JSON string.
        
        WARNING: This method returns JSON, not natural language text.
        Use extract_natural_language_from_json() to get displayable text.
        
        Args:
            line: Example line for the response
            actor: The actor speaking
            context: Previous messages in the conversation, can be strings or DialogueMessage objects
            temperature: Optional temperature override
            navigation_context: Optional dict with navigation event details
            
        Returns:
            JSON string containing DialogueMessage (NOT natural language)
        """
        context = context or []
        nav_ctx = navigation_context or {}
        
        # Parse previous messages into DialogueMessage objects
        previous_exchanges = []
        for msg in context:
            try:
                if isinstance(msg, DialogueMessage):
                    # If it's already a DialogueMessage, use it directly
                    previous_exchanges.append(msg)
                elif isinstance(msg, str) and ": " in msg:
                    # Legacy string format parsing
                    speaker, text = msg.split(": ", 1)
                    # Determine roles and callsigns from message content
                    is_control = any(control in speaker.upper() for control in ["CONTROL", "ORBITAL", "TRAFFIC"])
                    role = Role.CONTROLLER if is_control else Role.PILOT
                    
                    # Extract recipient from the message content itself
                    first_part = text.split(",")[0].strip().upper()
                    recipient = None
                    
                    # If speaker is pilot and message starts with a control-like word, that's our recipient
                    if not is_control and any(control in first_part for control in ["CONTROL", "ORBITAL", "TRAFFIC"]):
                        recipient = first_part
                    # If speaker is control and message starts with a non-control word, that's our recipient
                    elif is_control and not any(control in first_part for control in ["CONTROL", "ORBITAL", "TRAFFIC"]):
                        recipient = first_part
                    # Fallback to navigation context - but no placeholder if not found
                    else:
                        recipient = nav_ctx.get("recipient")
                    
                    # Create the message object
                    msg_obj = DialogueMessage(
                        role=role,
                        speaker_callsign=speaker.strip(),
                        recipient_callsign=recipient,
                        format=DialogueFormat.INITIAL_CONTACT if "this is" in text.lower() else DialogueFormat.RESPONSE,
                        message=text.strip(),
                        requires_readback="vector" in text.lower() or "heading" in text.lower()
                    )
                    
                    previous_exchanges.append(msg_obj)
            except Exception as e:
                if not self.quiet_mode:
                    print(f"Warning: Could not parse message into DialogueMessage: {e}")
                continue
        
        # Create dialogue context using navigation info
        # CRITICAL: Only use actual values, never placeholders
        # If required fields are missing, we need to get them from context or raise an error
        maneuver_type = nav_ctx.get("maneuver_type") or nav_ctx.get("maneuver")
        current_location = nav_ctx.get("current_location")
        destination = nav_ctx.get("destination")
        
        # If we don't have required fields, try to infer from previous exchanges
        if not maneuver_type and previous_exchanges:
            # Try to extract from previous message context if available
            pass  # Could parse from message text, but better to require nav_ctx
        
        # If still missing required fields, we cannot create a valid DialogueContext
        if not maneuver_type or not current_location or not destination:
            # This method requires navigation context - if it's not provided, we can't proceed
            raise ValueError(
                f"Missing required navigation context fields. "
                f"Required: maneuver_type, current_location, destination. "
                f"Got: {nav_ctx}"
            )
        
        dialogue_context = DialogueContext(
            maneuver_type=maneuver_type,
            current_location=current_location,
            destination=destination,
            cargo=nav_ctx.get("cargo", None),
            previous_exchanges=previous_exchanges
        )
        
        # Determine expected format based on context
        # CRITICAL: Check for acknowledgment scenario FIRST - this overrides all other format logic
        if nav_ctx.get("dialogue_type") == "acknowledgment":
            expected_format = DialogueFormat.ACKNOWLEDGMENT
        elif not previous_exchanges:
            expected_format = DialogueFormat.INITIAL_CONTACT
        elif previous_exchanges[-1].requires_readback and actor.role == Role.PILOT:
            expected_format = DialogueFormat.READBACK
        else:
            expected_format = DialogueFormat.RESPONSE
        
        # Determine recipient for the example message
        # Priority: nav_ctx recipient -> previous exchange speaker -> extract from line
        recipient_callsign = nav_ctx.get("recipient")
        if not recipient_callsign and previous_exchanges:
            recipient_callsign = previous_exchanges[-1].speaker_callsign
        elif not recipient_callsign and line:
            # Try to extract from line (e.g., "SHIP_NAME, this is CONTROL")
            import re
            match = re.match(r'^([A-Z][A-Z0-9_\s]+),', line.upper())
            if match:
                recipient_callsign = match.group(1).strip()
        
        # Use the new streamlined JSON response generation
        return self._get_actor_json_response_internal(
            actor=actor,
            context=dialogue_context,
            expected_format=expected_format,
            recipient_callsign=recipient_callsign,
            temperature=temperature
        )

    def _get_actor_json_response_internal(
        self,
        actor: Actor,
        context: DialogueContext,
        expected_format: DialogueFormat,
        recipient_callsign: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Generate dialogue for an actor using streamlined JSON-structured prompts.
        
        Args:
            actor: The actor speaking
            context: The dialogue context including navigation and previous messages
            expected_format: The expected format of the response
            recipient_callsign: The recipient callsign (determined from context if not provided)
            temperature: Optional temperature override
            
        Returns:
            Generated dialogue text
        """
        # Determine recipient if not provided
        if not recipient_callsign:
            if context.previous_exchanges:
                recipient_callsign = context.previous_exchanges[-1].speaker_callsign
            else:
                # Cannot determine recipient - this should not happen if called correctly
                raise ValueError(
                    f"Cannot determine recipient for dialogue. Actor: {actor.name}, "
                    f"Role: {actor.role}, previous_exchanges: {len(context.previous_exchanges)}"
                )
        
        # Determine the correct callsign for the speaker
        # For pilots: use ship name as callsign (ships are identified by name, not pilot name)
        # For controllers: use station name as callsign (they're anonymous)
        if actor.role == Actor.Role.PILOT:
            ship_name = actor.ship.name.upper() if hasattr(actor, 'ship') and actor.ship else actor.name.upper()
            speaker_callsign = ship_name
            speaker_description = f"{actor.name} (pilot of {ship_name})"
        else:
            speaker_callsign = actor.name
            speaker_description = f"{actor.name} (anonymous controller)"
        
        # Create scene-setting system message
        # CRITICAL: Do NOT include the schema definition - it causes the LLM to return the schema instead of a message
        
        # Build role-specific rule (cannot use backslash in f-string expression)
        if actor.role == Actor.Role.CONTROLLER:
            role_rule = f"CRITICAL FOR CONTROLLERS: You APPROVE, AUTHORIZE, CONFIRM, and CLEAR. You do NOT request things - that's what pilots do. When a pilot requests clearance, you APPROVE it in declarative/affirmative mode (e.g., \"{recipient_callsign}, {speaker_callsign}. Cleared for maneuver.\")."
        else:
            # Pilot role rules
            if expected_format == DialogueFormat.ACKNOWLEDGMENT:
                role_rule = f"""CRITICAL FOR ACKNOWLEDGMENTS: You are ACKNOWLEDGING an approval, NOT making a new request!
- The controller has ALREADY approved your request
- Your ONLY job is to BRIEFLY confirm you received the approval
- Keep it SHORT: one or two words plus your callsign
- Examples: "{recipient_callsign}, {speaker_callsign}. Roger." or "{recipient_callsign}, {speaker_callsign}. Acknowledged."
- Do NOT: make new requests, ask questions, provide additional information, or describe your situation
- DO: Simply confirm receipt with a brief acknowledgment"""
            else:
                role_rule = "CRITICAL FOR PILOTS: You REQUEST clearances and acknowledge instructions."
        
        scene_message = {
            "role": "system",
            "content": f"""You are {speaker_description} in a space traffic control simulation.

{actor.get_identity_prompt()}

CRITICAL: You are responding to {recipient_callsign}. Your recipient_callsign MUST be "{recipient_callsign}".

Your response must be ONLY a valid JSON object with these exact fields:
- "role": "{actor.role.value if hasattr(actor.role, 'value') else str(actor.role)}"
- "speaker_callsign": "{speaker_callsign}"
- "recipient_callsign": "{recipient_callsign}"
- "format": one of "INITIAL_CONTACT", "RESPONSE", "ACKNOWLEDGMENT", "READBACK", "HANDOFF"
- "message": your actual dialogue message as a string
- "requires_readback": true or false

{role_rule}

DO NOT return a schema definition. Return ONLY a dialogue message JSON object."""
        }

        # Create context message with example
        example = self._generate_contextual_example(actor, context, expected_format, recipient_callsign)
        context_message = {
            "role": "user",
            "content": f"""Current situation (JSON):
{json.dumps(context.model_dump(), indent=2)}

Your message should be in {expected_format} format.
Here's a contextually relevant example:
{json.dumps(example.model_dump(), indent=2)}

CRITICAL: Respond with ONLY a JSON object containing a dialogue message. 
DO NOT return a schema definition. Return ONLY the message object like this:
{json.dumps(example.model_dump(), indent=2)}"""
        }

        return self.chat(
            messages=[scene_message, context_message],
            temperature=temperature,
            max_tokens=self.max_tokens
        )

    def _generate_contextual_example(
        self,
        actor: Actor,
        context: DialogueContext,
        expected_format: DialogueFormat,
        recipient_callsign: Optional[str] = None
    ) -> DialogueMessage:
        """
        Generate a contextually appropriate example message.
        
        Args:
            actor: The actor speaking
            context: Dialogue context
            expected_format: Expected format
            recipient_callsign: The actual recipient callsign (REQUIRED - no placeholders)
        
        Returns:
            DialogueMessage with example
        """
        # Determine the correct callsign for the speaker
        if actor.role == Actor.Role.PILOT:
            ship_name = actor.ship.name.upper() if hasattr(actor, 'ship') and actor.ship else actor.name.upper()
            speaker_callsign = ship_name
        else:
            speaker_callsign = actor.name
        
        # Determine the other party's callsign - MUST use actual names, never placeholders
        if recipient_callsign:
            # Use the provided recipient (this is the programmatic value)
            other_callsign = recipient_callsign
        elif context.previous_exchanges:
            # Get from previous exchange
            other_callsign = context.previous_exchanges[-1].speaker_callsign
        else:
            # If we don't have a recipient, we cannot generate a valid example
            # This should never happen if called correctly, but raise an error rather than using placeholder
            raise ValueError(
                f"Cannot generate example message: no recipient_callsign provided and no previous exchanges. "
                f"Actor: {actor.name}, Role: {actor.role}"
            )

        # Build a message template based on format, context, and role
        # CRITICAL: Controllers APPROVE, not request!
        if actor.role == Actor.Role.CONTROLLER:
            if expected_format == DialogueFormat.INITIAL_CONTACT:
                message = f"{other_callsign}, {speaker_callsign}. Cleared for {context.maneuver_type}."
            elif expected_format == DialogueFormat.READBACK:
                message = f"{other_callsign}, {speaker_callsign}. Confirmed, proceed as instructed."
            else:
                message = f"{other_callsign}, {speaker_callsign}. Cleared for {context.maneuver_type}."
        else:
            # Pilot messages
            if expected_format == DialogueFormat.ACKNOWLEDGMENT:
                # CRITICAL: Acknowledgments are BRIEF confirmations, not new requests
                message = f"{other_callsign}, {speaker_callsign}. Roger."
            elif expected_format == DialogueFormat.INITIAL_CONTACT:
                message = f"{other_callsign}, this is {speaker_callsign}, requesting clearance for {context.maneuver_type} from {context.current_location} to {context.destination}"
            elif expected_format == DialogueFormat.READBACK:
                message = f"{other_callsign}, {speaker_callsign}, copy that. Executing {context.maneuver_type} as instructed"
            else:
                message = f"{other_callsign}, {speaker_callsign}. Acknowledged, proceeding with {context.maneuver_type}."

        return DialogueMessage(
            role=Role(actor.role),
            speaker_callsign=speaker_callsign,
            recipient_callsign=other_callsign,
            format=expected_format,
            message=message,
            requires_readback="vector" in message.lower() or "heading" in message.lower()
        )

class LLMJSONService:
    """
    JSON-based implementation of the LLM service.
    Uses structured prompts and responses for more reliable dialogue generation.
    """
    
    def __init__(self, config_path: str = "llm.config", quiet_mode: bool = True):
        """
        Initialize the LLM service.
        
        The YAML config file should contain:
        - base_url: The base URL for the API
        - api_key: The API key
        - model_name: The model name
        - temperature: Default temperature
        - max_tokens: Default maximum tokens
        
        Args:
            config_path: Path to the YAML config file
            quiet_mode: If True, suppress stdout/stderr during API calls
        """
        self.quiet_mode = quiet_mode

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        self.client = OpenAI(
            base_url=config["api_base"],
            api_key=config["api_key"]
        )
        self.model_name = config["model_name"]
        self.temperature = config["temperature"]
        self.max_tokens = config["max_tokens"]

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Send a chat request to the LLM and get a JSON-formatted response.
        
        Args:
            messages: List of message dictionaries with keys "role" and "content"
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            
        Returns:
            A valid JSON string containing the complete DialogueMessage
        """
        # Extract system and user messages
        system_msg = next((msg['content'] for msg in messages if msg.get('role') == 'system'), None)
        user_msg = next((msg['content'] for msg in messages if msg.get('role') == 'user'), None)

        # Add explicit JSON requirement to system message
        if system_msg:
            system_msg = f"""IMPORTANT: You must respond with ONLY a valid JSON object.
Your entire response must be parseable as JSON.
Do not include any text before or after the JSON.
Do NOT wrap the JSON in markdown code blocks (no ```json or ```).
Return ONLY the raw JSON object, nothing else.
The JSON must match this exact schema:

{DialogueMessage.model_json_schema()}

{system_msg}"""

        # Combine messages into a single prompt
        prompt = ""
        if system_msg:
            prompt += f"{system_msg}\n\n"
        if user_msg:
            prompt += user_msg

        try:
            # Debug output before API call - show what's ACTUALLY being sent
            if not self.quiet_mode:
                print("\n" + "="*80)
                print("=== FINAL PROMPT TO LLM (ACTUAL PROMPT SENT TO API) ===")
                print("="*80)
                print("=== SYSTEM MESSAGE (AFTER chat() MODIFICATIONS) ===")
                print(system_msg)
                print("\n=== USER MESSAGE ===")
                print(user_msg)
                print("="*80)
                print("=== END PROMPT ===\n")
            
            # Also log the ACTUAL prompt being sent
            import logging
            logger = logging.getLogger('llm_debug')
            logger.setLevel(logging.DEBUG)
            if not logger.handlers:
                handler = logging.FileHandler('llm_debug.log', mode='a', encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
                logger.addHandler(handler)
            logger.debug(f"=== ACTUAL PROMPT SENT TO LLM API ===")
            logger.debug(f"SYSTEM MESSAGE (after chat() modifications):\n{system_msg}")
            logger.debug(f"USER MESSAGE:\n{user_msg}")
            logger.debug(f"=== END ACTUAL PROMPT ===\n")

            # Make API call
            if self.quiet_mode:
                f_stdout = io.StringIO()
                f_stderr = io.StringIO()
                with redirect_stdout(f_stdout), redirect_stderr(f_stderr):
                    completion = self.client.completions.create(
                        model=self.model_name,
                        prompt=prompt,
                        temperature=temperature if temperature is not None else self.temperature,
                        max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                    )
            else:
                completion = self.client.completions.create(
                    model=self.model_name,
                    prompt=prompt,
                    temperature=temperature if temperature is not None else self.temperature,
                    max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                )

            response = completion.choices[0].text.strip()
            
            # Always log prompts and responses for debugging (even in quiet mode, log to file)
            if not self.quiet_mode:
                print(f"\n=== LLM RESPONSE ===")
                print(response)
                print("=== END RESPONSE ===\n")
            
            # Also log to a file for later analysis
            import logging
            logger = logging.getLogger('llm_debug')
            logger.setLevel(logging.DEBUG)
            if not logger.handlers:
                handler = logging.FileHandler('llm_debug.log', mode='a', encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
                logger.addHandler(handler)
            
            logger.debug(f"=== LLM CALL ===")
            logger.debug(f"SYSTEM: {system_msg}")
            logger.debug(f"USER: {user_msg}")
            logger.debug(f"RESPONSE: {response}")
            logger.debug(f"=== END CALL ===\n")

            try:
                # Extract JSON from response (in case LLM added extra text)
                start = response.find('{')
                end = response.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = response[start:end]
                    # Validate against DialogueMessage schema
                    dialogue_msg = DialogueMessage(**json.loads(json_str))
                    # Return the complete JSON object
                    return json_str
                else:
                    raise ValueError("No JSON object found in response")

            except (json.JSONDecodeError, ValueError) as e:
                if not self.quiet_mode:
                    print(f"Warning: LLM response was not valid JSON: {e}")
                    print(f"Raw response: {response}")
                raise ValueError(f"LLM failed to generate valid JSON: {e}")

        except Exception as e:
            raise ValueError(f"Error communicating with LLM: {str(e)}")

    def get_actor_json_response(
        self,
        line: str,
        actor: Actor,
        context: Optional[List[Union[str, DialogueMessage]]] = None,
        temperature: Optional[float] = None,
        navigation_context: Optional[Dict] = None
    ) -> str:
        """
        Generate dialogue for an actor and return as JSON string.
        
        WARNING: This method returns JSON, not natural language text.
        Use extract_natural_language_from_json() to get displayable text.
        
        Args:
            line: Example line for the response
            actor: The actor speaking
            context: Previous messages in the conversation, can be strings or DialogueMessage objects
            temperature: Optional temperature override
            navigation_context: Optional dict with navigation event details
            
        Returns:
            JSON string containing DialogueMessage (NOT natural language)
        """
        context = context or []
        nav_ctx = navigation_context or {}
        
        # Parse previous messages into DialogueMessage objects
        previous_exchanges = []
        for msg in context:
            try:
                if isinstance(msg, DialogueMessage):
                    # If it's already a DialogueMessage, use it directly
                    previous_exchanges.append(msg)
                elif isinstance(msg, str) and ": " in msg:
                    # Legacy string format parsing
                    speaker, text = msg.split(": ", 1)
                    # Determine roles and callsigns from message content
                    is_control = any(control in speaker.upper() for control in ["CONTROL", "ORBITAL", "TRAFFIC"])
                    role = Role.CONTROLLER if is_control else Role.PILOT
                    
                    # Extract recipient from the message content itself
                    first_part = text.split(",")[0].strip().upper()
                    recipient = None
                    
                    # If speaker is pilot and message starts with a control-like word, that's our recipient
                    if not is_control and any(control in first_part for control in ["CONTROL", "ORBITAL", "TRAFFIC"]):
                        recipient = first_part
                    # If speaker is control and message starts with a non-control word, that's our recipient
                    elif is_control and not any(control in first_part for control in ["CONTROL", "ORBITAL", "TRAFFIC"]):
                        recipient = first_part
                    # Fallback to navigation context - but no placeholder if not found
                    else:
                        recipient = nav_ctx.get("recipient")
                    
                    # Create the message object
                    msg_obj = DialogueMessage(
                        role=role,
                        speaker_callsign=speaker.strip(),
                        recipient_callsign=recipient,
                        format=DialogueFormat.INITIAL_CONTACT if "this is" in text.lower() else DialogueFormat.RESPONSE,
                        message=text.strip(),
                        requires_readback="vector" in text.lower() or "heading" in text.lower()
                    )
                    
                    previous_exchanges.append(msg_obj)
            except Exception as e:
                if not self.quiet_mode:
                    print(f"Warning: Could not parse message into DialogueMessage: {e}")
                continue

        # Build system prompt with actor identity, rules, and JSON schema
        # Determine recipient from context or navigation context
        # CRITICAL: We MUST have an actual recipient name - no placeholders allowed
        recipient_callsign = None
        if previous_exchanges:
            # If there are previous messages, the recipient is the speaker of the last message
            # (because we're responding to them)
            recipient_callsign = previous_exchanges[-1].speaker_callsign
        else:
            # Otherwise use explicit recipient from navigation context
            recipient_callsign = nav_ctx.get("recipient")
        
        # If we still don't have a recipient, we need to get it from available context
        # This should never happen if nav_context is set up correctly, but we'll try to infer
        if not recipient_callsign:
            # Try to get from the line parameter if it contains a callsign
            if line:
                # Extract callsign from line (e.g., "SHIP_NAME, this is CONTROL")
                import re
                match = re.match(r'^([A-Z][A-Z0-9_\s]+),', line.upper())
                if match:
                    recipient_callsign = match.group(1).strip()
            
            # If still no recipient, this is an error condition - we cannot proceed without knowing who we're talking to
            if not recipient_callsign:
                raise ValueError(
                    f"Cannot determine recipient for dialogue. Actor: {actor.name}, "
                    f"Role: {actor.role}, nav_ctx: {nav_ctx}, previous_exchanges: {len(previous_exchanges)}"
                )

        # Get role value safely (handle both enum and string)
        role_value = actor.role.value if hasattr(actor.role, 'value') else str(actor.role)
        
        # Determine the correct callsign for the speaker
        # For pilots: use ship name as callsign (ships are identified by name, not pilot name)
        # For controllers: use station name as callsign (they're anonymous)
        
        # Check if this is an acknowledgment scenario (pilot acknowledging controller's approval)
        is_acknowledgment = nav_ctx.get("dialogue_type") == "acknowledgment"
        controller_approval = nav_ctx.get("controller_approval", "")
        
        # DEBUG: Print acknowledgment detection
        if not self.quiet_mode:
            print(f"\n[DEBUG] is_acknowledgment: {is_acknowledgment}")
            print(f"[DEBUG] controller_approval: {repr(controller_approval)}")
            print(f"[DEBUG] nav_ctx.get('dialogue_type'): {repr(nav_ctx.get('dialogue_type'))}")
            print(f"[DEBUG] nav_ctx: {nav_ctx}\n")
        
        if actor.role == Actor.Role.PILOT:
            # Get ship name from actor's ship
            ship_name = actor.ship.name.upper() if hasattr(actor, 'ship') and actor.ship else actor.name.upper()
            speaker_callsign = ship_name
            # But clarify in prompt that the pilot is speaking
            speaker_description = f"{actor.name} (pilot of {ship_name})"
            controller_rule = ""
            
            if is_acknowledgment:
                # CRITICAL: This is an acknowledgment, not a request!
                # Override the generic pilot behavior completely
                pilot_rule = """CRITICAL: YOU ARE ACKNOWLEDGING AN APPROVAL - NOT MAKING A REQUEST!
   - The controller has ALREADY approved your request
   - Your ONLY job is to BRIEFLY confirm you received the approval
   - This is NOT the time to request anything new
   - Keep it SHORT: one or two words plus your callsign
   - Examples: "Roger", "Acknowledged", "Copy that", "Thanks", "Got it"
   - Do NOT: make new requests, ask questions, provide additional information, or describe your situation
   - DO: Simply confirm receipt with a brief acknowledgment"""
                example_message = f"{recipient_callsign}, {speaker_callsign}. Roger."
            else:
                # Normal pilot request scenario
                pilot_rule = "5. As a PILOT: You REQUEST clearances and acknowledge instructions."
                example_message = f"{recipient_callsign}, this is {speaker_callsign}, requesting clearance."
        else:
            # For controllers, the station name IS the callsign
            speaker_callsign = actor.name
            speaker_description = f"{actor.name} (anonymous controller)"
            controller_rule = """5. As a CONTROLLER: 
   - You APPROVE, AUTHORIZE, CONFIRM, and CLEAR requests
   - You do NOT request things - that's what pilots do
   - When a pilot requests clearance, you APPROVE it in declarative/affirmative mode
   - Example: "$SHIP, you are approved for $EVENT" or "$SHIP, cleared for $EVENT"
   - Everything is routine and in order - your job is to approve, not to question"""
            pilot_rule = ""
            example_message = f"{recipient_callsign}, {speaker_callsign}. Cleared for maneuver."
        
        # Build acknowledgment-specific instruction if this is an acknowledgment
        acknowledgment_instruction = ""
        if is_acknowledgment:
            if not self.quiet_mode:
                print(f"[DEBUG] Building acknowledgment instruction block...")
            
            # Build the instruction block - include controller approval if available
            approval_text = f'\n\nThe controller has ALREADY approved your request with this message:\n"{controller_approval}"\n' if controller_approval else ""
            
            acknowledgment_instruction = f"""

═══════════════════════════════════════════════════════════════════════════════
CRITICAL: YOU ARE ACKNOWLEDGING AN APPROVAL - THIS IS NOT A NEW REQUEST!
═══════════════════════════════════════════════════════════════════════════════
{approval_text}
YOUR ONLY JOB: BRIEFLY confirm you received and understood the approval.

REQUIRED FORMAT: "{recipient_callsign}, {speaker_callsign}. [BRIEF POLITE WORD]."

EXAMPLES OF CORRECT ACKNOWLEDGMENTS:
- "{recipient_callsign}, {speaker_callsign}. Roger."
- "{recipient_callsign}, {speaker_callsign}. Acknowledged."
- "{recipient_callsign}, {speaker_callsign}. Copy that."

WHAT TO DO:
✓ Keep it SHORT (one or two words plus callsign)
✓ Simply confirm receipt
✓ Use standard acknowledgment words: Roger, Acknowledged, Copy that, Thanks, Got it

WHAT NOT TO DO:
✗ Do NOT make a new request
✗ Do NOT ask questions
✗ Do NOT provide additional information about your situation
✗ Do NOT describe what you're doing or planning to do
✗ Do NOT use phrases like "requesting" or "preparing to"

REMEMBER: The controller has ALREADY approved you. You are just politely confirming you got the message.
═══════════════════════════════════════════════════════════════════════════════
"""
        
        system_prompt = f"""You are {speaker_description} in a space traffic control simulation.

{actor.get_identity_prompt()}
{acknowledgment_instruction}
CRITICAL: You are responding to {recipient_callsign}. Your recipient_callsign MUST be "{recipient_callsign}".

IMPORTANT: You must respond with ONLY a valid JSON object in the following format:
{{
    "role": "{role_value}",
    "speaker_callsign": "{speaker_callsign}",
    "recipient_callsign": "{recipient_callsign}",
    "format": "{'ACKNOWLEDGMENT' if is_acknowledgment else 'INITIAL_CONTACT'}",
    "message": "Your actual message text here",
    "requires_readback": false
}}

The message field must follow these rules:
1. Always identify both parties in communications
2. For initial contact, address recipient before identifying yourself
3. Keep messages clear, concise, and professional
4. Set requires_readback to true for any vectors, headings, or critical instructions
{f'5. CRITICAL FOR ACKNOWLEDGMENTS: This is an ACKNOWLEDGMENT, not a request. Keep it BRIEF - one or two words plus your callsign. Examples: "{recipient_callsign}, {speaker_callsign}. Roger." or "{recipient_callsign}, {speaker_callsign}. Acknowledged." Do NOT make a new request or ask questions.' if is_acknowledgment else ''}

{controller_rule}

{pilot_rule}

Example response for {'acknowledgment' if is_acknowledgment else 'initial contact'}:
{{
    "role": "{role_value}",
    "speaker_callsign": "{speaker_callsign}",
    "recipient_callsign": "{recipient_callsign}",
    "format": "{'ACKNOWLEDGMENT' if is_acknowledgment else 'INITIAL_CONTACT'}",
    "message": "{example_message}",
    "requires_readback": false
}}

Example response for readback:
{{
    "role": "{role_value}",
    "speaker_callsign": "{speaker_callsign}",
    "recipient_callsign": "{recipient_callsign}",
    "format": "READBACK",
    "message": "{recipient_callsign}, {speaker_callsign} good copy. Message received.",
    "requires_readback": false
}}

DO NOT include any text before or after the JSON object.
DO NOT wrap the JSON in markdown code blocks (no ```json or ```).
The response must be ONLY the raw JSON object, nothing else."""

        if actor.get_instruction_prompt():
            system_prompt += "\n\n" + actor.get_instruction_prompt()

        # Build user prompt with context and current situation
        # Explicitly include recipient information to avoid confusion
        # Only include fields that have actual values - no placeholders
        current_situation = {}
        if nav_ctx.get("maneuver_type"):
            current_situation["maneuver_type"] = nav_ctx["maneuver_type"]
        if nav_ctx.get("current_location"):
            current_situation["current_location"] = nav_ctx["current_location"]
        if nav_ctx.get("destination"):
            current_situation["destination"] = nav_ctx["destination"]
        if nav_ctx.get("cargo"):
            current_situation["cargo"] = nav_ctx["cargo"]
        
        user_prompt = {
            "current_situation": current_situation,
            "previous_exchanges": [msg.model_dump() for msg in previous_exchanges],
            "example_line": line,
            "recipient_callsign": recipient_callsign  # Explicitly state the recipient (actual name, never placeholder)
        }
        
        # If this is an acknowledgment scenario, add explicit instructions
        if is_acknowledgment:
            user_prompt["dialogue_type"] = "acknowledgment"
            if controller_approval:
                user_prompt["controller_approval"] = controller_approval
                user_prompt["instruction"] = (
                    f"The controller has just approved your request with: '{controller_approval}'\n"
                    f"Your job is to ACKNOWLEDGE this approval with a BRIEF confirmation.\n"
                    f"Examples: '{recipient_callsign}, {speaker_callsign}. Roger.' or '{recipient_callsign}, {speaker_callsign}. Acknowledged.'\n"
                    f"Do NOT make a new request. Simply confirm you received the approval."
                )
            else:
                user_prompt["instruction"] = (
                    f"The controller has just approved your request.\n"
                    f"Your job is to ACKNOWLEDGE this approval with a BRIEF confirmation.\n"
                    f"Examples: '{recipient_callsign}, {speaker_callsign}. Roger.' or '{recipient_callsign}, {speaker_callsign}. Acknowledged.'\n"
                    f"Do NOT make a new request. Simply confirm you received the approval."
                )

        # Send chat request
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, indent=2)}
        ]

        # Log the call for debugging - print to console if not in quiet mode
        import logging
        logger = logging.getLogger('llm_debug')
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            handler = logging.FileHandler('llm_debug.log', mode='a', encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
            logger.addHandler(handler)
        
        # Print detailed debug info to console if not in quiet mode
        if not self.quiet_mode:
            print("\n" + "="*80)
            print("=== LLMJSONService.get_actor_json_response DEBUG ===")
            print("="*80)
            print(f"Actor: {actor.name} (role: {actor.role})")
            print(f"Recipient: {recipient_callsign}")
            print(f"Line example: {line}")
            print(f"Is acknowledgment: {is_acknowledgment}")
            print(f"Controller approval: {repr(controller_approval)}")
            print(f"Acknowledgment instruction length: {len(acknowledgment_instruction)}")
            print(f"Acknowledgment instruction preview: {acknowledgment_instruction[:200] if acknowledgment_instruction else 'EMPTY - NOT BUILT!'}")
            print(f"\n--- SYSTEM PROMPT (BEFORE chat() modifications) ---")
            print(system_prompt)
            print(f"\n--- FULL USER PROMPT (JSON) ---")
            print(json.dumps(user_prompt, indent=2))
            print("="*80 + "\n")
        
        # Also log to file
        logger.debug(f"=== LLMJSONService.get_actor_json_response ===")
        logger.debug(f"Actor: {actor.name} (role: {actor.role})")
        logger.debug(f"Recipient: {recipient_callsign}")
        logger.debug(f"Line example: {line}")
        logger.debug(f"Is acknowledgment: {is_acknowledgment}")
        logger.debug(f"Controller approval: {controller_approval}")
        logger.debug(f"SYSTEM PROMPT:\n{system_prompt}")
        logger.debug(f"USER PROMPT:\n{json.dumps(user_prompt, indent=2)}")

        try:
            response = self.chat(messages, temperature=temperature)
            
            logger.debug(f"RAW RESPONSE:\n{response}")
            logger.debug(f"=== END LLMJSONService.get_actor_json_response ===\n")
            
            # Try to extract JSON from response
            try:
                # First, check if this is a schema definition (common LLM mistake)
                # Schema definitions have "$defs", "description", "properties", "title" etc.
                if any(keyword in response for keyword in ['"$defs"', '"description"', '"properties"', '"title"', '"type"']):
                    # This looks like a schema definition - try to extract actual message
                    if not self.quiet_mode:
                        print("Warning: LLM returned schema definition instead of message. Attempting extraction...")
                    
                    # Try to find a JSON object with "message" field that looks like a dialogue message
                    import re
                    # Pattern: find JSON objects that have "message" field and look like dialogue
                    # Look for objects with message, role, speaker_callsign, recipient_callsign
                    pattern = r'\{\s*"(?:role|speaker_callsign|recipient_callsign|message|format|requires_readback)"\s*:\s*[^}]+\}'
                    matches = list(re.finditer(pattern, response, re.DOTALL))
                    
                    # Try each potential match
                    for match in matches:
                        try:
                            # Expand match to include full object (find matching braces)
                            start = match.start()
                            brace_count = 0
                            end = start
                            for i, char in enumerate(response[start:], start):
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end = i + 1
                                        break
                            
                            if end > start:
                                json_str = response[start:end]
                                json_data = json.loads(json_str)
                                
                                # Check if this looks like a dialogue message (has message field, not schema)
                                if 'message' in json_data and 'role' in json_data and '$defs' not in json_data:
                                    msg_obj = DialogueMessage(**json_data)
                                    # Correct recipient if needed
                                    if msg_obj.recipient_callsign != recipient_callsign:
                                        msg_obj = DialogueMessage.model_construct(
                                            role=msg_obj.role,
                                            speaker_callsign=msg_obj.speaker_callsign,
                                            recipient_callsign=recipient_callsign,
                                            format=msg_obj.format,
                                            message=msg_obj.message,
                                            requires_readback=msg_obj.requires_readback
                                        )
                                    return json.dumps(msg_obj.model_dump())
                        except (json.JSONDecodeError, ValueError, TypeError):
                            continue
                    
                    # If we couldn't extract from schema, raise error
                    raise ValueError("LLM returned schema definition instead of dialogue message. Response: " + response[:200])
                
                # Normal JSON extraction - look for JSON object boundaries
                start = response.find('{')
                end = response.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = response[start:end]
                    json_data = json.loads(json_str)
                    
                    # Skip if this looks like a schema definition
                    if '$defs' in json_data or ('properties' in json_data and 'type' in json_data):
                        raise ValueError("Response appears to be a schema definition, not a message")
                    
                    msg_obj = DialogueMessage(**json_data)
                    
                    # CRITICAL FIX: Ensure recipient_callsign is correct
                    # We know the correct recipient from our logic above, so enforce it
                    if msg_obj.recipient_callsign != recipient_callsign:
                        # Correct the recipient if LLM got it wrong
                        # Use model_construct to bypass validation (message text may not match new recipient)
                        msg_obj = DialogueMessage.model_construct(
                            role=msg_obj.role,
                            speaker_callsign=msg_obj.speaker_callsign,
                            recipient_callsign=recipient_callsign,  # Use our determined recipient
                            format=msg_obj.format,
                            message=msg_obj.message,
                            requires_readback=msg_obj.requires_readback
                        )
                    
                    return json.dumps(msg_obj.model_dump())
                else:
                    raise ValueError("No JSON object found in response")
            except Exception as e:
                if not self.quiet_mode:
                    print(f"Error parsing JSON response: {e}")
                    print(f"Raw response: {response}")
                
                # If JSON parsing fails, try to construct a valid response
                # CRITICAL: Use actual recipient from context, never placeholders
                fallback_recipient = recipient_callsign  # Use the recipient we determined above
                if not fallback_recipient:
                    # Try to extract from response text as last resort
                    import re
                    # Look for a callsign pattern in the response
                    match = re.search(r'([A-Z][A-Z0-9_\s]+),?\s+this is', response.upper())
                    if match:
                        fallback_recipient = match.group(1).strip()
                
                if not fallback_recipient:
                    # If we truly cannot determine recipient, this is an error
                    raise ValueError(f"Cannot determine recipient for fallback response. Actor: {actor.name}, nav_ctx: {nav_ctx}")
                
                role_value = actor.role.value if hasattr(actor.role, 'value') else str(actor.role)
                return json.dumps({
                    "role": role_value,
                    "speaker_callsign": actor.name,
                    "recipient_callsign": fallback_recipient,
                    "format": "RESPONSE",
                    "message": f"{fallback_recipient}, {actor.name} here. {response.strip()}",
                    "requires_readback": False
                })
        except Exception as e:
            if not self.quiet_mode:
                print(f"Error generating response: {e}")
            
            # For error fallback, use recipient_callsign we determined above
            fallback_recipient = recipient_callsign
            if not fallback_recipient:
                # If we don't have recipient even for error message, use actor's name as fallback
                # (This is better than "CONTROL" placeholder)
                fallback_recipient = actor.name
            
            role_value = actor.role.value if hasattr(actor.role, 'value') else str(actor.role)
            return json.dumps({
                "role": role_value,
                "speaker_callsign": actor.name,
                "recipient_callsign": fallback_recipient,
                "format": "RESPONSE",
                "message": f"{fallback_recipient}, {actor.name} here. Error in communications.",
                "requires_readback": False
            })