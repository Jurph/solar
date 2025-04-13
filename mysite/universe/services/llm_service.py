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

    def get_actor_text(
        self,
        line: str,
        actor: Actor,
        context: Optional[List[Union[str, DialogueMessage]]] = None,
        temperature: Optional[float] = None,
        navigation_context: Optional[Dict] = None
    ) -> str:
        """
        Generate dialogue for an actor using JSON-structured prompts.
        
        Args:
            line: Example line for the response
            actor: The actor speaking
            context: Previous messages in the conversation, can be strings or DialogueMessage objects
            temperature: Optional temperature override
            navigation_context: Optional dict with navigation event details
            
        Returns:
            Generated dialogue text as a JSON string
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
                    # Fallback to navigation context
                    else:
                        recipient = nav_ctx.get("recipient", "UNKNOWN")
                    
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
        dialogue_context = DialogueContext(
            maneuver_type=nav_ctx.get("maneuver", "UNKNOWN"),
            current_location=nav_ctx.get("current_location", "UNKNOWN"),
            destination=nav_ctx.get("destination", "UNKNOWN"),
            cargo=nav_ctx.get("cargo", None),
            previous_exchanges=previous_exchanges
        )
        
        # Determine expected format based on context
        if not previous_exchanges:
            expected_format = DialogueFormat.INITIAL_CONTACT
        elif previous_exchanges[-1].requires_readback and actor.role == Role.PILOT:
            expected_format = DialogueFormat.READBACK
        else:
            expected_format = DialogueFormat.RESPONSE
        
        # Use the new streamlined JSON response generation
        return self.get_actor_json_response(
            actor=actor,
            context=dialogue_context,
            expected_format=expected_format,
            temperature=temperature
        )

    def get_actor_json_response(
        self,
        actor: Actor,
        context: DialogueContext,
        expected_format: DialogueFormat,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Generate dialogue for an actor using streamlined JSON-structured prompts.
        
        Args:
            actor: The actor speaking
            context: The dialogue context including navigation and previous messages
            expected_format: The expected format of the response
            temperature: Optional temperature override
            
        Returns:
            Generated dialogue text
        """
        # Create scene-setting system message
        scene_message = {
            "role": "system",
            "content": f"""You are {actor.name}, a {actor.role} in a space traffic control simulation.

CRITICAL SAFETY RULES:
- Always identify both parties in communications
- Use proper radio protocol and clear language
- Confirm critical maneuvers and vectors

Your response must be valid JSON matching this schema:
{json.dumps(DialogueMessage.model_json_schema(), indent=2)}"""
        }

        # Create context message with example
        example = self._generate_contextual_example(actor, context, expected_format)
        context_message = {
            "role": "user",
            "content": f"""Current situation (JSON):
{json.dumps(context.model_dump(), indent=2)}

Your message should be in {expected_format} format.
Here's a contextually relevant example:
{json.dumps(example.model_dump(), indent=2)}

Respond with a JSON object matching the DialogueMessage schema."""
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
        expected_format: DialogueFormat
    ) -> DialogueMessage:
        """Generate a contextually appropriate example message."""
        # Determine the other party's callsign from context
        other_callsign = (
            context.previous_exchanges[-1].speaker_callsign
            if context.previous_exchanges
            else "OTHER_SHIP"
        )

        # Build a message template based on format and context
        if expected_format == DialogueFormat.INITIAL_CONTACT:
            message = f"{other_callsign}, this is {actor.name}, requesting clearance for {context.maneuver_type} from {context.current_location} to {context.destination}"
        elif expected_format == DialogueFormat.READBACK:
            message = f"{other_callsign}, {actor.name}, copy that. Executing {context.maneuver_type} as instructed"
        else:
            message = f"{other_callsign}, {actor.name}. Proceed with {context.maneuver_type} when ready"

        return DialogueMessage(
            role=Role(actor.role),
            speaker_callsign=actor.name,
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
            # Debug output before API call
            if not self.quiet_mode:
                print("\n=== FINAL PROMPT TO LLM ===")
                print("=== SYSTEM MESSAGE ===")
                print(system_msg)
                print("\n=== USER MESSAGE ===")
                print(user_msg)
                print("\n=== END PROMPT ===\n")

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

    def get_actor_text(
        self,
        line: str,
        actor: Actor,
        context: Optional[List[Union[str, DialogueMessage]]] = None,
        temperature: Optional[float] = None,
        navigation_context: Optional[Dict] = None
    ) -> str:
        """
        Generate dialogue for an actor using JSON-structured prompts.
        
        Args:
            line: Example line for the response
            actor: The actor speaking
            context: Previous messages in the conversation, can be strings or DialogueMessage objects
            temperature: Optional temperature override
            navigation_context: Optional dict with navigation event details
            
        Returns:
            Generated dialogue text as a JSON string
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
                    # Fallback to navigation context
                    else:
                        recipient = nav_ctx.get("recipient", "UNKNOWN")
                    
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
        recipient_callsign = None
        if previous_exchanges:
            # If there are previous messages, use the speaker of the last message as recipient
            recipient_callsign = previous_exchanges[-1].speaker_callsign
        else:
            # Otherwise use from navigation context
            recipient_callsign = nav_ctx.get("recipient", "UNKNOWN")

        system_prompt = f"""You are {actor.name}, a {actor.role} in a space traffic control simulation.

{actor.get_identity_prompt()}

IMPORTANT: You must respond with ONLY a valid JSON object in the following format:
{{
    "role": "{actor.role.value}",
    "speaker_callsign": "{actor.name}",
    "recipient_callsign": "{recipient_callsign}",  # Use determined recipient
    "format": "INITIAL_CONTACT",
    "message": "Your actual message text here",
    "requires_readback": false
}}

The message field must follow these rules:
1. Always identify both parties in communications (e.g. "Control, this is Pilot")
2. For initial contact, address recipient before identifying yourself
3. Keep messages clear, concise, and professional
4. Set requires_readback to true for any vectors, headings, or critical instructions

Example response for initial contact:
{{
    "role": "{actor.role.value}",
    "speaker_callsign": "{actor.name}",
    "recipient_callsign": "{recipient_callsign}",  # Use determined recipient
    "format": "INITIAL_CONTACT",
    "message": "{recipient_callsign}, this is {actor.name}, requesting clearance.",
    "requires_readback": false
}}

Example response for readback:
{{
    "role": "{actor.role.value}",
    "speaker_callsign": "{actor.name}",
    "recipient_callsign": "{recipient_callsign}",  # Use determined recipient
    "format": "READBACK",
    "message": "{recipient_callsign}, {actor.name} copies. Message received.",
    "requires_readback": false
}}

DO NOT include any text before or after the JSON object. The response must be ONLY the JSON object."""

        if actor.get_instruction_prompt():
            system_prompt += "\n\n" + actor.get_instruction_prompt()

        # Build user prompt with context and current situation
        user_prompt = {
            "current_situation": {
                "maneuver_type": nav_ctx.get("maneuver_type", "UNKNOWN"),
                "current_location": nav_ctx.get("current_location", "UNKNOWN"),
                "destination": nav_ctx.get("destination", "UNKNOWN"),
                "cargo": nav_ctx.get("cargo", None)
            },
            "previous_exchanges": [msg.model_dump() for msg in previous_exchanges],
            "example_line": line
        }

        # Send chat request
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, indent=2)}
        ]

        try:
            response = self.chat(messages, temperature=temperature)
            
            # Try to extract JSON from response
            try:
                # Find the first { and last } to extract JSON
                start = response.find('{')
                end = response.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = response[start:end]
                    msg_obj = DialogueMessage(**json.loads(json_str))
                    return json.dumps(msg_obj.model_dump())
                else:
                    raise ValueError("No JSON object found in response")
            except Exception as e:
                if not self.quiet_mode:
                    print(f"Error parsing JSON response: {e}")
                    print(f"Raw response: {response}")
                
                # If JSON parsing fails, try to construct a valid response
                return json.dumps({
                    "role": actor.role.value,
                    "speaker_callsign": actor.name,
                    "recipient_callsign": nav_ctx.get("recipient", "CONTROL"),
                    "format": "RESPONSE",
                    "message": f"{nav_ctx.get('recipient', 'CONTROL')}, {actor.name} here. {response.strip()}",
                    "requires_readback": False
                })
        except Exception as e:
            if not self.quiet_mode:
                print(f"Error generating response: {e}")
            return json.dumps({
                "role": actor.role.value,
                "speaker_callsign": actor.name,
                "recipient_callsign": nav_ctx.get("recipient", "CONTROL"),
                "format": "RESPONSE",
                "message": f"{nav_ctx.get('recipient', 'CONTROL')}, {actor.name} here. Error in communications.",
                "requires_readback": False
            })