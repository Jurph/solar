"""
Concrete dialogue particle classes.

Each particle type represents a specific dialogue exchange type with its own
examples, counterexamples, and prompt structure. Particles inherit from
DialogueParticle and implement the abstract methods.
"""
import random
from typing import List
from .base import DialogueParticle
from mysite.universe.schemas.dialogue_schema import DialogueFormat


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
    
    def get_format(self) -> DialogueFormat:
        """
        Return expected DialogueFormat for pilot requests.
        
        Returns:
            DialogueFormat.INITIAL_CONTACT
        """
        return DialogueFormat.INITIAL_CONTACT
    
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        origin = self.nav_context.get("current_location", "current location")
        destination = self.nav_context.get("destination", "destination")
        azimuth = self.nav_context.get("azimuth", "five five")
        
        return [
            f"{recipient}, this is {sender} requesting permission for lift-off on {azimuth} degrees north.",
            f"{recipient}, {sender} here. We're planned for {azimuth} degrees departure angle, prepped for launch, and awaiting your clearance.",
            f"{recipient}, {sender}. Request launch clearance to outbound {azimuth} degrees north, heading to {destination}.",
            f"{recipient}, this is {sender}, requesting clearance for launch. We're planned on {azimuth} degrees departure angle.",
            f"{recipient}, {sender}. Ready for launch, requesting authorization. My crew want to get to {destination} as soon as you'll let us go.",
            f"{recipient}, {sender} here. Requesting clearance for takeoff, outbound to {destination} on heading {azimuth} north.",
            f"{recipient}, {sender}. Our launch window opened up about a minute ago, and I've got our azimuth keyed in. Permission to launch, please?",
            f"{recipient}, {sender}, standing by on {origin}. Requesting clearance for launch, bound for {destination} on heading {azimuth} north." ,
        ]
    
    def get_counterexample(self) -> str:
        """
        Return counterexample showing what NOT to do for launch requests.
        
        Returns:
            Counterexample string.
        """
        return "[DON'T DO THIS!] Earth Control, we want to launch the STELLAR HORIZON to Earth please."


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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        altitude_km = 200
        inclination_deg = 20
        
        return [
            f"{recipient}, this is {sender}, requesting clearance for circularization burn to {altitude_km} kilometers, {inclination_deg} degrees.",
            f"{recipient}, {sender}. Ready for circularization, looks like we can hit {altitude_km} kilometers and {inclination_deg} degrees pretty easily. Does that work for you?",
            f"{recipient}, {sender} here, coasting to apogee. Requesting permission to circularize orbit to {altitude_km} kilometers, {inclination_deg} degrees.",
            f"{recipient}, {sender}. Clearance to circularize to {altitude_km} by {inclination_deg}, please.",
            f"{recipient}, this is {sender}, ascent burn was clean. My nav computer shows {inclination_deg} degrees inclination and {altitude_km} kilometers is my minimum-energy burn. Any problem clearing me for that orbit?"
            f"{recipient}, {sender} here, approaching apogee on {inclination_deg} degrees inclination. Request clearance to circularize orbit to {altitude_km} kilometers."
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        destination = self.nav_context.get("destination", "destination")
        
        return [
            f"{recipient}, this is {sender}, requesting clearance for insertion burn into {destination} orbit.",
            f"{recipient}, {sender}. Ready for orbital insertion, requesting authorization.",
            f"{recipient}, {sender} here. Requesting permission for insertion maneuver into {destination} orbit.",
            f"{recipient}, {sender}. Request insertion burn clearance for {destination}.",
            f"{recipient}, this is {sender}, approaching {destination}. Requesting clearance for insertion burn.",
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        destination = self.nav_context.get("destination", "destination")
        
        return [
            f"{recipient}, this is {sender}, requesting clearance for deorbit burn.",
            f"{recipient}, {sender}. Ready for deorbit, requesting authorization.",
            f"{recipient}, {sender} here. Requesting permission to deorbit for {destination}.",
            f"{recipient}, {sender}. Request deorbit burn clearance.",
            f"{recipient}, this is {sender}, orbit is stable. Requesting clearance to begin deorbit sequence.",
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        destination = self.nav_context.get("destination", "destination")
        
        return [
            f"{recipient}, this is {sender}, requesting clearance for landing on {destination}.",
            f"{recipient}, {sender}. Ready for landing approach, requesting authorization.",
            f"{recipient}, {sender} here. Requesting permission to land on {destination}.",
            f"{recipient}, {sender}. Request landing clearance.",
            f"{recipient}, this is {sender}, deorbit complete. Requesting clearance for final approach and landing.",
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"{recipient}, this is {sender}, requesting clearance for {maneuver}.",
            f"{recipient}, {sender}. Ready for {maneuver}, requesting authorization.",
            f"{recipient}, {sender} here. Requesting clearance for {maneuver} maneuver.",
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
    
    def get_format(self) -> DialogueFormat:
        """
        Return expected DialogueFormat for controller responses.
        
        Returns:
            DialogueFormat.RESPONSE
        """
        return DialogueFormat.RESPONSE
    
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
    
    def get_examples(self) -> List[str]:
        """
        Return examples of controller responses.
        
        Returns:
            List of example dialogue strings.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"{recipient}, {sender}. Cleared for {maneuver} maneuver.",
            f"{recipient}, {sender}. Cleared, proceed as planned.",
            f"{recipient}, {sender}. Authorization granted, you're cleared.",
            f"{recipient}, {sender}. Cleared for {maneuver}, proceed when ready.",
            f"{recipient}, {sender}. You're cleared, proceed.",
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        inclination_deg = self.nav_context.get("inclination_deg", "inclination")
        altitude_km = self.nav_context.get("altitude_km", "altitude")
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"{recipient}, this is {sender}. We have your flight plan and your launch window is open. You are go.",
            f"{recipient}, {sender}. We see you cleared to {altitude_km} kilometers, {inclination_deg} degrees. Permission for {maneuver} granted.",
            f"{recipient}, this is {sender}. Don't let me stop you! Head on out. We're prepping your insertion at {inclination_deg} degrees now.",
            f"{recipient}, {sender} here. Your {maneuver} burn is approved. Execute when ready.",
            f"{recipient}, {sender}. You're cleared for launch, proceed.",
            f"{recipient}, {sender}. Your {maneuver} burn is approved. You can head up to {altitude_km} kilometers, try to keep it near {inclination_deg} degrees, and check in when you get to orbit.",
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        inclination_deg = self.nav_context.get("inclination_deg", "inclination")
        altitude_km = self.nav_context.get("altitude_km", "altitude")
        
        return [
            f"{recipient}, {sender}. Cleared for {maneuver}, proceed when ready.",
            f"{recipient}, {sender}. Cleared for orbital {maneuver}, you're go. Make your own way, try to keep it near {inclination_deg} degrees.",
            f"{recipient}, {sender}. {maneuver.capitalize()} clearance granted. You can have any achievable slot.",
            f"{recipient}, {sender}. Approved for {maneuver} to {inclination_deg} degrees, {altitude_km} kilometers.",
            f"{recipient}, {sender}. Bring it to {altitude_km} kilometers, {inclination_deg} degrees.",
            f"{recipient}, {sender}. Cleared for {maneuver} burn to {altitude_km} kilometers, {inclination_deg} degrees.",
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
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
            f"{recipient}, {sender}. You are go for {maneuver} to {destination}. {farewell}",
            f"{recipient}, {sender}. Cleared for {maneuver} {action}.",
            f"{recipient}, {sender}. {maneuver.capitalize()} clearance granted, you can start the {action} when you're ready.",
            f"{recipient}, {sender}. I've got a window for you; if you can {action} now, we can get you out right away. {farewell}",
            f"{recipient}, {sender}. {maneuver.capitalize()} {action} to {destination} is approved. {farewell}",
            f"{recipient}, {sender}. Your {action} to {destination} is approved.",
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
    
    def get_format(self) -> DialogueFormat:
        """
        Return expected DialogueFormat for acknowledgments.
        
        Returns:
            DialogueFormat.ACKNOWLEDGMENT
        """
        return DialogueFormat.ACKNOWLEDGMENT
    
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return [
            f"{recipient}, {sender}. Roger, proceeding as directed.",
            f"{recipient}, {sender}. Copy, understood.",
            f"{recipient}, {sender}. Acknowledged, proceeding.",
            f"{recipient}, {sender}. Roger that, thank you.",
            f"{recipient}, {sender}. Understood, proceeding.",
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
    
    def get_format(self) -> DialogueFormat:
        """
        Return expected DialogueFormat for readbacks.
        
        Returns:
            DialogueFormat.READBACK
        """
        return DialogueFormat.READBACK
    
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
        
        return f"{sender} has received specific instructions from {recipient} and is reading them back for confirmation."
    
    def get_examples(self) -> List[str]:
        """
        Return examples of pilot readbacks.
        
        Returns:
            List of example dialogue strings.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return [
            f"{recipient}, {sender}. Cleared for orbital insertion, maintaining current vector.",
            f"{recipient}, {sender}. 150km orbit, understood.",
            f"{recipient}, {sender}. Azimuth seven zero, understood.",
            f"{recipient}, {sender}. Cleared for launch on three two, copy.",
            f"{recipient}, {sender}. Maintaining heading zero nine zero, understood.",
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        roman_numeral = random.choice(["I", "II", "III", "IV", "V", "VI"])
        
        return [
            f"{recipient}, {sender}. Negative, hold position. We've lost custody on a Class {roman_numeral} debris track. We'll clear you once we re-acquire and confirm your safety.",
            f"{recipient}, this is {sender}. Hold on please. We have a ship with a flight emergency that needs priority. Stand by.",
            f"{recipient}, {sender}. Negative, hold. Adjusting clearance parameters.",
            f"{recipient}, {sender} here. Hold position, traffic conflict - we should clear you in a moment.",
            f"{recipient}, {sender}. Stand by, hold your position. We're clearing you in a moment.",
            f"{recipient}, this is {sender}. There's a flight emergency coming through. Stand by for your clearance and vector.",
            f"{recipient}, {sender}. There's a derelict probe drifting through your window, you'll be clear to proceed in a moment. Stand by please.",
            f"{recipient}, {sender}. There's some Class {roman_numeral} debris near your window. Probably nothing but we're going to let it go by. Hold for your clearance.",
            f"{recipient}, this is {sender}. We have -- hang on -- okay, it's cleared up, let me get that approval for you. Apologies for the delay."
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
    
    def get_format(self) -> DialogueFormat:
        """
        Return expected DialogueFormat for holding acknowledgment.
        
        Returns:
            DialogueFormat.ACKNOWLEDGMENT
        """
        return DialogueFormat.ACKNOWLEDGMENT
    
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"{recipient}, {sender}. Holding position and awaiting clearance for {maneuver}.",
            f"{recipient}, {sender}. Roger, holding.",
            f"{recipient}, {sender}. Glad we checked with you. Get that cleared up and let us know when it's safe, please.", 
            f"{recipient}, {sender}. Copy, we're standing by.",
            f"{recipient}, {sender}. Acknowledge your hold. We'll wait here for our {maneuver} clearance.",
            f"{recipient}, {sender}. We're holding position for our {maneuver} clearance.",
            f"{recipient}, {sender}. Understood, our {maneuver} clearance is on hold. We'll stand by.",
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
        sender = self.get_sender_callsign()
        recipient = self.recipient
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"{recipient}, {sender}. Okay, adjust to azimuth seven zero, and launch. Sorry for the delay.",
            f"{recipient}, {sender}. Cleared now, proceed with adjusted vector.",
            f"{recipient}, {sender}. Traffic cleared, you're good to go.",
            f"{recipient}, {sender}. Cleared for {maneuver}, proceed with adjusted parameters.",
            f"{recipient}, {sender}. You're cleared now, proceed.",
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

