from typing import List, Dict, Any, Optional
from openai import OpenAI

class LLMService:
    """
    A service for interacting with the Qwen2.5 model via Ollama.
    """
    
    def __init__(self, model_name: str = "qwen2.5:0.5b"):
        """
        Initialize the LLM service.
        
        Args:
            model_name: The name of the model to use (e.g., "qwen2.5:0.5b", "qwen2.5:7b")
        """
        self.client = OpenAI(
            base_url='http://localhost:11434/v1/',
            api_key='ollama',  # required but ignored by Ollama
        )
        self.model_name = model_name
    
    def chat(self, 
            messages: List[Dict[str, str]], 
            temperature: float = 0.7, 
            max_tokens: int = 512,
            system_prompt: Optional[str] = None) -> str:
        """
        Send a chat message to the LLM and get a response.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            temperature: Controls randomness (0-1)
            max_tokens: Maximum tokens in the response
            system_prompt: Optional system prompt to override default
            
        Returns:
            The LLM's response text
        """
        # If system prompt is provided, add or replace system message
        if system_prompt:
            # Check if there's already a system message
            has_system = any(msg.get('role') == 'system' for msg in messages)
            
            if has_system:
                # Replace existing system message
                messages = [
                    {'role': 'system', 'content': system_prompt} if msg.get('role') == 'system' else msg
                    for msg in messages
                ]
            else:
                # Add system message at the beginning
                messages = [{'role': 'system', 'content': system_prompt}] + messages
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            return f"Error communicating with LLM: {str(e)}"
    
    def generate_with_system_prompt(self, 
                                user_message: str, 
                                system_prompt: str,
                                temperature: float = 0.7, 
                                max_tokens: int = 512) -> str:
        """
        Convenience method to generate text with a system prompt and user message.
        
        Args:
            user_message: The user's message
            system_prompt: The system prompt to set context
            temperature: Controls randomness (0-1)
            max_tokens: Maximum tokens in the response
            
        Returns:
            The LLM's response text
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        return self.chat(messages, temperature, max_tokens) 