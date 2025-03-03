from typing import List, Dict, Any, Optional
from openai import OpenAI
from mysite.universe.models.navigation import NavigationEvent
import random

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

    def build_controller_prompt(self, 
                               controller_name: str, 
                               controller_location: str, 
                               personality_traits: Optional[List[str]] = None,
                               previous_comms: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Build a system prompt for a traffic controller character.
        
        Args:
            controller_name: Name of the controller (e.g., "Mars Control")
            controller_location: The location the controller is responsible for
            personality_traits: Optional list of personality characteristics
            previous_comms: Optional list of previous communications
            
        Returns:
            A system prompt tailored for a traffic controller character
        """
        # Default personality traits if none provided
        if not personality_traits:
            personality_traits = ["professional", "calm", "focused"]
        
        # Create personality description
        personality_str = ", ".join(personality_traits)
        
        # Random speech patterns or communication quirks
        speech_quirks = [
            "occasionally uses technical jargon",
            "speaks in crisp, efficient sentences",
            "has a slight formal tone",
            "occasionally uses local planetary slang",
            "uses standardized communication protocols",
            "speaks slowly and deliberately",
            "has a reassuring tone",
            "uses occasional humor to ease tense situations",
        ]
        speech_pattern = random.choice(speech_quirks)
        
        prompt = f"""
        You are a space traffic controller at {controller_name}, responsible for {controller_location}.
        Your primary duties include:
        
        1. Providing clearance for spacecraft maneuvers
        2. Monitoring traffic in your jurisdiction
        3. Relaying important information to pilots
        4. Enforcing safety regulations
        
        Personality: You are {personality_str}. You {speech_pattern}.
        
        COMMUNICATION GUIDELINES:
        1. ALWAYS follow standard radio protocol. Begin messages with who you're talking to, then identify yourself
        2. Keep responses concise and efficient
        3. Use appropriate technical terminology
        4. Mention relevant details about local conditions when appropriate
        5. Ask for acknowledgment when giving critical instructions
        6. STAY IN CHARACTER at all times
        
        Respond as this character would to the next transmission, maintaining realistic dialogue flow.
        """
        
        return prompt

    def build_pilot_prompt(self, 
                          pilot_name: str, 
                          ship_name: str, 
                          ship_class: str, 
                          cargo: str,
                          current_location: str,
                          destination: str,
                          personality_traits: Optional[List[str]] = None,
                          last_event: Optional[NavigationEvent] = None) -> str:
        """
        Build a system prompt for a ship pilot character.
        
        Args:
            pilot_name: Name of the pilot
            ship_name: Name of the ship
            ship_class: Class/type of the ship
            cargo: What the ship is carrying
            current_location: Where the ship currently is
            destination: Where the ship is headed
            personality_traits: Optional list of personality traits
            last_event: Optional reference to the last navigation event
            
        Returns:
            A system prompt tailored for a pilot character
        """
        # Default personality traits if none provided
        if not personality_traits:
            personalities = [
                ["experienced", "calm", "methodical"],
                ["young", "eager", "by-the-book"],
                ["veteran", "slightly impatient", "professional"],
                ["seasoned", "laconic", "precise"],
                ["cautious", "meticulous", "respectful"]
            ]
            personality_traits = random.choice(personalities)
        
        # Create personality description
        personality_str = ", ".join(personality_traits)
        
        # Random speech patterns or communication quirks
        speech_quirks = [
            "uses standard communication protocols",
            "occasionally uses informal language",
            "speaks crisply and efficiently",
            "uses the occasional idiom from their home world",
            "has a slight regional accent",
            "is economical with words",
            "is particularly courteous",
            "is slightly nervous around authority",
        ]
        speech_pattern = random.choice(speech_quirks)
        
        # Build experience level
        experience_levels = [
            f"You've been flying {ship_class} vessels for over 15 years",
            f"You're relatively new to {ship_class} vessels but compensate with careful attention",
            f"You have extensive experience with this route",
            f"This is your first time on this particular route",
            f"You've served on numerous ships before taking command of {ship_name}"
        ]
        experience = random.choice(experience_levels)
        
        # Build event context if available
        event_context = ""
        if last_event:
            event_context = f"""
            Your current maneuver is a {last_event.maneuver.name} toward {last_event.target.name}.
            You need to communicate with {last_event.controller.name if last_event.controller else 'local control'}.
            """
        
        prompt = f"""
        You are {pilot_name}, the pilot of the {ship_class} vessel '{ship_name}'.
        
        CURRENT MISSION:
        - Carrying: {cargo}
        - Current location: {current_location}
        - Destination: {destination}
        
        ABOUT YOU:
        - Personality: You are {personality_str}
        - Experience: {experience}
        - Communication style: You {speech_pattern}
        
        {event_context}
        
        COMMUNICATION GUIDELINES:
        1. ALWAYS follow standard radio protocol. Begin messages with who you're talking to, then identify yourself
        2. Use appropriate technical terminology for space navigation
        3. Keep communications professional but with your personal touch
        4. Include relevant details about your ship or cargo when appropriate
        5. Acknowledge instructions from control
        6. STAY IN CHARACTER at all times
        
        Respond as this character would to the next transmission, maintaining realistic dialogue flow.
        """
        
        return prompt

    def build_pilot_greeting(self,
                            pilot_name: str,
                            ship_name: str,
                            controller_name: str,
                            maneuver: str,
                            cargo: str = None) -> str:
        """
        Build a system prompt for a pilot's initial greeting to control.
        
        Args:
            pilot_name: Name of the pilot
            ship_name: Name of the ship
            controller_name: Name of the control station being contacted
            maneuver: The maneuver being requested
            cargo: Optional cargo information
            
        Returns:
            A prompt for generating an initial greeting message
        """
        system_prompt = f"""
        You are {pilot_name}, the pilot of vessel '{ship_name}'.
        You need to make initial contact with {controller_name} to request clearance for a {maneuver} maneuver.
        
        GUIDELINES:
        1. Follow proper radio protocol format: "<recipient>, this is <sender>"
        2. Be professional and concise
        3. Include your ship name, current location, and requested maneuver
        4. Mention your cargo if relevant: "{cargo if cargo else 'standard cargo'}"
        5. Ask specifically for the clearance you need
        6. Your response should ONLY be the initial greeting message, nothing else
        7. Keep it to 2-3 sentences maximum
        
        Generate ONLY the pilot's initial radio message to the controller.
        """
        
        # The user message is just a prompt to generate the greeting
        user_message = f"Generate initial contact message from {ship_name} to {controller_name} requesting {maneuver}."
        
        return self.generate_with_system_prompt(
            user_message=user_message,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=150
        )
    
    def generate_in_character_response(self,
                                     character_type: str,
                                     incoming_message: str,
                                     **character_params) -> str:
        """
        Generate a response from a character to an incoming message.
        
        Args:
            character_type: "controller" or "pilot"
            incoming_message: The message they're responding to
            **character_params: Parameters for the specific character type
            
        Returns:
            An in-character response to the incoming message
        """
        if character_type.lower() == "controller":
            system_prompt = self.build_controller_prompt(**character_params)
        elif character_type.lower() == "pilot":
            system_prompt = self.build_pilot_prompt(**character_params)
        else:
            return "Error: Invalid character type. Use 'controller' or 'pilot'."
        
        return self.generate_with_system_prompt(
            user_message=f"Respond to this incoming transmission: \"{incoming_message}\"",
            system_prompt=system_prompt,
            temperature=0.75,  # Slightly higher temperature for character variety
            max_tokens=200
        ) 