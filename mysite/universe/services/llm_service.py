from typing import List, Dict, Any, Optional
from openai import OpenAI
from mysite.universe.models.actor import Actor
import yaml
import io
import sys
from contextlib import redirect_stdout, redirect_stderr

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
        Send a chat message to the LLM and get a response.

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
        try:
            # Optionally redirect stdout/stderr during API call
            if self.quiet_mode:
                import io
                import sys
                from contextlib import redirect_stdout, redirect_stderr
                
                f_stdout = io.StringIO()
                f_stderr = io.StringIO()
                
                with redirect_stdout(f_stdout), redirect_stderr(f_stderr):
                    chat_completion = self.client.chat.completions.create(
                        messages=messages,
                        model=self.model_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
            else:
                chat_completion = self.client.chat.completions.create(
                    messages=messages,
                    model=self.model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            return chat_completion.choices[0].message.content
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
        context: Optional[List[str]] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Generate a version of the provided dialogue line "in character" for the given actor.

        Args:
            line: The dialogue line to convert.
            actor: The Actor instance for which to generate dialogue.
            context: Optional list of previous dialogue lines.
            temperature: Controls randomness (0-1). If None, uses the service's default temperature.

        Returns:
            A string representing the line spoken in character.
        """
        context = context or []
        actor_prompt = actor.get_identity_prompt()
        instruction_prompt = actor.get_instruction_prompt()
        
        system_prompt = f"{actor_prompt} {instruction_prompt}"
        user_message = f"Your line should be something very similar to: '{line}'."
        if context:
            user_message = f"The last thing said to you was: {context[-1]}. {user_message}"
        user_message += " Given the situation, say your line in character."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        return self.chat(
            messages, 
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=self.max_tokens
        ) 