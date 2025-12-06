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
        
        return f"{sender} is a ship intending to fly to {destination} from {current}. The {sender} needs permission from {self.recipient} to {maneuver.lower()}."
    
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
        return "[DON'T DO THIS!] Earth Control, we want to launch the STELLAR HORIZON to Earth please."
    
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
        return "[DON'T DO THIS!] We're gonna start the sublight burn now, okay?"


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
        return "[DON'T DO THIS!] We're gonna insert now, okay?"


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
        return "[DON'T DO THIS!] We're starting our deorbit burn now."


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
        return "[DON'T DO THIS!] We're landing now, see you on the ground!"


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

        return f"[DON'T DO THIS!] {sender}, {recipient}, our plan for {maneuver} is approved. Over."


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
        Return examples of controller responses.
        
        Returns:
            List of example dialogue strings.
        """
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"Cleared for {maneuver} maneuver.",
            f"Cleared, proceed as planned.",
            f"Authorization granted, you're cleared.",
            f"Cleared for {maneuver}, proceed when ready.",
            f"You're cleared, proceed.",
        ]
    
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


class LaunchResponse(RadioResponse):
    """
    Controller responding to launch or direct ascent requests.
    
    Used when controller grants clearance for launch maneuvers.
    """
    
    def get_examples(self) -> List[str]:
        """
        Return examples of launch clearance responses.
        
        Returns:
            List of example dialogue strings.
        """
        inclination_deg = self.nav_context.get("inclination_deg", "inclination")
        altitude_km = self.nav_context.get("altitude_km", "altitude")
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"We have your flight plan and your launch window is open. You are go.",
            f"We see you cleared to {altitude_km} kilometers, {inclination_deg} degrees. Permission for {maneuver} granted.",
            f"Don't let me stop you! Head on out. We're prepping your insertion at {inclination_deg} degrees now.",
            f"Your {maneuver} burn is approved. Execute when ready.",
            f"You're cleared for launch, proceed.",
            f"Your {maneuver} burn is approved. You can head up to {altitude_km} kilometers, try to keep it near {inclination_deg} degrees, and check in when you get to orbit.",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do.
        
        Returns:
            Counterexample string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        return f"[DON'T DO THIS!] {sender}, {recipient}, requesting clearance for launch. Over."
    
    # Inherits get_next_particle_probabilities() from RadioResponse
    # (100% readback - approvals always require readback)


class OrbitResponse(RadioResponse):
    """
    Controller responding to insertion or circularization requests.
    
    Used when controller grants clearance for orbital maneuvers.
    """
    
    def get_examples(self) -> List[str]:
        """
        Return examples of orbital maneuver clearance responses.
        
        Returns:
            List of example dialogue strings.
        """

        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        inclination_deg = self.nav_context.get("inclination_deg", "inclination")
        altitude_km = self.nav_context.get("altitude_km", "altitude")
        
        return [
            f"Cleared for {maneuver}, proceed when ready.",
            f"Cleared for orbital {maneuver}, you're go. Make your own way, try to keep it near {inclination_deg} degrees.",
            f"{maneuver.capitalize()} clearance granted. You can have any achievable slot.",
            f"Approved for {maneuver} to {inclination_deg} degrees, {altitude_km} kilometers.",
            f"Bring it to {altitude_km} kilometers, {inclination_deg} degrees.",
            f"Cleared for {maneuver} burn to {altitude_km} kilometers, {inclination_deg} degrees.",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do.
        
        Returns:
            Counterexample string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        return f"[DON'T DO THIS!] {sender}, {recipient}, requesting clearance for launch. Over."


class DepartureResponse(RadioResponse):
    """
    Controller responding to sublight or hyperspace departure requests.
    
    Used when controller grants clearance for departure maneuvers.
    """
    
    def get_examples(self) -> List[str]:
        """
        Return examples of departure clearance responses.
        
        Returns:
            List of example dialogue strings.
        """

        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        destination = self.nav_context.get("destination", "destination")
        if maneuver == "sublight":
            action = "burn"
        elif maneuver == "hyperspace":
            action = "jump"
        else:
            action = ""
        
        farewells = [
            "Safe travels.",
            "Good luck.",
            "See you again soon.",
            "Take care.",
            "Fly safe.",
            "Stay safe out there."
        ]
        
        farewell = random.choice(farewells)
        
        return [
            f"You are go for {maneuver} to {destination}. {farewell}",
            f"Cleared for {maneuver} {action}.",
            f"{maneuver.capitalize()} clearance granted, you can start the {action} when you're ready.",
            f"I've got a window for you; if you can {action} now, we can get you out right away. {farewell}",
            f"{maneuver.capitalize()} {action} to {destination} is approved. {farewell}",
            f"Your {action} to {destination} is approved.",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do.
        
        Returns:
            Counterexample string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        return f"[DON'T DO THIS!] {sender}, {recipient}, requesting clearance for launch. Over."
    
    # Inherits get_next_particle_probabilities() from RadioResponse
    # (100% readback - approvals always require readback)


class RadioAcknowledgment(DialogueParticle):
    """
    Pilot acknowledging controller approval.
    
    Used when pilot confirms receipt of clearance or instructions.
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
        Return situation description for acknowledgment.
        
        Builds description like: "{sender} has received clearance from {recipient}
        and is acknowledging receipt."
        
        Returns:
            Situation description string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return f"{sender} has received clearance from {recipient} and is acknowledging receipt."
    
    def get_examples(self) -> List[str]:
        """
        Return examples of pilot acknowledgments.
        
        Returns:
            List of example dialogue strings.
        """
     
        return [
            f"Roger, proceeding as directed.",
            f"Copy, understood.",
            f"Acknowledged, proceeding.",
            f"Roger that, thank you.",
            f"Understood, proceeding.",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do.
        
        Returns:
            Counterexample string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        return f"[DON'T DO THIS!] {sender}, {recipient}, requesting clearance for launch. Over."
    
    def get_next_particle_probabilities(self) -> Dict[str, float]:
        """
        Return probabilities for what can follow an acknowledgment.
        
        Acknowledgments typically end the chain.
        
        Returns:
            Empty dict - chain ends after acknowledgment.
        """
        return {}  # Chain ends after acknowledgment


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


class AdjustedResponse(RadioResponse):
    """
    Controller providing adjusted clearance after hold.
    
    Used when controller provides new clearance after a hold instruction.
    """
    
    def get_examples(self) -> List[str]:
        """
        Return examples of adjusted responses.
        
        Returns:
            List of example dialogue strings.
        """
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"Okay, adjust to azimuth seven zero, and launch. Sorry for the delay.",
            f"Cleared now, proceed with adjusted vector.",
            f"Traffic cleared, you're good to go.",
            f"Cleared for {maneuver}, proceed with adjusted parameters.",
            f"You're cleared now, proceed.",
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do.
        
        Returns:
            Counterexample string.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        return f"[DON'T DO THIS!] {sender}, {recipient}, requesting clearance for launch. Over."

