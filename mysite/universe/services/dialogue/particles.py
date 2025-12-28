"""
Concrete dialogue particle classes.

Each particle type represents a specific dialogue exchange type with its own
examples, counterexamples, and prompt structure. Particles inherit from
DialogueParticle and implement the abstract methods.
"""
import random
from typing import List, Dict, Optional
from .base import DialogueParticle, UserPromptData


class PilotRequest(DialogueParticle):
    """
    Base class for pilot request particles.
    
    Provides shared logic for all pilot request types (LaunchRequest,
    CircularizationRequest, etc.). Subclasses only need to implement
    get_examples() and get_counterexample().
    
    Subclasses can access the nav_context to get the destination, maneuver_type, current_location, etc.
    Syntax is self.nav_context.get("destination", "destination")
    """
    
    def get_role_description(self) -> str:
        """
        Return role description for pilot.
        
        Format: "{pilot_name}, the pilot of the {ship_name}"
        
        Returns:
            Role description string.
        """
        ship_name = self.get_sender_callsign()
        pilot_name = self.actor.name
        return f"{pilot_name}, the pilot of the {ship_name}"
    
    def get_situation_description(self) -> str:
        """
        Return situation description from nav_context.
        
        Builds description like: "{sender} is a ship intending to fly to {destination}
        from {current}. The {sender} needs permission from {recipient} to {maneuver}."
        
        Returns:
            Situation description string.
        """
        sender = self.get_sender_callsign()
        destination = self.nav_context.get("destination", "destination")
        maneuver = self.nav_context.get("maneuver_type", "maneuver")
        current = self.nav_context.get("current_location", "current location")
        
        return f"{sender} is a ship intending to fly to {destination} from {current}. The {sender} is asking for permission from {self.recipient} to {maneuver.lower()}. CRITICAL: the sender MUST NEVER grant themselves permission; they MUST ask or request."
    
    def generate_procedural_greeting(self) -> str:
        """
        Generate procedural greeting for initial contact requests.
        
        Protocol: "{recipient}, this is {sender}." (with weighted variants)
        The greeting is generated procedurally to ensure correct protocol ordering.
        All PilotRequest subclasses inherit this method.
        
        Returns:
            Greeting string to prepend to message content.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        # Generate the procedural greeting prefix with weighted variants
        # Default greeting occurs ~90% of the time, variants ~5% each
        greetings = [
            f"{recipient}, this is {sender}.",   # Default (90%)
            f"{recipient}, {sender} here.",      # Variant 1 (5%)
            f"{recipient}, {sender}.",            # Variant 2 (5%)
        ]
        weights = [0.90, 0.05, 0.05]
        
        return random.choices(greetings, weights=weights, k=1)[0]
    
    def get_next_particle_probabilities(self) -> Dict[str, float]:
        """
        Return probabilities for what can follow a pilot request.
        
        Default: Requests are usually approved, but can sometimes result in holds.
        Subclasses can override for maneuver-specific behavior.
        
        Returns:
            Dict mapping particle types to probabilities.
        """
        return {
            "response": 0.95,      # Usually approved quickly
            "hold_response": 0.05,  # Sometimes held (traffic, hazards)
        }
    
    def format_user_prompt(self, data: UserPromptData) -> str:
        """
        Format user prompt with pilot-specific forbidden words instruction.
        
        Adds a forbidden words section to prevent pilots from granting themselves
        clearance or using controller language.
        """
        # Get the base prompt from parent class
        prompt = super().format_user_prompt(data)
        
        # Insert forbidden words section right after role/situation/sender/recipient
        # The base format always has: role, situation, sender, recipient, optional fields, empty line,
        # then either "Below is the LAST_DIALOGUE_LINE" or "Here are three GOOD example"
        lines = prompt.split('\n')
        
        # Find the empty line that comes right before the examples section
        # Look for lines that start with "Below is" or "Here are" - the empty line is just before them
        insert_index = None
        for i, line in enumerate(lines):
            if line.startswith("Below is the LAST_DIALOGUE_LINE") or line.startswith("Here are three GOOD example messages"):
                # The empty line should be 1-2 lines before this
                if i > 0 and lines[i-1].strip() == "":
                    insert_index = i - 1
                    break
        
        if insert_index is not None:
            forbidden_section = [
                "",
                "FORBIDDEN WORDS: cleared, approved, denied, authorized",
                "BETTER CHOICES: maneuvering, burning, executing, requesting, standing by",
                "CRITICAL: You are REQUESTING clearance, never GRANTING or APPROVING clearance. Even when clearance has been granted to you, you reply that you're COMPLYING or EXECUTING.",
            ]
            # Insert the forbidden section
            lines[insert_index:insert_index] = forbidden_section
        
        return '\n'.join(lines)


# ============================================================================
# FLIGHT SEQUENCE: Request classes ordered by typical mission flow
# ============================================================================
# 1. LAUNCH/UNDOCK → 2. CIRCULARIZE → 3. SUBLIGHT/TRANSFER → 
# 4. INSERTION → 5. CIRCULARIZE → 6. DEORBIT → 7. LANDING/DOCK
# ============================================================================


class LaunchRequest(PilotRequest):
    """
    Pilot requesting launch clearance.
    
    Used when a pilot requests permission to launch/takeoff from a planet or station.
    This is typically the first maneuver in a flight sequence.
    """
    
    def get_examples(self) -> List[str]:
        """
        Return 5+ examples of launch requests.
        
        Returns:
            List of example launch request dialogue strings.
        """
        origin = self.nav_context.get("current_location", "current location")
        destination = self.nav_context.get("destination", "destination")
        azimuth = self.nav_context.get("azimuth_deg", "zero nine zero")
        
        return [
            f"Requesting launch clearance. We're planned for {azimuth} degrees departure, bound for {destination}. Standing by for your go.",
            f"Ready for launch, requesting authorization. Our flight plan calls for {azimuth} degrees departure angle to {destination}.",
            f"Requesting clearance for lift-off. We're filed for {azimuth} degrees departure lane, heading to {destination}.",
            f"Standing by on {origin}. Requesting launch clearance on {azimuth} degrees departure lane, bound for {destination}.",
            f"Ready for launch, requesting clearance. Our departure azimuth is {azimuth} degrees, destination {destination}.",
            f"Requesting permission to launch. We're planned on {azimuth} degrees departure angle, outbound for {destination}.",
            f"Our launch window is open. Requesting clearance for {azimuth} degrees departure lane to {destination}.",
            f"Requesting launch authorization. We're prepped for {azimuth} degrees departure, destination {destination}.",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do for launch requests.
        
        Returns:
            Counterexample string.
        """
        return "[DON'T DO THIS!] Earth Control, permission granted. We're the STELLAR HORIZON and we're cleared for launch."
    
    def get_next_particle_probabilities(self) -> Dict[str, float]:
        """
        Return probabilities for what can follow a launch request.
        
        Requests always get a response: 95% routine approval, 5% hold.
        
        Returns:
            Dict mapping particle types to probabilities.
        """
        return {
            "response": 0.95,      # 95% routine positive approval
            "hold_response": 0.05,  # 5% hold (traffic, hazards)
        }
    
    def get_delay_until_next(self) -> Optional[float]:
        """
        Return delay until next event.
        
        Launch requests typically get quick responses (3 seconds).
        Future: Could be longer if altitude_km is very high.
        
        Returns:
            Seconds until next event.
        """
        # Future: Could calculate based on altitude_km
        # altitude = float(self.nav_context.get("altitude_km", 150))
        # return 3.0 + (altitude / 100.0)  # Longer for higher altitudes
        return 3.0


