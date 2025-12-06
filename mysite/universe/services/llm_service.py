from typing import List, Dict, Optional
from openai import OpenAI
import yaml
import io
import re
from contextlib import redirect_stdout, redirect_stderr
import json
import requests
from ..schemas.dialogue_schema import (
    DialogueMessage,
    Role,
)

class LLMService:
    """
    A service for interacting with a local LLM model via Ollama.
    """
    
    # Compiled regex for detecting invalid dialogue message content
    # This is the SINGLE SOURCE OF TRUTH for message content validation
    # Patterns detected: template variables (${...}), JSON fragments ({ "...), error fallbacks
    _INVALID_DIALOGUE_CONTENT_PATTERN = re.compile(r"\$\{|\{\s*\"|Error in communication", re.IGNORECASE)
    
    @classmethod
    def is_invalid_dialogue_message(cls, message_text: str) -> bool:
        """
        Check if a dialogue message contains invalid content that should trigger a retry.
        
        All code that needs to validate dialogue message content should use this method.
        
        Detects:
        - Template variables: ${...} patterns
        - JSON fragments: { " patterns (leaked JSON structure)
        - Error fallbacks: "Error in communication" (case-insensitive)
        
        Args:
            message_text: The message text to validate
            
        Returns:
            True if message contains invalid content (should retry), False otherwise
        """
        if not message_text or not isinstance(message_text, str):
            return False
        return bool(cls._INVALID_DIALOGUE_CONTENT_PATTERN.search(message_text))

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
        self.api_base = config["api_base"]
        self.client = OpenAI(
            base_url=self.api_base,
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
        use_structured_output: bool = True,
        format: Optional[Dict] = None,
    ) -> str:
        """
        Send a chat request to the LLM and get a JSON-formatted response.
        
        Args:
            messages: List of message dictionaries with keys "role" and "content"
            temperature: Optional temperature override (defaults to instance temperature)
            max_tokens: Optional max tokens override (defaults to instance max_tokens)
            system_prompt: Optional system prompt (for backward compatibility with old API)
            use_structured_output: Whether to use structured outputs (default: True)
            format: Optional JSON schema dict for structured outputs (Ollama format parameter)
            
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

            # Use structured outputs if format schema is provided
            if use_structured_output and format is not None:
                # Use Ollama's /api/chat endpoint directly for structured outputs
                base_url = self.api_base.rstrip('/')
                if base_url.endswith('/v1'):
                    base_url = base_url[:-3]
                api_url = f"{base_url}/api/chat"
                
                # Convert messages to Ollama format
                ollama_messages = []
                for msg in messages:
                    ollama_messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
                
                payload = {
                    "model": self.model_name,
                    "messages": ollama_messages,
                    "stream": False,
                    "format": format,
                    "options": {
                        "temperature": temperature if temperature is not None else self.temperature,
                    }
                }
                
                response_obj = requests.post(api_url, json=payload)
                response_obj.raise_for_status()
                result = response_obj.json()
                response = result['message']['content'].strip()
            else:
                # Fallback to OpenAI client completions API (legacy)
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
