"""
TextService provides natural language generation capabilities for the universe simulation.

This service uses the Qwen2.5 model to generate contextually appropriate dialogue for
various in-game scenarios such as ship-to-station communications, mission briefings,
and character interactions.
"""

import os
import torch
from typing import Dict, List, Optional, Union
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_PATH = "mysite/universe/models/language/Qwen2.5/checkpoints/qwen2.5-0.5b-instruct-q4_0.gguf"

class TextService:
    """
    Service for generating text using the Qwen2.5 model.
    
    This class provides methods to generate contextually appropriate dialogue
    for various in-game scenarios, particularly for space navigation communications.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the TextService with the Qwen2.5 model.
        
        Args:
            model_path: Path to the Qwen2.5 model. If None, uses the default path.
        """
        self.model_path = model_path or MODEL_PATH
        self.model = None
        self.tokenizer = None
        self._load_model()
    
    def _load_model(self):
        """Load the Qwen2.5 model and tokenizer."""
        try:
            print(f"Loading Qwen2.5 model from {self.model_path}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
            
            # Use bfloat16 precision and only load on demand for memory efficiency
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                device_map="auto",
                torch_dtype=torch.bfloat16,
                trust_remote_code=True
            )
            print("Qwen2.5 model loaded successfully")
        except Exception as e:
            print(f"Error loading Qwen2.5 model: {e}")
            raise
    
    def generate_text(self, prompt: str, max_length: int = 200, temperature: float = 0.7) -> str:
        """
        Generate text based on a prompt.
        
        Args:
            prompt: The prompt to generate text from
            max_length: Maximum length of generated text
            temperature: Controls randomness (lower = more deterministic)
            
        Returns:
            Generated text as a string
        """
        if not self.model or not self.tokenizer:
            raise RuntimeError("Model not loaded. Please ensure _load_model() completed successfully.")
        
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        # Generate with some randomness for variety
        outputs = self.model.generate(
            inputs.input_ids,
            max_new_tokens=max_length,
            temperature=temperature,
            top_p=0.9,
            do_sample=True
        )
        
        # Decode and extract just the generated response (not the prompt)
        full_output = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        response = full_output[len(self.tokenizer.decode(inputs.input_ids[0], skip_special_tokens=True)):]
        
        return response.strip()
    
    def generate_controller_dialogue(
        self, 
        controller_name: str, 
        ship_name: str, 
        context: str,
        controller_personality: Optional[str] = None
    ) -> str:
        """
        Generate dialogue for a traffic controller responding to a ship.
        
        Args:
            controller_name: Name/callsign of the controller (e.g., "CERES CONTROL")
            ship_name: Name of the ship being addressed
            context: Recent dialogue or situation context
            controller_personality: Optional personality traits for the controller
            
        Returns:
            Generated controller dialogue
        """
        personality_desc = ""
        if controller_personality:
            personality_desc = f"You have the following personality: {controller_personality}. "
        
        prompt = f"""You are an orbital traffic controller handling ship flights in and out of {controller_name.split()[0]}. 
Your radio callsign is "{controller_name}". {personality_desc}You respond to ships by saying their ship name and then your name, 
and then going ahead with what you have to say. You do not often make small-talk. You always keep your messages brief and professional.

The recent dialogue is:
{context}

Your response (using the proper callsign format):
"""
        
        return self.generate_text(prompt, max_length=150, temperature=0.6)
    
    def generate_mission_brief(self, cargo: str, origin: str, destination: str) -> str:
        """
        Generate a mission briefing for a cargo transport mission.
        
        Args:
            cargo: Description of the cargo
            origin: Starting location
            destination: Destination location
            
        Returns:
            A mission briefing text
        """
        prompt = f"""Generate a brief mission description for a space cargo transport mission.
The ship is carrying {cargo} from {origin} to {destination}.
The mission brief should be concise, professional, and include details about the cargo's importance.
Mission brief:
"""
        
        return self.generate_text(prompt, max_length=300)
    
    def generate_system_announcement(self, event_type: str, location: str, details: str) -> str:
        """
        Generate a system announcement for in-game events.
        
        Args:
            event_type: Type of event (e.g., "docking", "departure", "emergency")
            location: Location where the event is happening
            details: Additional details about the event
            
        Returns:
            A system announcement text
        """
        prompt = f"""Generate a short system announcement for a {event_type} event at {location}.
Additional details: {details}
The announcement should be formal and concise, as if broadcast over a station's PA system.
Announcement:
"""
        
        return self.generate_text(prompt, max_length=100, temperature=0.5)