class CircularizationRequest(PilotRequest):
    """
    Pilot requesting circularization burn clearance.
    
    Used when a pilot requests permission to circularize their orbit around a body.
    Typically occurs after launch (to establish initial orbit) or after insertion
    (to circularize around destination).
    """
    
    def get_examples(self) -> List[str]:
        """
        Return 5+ examples of circularization requests.
        
        Returns:
            List of example circularization request dialogue strings.
        """
        # Get current inclination if available, otherwise use placeholder
        current_inclination = self.nav_context.get("current_inclination_deg", "twenty")
        if isinstance(current_inclination, (int, float)):
            current_inclination = f"{int(current_inclination)}"
        
        return [
            f"We're suborbital and planning to circularize. Our current inclination is {current_inclination} degrees. Can you give us an approved orbit?",
            f"Approaching apogee, requesting clearance to circularize. We're at {current_inclination} degrees inclination. What orbit parameters do you want us to target?",
            f"Coasting to apogee. Our inclination is {current_inclination} degrees. Requesting permission to circularize - can you specify the approved altitude?",
            f"We're ready for circularization burn. Currently at {current_inclination} degrees inclination. Requesting clearance and orbit parameters.",
            f"Ascent burn complete. We're suborbital at {current_inclination} degrees inclination. Can you give us clearance and an approved circularization orbit?",
            f"Requesting circularization clearance. We're approaching apogee on {current_inclination} degrees inclination. What orbit do you want us to establish?",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do for circularization requests.
        
        Returns:
            Counterexample string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        destination = self.nav_context.get("destination", "destination")
        inclination_deg = 20
        return f"[DON'T DO THIS!] {recipient}, my circular orbit to {destination} is approved, {sender}. Use {inclination_deg} degrees of altitude. Over."


class SublightRequest(PilotRequest):
    """
    Pilot requesting sublight burn clearance.
    
    Used when a pilot requests permission for sublight travel between locations
    within a star system. Typically occurs after circularization and before
    insertion at destination.
    """
    
    def get_examples(self) -> List[str]:
        """
        Return 5+ examples of sublight requests.
        
        Returns:
            List of example sublight request dialogue strings.
        """
        destination = self.nav_context.get("destination", "destination")
        maneuver = (self.nav_context.get("maneuver_type") or "sublight").lower()
        # Transfers in this universe are sublight burns; "burn" keeps it consistent with design docs.
        action = "burn"
        if maneuver == "transfer":
            action = "transfer burn"
        
        return [
            f"Orbit is stable. We're outbound for {destination}. Requesting clearance for {action} and a departure azimuth.",
            f"Requesting clearance for {action} to {destination}. Can you give us an azimuth for departure?",
            f"Ready for {action} to {destination}. Requesting departure azimuth and clearance to proceed.",
            f"We're ready to depart orbit and begin {action} outbound for {destination}. Requesting departure azimuth.",
            f"Orbit is circular. Requesting permission to begin {action} toward {destination}. What azimuth do you want us to fly?",
            f"Requesting {action} clearance to {destination}. Please specify our departure azimuth.",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do for sublight requests.
        
        Returns:
            Counterexample string.
        """
        return "[DON'T DO THIS!] We're approved for sublight. Permission granted, over."


class HyperspaceRequest(PilotRequest):
    """
    Pilot requesting hyperspace jump clearance.

    Used when a pilot requests permission to initiate a hyperspace jump between star systems.
    """

    def get_examples(self) -> List[str]:
        destination = self.nav_context.get("destination", "destination")

        return [
            f"Requesting clearance for hyperspace jump to {destination}. Please provide a jump azimuth.",
            f"We're ready to initiate hyperspace jump to {destination}. Requesting authorization and jump azimuth.",
            f"Requesting hyperspace clearance to {destination}. Can you give us an approved azimuth for the jump?",
            f"Standing by for hyperspace jump. We're bound for {destination}. Requesting jump authorization and azimuth.",
            f"Ready for hyperspace jump to {destination}. Requesting clearance and jump azimuth.",
        ]

    def get_counterexample(self) -> str:
        return "[DON'T DO THIS!] Hyperspace jump is approved. Permission granted, over."


class InsertionRequest(PilotRequest):
    """
    Pilot requesting orbital insertion burn clearance.
    
    Used when a pilot requests permission for an insertion burn into orbit around the LOCAL body.
    Typically occurs after sublight travel when entering a body's sphere of influence.
    
    NOTE: Uses current_location (where insertion happens), NOT destination (final journey endpoint).
    """
    
    def get_examples(self) -> List[str]:
        """
        Return 5+ examples of insertion requests.
        
        Returns:
            List of example insertion request dialogue strings.
        """
        # Use current_location - that's where the insertion is happening
        # NOT destination, which is the final journey endpoint
        local_body = self.nav_context.get("current_location", "destination")
        current_inclination = self.nav_context.get("current_inclination_deg", "twenty")
        if isinstance(current_inclination, (int, float)):
            current_inclination = f"{int(current_inclination)}"
        
        return [
            f"Approaching {local_body}. Requesting clearance for insertion burn. Can you give us approved orbit parameters?",
            f"Ready for orbital insertion at {local_body}. Our current inclination is {current_inclination} degrees. What orbit do you want us to establish?",
            f"Requesting permission for insertion maneuver into {local_body} orbit. Can you specify the target altitude and inclination?",
            f"Entering {local_body} sphere of influence. Requesting insertion clearance and orbit parameters.",
            f"Approaching {local_body}. We're at {current_inclination} degrees inclination. Requesting clearance for insertion burn - what orbit should we target?",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do for insertion requests.
        
        Returns:
            Counterexample string.
        """
        return "[DON'T DO THIS!] Permission granted. Your request is approved."


class DeorbitRequest(PilotRequest):
    """
    Pilot requesting deorbit burn clearance.
    
    Used when a pilot requests permission to deorbit from orbit around the LOCAL body.
    Typically occurs after circularization, before landing.
    
    NOTE: Uses current_location (where deorbit happens), NOT destination (final journey endpoint).
    """
    
    def get_examples(self) -> List[str]:
        """
        Return 5+ examples of deorbit requests.
        
        Returns:
            List of example deorbit request dialogue strings.
        """
        # Use current_location - that's where the deorbit is happening
        local_body = self.nav_context.get("current_location", "destination")
        current_altitude = self.nav_context.get("current_altitude_km", "two hundred")
        if isinstance(current_altitude, (int, float)):
            current_altitude = f"{int(current_altitude)}"
        
        return [
            f"Orbit is stable at {current_altitude} kilometers. Requesting clearance for deorbit burn to {local_body}. Can you give us entry parameters?",
            f"Ready for deorbit, requesting authorization. We're at {current_altitude} kilometers altitude. What entry angle do you want us to use?",
            f"Requesting permission to deorbit for {local_body}. Currently at {current_altitude} kilometers. Can you specify the deorbit burn parameters?",
            f"Request deorbit burn clearance. We're at {current_altitude} kilometers. What entry corridor should we target?",
            f"Orbit is stable. Requesting clearance to begin deorbit sequence to {local_body}. Can you give us approved entry parameters?",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do for deorbit requests.
        
        Returns:
            Counterexample string.
        """
        return "[DON'T DO THIS!] I've approved the deorbit request and you can begin."


class LandingRequest(PilotRequest):
    """
    Pilot requesting landing clearance.
    
    Used when a pilot requests permission to land on the LOCAL body (planet or moon).
    Typically the final maneuver in a flight sequence (after deorbit).
    
    NOTE: Uses current_location (where landing happens), NOT destination (final journey endpoint).
    """
    
    def get_examples(self) -> List[str]:
        """
        Return 5+ examples of landing requests.
        
        Returns:
            List of example landing request dialogue strings.
        """
        # Use current_location - that's where the landing is happening
        local_body = self.nav_context.get("current_location", "destination")
        
        return [
            f"Deorbit complete. Requesting clearance for final approach and landing on {local_body}. Can you give us approach parameters?",
            f"Ready for landing approach to {local_body}, requesting authorization and approach heading.",
            f"Requesting permission to land on {local_body}. Can you specify our approach vector?",
            f"Request landing clearance for {local_body}. What approach parameters should we use?",
            f"On final approach to {local_body}. Requesting landing clearance and approach instructions.",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do for landing requests.
        
        Returns:
            Counterexample string.
        """
        return f"[DON'T DO THIS!] We are fully approved to land. Permission granted for final approach to {self.nav_context.get('destination', 'our destination')}."


class GenericRequest(PilotRequest):
    """
    Generic pilot request fallback for unspecified maneuvers.
    
    Used when no specific request particle exists for a maneuver type.
    Provides generic templates that work for any maneuver.
    """
    
    def get_examples(self) -> List[str]:
        """
        Return generic examples that work for any maneuver type.
        
        Uses maneuver_type from nav_context to customize examples.
        
        Returns:
            List of generic example dialogue strings.
        """
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"Requesting clearance for {maneuver}. Can you give us approved parameters?",
            f"Ready for {maneuver}, requesting authorization and maneuver parameters.",
            f"Requesting clearance for {maneuver} maneuver. What parameters should we use?",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return generic counterexample.
        
        Returns:
            Generic counterexample string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()

        return f"[DON'T DO THIS!] {sender}, {recipient}, our plan for {maneuver} is now approved. Over."


class RadioResponse(DialogueParticle):
    """
    Controller responding to pilot request.
    
    Used when controller grants clearance or provides instructions.
    """
    
    def get_role_description(self) -> str:
        """
        Return role description for controller.
        
        Format: "An anonymous space traffic controller at {controller_name}"
        
        Returns:
            Role description string.
        """
        controller_name = self.actor.name
        return f"An anonymous space traffic controller at {controller_name}"
    
    def get_situation_description(self) -> str:
        """
        Return situation description for controller response.
        
        Builds description like: "{recipient} has requested clearance for {maneuver}.
        {sender} is responding with specific appropriate details about the maneuver."
        
        Returns:
            Situation description string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return f"{recipient} has requested clearance for {maneuver}. {sender} is responding with specific appropriate details about the maneuver."
    
    def generate_procedural_greeting(self) -> str:
        """
        Generate procedural greeting for controller responses.
        
        Protocol: "{recipient}, {sender}." (with weighted variants)
        All RadioResponse subclasses inherit this method.
        
        Returns:
            Greeting string to prepend to message content.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        # Controller responses use simpler greeting pattern
        # Default: "{recipient}, {sender}." (90%), variants (5% each)
        greetings = [
            f"{recipient}, {sender}.",            # Default (90%)
            f"{recipient}, {sender} here.",       # Variant 1 (5%)
            f"{recipient}, this is {sender}.",    # Variant 2 (5%)
        ]
        weights = [0.90, 0.05, 0.05]
        
        return random.choices(greetings, weights=weights, k=1)[0]
    
    def get_examples(self) -> List[str]:
        """
        Return examples of controller responses with detailed instructions.
        
        Generates context-aware examples based on maneuver type and nav_context.
        Uses ControllerPhysicsService to generate realistic physics-based parameters.
        
        Returns:
            List of example dialogue strings.
        """
        from mysite.universe.services.controller_physics import ControllerPhysicsService
        
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        destination = self.nav_context.get("destination", "")
        
        # Generate physics-based parameters
        physics_params = {}
        if self.actor:
            physics_params = ControllerPhysicsService.generate_parameters(self.actor, self.nav_context)
        
        # Build examples based on maneuver type with physics parameters
        examples = []
        
        # Launch/direct ascent examples
        if maneuver in ["launch", "direct_ascent"]:
            apogee_km = physics_params.get("apogee_km")
            inclination_deg = physics_params.get("inclination_deg")
            azimuth_deg = physics_params.get("azimuth_deg")
            
            if apogee_km and inclination_deg:
                # Format azimuth as three-digit heading (e.g., "090 degrees")
                azimuth_str = f"{int(azimuth_deg):03d}" if azimuth_deg else ""
                examples.extend([
                    f"Your launch is approved. Head up to {int(apogee_km)} kilometers apogee, launch azimuth {azimuth_str} degrees. Check in when you reach apogee.",
                    f"Launch clearance granted. Target apogee {int(apogee_km)} kilometers, {int(inclination_deg)} degrees inclination.",
                    f"Your launch burn is approved. You can head up to {int(apogee_km)} kilometers, try to keep it near {int(inclination_deg)} degrees, and check in when you get to orbit.",
                    "We have your flight plan and your launch window is open. You are go.",
                ])
            else:
                examples.extend([
                    "Your launch burn is approved. Execute when ready.",
                    "You're cleared for launch, proceed.",
                    "Launch clearance granted. Proceed when ready.",
                ])
        
        # Orbital maneuvers (insertion, circularization)
        elif maneuver in ["insertion", "circularization"]:
            altitude_km = physics_params.get("altitude_km")
            inclination_deg = physics_params.get("inclination_deg")
            
            if altitude_km and inclination_deg:
                examples.extend([
                    f"Cleared for {maneuver} burn to {int(altitude_km)} kilometers, {int(inclination_deg)} degrees inclination.",
                    f"Approved for {maneuver} to {int(inclination_deg)} degrees, {int(altitude_km)} kilometers.",
                    f"Cleared for orbital {maneuver}, you're go. Make your own way, try to keep it near {int(inclination_deg)} degrees.",
                    f"{maneuver.capitalize()} clearance granted. You can have any achievable slot.",
                    f"Bring it to {int(altitude_km)} kilometers, {int(inclination_deg)} degrees.",
                ])
            else:
                examples.extend([
                    f"Cleared for {maneuver}, proceed when ready.",
                    f"{maneuver.capitalize()} clearance granted.",
                    f"Authorization granted for {maneuver} maneuver.",
                ])
        
        # Departure maneuvers (sublight, transfer, hyperspace)
        elif maneuver in ["sublight", "transfer", "hyperspace"]:
            action = "jump" if maneuver == "hyperspace" else "burn"
            azimuth_deg = (
                physics_params.get("azimuth_deg")
                or physics_params.get("departure_angle_deg")
            )
            if azimuth_deg is None:
                azimuth_deg = random.uniform(0.0, 360.0)
            farewells = ["Safe travels.", "Good luck.", "See you again soon.", "Take care.", "Fly safe."]
            farewell = random.choice(farewells)
            azimuth_str = f"{int(float(azimuth_deg)) % 360:03d}"
            
            if destination:
                examples.extend([
                    f"You are go for {maneuver} {action} to {destination}. Depart on azimuth {azimuth_str} degrees. {farewell}",
                    f"{maneuver.capitalize()} {action} to {destination} is approved. Azimuth {azimuth_str} degrees. {farewell}",
                    f"Cleared for {maneuver} {action}. Azimuth {azimuth_str} degrees.",
                    f"{maneuver.capitalize()} clearance granted. Depart on azimuth {azimuth_str} degrees.",
                ])
            else:
                examples.extend([
                    f"Cleared for {maneuver} {action}. Depart on azimuth {azimuth_str} degrees.",
                    f"{maneuver.capitalize()} clearance granted. Azimuth {azimuth_str} degrees.",
                    f"You are go for {maneuver} {action}. Azimuth {azimuth_str} degrees.",
                ])
        
        # Plane change
        elif maneuver == "plane_change":
            target_inclination_deg = physics_params.get("target_inclination_deg")
            
            if target_inclination_deg:
                examples.extend([
                    f"Cleared for plane change maneuver. Target inclination {int(target_inclination_deg)} degrees, execute at ascending node.",
                    f"Plane change authorization granted. Adjust to {int(target_inclination_deg)} degrees inclination.",
                    f"Cleared for plane change to {int(target_inclination_deg)} degrees.",
                ])
            else:
                examples.extend([
                    "Cleared for plane change maneuver.",
                    "Plane change authorization granted.",
                    "Plane change clearance approved.",
                ])
        
        # Deorbit
        elif maneuver == "deorbit":
            entry_angle_deg = physics_params.get("entry_angle_deg")
            atmosphere = None
            if self.actor and self.actor.location:
                from mysite.universe.services.controller_physics import ControllerPhysicsService
                body = ControllerPhysicsService.get_relevant_body(self.actor, self.nav_context)
                if body:
                    atmosphere = body.get_atmosphere()
            
            if entry_angle_deg and atmosphere and atmosphere.atmosphere_height_km:
                examples.extend([
                    f"Cleared for deorbit burn. Entry interface at {int(atmosphere.atmosphere_height_km)} kilometers, entry angle {entry_angle_deg:.1f} degrees.",
                    f"Deorbit authorization granted. Entry angle {entry_angle_deg:.1f} degrees, entry interface {int(atmosphere.atmosphere_height_km)} kilometers.",
                    f"Cleared for deorbit. Entry angle {entry_angle_deg:.1f} degrees.",
                ])
            elif entry_angle_deg:
                examples.extend([
                    f"Cleared for deorbit burn. Entry angle {entry_angle_deg:.1f} degrees.",
                    f"Deorbit authorization granted. Entry angle {entry_angle_deg:.1f} degrees.",
                ])
            else:
                examples.extend([
                    "Cleared for deorbit burn.",
                    "Deorbit authorization granted.",
                    "Deorbit clearance approved.",
                ])
        
        # Landing/dock
        elif maneuver in ["landing", "dock"]:
            approach_heading_deg = physics_params.get("approach_heading_deg")
            approach_speed_ms = physics_params.get("approach_speed_ms")
            
            if approach_heading_deg and approach_speed_ms:
                examples.extend([
                    f"Cleared for landing approach. Heading {int(approach_heading_deg)} degrees, final approach speed {int(approach_speed_ms)} meters per second.",
                    f"Landing clearance granted. Approach heading {int(approach_heading_deg)} degrees, speed {int(approach_speed_ms)} meters per second.",
                    f"Cleared for landing. Heading {int(approach_heading_deg)} degrees.",
                ])
            elif approach_heading_deg:
                examples.extend([
                    f"Cleared for landing approach. Heading {int(approach_heading_deg)} degrees.",
                    "Landing clearance granted.",
                    "Landing authorization approved.",
                ])
            else:
                examples.extend([
                    "Cleared for landing.",
                    "Landing clearance granted.",
                    "Landing authorization approved.",
                ])
        
        # Generic fallback
        else:
            examples.extend([
                f"Cleared for {maneuver} maneuver.",
                "Cleared, proceed as planned.",
                "Authorization granted, you're cleared.",
                f"Cleared for {maneuver}, proceed when ready.",
            ])
        
        # Check if this is an adjusted response (after a hold)
        # If nav_context indicates a hold occurred, add adjusted clearance examples
        if self.nav_context.get("after_hold", False) or "adjusted" in str(self.nav_context.get("maneuver_type", "")).lower():
            examples.extend([
                f"Okay, adjust to azimuth seven zero, and {maneuver}. Sorry for the delay.",
                "Cleared now, proceed with adjusted vector.",
                "Traffic cleared, you're good to go.",
                f"Cleared for {maneuver}, proceed with adjusted parameters.",
                "You're cleared now, proceed.",
            ])
        
        return examples
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do.
        
        Counterexample shows controller incorrectly requesting clearance (controllers grant, not request).
        
        Returns:
            Counterexample string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        return f"[DON'T DO THIS!] {recipient}, {sender} here - I am requesting clearance for launch. Over."
    
    def get_next_particle_probabilities(self) -> Dict[str, float]:
        """
        Return probabilities for what can follow a controller response.
        
        Approvals always require a readback (not just acknowledgment).
        
        Returns:
            Dict mapping particle types to probabilities.
        """
        return {
            "readback": 1.0,  # Approvals always require readback
        }


class RadioReadback(DialogueParticle):
    """
    Pilot reading back instructions.
    
    Used when pilot confirms receipt of specific instructions (vectors, headings, etc.)
    by reading them back verbatim.
    """
    
    def get_role_description(self) -> str:
        """
        Return role description for pilot.
        
        Format: "{pilot_name}, the pilot of the {ship_name}"
        
        Returns:
            Role description string.
        """
        ship_name = self.get_sender_callsign()
        pilot_name = self.actor.name
        controller_name = self.recipient
        return f"{pilot_name}, the pilot of the {ship_name} is reassuring {controller_name} that they are executing the approved course of action."
    
    def get_situation_description(self) -> str:
        """
        Return situation description for readback.
        
        Builds description like: "{sender} has received specific instructions from {recipient}
        and is reading them back for confirmation."
        
        Returns:
            Situation description string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return f"{sender} has received specific instructions from {recipient}. {sender} reads back a concise summary of any technical details from the last dialogue line. You are replying that you are DOING the maneuver. It's not important to tell the Controller that you are approved (they already know this!). They need to know that you are ACTING on the approval." 
    
    def get_examples(self) -> List[str]:
        """
        Return examples of pilot readbacks.
        
        Readbacks should echo the EXACT values from the controller's instructions.
        We parse the previous dialogue (controller's response) to extract the 
        instructed kilometers and degrees, so examples teach the LLM to read back
        the actual values given.
        
        Returns:
            List of example dialogue strings.
        """
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        if not maneuver:
            maneuver = "maneuver"
        
        # Parse the controller's actual instructions from previous dialogue
        # This is critical - readbacks must echo the EXACT values given
        instructed = self.parse_instructed_values()
        
        # Use parsed values from controller, fall back to nav_context, then random
        altitude_km = instructed.get('instructed_km')
        if altitude_km is None:
            altitude_km = self.nav_context.get("altitude_km")
        if altitude_km is None:
            altitude_km = random.randint(200, 500)
        
        inclination_deg = instructed.get('instructed_deg')
        if inclination_deg is None:
            inclination_deg = self.nav_context.get("inclination_deg")
        if inclination_deg is None:
            inclination_deg = random.randint(15, 45)
            
        if maneuver in ["launch", "direct_ascent"]:
            verb = "launch"
        elif maneuver in ["insertion", "circularization"]:
            verb = "burn"
        elif maneuver in ["sublight", "transfer"]:
            verb = "burn"
        elif maneuver in ["hyperspace"]:
            verb = "jump"
        else:
            verb = "maneuver"
        
        # For transfers/jumps, read back the azimuth/instructional degrees only (do not invent kilometers).
        if maneuver in ["sublight", "transfer", "hyperspace"]:
            az = int(inclination_deg) % 360
            az_str = f"{az:03d}"
            return [
                f"Copy, azimuth {az_str} degrees. {verb}ing now.",
                f"Roger, azimuth {az_str} degrees. {verb}ing.",
                f"Okay, azimuth {az_str} degrees. {verb}ing now.",
                f"Copy your azimuth {az_str}. {verb}ing now.",
            ]

        # Otherwise, build examples that demonstrate reading back the instructed values
        # Some examples use just one value (for cases where only km or deg was given)
        examples = []

        # Examples that use altitude only
        examples.append(f"Roger, {altitude_km} kilometers, we'll {verb} now.")
        examples.append(f"Copy, {verb}ing to {altitude_km} kilometers.")

        # Examples that use degrees only
        examples.append(f"Roger, {verb}ing on {inclination_deg} degrees.")
        examples.append(f"Okay, {inclination_deg} degrees, {verb}ing now.")

        # Examples that use both values (when both were instructed)
        examples.append(f"Copy, {altitude_km} kilometers, {inclination_deg} degrees.")
        examples.append(f"Locking in your instructions... {inclination_deg} degrees, {altitude_km} kilometers. Okay, {verb}ing now.")
        examples.append(f"We copy. {altitude_km} kilometers, {inclination_deg} degrees. Proceeding with {maneuver}.")
        examples.append(f"Roger, {maneuver} to {altitude_km} kilometers at {inclination_deg} degrees.")

        return examples
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do.
        
        Returns:
            Counterexample string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        return f"""
            "[DON'T DO THIS!] Roger, {sender}, {recipient}, I am saying 'YES' but I'm not echoing back your detailed instructions."
            "[DON'T DO THIS!] Roger, now you can proceed." [You only echo back - you don't tell Control what to do!]
            "[DON'T DO THIS!] Copy, sounds good {sender}, you should go ahead and do it. [Pilots "do", Controllers "tell"]
            """

    def get_next_particle_probabilities(self) -> Dict[str, float]:
        """
        Return probabilities for what can follow a readback.
        
        Readbacks typically end the chain (acknowledgment is implicit).
        
        Returns:
            Empty dict - chain ends after readback.
        """
        return {}  # Chain ends after readback


class HoldResponse(RadioResponse):
    """
    Controller responding with a hold instruction.
    
    Used when controller needs pilot to wait (hazard, traffic, etc.).
    """
    
    def get_examples(self) -> List[str]:
        """
        Return examples of hold responses.
        
        Returns:
            List of example dialogue strings.
        """

        roman_numeral = random.choice(["I", "II", "III", "IV", "V", "VI"])
        
        return [
            f"Negative, hold position. We've lost custody on a Class {roman_numeral} debris track. We'll clear you once we re-acquire and confirm your safety.",
            "Hold on please. We have a ship with a flight emergency that needs priority. Stand by.",
            "Negative, hold. Adjusting clearance parameters.",
            "Hold position, traffic conflict - we should clear you in a moment.",
            "Stand by, hold your position. We're clearing you in a moment.",
            "There's a flight emergency coming through. Stand by for your clearance and vector.",
            "There's a derelict probe drifting through your window, you'll be clear to proceed in a moment. Stand by please.",
            f"There's some Class {roman_numeral} debris near your window. Probably nothing but we're going to let it go by. Hold for your clearance.",
            "We have -- hang on -- okay, it's cleared up, let me get that approval for you. Apologies for the delay."
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do.
        
        Returns:
            Counterexample string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        return f"[DON'T DO THIS!] {sender}, {recipient}, the hold is okay. We're going to route you around a new cleared jump window."
    
    def get_duration(self) -> float:
        """
        Return duration for hold response.
        
        Hold responses take longer (controller checking traffic, hazards, etc.).
        
        Returns:
            Duration in seconds.
        """
        return 60.0  # Hold takes longer
    
    def get_delay_until_next(self) -> Optional[float]:
        """
        Return delay until next event.
        
        Pilot needs time to acknowledge hold.
        
        Returns:
            Seconds until next event.
        """
        return 5.0
    
    def get_next_particle_probabilities(self) -> Dict[str, float]:
        """
        Return probabilities for what can follow a hold response.
        
        Hold responses must be followed by holding acknowledgment.
        
        Returns:
            Dict mapping particle types to probabilities.
        """
        return {
            "holding": 1.0  # Must acknowledge hold
        }


class Holding(DialogueParticle):
    """
    Pilot acknowledging hold instruction.
    
    Used when pilot confirms they are holding position.
    """
    
    def get_role_description(self) -> str:
        """
        Return role description for pilot.
        
        Format: "{pilot_name}, the pilot of the {ship_name}"
        
        Returns:
            Role description string.
        """
        ship_name = self.get_sender_callsign()
        pilot_name = self.actor.name
        return f"{pilot_name}, the pilot of the {ship_name}"
    
    def get_situation_description(self) -> str:
        """
        Return situation description for holding.
        
        Builds description like: "{sender} has been instructed to hold by {recipient}
        and is acknowledging the hold."
        
        Returns:
            Situation description string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return f"{sender} has been instructed to hold by {recipient} and is acknowledging the hold."
    
    def get_examples(self) -> List[str]:
        """
        Return examples of holding acknowledgments.
        
        Returns:
            List of example dialogue strings.
        """
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"Holding position and awaiting clearance for {maneuver}.",
            "Roger, holding.",
            "Glad we checked with you. Get that cleared up and let us know when it's safe, please.",
            "Copy, we're standing by.",
            f"Acknowledge your hold. We'll wait here for our {maneuver} clearance.",
            f"We're holding position for our {maneuver} clearance.",
            f"Understood, our {maneuver} clearance is on hold. We'll stand by.",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do.
        
        Returns:
            Counterexample string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        return f"[DON'T DO THIS!] {sender}, {recipient}, My hold request is getting cold, I want to speak to the manager. Over."
    
    def get_next_particle_probabilities(self) -> Dict[str, float]:
        """
        Return probabilities for what can follow a holding acknowledgment.
        
        After acknowledging hold, controller provides adjusted clearance.
        
        Returns:
            Dict mapping particle types to probabilities.
        """
        return {
            "adjusted_response": 1.0  # Controller provides adjusted clearance
        }


class CommsCheckRequest(PilotRequest):
    """
    Pilot performing a comms check with an automated satellite.
    
    Used when a pilot performs a routine comms check with a relay satellite or nav beacon.
    This is a TECHNICAL procedure, not a conversation - the satellite is automated and
    will just echo back a pre-programmed response.
    """
    
    def get_situation_description(self) -> str:
        """
        Return situation description for comms check.
        
        CRITICAL: This is a technical signal check, NOT a request for clearance or permission.
        The satellite is automated - it cannot grant clearance or understand requests.
        
        Returns:
            Situation description string.
        """
        sender = self.get_sender_callsign()
        satellite_name = self.recipient
        
        return f"{sender} is performing a routine signal check with {satellite_name}, an AUTOMATED relay satellite. This is purely technical - just transmit a brief check and wait for the echo. The satellite CANNOT grant clearance or understand requests - it just echoes back an automated response."
    
    def get_examples(self) -> List[str]:
        """
        Return examples of comms check requests.
        
        These are procedural transmissions to an automated relay satellite,
        not conversational requests. The pilot just identifies and transmits;
        the satellite echoes back automatically.
        
        Returns:
            List of example comms check dialogue strings.
        """
        return [
            "Comms check.",
            "Radio check, please?",
            "Can you give me a calibration tone?",
            "Signal check on this frequency.",
            "Testing relay link.",
            "Checking signal strength.",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do.
        
        Don't treat automated satellites like people who can understand and respond.
        
        Returns:
            Counterexample string.
        """
        return "[DON'T DO THIS!] Can you give me clearance? Requesting permission to maneuver."
    
    def get_next_particle_probabilities(self) -> Dict[str, float]:
        """
        Return probabilities for what can follow a comms check request.
        
        Comms checks always get a satellite response.
        
        Returns:
            Dict mapping particle types to probabilities.
        """
        return {
            "satellite_response": 1.0  # Always get satellite response
        }
    
    def get_delay_until_next(self) -> Optional[float]:
        """
        Return delay until satellite response.
        
        Satellites respond quickly to comms checks (2-3 seconds).
        
        Returns:
            Seconds until next event.
        """
        return 3.0  # Quick satellite response


class SatelliteResponse(DialogueParticle):
    """
    Satellite responding to a comms check with a pre-programmed message.
    
    This particle does NOT use LLM generation - it returns the satellite's
    pre-programmed response message directly.
    """
    
    def get_role_description(self) -> str:
        """
        Return role description for satellite.
        
        Format: "An automated relay satellite named {satellite_name}"
        
        Returns:
            Role description string.
        """
        satellite_name = self.actor.name
        return f"An automated relay satellite named {satellite_name}"
    
    def get_situation_description(self) -> str:
        """
        Return situation description for satellite response.
        
        Returns:
            Situation description string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return f"{sender} has requested a comms check from {recipient}. {recipient} is responding with its pre-programmed automated message."
    
    def generate_procedural_greeting(self) -> str:
        """
        Generate procedural greeting for satellite responses.
        
        Satellites follow radio protocol: "{recipient}, {satellite_name}."
        This ensures the recipient is identified in the message for validation.
        
        Returns:
            Greeting string with recipient and satellite name.
        """
        satellite_name = self.actor.name.upper()
        recipient = self.recipient
        return f"{recipient}, {satellite_name}."
    
    def get_examples(self) -> List[str]:
        """
        Return examples (not used for LLM, but required by interface).
        
        This particle bypasses LLM generation and uses the satellite's
        pre-programmed message instead.
        
        Returns:
            Empty list (not used).
        """
        return []
    
    def get_counterexample(self) -> str:
        """
        Return counterexample (not used for LLM, but required by interface).
        
        Returns:
            Empty string (not used).
        """
        return ""
    
    def get_pre_programmed_message(self) -> str:
        """
        Get the pre-programmed response message from the satellite.
        
        This method is called instead of LLM generation for satellite responses.
        
        Returns:
            Pre-programmed message string.
        """
        from mysite.universe.models.actor import Satellite
        
        if isinstance(self.actor, Satellite):
            return self.actor.get_response_message()
        else:
            # Fallback if actor is not a Satellite
            return "BEEP BOOP"
    
    def build_user_prompt_data(self, previous_dialogue: Optional[str] = None):
        """
        Override to prevent building prompt data for satellites.
        
        Satellites never use LLM generation, so this method should never be called.
        This is a defensive override to catch any accidental calls.
        
        Args:
            previous_dialogue: Optional previous dialogue line text (ignored)
            
        Returns:
            Minimal UserPromptData (should never be used)
        """
        from .base import UserPromptData
        # Return minimal data, but log a warning
        import logging
        logger = logging.getLogger('dialogue_service')
        logger.warning(
            "build_user_prompt_data() called on SatelliteResponse - "
            "this should never happen as satellites use pre-programmed messages"
        )
        # Return minimal data structure (should never be used)
        return UserPromptData(
            role="",
            situation="",
            sender="",
            recipient="",
            example1="",
            example2="",
            example3="",
            last_dialogue_line=previous_dialogue,
        )
    
    def get_next_particle_probabilities(self) -> Dict[str, float]:
        """
        Return probabilities for what can follow a satellite response.
        
        Satellite responses typically end the chain (optional pilot acknowledgment).
        
        Returns:
            Empty dict - chain typically ends after satellite response.
        """
        return {}  # Chain typically ends after satellite response


class NavBroadcast(DialogueParticle):
    """
    Satellite navigation broadcast particle.
    
    Generates automated navigation update messages from satellites.
    The display text is a plaintext human-readable announcement.
    The audio plan encodes the technical data as modem noise.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize NavBroadcast particle and cache generated data."""
        super().__init__(*args, **kwargs)
        self._cached_broadcast_data = None  # Cache for consistent data between announcement and modem encoding
    
    def get_role_description(self) -> str:
        """
        Return role description for satellite.
        
        Format: "An automated navigation satellite named {satellite_name}"
        
        Returns:
            Role description string.
        """
        satellite_name = self.actor.name
        return f"An automated navigation satellite named {satellite_name}"
    
    def get_situation_description(self) -> str:
        """
        Return situation description for nav broadcast.
        
        Returns:
            Situation description string.
        """
        satellite_name = self.actor.name.upper()
        return f"{satellite_name} is broadcasting a periodic navigation update with navigation conditions and hazard information."
    
    def generate_procedural_greeting(self) -> str:
        """
        Generate procedural greeting for nav broadcasts.
        
        Returns:
            Human-readable announcement text.
        """
        satellite_name = self.actor.name.upper()
        return f"All stations, this is {satellite_name} with a Navigation Update."
    
    
    def get_examples(self) -> List[str]:
        """
        Return examples of human-readable nav broadcast announcements.
        
        Includes examples with navigation hazards referencing subordinate bodies.
        
        Returns:
            List of example broadcast announcements.
        """
        satellite_name = self.actor.name.upper()
        
        # Get subordinate bodies for hazard examples
        from mysite.universe.services.location_service import get_subordinate_bodies, find_star_system_for_location
        
        # Get satellite's location - satellites always orbit a body
        location = self.actor.location
        if location:
            # Find the star system containing this location
            star_system = find_star_system_for_location(location)
            # Use the star system to get subordinate bodies
            location = star_system if star_system else location
        
        # Get subordinate bodies using the location (only bodies in this system)
        subordinate_bodies = get_subordinate_bodies(location=location) if location else []
        
        examples = []
        
        # Generate a hazard example if we have subordinate bodies  
        # TODO: Hazard class and persistent tracking of hazards in the simulation at large. 
        if subordinate_bodies:
            roman_numerals = ["I", "II", "III", "IV", "V", "VI"]
            hazards = ["asteroid", "comet", "debris field", "derelict ship", "unregistered satellite", "spent booster stage"]
            # TODO: make these draw from a better distribution than uniform - probably promote to a Hazard class later. 
            hazard = random.choice(hazards)
            hazard_class = random.choice(roman_numerals)
            
            # Select a random subordinate body
            impacted_body = random.choice(subordinate_bodies)
            body_name = impacted_body.name
            
            hazard_text = f"one Class {hazard_class} {hazard}"
            
            examples.extend([
                f"All stations, this is {satellite_name} with a Navigation Update. Conditions are nominal.",
                f"All stations, this is {satellite_name} with a Navigation Update. Standby for today's hazard data and closures.",
                f"All stations, this is {satellite_name} with a Navigation Update. Standby for today's updates.",
                f"All stations, this is {satellite_name} with a Navigation Update. We are tracking {hazard_text} near {body_name}. Otherwise conditions are nominal. Standby for hazard data and closures.",
                f"All stations, this is {satellite_name} with a Navigation Update. We are tracking {hazard_text} near {body_name}. Otherwise conditions are nominal. Standby for hazard data and closures.",
                f"All stations, this is {satellite_name} with a Navigation Update. No new navigation hazards to declare at this time. Standby for a refreshed data table.",
            ])
        
        # Add standard position/status examples     
        return examples
    
    def get_counterexample(self) -> str:
        """
        Return counterexample (not used for nav broadcasts).
        
        Returns:
            Empty string.
        """
        return ""
    
    def _get_broadcast_data(self) -> dict:
        """
        Get nav broadcast data (cached for consistency between announcement and modem encoding).
        
        Returns:
            Dict with satellite_name, timestamp, and optional hazard information.
        """
        if self._cached_broadcast_data is None:
            satellite_name = self.actor.name.upper()
            
            # Timestamp
            from mysite.universe.models.simulation import get_simulation_time
            timestamp = int(get_simulation_time())
            
            # Get subordinate bodies for potential hazard references
            from mysite.universe.services.location_service import get_subordinate_bodies, find_star_system_for_location
            
            # Get satellite's location - satellites always orbit a body
            location = self.actor.location
            if location:
                # Find the star system containing this location
                star_system = find_star_system_for_location(location)
                # Use the star system to get subordinate bodies
                location = star_system if star_system else location
            
            # Get subordinate bodies using the location (only bodies in this system)
            subordinate_bodies = get_subordinate_bodies(location=location) if location else []
            
            # Determine if we should include a hazard (30% chance if we have subordinate bodies)
            hazard_info = None
            if subordinate_bodies and random.random() < 0.3:
                roman_numerals = ["I", "II", "III", "IV", "V", "VI"]
                hazards = ["asteroid", "comet", "debris field", "derelict ship", "unregistered satellite", "spent booster stage"]
                hazard = random.choice(hazards)
                hazard_class = random.choice(roman_numerals)
                impacted_body = random.choice(subordinate_bodies)
                
                hazard_info = {
                    "hazard": hazard,
                    "hazard_class": hazard_class,
                    "body_name": impacted_body.name,
                }
            
            self._cached_broadcast_data = {
                "satellite_name": satellite_name,
                "timestamp": timestamp,
                "hazard_info": hazard_info,
            }
        
        return self._cached_broadcast_data
    
    def generate_nav_broadcast_text(self) -> str:
        """
        Generate a human-readable navigation broadcast announcement.
        
        Creates a plaintext announcement suitable for TTS voice reading.
        The technical data will be encoded as modem noise in the audio plan.
        
        Returns:
            Human-readable broadcast announcement text.
        """
        data = self._get_broadcast_data()
        satellite_name = data['satellite_name']
        hazard_info = data.get('hazard_info')
        
        # Base opening
        opening = f"All stations, this is {satellite_name} with a Navigation Update."
        
        # Select announcement pattern based on whether we have a hazard
        if hazard_info:
            # Hazard announcement pattern
            hazard_text = f"one Class {hazard_info['hazard_class']} {hazard_info['hazard']}"
            body_name = hazard_info['body_name']
            return f"{opening} We are tracking {hazard_text} near {body_name}. Otherwise conditions are nominal. Standby for hazard data and closures."
        else:
            # Routine announcement patterns (no hazards)
            patterns = [
                "Conditions are nominal.",
                "Standby for today's hazard data and closures.",
                "Standby for today's updates.",
                "No new navigation hazards to declare at this time. Standby for a refreshed data table.",
            ]
            return f"{opening} {random.choice(patterns)}"
    
    def get_modem_encoded_data(self) -> str:
        """
        Get the technical data format for modem encoding.
        
        This is the raw data that will be encoded as modem noise in the audio plan.
        Uses the same cached data as generate_nav_broadcast_text() for consistency.
        
        Returns:
            Technical data string in format suitable for modem encoding.
        """
        data = self._get_broadcast_data()
        
        # Placeholder format for modem encoding (per design doc)
        # Eventually this should encode the actual broadcast text, but for now
        # it's a placeholder that indicates this is technical data
        technical_data = (
            f"{data['satellite_name']} NAV UPDATE // "
            f"TIMESTAMP {data['timestamp']} // "
            f"IF THIS WERE A REAL NAV UPDATE YOU'D BE ABLE TO READ IT BY NOW"
        )
        
        return technical_data
    
    def build_user_prompt_data(self, previous_dialogue: Optional[str] = None):
        """
        Build prompt data for nav broadcast generation.
        
        Nav broadcasts use procedural generation (not LLM), but we still
        need to implement this method for the interface.
        
        Args:
            previous_dialogue: Optional previous dialogue (ignored for broadcasts)
            
        Returns:
            UserPromptData with examples for consistency
        """
        from .base import UserPromptData
        
        return UserPromptData(
            role_description=self.get_role_description(),
            situation_description=self.get_situation_description(),
            examples=self.get_examples(),
            counterexample=self.get_counterexample(),
            previous_dialogue=previous_dialogue or "",
        )
    
    def get_next_particle_probabilities(self) -> Dict[str, float]:
        """
        Return probabilities for what can follow a nav broadcast.
        
        Nav broadcasts have a 5% chance of generating a gratitude response
        from a random ship in the system.
        
        Returns:
            Dict with "gratitude" probability (0.05) if chance succeeds, else empty.
        """
        # 5% chance of gratitude response
        if random.random() < 0.05:
            return {"gratitude": 1.0}
        return {}  # Most broadcasts are standalone


class GratitudeParticle(DialogueParticle):
    """
    Pilot gratitude particle for thanking satellites for nav broadcasts.
    
    Generated as a casual response to satellite navigation updates.
    No callsigns needed - just a brief acknowledgment.
    """
    
    def get_role_description(self) -> str:
        """
        Return role description for pilot.
        
        Format: "{pilot_name}, a pilot"
        
        Returns:
            Role description string.
        """
        pilot_name = self.actor.name if self.actor else "pilot"
        return f"{pilot_name}, a pilot"
    
    def get_situation_description(self) -> str:
        """
        Return situation description for gratitude response.
        
        Returns:
            Situation description string.
        """
        return "A pilot is casually acknowledging a useful message from a satellite, controller, or other pilot. This is a brief, informal thank-you, not a formal radio exchange."
    
    def generate_procedural_greeting(self) -> str:
        """
        Generate procedural greeting for gratitude (none needed).
        
        Returns:
            Empty string (gratitude doesn't need greetings).
        """
        return ""
    
    def get_examples(self) -> List[str]:
        """
        Return examples of gratitude responses.
        
        Returns:
            List of example gratitude messages.
        """
        return [
            "Thanks for the update.",
            "Good copy, appreciate the detailed data.",
            "Appreciate the update.",
            "Thanks, that's helpful.",
            "Good copy on the update.",
            "Appreciate it.",
            "Good data, thanks.",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample (not used for gratitude).
        
        Returns:
            Empty string.
        """
        return ""
    
    def build_user_prompt_data(self, previous_dialogue: Optional[str] = None):
        """
        Build prompt data for gratitude generation.
        
        Uses the base class implementation which properly formats UserPromptData.
        
        Args:
            previous_dialogue: The nav broadcast message that triggered this gratitude
            
        Returns:
            UserPromptData with examples
        """
        # Use base class implementation which handles proper formatting
        return super().build_user_prompt_data(previous_dialogue)
    
    def get_next_particle_probabilities(self) -> Dict[str, float]:
        """
        Return probabilities for what can follow a gratitude response.
        
        Gratitude responses end the chain.
        
        Returns:
            Empty dict - gratitude ends the chain.
        """
        return {}  # Gratitude ends the chain