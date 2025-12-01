from mysite.universe.services.dictionary import DictionaryService
from typing import Optional, List
import json

# Import our navigation models
from mysite.universe.models.navigation import NavigationEvent, ManeuverType
from mysite.universe.models.event import DialogueEvent
from mysite.universe.models.ship import Ship
from mysite.universe.models.actor import Pilot, Controller, Actor
from mysite.universe.services.route_server import RouteService
from mysite.universe.schemas.dialogue_schema import DialogueMessage, DialogueFormat, Role

route_service = RouteService()
dictionary_service = DictionaryService()

class ScriptService:
    """
    Service for converting high-level NavigationEvents into DialogueEvents,
    and for processing DialogueEvents to generate appropriate replies.
    
    It provides:
    • parse_navigation_event(navigation_event, ship)
    Converts a NavigationEvent (e.g. a SUBLIGHT maneuver) into an initial DialogueEvent
    from the ship's pilot. The event text is constructed from various mission details.


    • parse_dialogue_event(pilot_dialogue)
    Given a DialogueEvent (from pilot) that expects a reply, this method generates a standard
    reply from Control.
    """

    _instance = None
    
    @classmethod
    def get_instance(cls, llm=None):
        """Get or create the ScriptService instance with optional LLM configuration."""
        if cls._instance is None:
            if llm is None:
                # Use unified LLMService for structured JSON dialogue generation
                from mysite.universe.services.llm_service import LLMService
                llm = LLMService(quiet_mode=True)
            cls._instance = cls(llm)
        return cls._instance

    def __init__(self, llm):
        self.llm = llm
        self.pilot_call_sign = None
    
    def _validate_text_is_natural_language(self, text: str) -> str:
        """
        Ensure text is natural language, not JSON.
        If text appears to be JSON, extract the message field.
        
        Returns:
            Natural language text (never JSON)
        """
        if not text or not isinstance(text, str):
            return "[Error: Invalid text]"
        
        text = text.strip()
        
        # If it doesn't look like JSON, return as-is
        if not text.startswith('{') and '"message"' not in text:
            return text
        
        # Try to extract message from JSON
        try:
            import json
            from mysite.universe.schemas.dialogue_schema import DialogueMessage
            
            # Find JSON object
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = text[start:end]
                json_data = json.loads(json_str)
                
                if isinstance(json_data, dict) and 'message' in json_data:
                    return json_data['message']
                elif isinstance(json_data, dict):
                    try:
                        msg_obj = DialogueMessage(**json_data)
                        return msg_obj.message
                    except (ValueError, TypeError):
                        pass
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        
        # Try regex extraction
        import re
        match = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if match:
            return match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
        
        # If all else fails, return error message
        return "[Error: Could not extract message from response]"
    
    def _extract_message_from_response(self, response: str) -> tuple[str, Optional[DialogueMessage]]:
        """
        Extract message text from LLM response, handling both JSON and plain text.
        
        CRITICAL: This method MUST always return natural language text, never JSON.
        If JSON parsing fails, we extract the message field or use a fallback.
        
        Args:
            response: The response from the LLM (may be JSON or plain text)
            
        Returns:
            Tuple of (message_text, dialogue_message_obj)
            - message_text: The actual message text to display (ALWAYS natural language)
            - dialogue_message_obj: The DialogueMessage object if response was JSON, None otherwise
        """
        # Strip markdown code blocks if present (LLMs often wrap JSON in ```json ... ```)
        if isinstance(response, str):
            response = response.strip()
            # Remove markdown code blocks
            if response.startswith('```'):
                # Find the closing ```
                end_marker = response.find('```', 3)
                if end_marker > 0:
                    # Extract content between code blocks
                    response = response[3:end_marker].strip()
                    # Remove language identifier if present (e.g., "json")
                    if response.startswith('json'):
                        response = response[4:].strip()
                    elif response.startswith('JSON'):
                        response = response[4:].strip()
        
        # Check if response is JSON
        if isinstance(response, str) and response.strip().startswith('{'):
            # First check if this is a schema definition (common LLM mistake)
            if any(keyword in response for keyword in ['"$defs"', '"description"', '"properties"', '"title"', '"type"']):
                # This is a schema definition - try to extract actual message from it
                import re
                # Look for a JSON object with "message" field that's not part of schema
                # Pattern: find objects with message field
                pattern = r'\{\s*"[^"]*"\s*:\s*[^,}]+\s*,\s*"message"\s*:\s*"((?:[^"\\]|\\.)*)"'
                match = re.search(pattern, response)
                if match:
                    message_text = match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
                    return message_text, None
                else:
                    return "[Error: LLM returned schema definition instead of dialogue message]", None
            
            try:
                # Try to parse as JSON
                json_data = json.loads(response)
                # Check if it's a schema definition
                if '$defs' in json_data or ('properties' in json_data and 'type' in json_data):
                    # It's a schema - try to extract message field
                    if 'message' in json_data:
                        return str(json_data['message']), None
                    return "[Error: LLM returned schema definition instead of dialogue message]", None
                
                msg_obj = DialogueMessage(**json_data)
                return msg_obj.message, msg_obj
            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, try to extract JSON from response
                start = response.find('{')
                end = response.rfind('}') + 1
                if start >= 0 and end > start:
                    try:
                        json_str = response[start:end]
                        json_data = json.loads(json_str)
                        # Check if it's a schema
                        if '$defs' in json_data or ('properties' in json_data and 'type' in json_data):
                            # Try to extract message from schema
                            if 'message' in json_data:
                                return str(json_data['message']), None
                            return "[Error: LLM returned schema definition instead of dialogue message]", None
                        
                        msg_obj = DialogueMessage(**json_data)
                        return msg_obj.message, msg_obj
                    except (json.JSONDecodeError, ValueError):
                        pass
                
                # If JSON parsing fails, try to extract message field with regex
                import re
                # Try to find "message": "..." pattern
                match = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', response)
                if match:
                    # Unescape the message
                    message_text = match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
                    return message_text, None
                
                # Last resort: if it looks like JSON but we can't parse it, return a fallback
                # NEVER return raw JSON
                return "[Error: Could not parse dialogue response]", None
        
        # Plain text response - return as-is
        return response.strip(), None

    def parse_navigation_event(self, nav_event: NavigationEvent, ship: Ship) -> DialogueEvent:
        """       
        Convert a NavigationEvent (e.g. a SUBLIGHT maneuver) into an initial DialogueEvent representing the pilot's broadcast.

        Args:
            nav_event (NavigationEvent): The navigation event to convert
            ship (Ship): The ship performing the maneuver

        Raises:
            ValueError: If the controller name cannot be determined
            ValueError: If the location name cannot be determined
            NotImplementedError: If the navigation event type is not implemented

        Returns:
            DialogueEvent: _description_
        """

        # ====================================================================
        # DIALOGUE TYPE 1: Pilot Request
        # Pilot, on behalf of their ship, requests approval for a maneuver.
        # This is the initial request that starts a dialogue exchange.
        # ====================================================================

        if not ship or not hasattr(ship, 'pilot') or not ship.pilot:
            raise ValueError("Ship must have a pilot to generate dialogue")

        pilot = ship.pilot
        ship_call_sign = ship.name.upper()

        # Determine controller name and expected reply actor
        # CRITICAL: Always use actual names from programmatic sources, never placeholders
        controller_name = None
        expected_reply_actor = None
        
        if hasattr(nav_event, 'controller') and nav_event.controller:
            if hasattr(nav_event.controller, 'role') and nav_event.controller.role == 'CONTROLLER':
                controller_name = nav_event.controller.name
                expected_reply_actor = nav_event.controller
            else:
                controller_name = getattr(nav_event.controller, "name", None)
                if not controller_name and hasattr(nav_event, 'destination') and nav_event.destination:
                    # Derive controller name from destination location
                    controller_name = f"{nav_event.destination.name} Control"
                from mysite.universe.models.actor import Controller
                if controller_name:
                    expected_reply_actor = Controller.objects.filter(name=controller_name).first()
                    if not expected_reply_actor:
                        expected_reply_actor = Controller.create(name=controller_name, location=nav_event.controller)
        
        # If we still don't have a controller, try to derive from destination
        if not controller_name and hasattr(nav_event, 'destination') and nav_event.destination:
            controller_name = f"{nav_event.destination.name} Control"
            from mysite.universe.models.actor import Controller
            expected_reply_actor = Controller.objects.filter(name=controller_name).first()
            if not expected_reply_actor:
                expected_reply_actor = Controller.create(name=controller_name)
        
        # If we truly cannot determine controller, this is an error - we need actual names
        if not controller_name:
            raise ValueError(
                f"Cannot determine controller name for navigation event. "
                f"Ship: {ship_call_sign}, Maneuver: {nav_event.maneuver}, "
                f"Destination: {getattr(nav_event, 'destination', None)}"
            )

        def get_location_name(location) -> str:
            # CRITICAL: Always return actual location name, never placeholder
            if location and hasattr(location, 'name') and location.name:
                return location.name
            # If location doesn't have a name, this is an error condition
            raise ValueError(f"Location object missing name attribute: {location}")

        def get_next_name(nav_event) -> str:
            if hasattr(nav_event, 'next') and nav_event.next:
                return get_location_name(nav_event.next)
            return get_location_name(nav_event.destination)

        # Generate template variations based on maneuver type - these will be passed as examples to the LLM
        templates = []
        if nav_event.maneuver == ManeuverType.LAUNCH:
            templates = [
                f"{controller_name}, {ship_call_sign}, requesting clearance for takeoff from {get_location_name(nav_event.origin)}.",
                f"{controller_name}, this is {ship_call_sign}, ready for launch from {get_location_name(nav_event.origin)}. Requesting clearance.",
                f"{controller_name}, {ship_call_sign} here. Requesting takeoff clearance from {get_location_name(nav_event.origin)}.",
                f"{controller_name}, {ship_call_sign}. Please clear us for {get_location_name(nav_event.origin)} departure.",
            ]
        elif nav_event.maneuver == ManeuverType.DIRECT_ASCENT:
            templates = [
                f"{controller_name}, {ship_call_sign}, requesting a direct ascent burn for {get_location_name(nav_event.destination)}.",
                f"{controller_name}, {ship_call_sign} here. Ready for direct ascent to {get_location_name(nav_event.destination)}. Requesting clearance.",
                f"{controller_name}, this is {ship_call_sign}, requesting permission for direct ascent burn to {get_location_name(nav_event.destination)}.",
                f"{controller_name}, {ship_call_sign}, I need a vector for a direct ascent burn to {get_location_name(nav_event.destination)}. Please advise.",
            ]
        elif nav_event.maneuver == ManeuverType.CIRCULARIZE:
            templates = [
                f"{controller_name}, {ship_call_sign}. Requesting permission to circularize around {get_location_name(nav_event.current)}.",
                f"{controller_name}, {ship_call_sign}, can you transmit a circularization approval for {get_location_name(nav_event.current)} orbit please?",
                f"{controller_name}, {ship_call_sign} here. Ready to circularize orbit around {get_location_name(nav_event.current)}. Requesting clearance.",
                f"{controller_name}, this is {ship_call_sign}, requesting clearance to circularize around {get_location_name(nav_event.current)}.",
            ]
        elif nav_event.maneuver == ManeuverType.PLANE_CHANGE:
            templates = [
                f"{controller_name}, this is {ship_call_sign}, we're ready for our plane change maneuver.",
                f"{controller_name}, {ship_call_sign} here. Requesting clearance for plane change maneuver.",
                f"{controller_name}, this is {ship_call_sign}, ready to execute plane change. Requesting permission.",
            ]
        elif nav_event.maneuver == ManeuverType.DEORBIT:
            templates = [
                f"{controller_name}, this is {ship_call_sign}, we're ready to break orbit and head in to {get_location_name(nav_event.destination)}. Can you give us a vector?",
                f"{controller_name}, {ship_call_sign} here. Ready for deorbit burn to {get_location_name(nav_event.destination)}. Requesting vector.",
                f"{controller_name}, this is {ship_call_sign}, requesting deorbit clearance and vector for {get_location_name(nav_event.destination)}.",
            ]
        elif nav_event.maneuver == ManeuverType.LANDING:
            templates = [
                f"{controller_name}, this is {ship_call_sign}, on final for our landing at {get_location_name(nav_event.destination)}. Please advise.",
                f"{controller_name}, {ship_call_sign} here. On final approach to {get_location_name(nav_event.destination)}. Requesting landing clearance.",
                f"{controller_name}, this is {ship_call_sign}, approaching {get_location_name(nav_event.destination)} for landing. Requesting final clearance.",
            ]
        elif nav_event.maneuver == ManeuverType.INSERTION:
            templates = [
                f"{controller_name}, this is {ship_call_sign}, we're ready for our insertion burn. Can you give us a vector for {get_location_name(nav_event.current)}?",
                f"{controller_name}, {ship_call_sign} here. Ready for insertion burn into {get_location_name(nav_event.current)} orbit. Requesting vector.",
                f"{controller_name}, this is {ship_call_sign}, requesting insertion burn clearance and vector for {get_location_name(nav_event.current)}.",
            ]
        elif nav_event.maneuver == ManeuverType.DOCK:
            templates = [
                f"{controller_name}, this is {ship_call_sign}, requesting docking clearance for {get_location_name(nav_event.destination)}.",
                f"{controller_name}, {ship_call_sign} here. Approaching {get_location_name(nav_event.destination)} for docking. Requesting clearance.",
                f"{controller_name}, this is {ship_call_sign}, requesting permission to dock at {get_location_name(nav_event.destination)}.",
            ]
        elif nav_event.maneuver == ManeuverType.UNDOCK:
            templates = [
                f"{controller_name}, this is {ship_call_sign}, ready for departure. Request permission to undock from {get_location_name(nav_event.origin)}.",
                f"{controller_name}, {ship_call_sign} here. Ready to undock from {get_location_name(nav_event.origin)}. Requesting clearance.",
                f"{controller_name}, this is {ship_call_sign}, requesting undocking clearance from {get_location_name(nav_event.origin)}.",
            ]
        elif nav_event.maneuver == ManeuverType.SUBLIGHT:
            if controller_name == get_next_name(nav_event):
                templates = [
                    f"{controller_name}, this is {ship_call_sign}, we're inbound from {get_location_name(nav_event.origin)}, request a vector for {get_location_name(nav_event.destination)}.",
                    f"{controller_name}, {ship_call_sign} here. Inbound from {get_location_name(nav_event.origin)} to {get_location_name(nav_event.destination)}. Requesting vector.",
                    f"{controller_name}, this is {ship_call_sign}, requesting approach vector from {get_location_name(nav_event.origin)} to {get_location_name(nav_event.destination)}.",
                ]
            elif controller_name == get_location_name(nav_event.current):
                templates = [
                    f"{controller_name}, this is {ship_call_sign}, heading for {get_location_name(nav_event.destination)} and ready for our outbound sublight burn.",
                    f"{controller_name}, {ship_call_sign} here. Ready for outbound sublight burn to {get_location_name(nav_event.destination)}. Requesting clearance.",
                    f"{controller_name}, this is {ship_call_sign}, requesting clearance for outbound sublight burn to {get_location_name(nav_event.destination)}.",
                ]
            else:
                templates = [
                    f"{controller_name}, this is {ship_call_sign}, requesting sublight burn on our way to {get_location_name(nav_event.destination)}.",
                    f"{controller_name}, {ship_call_sign} here. Ready for sublight burn to {get_location_name(nav_event.destination)}. Requesting clearance.",
                    f"{controller_name}, this is {ship_call_sign}, requesting permission for sublight burn to {get_location_name(nav_event.destination)}.",
                ]
        elif nav_event.maneuver == ManeuverType.HYPERSPACE:
            templates = [
                f"{controller_name}, this is {ship_call_sign}. Gravity well shows clear; requesting hyperspace jump to {get_next_name(nav_event)}.",
                f"{controller_name}, {ship_call_sign} here. Gravity well is clear. Requesting clearance for hyperspace jump to {get_next_name(nav_event)}.",
                f"{controller_name}, this is {ship_call_sign}, requesting hyperspace jump clearance to {get_next_name(nav_event)}. Gravity well is clear.",
            ]
        else:
            raise NotImplementedError("Navigation parsing for this maneuver type is not implemented.")

        # Build metadata: preserve existing fields and add rich context for the LLM
        metadata = {
            "control_name": controller_name,
            "ship_name": ship_call_sign,
            "pilot_name": pilot.name,
            "maneuver": nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else nav_event.maneuver,
            "llm_system_prompt": f"{pilot.get_identity_prompt()} {pilot.get_instruction_prompt()}",
            # Build a more specific example using the actual context
            "llm_user_prompt": (
                f"Current situation: {ship_call_sign} is performing a {nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else nav_event.maneuver} maneuver "
                f"from {get_location_name(nav_event.origin)} to {get_location_name(nav_event.destination)}. "
                f"Currently at {get_location_name(nav_event.current)}, next stop is {get_next_name(nav_event)}.\n\n"
                f"You are requesting clearance from {controller_name} for a {nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else nav_event.maneuver} maneuver.\n"
                f"<YOUR LINE> should be something similar to: '{templates[0]}'\n"
                "Given the situation, say <YOUR LINE> in character, but feel free to improvise a bit and make it your own."
            ),
            # Add new context without breaking existing functionality
            "context": {
                "mission": {
                    "origin": get_location_name(nav_event.origin),
                    "destination": get_location_name(nav_event.destination),
                    "controller": controller_name,
                },
                "current_situation": {
                    "ship": ship_call_sign,
                    "location": get_location_name(nav_event.current),
                    "next_waypoint": get_location_name(nav_event.next),
                    "maneuver": nav_event.maneuver.value,
                }
            }
        }

        # Generate LLM text for the pilot's request
        nav_context = {
            "maneuver_type": nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else nav_event.maneuver,
            "current_location": get_location_name(nav_event.current),
            "destination": get_location_name(nav_event.destination),
            "recipient": controller_name
        }
        
        llm_response = self.llm.get_actor_json_response(
            line=templates[0],
            actor=pilot,
            context=[],
            navigation_context=nav_context,
            temperature=getattr(self.llm, 'temperature', None)
        )
        
        # Extract message text from response (handles both JSON and plain text)
        llm_text, dialogue_msg = self._extract_message_from_response(llm_response)
        
        # CRITICAL: Ensure text is natural language, never JSON
        llm_text = self._validate_text_is_natural_language(llm_text)
        
        # Store structured dialogue message in metadata if available
        if dialogue_msg:
            metadata['dialogue_message'] = dialogue_msg.model_dump()
            format_value = dialogue_msg.format.value if hasattr(dialogue_msg.format, 'value') else str(dialogue_msg.format)
            metadata['dialogue_format'] = format_value
            metadata['requires_readback'] = dialogue_msg.requires_readback

        return DialogueEvent(
            timestamp=nav_event.duration,
            actor=pilot,
            text=llm_text,  # Use LLM-generated text instead of template
            expect_reply=True,
            expected_reply_actor=expected_reply_actor,
            duration=RouteService().get_event_duration(nav_event),
            event_type="dialogue",
            metadata=metadata
        )
            
    
    def parse_dialogue_event(self, dialogue: DialogueEvent) -> Optional[DialogueEvent]:
        if not dialogue.expect_reply:
            return None

        # Check if dialogue.text is JSON (LLMService now always returns JSON for get_actor_json_response)
        # Convert dialogue.text to DialogueMessage if it's JSON
        previous_message = None
        if dialogue.text.strip().startswith('{'):
            try:
                previous_message = DialogueMessage(**json.loads(dialogue.text))
            except (json.JSONDecodeError, ValueError):
                # If parsing fails, treat as plain text
                pass

        if getattr(dialogue.actor, 'role', None) == Actor.Role.PILOT:
            # ====================================================================
            # DIALOGUE TYPE 2: Controller Approval
            # Pilot has made a request -> Controller approves it
            # Controllers APPROVE, AUTHORIZE, CONFIRM, and CLEAR - they don't request
            # ====================================================================
            # CRITICAL: Get actual names from metadata - these should always be present
            control_name = dialogue.metadata.get("control_name")
            ship_name = dialogue.metadata.get("ship_name")
            
            # If names are missing, this is an error - we need actual values
            if not control_name:
                raise ValueError(f"Missing control_name in dialogue metadata. Event: {dialogue}")
            if not ship_name:
                raise ValueError(f"Missing ship_name in dialogue metadata. Event: {dialogue}")
            
            control_name = control_name.upper()
            ship_name = ship_name.upper()

            control_actor = dialogue.expected_reply_actor
            if not control_actor:
                control_actor = Controller.objects.filter(name=control_name).first()
                if not control_actor:
                    control_actor = Controller.create(name=control_name)

            # Extract what the pilot requested from their message
            maneuver = dialogue.metadata.get("maneuver", "maneuver")
            current_location = dialogue.metadata.get("context", {}).get("current_situation", {}).get("location", "current location")
            
            # Build an approval example - controllers APPROVE, not request
            # Format: "$SHIP, you are approved for $EVENT" or "$SHIP, cleared for $EVENT"
            if maneuver == "launch" or maneuver == "takeoff":
                reply_text = f"{ship_name}, {control_name} here. You are cleared for takeoff."
            elif maneuver == "landing":
                reply_text = f"{ship_name}, {control_name}. Cleared for landing approach."
            elif maneuver == "insertion":
                reply_text = f"{ship_name}, {control_name}. Insertion burn approved."
            elif maneuver == "circularize":
                reply_text = f"{ship_name}, {control_name} here. Cleared to circularize."
            elif maneuver == "deorbit":
                reply_text = f"{ship_name}, {control_name}. Cleared for deorbit... you can head on in."
            else:
                reply_text = f"{ship_name}, {control_name}. Cleared for {maneuver}."

            # Build context - use DialogueMessage if available, otherwise use string
            context = [previous_message] if previous_message else [dialogue.text]
            
            # Build navigation context for LLM
            # CRITICAL: Always use actual names from metadata, never placeholders
            nav_context = {
                "maneuver_type": dialogue.metadata.get("maneuver"),
                "current_location": dialogue.metadata.get("context", {}).get("current_situation", {}).get("location"),
                "destination": dialogue.metadata.get("context", {}).get("mission", {}).get("destination"),
                "recipient": ship_name  # Controller is responding to the pilot - use actual ship name
            }
            
            # Remove None values to avoid passing "UNKNOWN" defaults
            nav_context = {k: v for k, v in nav_context.items() if v is not None}

            # Log the call before making it - print to console if LLM is not in quiet mode
            import logging
            logger = logging.getLogger('script_service_debug')
            logger.setLevel(logging.DEBUG)
            if not logger.handlers:
                handler = logging.FileHandler('script_service_debug.log', mode='a', encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
                logger.addHandler(handler)
            
            # Print to console if not in quiet mode
            is_debug = not getattr(self.llm, 'quiet_mode', True)
            if is_debug:
                print("\n" + "="*80)
                print("=== CONTROLLER RESPONSE CALL (DIALOGUE TYPE 2) ===")
                print("="*80)
                print(f"Actor: {control_actor.name} (role: {control_actor.role})")
                print(f"Reply text example: {reply_text}")
                print(f"Context: {context}")
                print(f"Nav context: {nav_context}")
                print("="*80 + "\n")
            
            logger.debug(f"=== CONTROLLER RESPONSE CALL ===")
            logger.debug(f"Actor: {control_actor.name} (role: {control_actor.role})")
            logger.debug(f"Reply text example: {reply_text}")
            logger.debug(f"Context: {context}")
            logger.debug(f"Nav context: {nav_context}")
            
            llm_response = self.llm.get_actor_json_response(
                line=reply_text,
                actor=control_actor,
                context=context,
                navigation_context=nav_context,
                temperature=getattr(self.llm, 'temperature', None)
            )
            
            logger.debug(f"Raw LLM response: {llm_response}")
            
            # Extract message text from response (handles both JSON and plain text)
            llm_text, dialogue_msg = self._extract_message_from_response(llm_response)
            
            if is_debug:
                print(f"Raw LLM response: {llm_response}")
                print(f"Extracted text: {llm_text}")
                print(f"Dialogue message object: {dialogue_msg}")
                print("="*80 + "\n")
            
            logger.debug(f"Extracted text: {llm_text}")
            logger.debug(f"Dialogue message object: {dialogue_msg}")
            logger.debug(f"=== END CONTROLLER RESPONSE CALL ===\n")
            
            # CRITICAL: Ensure text is natural language, never JSON
            llm_text = self._validate_text_is_natural_language(llm_text)

            metadata = dialogue.metadata.copy() if dialogue.metadata else {}
            metadata.update({
                'llm_system_prompt': f"{control_actor.get_identity_prompt()} {control_actor.get_instruction_prompt()}",
                # Build a more specific example using the actual context
                'llm_user_prompt': (
                    f"SITUATION: {ship_name} has requested clearance for a {maneuver} maneuver. "
                    f"They are currently at {current_location}.\n\n"
                    f"PILOT'S REQUEST: {dialogue.text}\n\n"
                    f"YOUR JOB: APPROVE their request. Everything is in order - this is routine and good!\n"
                    f"You are NOT requesting anything - you are APPROVING their request.\n\n"
                    f"APPROVE by echoing back what they asked for in affirmative/declarative mode.\n"
                    f"Example: '{ship_name}, {control_name}. Cleared for {maneuver}.'\n"
                    f"Or: '{ship_name}, you are approved for {maneuver}.'\n\n"
                    f"Your response should be an APPROVAL, not a request."
                ),
                'ship_name': ship_name,
                'control_name': control_name,
                # Preserve all existing metadata while ensuring context is maintained
                'context': metadata.get('context', {}),
                'maneuver': metadata.get('maneuver'),
                'pilot_name': metadata.get('pilot_name')
            })
            
            # Store structured dialogue message in metadata if available
            if dialogue_msg:
                metadata['dialogue_message'] = dialogue_msg.model_dump()
                # Handle both enum and string formats
                format_value = dialogue_msg.format.value if hasattr(dialogue_msg.format, 'value') else str(dialogue_msg.format)
                metadata['dialogue_format'] = format_value
                metadata['requires_readback'] = dialogue_msg.requires_readback

            return DialogueEvent(
                timestamp=dialogue.timestamp + 3.0,
                actor=control_actor,
                text=llm_text,
                expect_reply=True,  # Controller expects pilot to acknowledge
                duration=3.0,
                event_type="dialogue",
                metadata=metadata
            )

        elif getattr(dialogue.actor, 'role', None) == Actor.Role.CONTROLLER:
            # ====================================================================
            # DIALOGUE TYPE 3: Pilot Acknowledgment
            # Controller has approved a request -> Pilot acknowledges receipt
            # This is a BRIEF confirmation, not a new request!
            # ====================================================================
            
            # CRITICAL: Get actual ship name and pilot from metadata - should always be present
            ship_name = dialogue.metadata.get("ship_name")
            if not ship_name:
                raise ValueError(f"Missing ship_name in dialogue metadata. Event: {dialogue}")
            ship_name = ship_name.upper()
            control_name = dialogue.actor.name.upper()
            
            # Try to get the actual pilot from metadata first
            pilot_name = dialogue.metadata.get("pilot_name")
            from mysite.universe.models.ship import Ship
            ship = Ship.objects.filter(name=ship_name).first()
            
            if ship and ship.pilot:
                # Use the actual pilot from the ship
                pilot_actor = ship.pilot
            elif pilot_name:
                # Try to find pilot by name from metadata
                pilot_actor = Pilot.objects.filter(name=pilot_name).first()
                if not pilot_actor:
                    # Create pilot with the actual pilot name from metadata
                    pilot_actor = Pilot.create(name=pilot_name, ship=ship)
            else:
                # Last resort: create pilot with ship name (this is the fallback design)
                pilot_actor = Pilot.create(name=ship_name, ship=ship)

            # Build acknowledgment examples - these should be BRIEF confirmations
            acknowledgment_examples = [
                f"{control_name}, {ship_name}. Roger.",
                f"{control_name}, {ship_name}. Acknowledged.",
                f"{control_name}, {ship_name}. Copy that.",
                f"{control_name}, {ship_name}. Thanks.",
                f"{control_name}, {ship_name}. Got it.",
                f"{control_name}, {ship_name}. Understood."
            ]
            # Use the first example as the template
            reply_text = acknowledgment_examples[0]

            # Build context - use DialogueMessage if available, otherwise use string
            context = [previous_message] if previous_message else [dialogue.text]
            
            # Build navigation context for LLM
            # CRITICAL: Always use actual names from metadata, never placeholders
            # CRITICAL: Mark this as an acknowledgment scenario so LLM knows to generate brief confirmation
            nav_context = {
                "maneuver_type": dialogue.metadata.get("maneuver"),
                "current_location": dialogue.metadata.get("context", {}).get("current_situation", {}).get("location"),
                "destination": dialogue.metadata.get("context", {}).get("mission", {}).get("destination"),
                "recipient": control_name,  # Pilot is responding to the controller - use actual controller name
                "dialogue_type": "acknowledgment",  # CRITICAL: Tell LLM this is an acknowledgment, not a request
                "controller_approval": dialogue.text  # The approval message being acknowledged
            }
            
            # Remove None values to avoid passing "UNKNOWN" defaults
            nav_context = {k: v for k, v in nav_context.items() if v is not None}

            # Log the call before making it - print to console if LLM is not in quiet mode
            import logging
            logger = logging.getLogger('script_service_debug')
            logger.setLevel(logging.DEBUG)
            if not logger.handlers:
                handler = logging.FileHandler('script_service_debug.log', mode='a', encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
                logger.addHandler(handler)
            
            # Print to console if not in quiet mode
            is_debug = not getattr(self.llm, 'quiet_mode', True)
            if is_debug:
                print("\n" + "="*80)
                print("=== PILOT ACKNOWLEDGMENT CALL (DIALOGUE TYPE 3) ===")
                print("="*80)
                print(f"Actor: {pilot_actor.name} (role: {pilot_actor.role})")
                print(f"Controller's approval: {dialogue.text}")
                print(f"Acknowledgment examples: {acknowledgment_examples}")
                print(f"Context: {context}")
                print(f"Nav context: {nav_context}")
                print("="*80 + "\n")
            
            logger.debug(f"=== PILOT ACKNOWLEDGMENT CALL ===")
            logger.debug(f"Actor: {pilot_actor.name} (role: {pilot_actor.role})")
            logger.debug(f"Controller's approval: {dialogue.text}")
            logger.debug(f"Acknowledgment examples: {acknowledgment_examples}")
            logger.debug(f"Context: {context}")
            logger.debug(f"Nav context: {nav_context}")

            llm_response = self.llm.get_actor_json_response(
                line=reply_text,
                actor=pilot_actor,
                context=context,
                navigation_context=nav_context,
                temperature=getattr(self.llm, 'temperature', None)
            )
            
            logger.debug(f"Raw LLM response: {llm_response}")
            
            # Extract message text from response (handles both JSON and plain text)
            llm_text, dialogue_msg = self._extract_message_from_response(llm_response)
            
            if is_debug:
                print(f"Raw LLM response: {llm_response}")
                print(f"Extracted text: {llm_text}")
                print(f"Dialogue message object: {dialogue_msg}")
                print("="*80 + "\n")
            
            logger.debug(f"Extracted text: {llm_text}")
            logger.debug(f"Dialogue message object: {dialogue_msg}")
            logger.debug(f"=== END PILOT ACKNOWLEDGMENT CALL ===\n")
            
            # CRITICAL: Ensure text is natural language, never JSON
            llm_text = self._validate_text_is_natural_language(llm_text)

            # Build explicit prompt for acknowledgment
            maneuver = dialogue.metadata.get("maneuver", "maneuver")
            examples_str = "\n".join([f"- '{ex}'" for ex in acknowledgment_examples[:3]])
            
            metadata = dialogue.metadata.copy() if dialogue.metadata else {}
            metadata.update({
                'llm_system_prompt': f"{pilot_actor.get_identity_prompt()} {pilot_actor.get_instruction_prompt()}",
                'llm_user_prompt': (
                    f"SITUATION: {control_name} has just APPROVED your request for a {maneuver} maneuver.\n\n"
                    f"CONTROLLER'S APPROVAL: {dialogue.text}\n\n"
                    f"YOUR JOB: ACKNOWLEDGE receipt of the approval. This is a BRIEF confirmation, NOT a new request!\n\n"
                    f"You are simply confirming that you received and understood the approval.\n"
                    f"Keep it SHORT - one or two words plus your callsign is typical.\n\n"
                    f"Examples of appropriate acknowledgments:\n{examples_str}\n\n"
                    f"Your response should be a BRIEF ACKNOWLEDGMENT, not a new request or question."
                ),
                'ship_name': ship_name,
                'control_name': control_name,
                'pilot_name': pilot_name or pilot_actor.name,
                # Preserve all existing metadata
                'context': metadata.get('context', {}),
                'maneuver': metadata.get('maneuver')
            })
            
            # Store structured dialogue message in metadata if available
            if dialogue_msg:
                metadata['dialogue_message'] = dialogue_msg.model_dump()
                # Handle both enum and string formats
                format_value = dialogue_msg.format.value if hasattr(dialogue_msg.format, 'value') else str(dialogue_msg.format)
                metadata['dialogue_format'] = format_value
                metadata['requires_readback'] = dialogue_msg.requires_readback

            return DialogueEvent(
                timestamp=dialogue.timestamp + 3.0,
                actor=pilot_actor,
                text=llm_text,
                expect_reply=False,  # Pilot acknowledgment ends the exchange
                duration=3.0,
                event_type="dialogue",
                metadata=metadata
            )

        else:
            # Fall back to a generic reply
            return DialogueEvent(
                timestamp=dialogue.timestamp + 5.0,
                actor=dialogue.actor,
                text="Did you say something?",
                expect_reply=False,
                duration=2.0,
                event_type="dialogue",
                metadata=dialogue.metadata
            )

    def parse_navigation_events(self, nav_events, ship):
        """Convert a list of navigation events into dialogue events with updated sequential timestamps.

        Each dialogue event's timestamp is set to the accumulated duration from previous events.
        Uses dataclasses.replace() since DialogueEvent is frozen.
        """
        from dataclasses import replace
        script_events = []
        current_timestamp = 0.0
        for nav_event in nav_events:
            dialogue_event = self.parse_navigation_event(nav_event, ship)
            dialogue_event = replace(dialogue_event, timestamp=current_timestamp)
            current_timestamp += dialogue_event.duration
            script_events.append(dialogue_event)
        return script_events

    def build_situation_prompt(self, nav_event: NavigationEvent, ship: Ship) -> str:
        return f"""Current Situation:
- Ship {ship.name.upper()} is on a journey from {nav_event.origin} to {nav_event.destination}
- Currently at {nav_event.current}, next stop is {nav_event.next}
- Performing a {nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else nav_event.maneuver} maneuver
- Under the direction of {nav_event.controller} 
"""

    def get_dialogue_context(self, dialogue: DialogueEvent) -> dict:
        """Assembles dialogue context from existing metadata and exchanges."""
        context = {
            "navigation": dialogue.metadata.get("context", {}),
            "recent_exchanges": dialogue.metadata.get("recent_exchanges", [])[-3:],  # Last 3 exchanges
            "current_maneuver": dialogue.metadata.get("maneuver"),
        }
        return context

    def format_context_for_llm(self, context: dict, dialogue: DialogueEvent) -> List[str]:
        """Formats context into a list of strings for the LLM."""
        messages = []
        
        # Add situation prompt if we have navigation context
        if nav_context := context["navigation"]:
            mission = nav_context.get("mission", {})
            situation = nav_context.get("current_situation", {})
            
            situation_text = f"""Current Situation:
- Ship {situation.get('ship', 'UNIDENTIFIED VESSEL').upper()} is on a journey from {mission.get('origin')} to {mission.get('destination')}
- Currently at {situation.get('location')}, next stop is {situation.get('next_waypoint')}
- Performing a {situation.get('maneuver')} maneuver
- Under the direction of {mission.get('controller')}
"""
            messages.append(situation_text)
        
        # Add recent exchanges in chronological order
        for exchange in context["recent_exchanges"]:
            messages.append(f"{exchange['speaker']}: {exchange['message']}")
        
        # Add the current message last
        messages.append(dialogue.text)
        
        return messages

    def build_controller_examples(self, ship_name: str, control_name: str) -> str:
        ship_name = ship_name.upper()
        control_name = control_name.upper()
        return f"""Examples of responding to a Pilot, using your identity as {control_name}:
Pilot: "{control_name}, this is {ship_name}, requesting clearance for launch."
{control_name}: "{ship_name}, {control_name}. Cleared for takeoff, heading 090."

Pilot: "{control_name}, this is {ship_name}, ready for insertion burn."
{control_name}: "{ship_name}, {control_name}. Confirmed for insertion burn whenever you're ready."

Remember: You are {control_name}. Always identify yourself when speaking. Never pretend to be the {ship_name}. 
All of your dialogue with {ship_name} should be in the format '{control_name}: "{ship_name}, {control_name}, <approval or instructions here>"'"""

    def build_pilot_examples(self, ship_name: str, control_name: str) -> str:
        ship_name = ship_name.upper()
        control_name = control_name.upper() 
        return f"""Examples of responding to a Controller, using your identity as {ship_name}:

{control_name}: "{ship_name}, {control_name}. Adjust course 45 degrees right."
{ship_name}: "{control_name}, this is {ship_name}. Coming right 45 degrees, confirmed."

{control_name}: "{ship_name}, {control_name}. You're cleared for landing."
{ship_name}: "{control_name}, this is {ship_name}. Beginning landing approach."

Remember: You are {ship_name}. Always identify yourself when speaking. Never pretend to be {control_name}.
All of your dialogue with {control_name} should be in the format '{ship_name}: "{control_name}, {ship_name}, <request or polite concurrence here>"'"""

