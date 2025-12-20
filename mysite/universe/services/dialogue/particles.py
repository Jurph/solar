"""
Concrete dialogue particle classes.

Each particle type represents a specific dialogue exchange type with its own
examples, counterexamples, and prompt structure. Particles inherit from
DialogueParticle and implement the abstract methods.
"""
import random
from typing import List, Dict, Optional
from .base import DialogueParticle


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
        azimuth = self.nav_context.get("azimuth", "five five")
        
        return [
            f"Requesting permission for lift-off on {azimuth} degrees north.",
            f"We're planned for {azimuth} degrees departure angle, prepped for launch, and awaiting your clearance.",
            f"Request launch clearance to outbound {azimuth} degrees north, heading to {destination}.",
            f"Requesting clearance for launch. We're planned on {azimuth} degrees departure angle.",
            f"Ready for launch, requesting authorization. My crew want to get to {destination} as soon as you'll let us go.",
            f"Requesting clearance for takeoff, outbound to {destination} on heading {azimuth} north.",
            f"Our launch window opened up about a minute ago, and I've got our azimuth keyed in. Permission to launch, please?",
            f"Standing by on {origin}. Requesting clearance for launch, bound for {destination} on heading {azimuth} north.",
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
        altitude_km = 200
        inclination_deg = 20
        
        return [
            f"Requesting clearance for circularization burn to {altitude_km} kilometers, {inclination_deg} degrees.",
            f"Ready for circularization, looks like we can hit {altitude_km} kilometers and {inclination_deg} degrees pretty easily. Does that work for you?",
            f"Coasting to apogee. Requesting permission to circularize orbit to {altitude_km} kilometers, {inclination_deg} degrees.",
            f"Clearance to circularize to {altitude_km} by {inclination_deg}, please.",
            f"Ascent burn was clean. My nav computer shows {inclination_deg} degrees inclination and {altitude_km} kilometers is my minimum-energy burn. Any problem clearing me for that orbit?",
            f"Approaching apogee on {inclination_deg} degrees inclination. Request clearance to circularize orbit to {altitude_km} kilometers."
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        destination = self.nav_context.get("destination", "destination")
        
        return [
            f"{recipient}, this is {sender}, requesting clearance for sublight burn to {destination}.",
            f"{recipient}, {sender}. Ready for sublight transit, requesting authorization.",
            f"{recipient}, {sender} here. Requesting permission to begin sublight burn toward {destination}.",
            f"{recipient}, {sender}. Request clearance for sublight maneuver.",
            f"{recipient}, this is {sender}, orbit is stable. Requesting clearance to initiate sublight burn for {destination}.",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do for sublight requests.
        
        Returns:
            Counterexample string.
        """
        return "[DON'T DO THIS!] We're approved for sublight. Permission granted, over."


class InsertionRequest(PilotRequest):
    """
    Pilot requesting orbital insertion burn clearance.
    
    Used when a pilot requests permission for an insertion burn into orbit around a destination.
    Typically occurs after sublight travel when entering the destination's sphere of influence.
    """
    
    def get_examples(self) -> List[str]:
        """
        Return 5+ examples of insertion requests.
        
        Returns:
            List of example insertion request dialogue strings.
        """
        destination = self.nav_context.get("destination", "destination")
        
        return [
            f"Requesting clearance for insertion burn into {destination} orbit.",
            f"Ready for orbital insertion, requesting authorization.",
            f"Requesting permission for insertion maneuver into {destination} orbit.",
            f"Request insertion burn clearance for {destination}.",
            f"Approaching {destination}. Requesting clearance for insertion burn.",
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
    
    Used when a pilot requests permission to deorbit from orbit around a destination.
    Typically occurs after circularization at destination, before landing.
    """
    
    def get_examples(self) -> List[str]:
        """
        Return 5+ examples of deorbit requests.
        
        Returns:
            List of example deorbit request dialogue strings.
        """
        destination = self.nav_context.get("destination", "destination")
        
        return [
            f"Requesting clearance for deorbit burn.",
            f"Ready for deorbit, requesting authorization.",
            f"Requesting permission to deorbit for {destination}.",
            f"Request deorbit burn clearance.",
            f"Orbit is stable. Requesting clearance to begin deorbit sequence.",
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
    
    Used when a pilot requests permission to land on a planet or moon.
    Typically the final maneuver in a flight sequence (after deorbit).
    """
    
    def get_examples(self) -> List[str]:
        """
        Return 5+ examples of landing requests.
        
        Returns:
            List of example landing request dialogue strings.
        """
        destination = self.nav_context.get("destination", "destination")
        
        return [
            f"Requesting clearance for landing on {destination}.",
            f"Ready for landing approach, requesting authorization.",
            f"Requesting permission to land on {destination}.",
            f"Request landing clearance.",
            f"Deorbit complete. Requesting clearance for final approach and landing.",
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
            f"Requesting clearance for {maneuver}.",
            f"Ready for {maneuver}, requesting authorization.",
            f"Requesting clearance for {maneuver} maneuver.",
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
                    f"We have your flight plan and your launch window is open. You are go.",
                ])
            else:
                examples.extend([
                    f"Your launch burn is approved. Execute when ready.",
                    f"You're cleared for launch, proceed.",
                    f"Launch clearance granted. Proceed when ready.",
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
        
        # Departure maneuvers (sublight, transfer)
        elif maneuver in ["sublight", "transfer"]:
            action = "burn" if maneuver == "sublight" else "transfer"
            departure_angle_deg = physics_params.get("departure_angle_deg")
            farewells = ["Safe travels.", "Good luck.", "See you again soon.", "Take care.", "Fly safe."]
            farewell = random.choice(farewells)
            
            if destination:
                if departure_angle_deg:
                    examples.extend([
                        f"You are go for {maneuver} {action} to {destination}. Departure angle {int(departure_angle_deg)} degrees. {farewell}",
                        f"{maneuver.capitalize()} {action} to {destination} is approved. Departure angle {int(departure_angle_deg)} degrees. {farewell}",
                        f"Cleared for {maneuver} {action}.",
                        f"{maneuver.capitalize()} clearance granted, you can start the {action} when you're ready.",
                    ])
                else:
                    examples.extend([
                        f"You are go for {maneuver} to {destination}. {farewell}",
                        f"{maneuver.capitalize()} {action} to {destination} is approved. {farewell}",
                        f"Cleared for {maneuver} {action}.",
                    ])
            else:
                examples.extend([
                    f"Cleared for {maneuver} {action}.",
                    f"{maneuver.capitalize()} clearance granted.",
                    f"You are go for {maneuver} {action}.",
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
                    f"Cleared for plane change maneuver.",
                    f"Plane change authorization granted.",
                    f"Plane change clearance approved.",
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
                    f"Cleared for deorbit burn.",
                    f"Deorbit authorization granted.",
                    f"Deorbit clearance approved.",
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
                    f"Landing clearance granted.",
                    f"Landing authorization approved.",
                ])
            else:
                examples.extend([
                    f"Cleared for landing.",
                    f"Landing clearance granted.",
                    f"Landing authorization approved.",
                ])
        
        # Generic fallback
        else:
            examples.extend([
                f"Cleared for {maneuver} maneuver.",
                f"Cleared, proceed as planned.",
                f"Authorization granted, you're cleared.",
                f"Cleared for {maneuver}, proceed when ready.",
            ])
        
        # Check if this is an adjusted response (after a hold)
        # If nav_context indicates a hold occurred, add adjusted clearance examples
        if self.nav_context.get("after_hold", False) or "adjusted" in str(self.nav_context.get("maneuver_type", "")).lower():
            examples.extend([
                f"Okay, adjust to azimuth seven zero, and {maneuver}. Sorry for the delay.",
                f"Cleared now, proceed with adjusted vector.",
                f"Traffic cleared, you're good to go.",
                f"Cleared for {maneuver}, proceed with adjusted parameters.",
                f"You're cleared now, proceed.",
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
        return f"{pilot_name}, the pilot of the {ship_name}"
    
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
        
        return f"{sender} has received specific instructions from {recipient}. {sender} reads back a concise summary of any technical details from the last dialogue line." 
    
    def get_examples(self) -> List[str]:
        """
        Return examples of pilot readbacks.
        
        Returns:
            List of example dialogue strings.
        """
        
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        if not maneuver:
            maneuver = "maneuver"
        inclination_deg = self.nav_context.get("inclination_deg", "inclination")
        if not inclination_deg:
            inclination_deg = "45"
        altitude_km = self.nav_context.get("altitude_km", "altitude")
        if not altitude_km:
            altitude_km = "150"
            
        if maneuver in ["launch", "direct_ascent"]:
            verb = "launch"
        elif maneuver in ["insertion", "circularization"]:
            verb = "burn"
        elif maneuver in ["sublight", "hyperspace"]:
            verb = "jump"
        else:
            verb = "maneuver"
        
        heading = random.randint(1, 360)
        number = random.randint(1, 100)
                
        return [
            f"Roger, {verb}ing on heading {heading}.",
            f"Copy, {maneuver} {verb} on bearing {heading} degrees.",
            f"Got it, {altitude_km} kilometers, we'll {verb} now.",
            f"Locking in your instructions... {inclination_deg} degrees, {altitude_km} kilometers. Okay, {verb}ing now.",
            f"Copy, {maneuver} {verb} to {altitude_km} kilometers, {inclination_deg} degrees.",
            f"Wilco, starting {verb}, setting heading to {heading} as directed.",
            f"Okay, {verb}ing on {number} degrees.",
            f"We copy. Proceeding with {maneuver} {verb} to {altitude_km} kilometers, {inclination_deg} degrees, bearing {heading} degrees.",
        ]
    
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
            f"Hold on please. We have a ship with a flight emergency that needs priority. Stand by.",
            f"Negative, hold. Adjusting clearance parameters.",
            f"Hold position, traffic conflict - we should clear you in a moment.",
            f"Stand by, hold your position. We're clearing you in a moment.",
            f"There's a flight emergency coming through. Stand by for your clearance and vector.",
            f"There's a derelict probe drifting through your window, you'll be clear to proceed in a moment. Stand by please.",
            f"There's some Class {roman_numeral} debris near your window. Probably nothing but we're going to let it go by. Hold for your clearance.",
            f"We have -- hang on -- okay, it's cleared up, let me get that approval for you. Apologies for the delay."
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
            f"Roger, holding.",
            f"Glad we checked with you. Get that cleared up and let us know when it's safe, please.", 
            f"Copy, we're standing by.",
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
    Pilot requesting a comms check from a satellite.
    
    Used when a pilot performs a routine comms check with a relay satellite or nav beacon.
    """
    
    def get_examples(self) -> List[str]:
        """
        Return examples of comms check requests.
        
        Returns:
            List of example comms check dialogue strings.
        """
        recipient = self.recipient
        
        return [
            f"Performing routine comms check, do you copy?",
            f"Comms check, please respond.",
            f"I'm calibrating my receivers, {recipient}, can you give me a tone?",
            f"Requesting comms check, {recipient}, please respond.",
            f"{recipient}, comms check on this channel please?",
            f"Comms check, {recipient}, is this a working channel?",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do.
        
        Returns:
            Counterexample string.
        """
        return "[DON'T DO THIS!] Hey little satellite buddy, are you there?"
    
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