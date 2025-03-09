# Script Service Specification

## Overview
The Script Service is responsible for converting NavigationEvents into ScriptEvents for simulation playback. The ScriptEvents drive dialogue in the simulation, whether via a scrolling terminal view or a text-to-speech system. This service acts as the intermediary that translates maneuver actions into human-readable, timed dialogue sequences, ensuring that both ship pilots and controllers communicate in character.

## Requirements

### Input
- **NavigationEvent**  
  An object produced by the route planning system that contains:
  - **origin:** The starting Location (must have a name, type, and associated controller information).
  - **destination:** The target Location (with name and controller info).
  - **current:** The current Location in the journey.
  - **maneuver:** A ManeuverType (e.g., LAUNCH, SUBLIGHT, HYPERSPACE, etc.).
  - **controller:** The effective Controller, determined previously (if available).
- **Ship** paired with the event, which also yields the
  - **Pilot:** the Actor object attached to the ship 
  - **cargo:** a text field describing the ship's cargo 

_Note:_ Initially, the service will only handle NavigationEvents with the **SUBLIGHT** maneuver type, but it should be designed for future extension to all of the maneuver types. 

### Output
- A list of **ScriptEvent** objects. Each ScriptEvent includes:
  - **time_offset:** A float representing the number of seconds after the simulation start at which the event should trigger.
  - **actor:** A string identifying the actor delivering the dialogue (e.g., `"Ship.Pilot"` for pilot speech; or the effective controller's name for controller dialogue).
  - **text:** The dialogue message to be displayed or spoken.

### EXAMPLE: Behavior for SUBLIGHT Maneuvers

For a NavigationEvent with a **SUBLIGHT** maneuver, the Script Service must generate a sequence of about three ScriptEvents with predefined time offsets:
1. **Pilot Announcement (t = 0s):**
   - **Format:**  
     `"{controller}, this is {pilot_call_sign}, inbound from {origin} carrying {cargo}. I need a vector for an insertion burn for {destination} orbit."`
   - **Actor:** `"Ship.Pilot"`
   - **Details:**  
     - *controller* is taken from the effective controller of the NavigationEvent (or defaults to `"{destination} Control"`).
     - *pilot_call_sign* is just `"Ship.name.upper()"` for now. Later on we may let Pilots have some latitude about how they self-identify but for now let's assume they stick to the script 
     - *cargo* is another configurable default (e.g., `"sulfuric acid"`).  

2. **Controller Response (t = 3s):**
   - **Format:**  
     `"{pilot_call_sign}, this is {controller}. Confirmed for insertion. Come left 20 degrees and make your burn."`
   - **Actor:** The effective controller's name.

3. **Pilot Confirmation (t = 6s):**
   - **Format:**  
     `"Control, {pilot_call_sign}, 20 degrees left, thank you. Burning now."`
   - **Actor:** `"Ship.Pilot"`

These three events are `raw_dialogue` and we should pass them to the LLM_service along with their `Actor` object, where the Actor's `Actor.prompt` will guide how the LLM shapes the `actor_dialogue` for the script. The finished `actor_dialogue` is pushed to the user View (probably an API!) so that it can be consumed by the webpage for scrolling text _or_ eventually pushed to TTS with a custom voice. 

### Extensibility

- **Support for Other Maneuver Types:**  
  The service should be designed in a modular way such that new dialogue templates can be easily integrated. For example, future implementations may handle:
  - **HYPERSPACE:** Different dialogue for initiating and confirming hyperspace jumps.
  - **LAUNCH:** Custom dialogue for departing from a planetary surface or a station.
- **Customization:**  
  Both time offsets and dialogue templates should be configurable (e.g., through constructor parameters or external configuration).

### Integration & Deployment
- **Simulation Queue:**  
  NavigationEvents will be loaded into a simulation queue with associated timestamps or offsets (e.g., relative to `time.now()`). As these events pop off the queue, the Script Service converts each NavigationEvent into a series of ScriptEvents.
- **Output Routing:**  
  Initially, ScriptEvents will be directed to a web-based scrolling terminal. In the future, they could be routed to a text-to-speech engine for audio playback.

## Example Workflow
For a NavigationEvent representing a SUBLIGHT maneuver from Venus to Mars where the effective controller is determined to be `"Mars Control"`, and using a pilot call sign `"DUKAKIS TANGO"`:
- **At t = 0s:**  
  The ScriptService produces:  
  `"Mars Control, this is DUKAKIS TANGO, inbound from Venus carrying sulfuric acid. I need a vector for an insertion burn for Mars orbit."`
  
- **At t = 3s:**  
  It produces:  
  `"DUKAKIS TANGO, this is Mars Control. Confirmed for insertion. Come left 20 degrees and make your burn."`
  
- **At t = 6s:**  
  It produces:  
  `"Control, DUKAKIS TANGO, 20 degrees left, thank you. Burning now."`

## Future Considerations
- **Extended Dialogue:** Additional maneuver types and dynamic dialogue adjustments based on context.
- **Real-Time Adjustments:** Possibility to adjust script timings based on simulation speed or events.
- **Data-Driven Templates:** Storing dialogue templates in a configuration file or database for easier updates.
- **Better Actor Management:** Integrating with a more robust actor model that differentiates between various pilot, controller, and other role types.

## Conclusion
This spec defines the Script Service's requirements and desired functionality for converting NavigationEvents into ScriptEvents for system simulation. It provides a clear path for initial implementation (starting with SUBLIGHT maneuvers) and outlines possibilities for future enhancement.
