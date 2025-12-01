from typing import List, Dict, Optional, Union
from openai import OpenAI
from mysite.universe.models.actor import Actor
import yaml
import io
import re
from contextlib import redirect_stdout, redirect_stderr
import json
from ..schemas.dialogue_schema import (
    DialogueMessage,
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
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Send a chat request to the LLM and get a JSON-formatted response.
        
        Args:
            messages: List of message dictionaries with keys "role" and "content"
            temperature: Optional temperature override (defaults to instance temperature)
            max_tokens: Optional max tokens override (defaults to instance max_tokens)
            system_prompt: Optional system prompt (for backward compatibility with old API)
            
        Returns:
            A valid JSON string containing the complete DialogueMessage (or plain text if not JSON mode)
        """
        # If a system prompt is provided (backward compatibility), add or replace a system message
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

        # Check if this is a JSON request (system message contains JSON schema or JSON instructions)
        is_json_mode = system_msg and (
            'JSON' in system_msg.upper() or 
            'json' in system_msg.lower() or
            'DialogueMessage' in system_msg or
            'schema' in system_msg.lower()
        )

        # Add explicit JSON requirement to system message if in JSON mode
        if is_json_mode and system_msg:
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
            if not self.quiet_mode:
                print("\n" + "="*80)
                print("=== PROMPT ===")
                print("="*80)
                print("=== SYSTEM MESSAGE ===")
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
            logger.debug(f"=== PROMPT SENT TO LLM API ===")
            logger.debug(f"SYSTEM MESSAGE:\n{system_msg}")
            logger.debug(f"USER MESSAGE:\n{user_msg}")
            logger.debug(f"=== END PROMPT ===\n")

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
            logger.debug(f"=== LLM CALL ===")
            logger.debug(f"SYSTEM: {system_msg}")
            logger.debug(f"USER: {user_msg}")
            logger.debug(f"RESPONSE: {response}")
            logger.debug(f"=== END CALL ===\n")

            # If JSON mode, extract and validate JSON
            if is_json_mode:
                try:
                    # Extract JSON from response (in case LLM added extra text or markdown)
                    # First, try to strip markdown code blocks
                    if response.startswith('```'):
                        # Remove markdown code block markers
                        lines = response.split('\n')
                        # Remove first line if it's ```json or ```
                        if lines[0].strip().startswith('```'):
                            lines = lines[1:]
                        # Remove last line if it's ```
                        if lines and lines[-1].strip() == '```':
                            lines = lines[:-1]
                        response = '\n'.join(lines).strip()
                    
                    # Find JSON object boundaries
                    start = response.find('{')
                    end = response.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_str = response[start:end]
                        json_data = json.loads(json_str)
                        
                        # Convert string enum values to enum types
                        if 'role' in json_data and isinstance(json_data['role'], str):
                            json_data['role'] = Role(json_data['role'])
                        if 'format' in json_data and isinstance(json_data['format'], str):
                            json_data['format'] = DialogueFormat(json_data['format'])
                        
                        # Try to validate against DialogueMessage schema
                        try:
                            dialogue_msg = DialogueMessage(**json_data)
                            # Return the complete JSON object
                            return json_str
                        except Exception as validation_error:
                            # If validation fails, try to fix common issues and use model_construct
                            # This allows us to bypass validation for messages that are close but not perfect
                            if not self.quiet_mode:
                                print(f"Warning: DialogueMessage validation failed: {validation_error}")
                                print(f"Attempting to construct message with model_construct (bypassing validation)...")
                            
                            # Use model_construct to bypass validation - this is acceptable for LLM-generated content
                            # that might have minor validation issues but is otherwise valid
                            try:
                                dialogue_msg = DialogueMessage.model_construct(**json_data)
                                # Return the corrected JSON
                                return json.dumps(dialogue_msg.model_dump())
                            except Exception as construct_error:
                                # If even model_construct fails, raise the original validation error
                                if not self.quiet_mode:
                                    print(f"Error: Could not construct DialogueMessage even with model_construct: {construct_error}")
                                raise ValueError(f"LLM failed to generate valid DialogueMessage: {validation_error}")
                    else:
                        raise ValueError("No JSON object found in response")

                except (json.JSONDecodeError, ValueError) as e:
                    if not self.quiet_mode:
                        print(f"Warning: LLM response was not valid JSON: {e}")
                        print(f"Raw response: {response}")
                    raise ValueError(f"LLM failed to generate valid JSON: {e}")
            else:
                # Plain text mode - return as-is
                return response

        except Exception as e:
            if is_json_mode:
                raise ValueError(f"Error communicating with LLM: {str(e)}")
            else:
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
        
        # Extract maneuver_type for use in examples (available for both pilots and controllers)
        maneuver_type = nav_ctx.get("maneuver_type")
        if maneuver_type:
            maneuver_type = maneuver_type.lower()
        else:
            maneuver_type = "maneuver"
        
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
                pilot_rule = """You are acknowledging an approval, not making a new request.
   - The controller has ALREADY approved your request
   - Simply confirm receipt with a brief acknowledgment, and optionally echo back the approved maneuver.
   - DO NOT make a new request or complicate the exchange."""
                # Use a more varied example that includes the maneuver_type
                example_message = f"{recipient_callsign}, {speaker_callsign}. Acknowledged, beginning {maneuver_type}."
            else:
                # Normal pilot request scenario
                pilot_rule = "5. As a PILOT: You request clearances and acknowledge instructions."
                example_message = f"{recipient_callsign}, this is {speaker_callsign}, requesting clearance."
        else:
            # For controllers, the station name IS the callsign
            speaker_callsign = actor.name
            speaker_description = f"{actor.name} (anonymous controller)"
            controller_rule = f"""5. As a CONTROLLER: 
   - You APPROVE, AUTHORIZE, CONFIRM, and CLEAR requests in a professional, declarative manner
   - You do NOT request things - that's what pilots do
   - You do NOT describe 'where things stand' in the situation. You just approve the request.
   - When a pilot requests clearance, you APPROVE it in declarative/affirmative mode
   - Speak naturally and conversationally
   - Use proper grammar: don't say "cleared for circularize", instead say "cleared for circularization". 
   - Keep responses professional, specific, and friendly.
   - Examples: 
   - "{recipient_callsign}, {speaker_callsign}. Cleared for {maneuver_type} maneuver."
   - "{recipient_callsign}, {speaker_callsign}, maneuver is approved."
   - "{recipient_callsign}, {speaker_callsign}. Approved for {maneuver_type}, go ahead."
   - "{recipient_callsign}, {speaker_callsign}, you're cleared to proceed. Begin your {maneuver_type} when you're ready." 
   - "{recipient_callsign}, {speaker_callsign}, confirmed for {maneuver_type} maneuver. Safe travels."
   - CRITICAL: Use ACTUAL callsigns, NEVER use placeholders like $SHIP or $EVENT or CONTROL or PILOT
   - CRITICAL: Your response must be natural dialogue, NOT structured data or metadata like VARIABLE:VALUE or RANGE:750KM.
   """
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
YOUR ONLY JOB: BRIEFLY confirm you received and understood the approval, and that you are now carrying out the approved maneuver.

REQUIRED FORMAT: "{recipient_callsign}, {speaker_callsign}. [ACKNOWLEDGMENT WORD] [OPTIONAL: confirmation of maneuver start]." 

EXAMPLES OF CORRECT ACKNOWLEDGMENTS:
- "{recipient_callsign}, {speaker_callsign}. We copy, and we're starting the {maneuver_type} burn ... now."
- "{recipient_callsign}, {speaker_callsign}, acknowledged. Changing heading as directed and initiating {maneuver_type} sequence."
- "{recipient_callsign}, {speaker_callsign} here. Copy that. We'll start the sequence as directed. Thanks."
- "{recipient_callsign}, {speaker_callsign}. Thank you, proceeding as directed."
- "{recipient_callsign}, {speaker_callsign}, got it, thanks."
- "{recipient_callsign}, {speaker_callsign}. Acknowledged, beginning the {maneuver_type}."

WHAT TO DO:
✓ Keep it SHORT: their callsign, your callsign, one or two confirmation words, and optionally echo back the approved maneuver
✓ Always start with standard protocol - say their callsign, then yours. 
✓ Then use brief polite acknowledgment words like "Roger", "Acknowledged", "Copy that", "Thanks", or "Got it." - mix it up!
✓ Then lastly, repeat an extremely concise plan back - "Starting burn", or "Beginning deorbit" or "{maneuver_type} sequence go." 

WHAT NOT TO DO:
✗ Do NOT make a new request
✗ Do NOT ask questions
✗ Do NOT use phrases like "requesting" or "preparing to" or "planning" - your request is approved and you are already prepared! 

REMEMBER: The controller has ALREADY approved you. You are just politely confirming you got the message, and declaring your intent to carry out the approved maneuver.
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
    "message": "{example_message}",
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
        
        # If navigation context includes example_lines (for initial requests), add them as multiple examples
        if nav_ctx and nav_ctx.get("example_lines") and not is_acknowledgment:
            user_prompt["example_lines"] = nav_ctx["example_lines"]
            user_prompt["instruction"] = (
                f"Here are some example lines for this situation:\n" +
                "\n".join([f'  - "{ex}"' for ex in nav_ctx["example_lines"]]) +
                "\n\nUse these as inspiration, but feel free to improvise and make it your own within the basic context of the script."
            )
        
        # If this is an acknowledgment scenario, add explicit instructions
        if is_acknowledgment:
            user_prompt["dialogue_type"] = "acknowledgment"
            if controller_approval:
                user_prompt["controller_approval"] = controller_approval
                user_prompt["maneuver_type"] = nav_ctx.get("maneuver_type")
                user_prompt["instruction"] = (
                    f"The controller has just approved your request with: '{controller_approval}'\n"
                    f"Your job is to ACKNOWLEDGE this approval with a BRIEF confirmation; optionally, echo back that you're beginning the maneuver as directed.\n"
                    f"Examples: '{recipient_callsign}, {speaker_callsign}. Thanks, proceeding as directed.' or '{recipient_callsign}, {speaker_callsign}. Acknowledged, beginning the burn.'\n"
                    f"Do NOT make a new request. Simply confirm you received the approval, and optionally, echo back a short concise reply that clarifies you're doing the approved action now."
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
            print("=== LLMService.get_actor_json_response DEBUG ===")
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
        logger.debug(f"=== LLMService.get_actor_json_response ===")
        logger.debug(f"Actor: {actor.name} (role: {actor.role})")
        logger.debug(f"Recipient: {recipient_callsign}")
        logger.debug(f"Line example: {line}")
        logger.debug(f"Is acknowledgment: {is_acknowledgment}")
        logger.debug(f"Controller approval: {controller_approval}")
        logger.debug(f"SYSTEM PROMPT:\n{system_prompt}")
        logger.debug(f"USER PROMPT:\n{json.dumps(user_prompt, indent=2)}")

        # Simple regex-based safety fence for bad dialogue content
        bad_msg_re = re.compile(r"\$\{|\{\s*\"|Error in communication", re.IGNORECASE)
        max_retries = 2

        try:
            for attempt in range(max_retries + 1):
                response = self.chat(messages, temperature=temperature)
                
                logger.debug(f"RAW RESPONSE:\n{response}")
                logger.debug(f"=== END LLMService.get_actor_json_response ===\n")
                
                # Try to extract JSON from response
                try:
                    # First, check if this is a schema definition (common LLM mistake)
                    # Schema definitions have "$defs", "description", "properties", "title" etc.
                    if any(keyword in response for keyword in ['"$defs"', '"description"', '"properties"', '"title"', '"type"']):
                        # This looks like a schema definition - try to extract actual message
                        if not self.quiet_mode:
                            print("Warning: LLM returned schema definition instead of message. Attempting extraction...")
                        
                        # Try to find a JSON object with "message" field that looks like a dialogue message
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
                                    
                                    # Convert string enum values to enum types
                                    if 'role' in json_data and isinstance(json_data['role'], str):
                                        json_data['role'] = Role(json_data['role'])
                                    if 'format' in json_data and isinstance(json_data['format'], str):
                                        json_data['format'] = DialogueFormat(json_data['format'])
                                    
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
                                        # Safety fence: check message content
                                        msg_text = msg_obj.message or ""
                                        if bad_msg_re.search(msg_text) and attempt < max_retries:
                                            logger.debug("Bad dialogue message content detected (schema branch); retrying LLM call")
                                            continue
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
                        
                        # Convert string enum values to enum types
                        if 'role' in json_data and isinstance(json_data['role'], str):
                            json_data['role'] = Role(json_data['role'])
                        if 'format' in json_data and isinstance(json_data['format'], str):
                            json_data['format'] = DialogueFormat(json_data['format'])
                        
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
                        
                        # Safety fence: check message content
                        msg_text = msg_obj.message or ""
                        if bad_msg_re.search(msg_text) and attempt < max_retries:
                            logger.debug("Bad dialogue message content detected (normal branch); retrying LLM call")
                            continue
                        
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
            # Always log the actual error, even in quiet mode
            import logging
            import traceback
            logger = logging.getLogger('llm_debug')
            logger.setLevel(logging.ERROR)
            if not logger.handlers:
                handler = logging.FileHandler('llm_debug.log', mode='a', encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
                logger.addHandler(handler)
            
            error_msg = f"Error generating response in get_actor_json_response: {type(e).__name__}: {str(e)}"
            error_traceback = traceback.format_exc()
            logger.error(f"{error_msg}\n{error_traceback}")
            
            if not self.quiet_mode:
                print(f"ERROR: {error_msg}")
                print(f"Traceback:\n{error_traceback}")
            
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
