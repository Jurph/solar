# "Solar" - the space comms simulation 
## Software Feature Specification

## 1. Overview

This ambient simulation creates a radio-like environment for ship communications in a procedurally generated universe. The simulation features:

- **Ambient Radio Traffic:** A rolling, text-only log of scripted dialogue resembling police scanners or ATC radios.
- **Ship Events:** A variety of events (launch, docking, landing, hyperspace jumps, subsystem failures, in-flight emergencies, navigation errors, near misses, and small talk) that generate narrative communications.
- **Pilot & Control Characters:** Characters with a name, personality archetype, and a simple backstory. Their dialogue is generated from a fixed script "skeleton" and later modulated by a local LLM and text-to-speech (TTS) system.
- **Time-Based Simulation:** A simulation loop that advances time at regular intervals (approximately every 2 seconds), allowing dialogue events to unfold sequentially rather than all at once.
- **Scheduling and Reservations:** A global (or per star system) scheduler that reserves discrete time slots for dialogue events, ensuring that no two events conflict.
- **Simulation Parameters:** Adjustable knobs for simulation speed (acceleration factor), event density (e.g., average comms per minute), and audio mixing (TTS volume vs. ambient static/beeps). These parameters will eventually influence dynamic audio generation.
- **Celestial & System Hierarchy:** Universe structure is defined in XML and stored in the database. The system successfully models the hierarchical relationships between galaxies, star systems, stars, planets, moons, and stations.

---

## 2. Requirements

### 2.1 Ship Events and Communications

- **Core Navigation Event Types:**
  - **Departure Maneuvers:** UNDOCK, LAUNCH, INSERTION, DIRECT_ASCENT
  - **Transition Maneuvers:** PLANE_CHANGE, SUBLIGHT, HYPERSPACE, CIRCULARIZE
  - **Arrival Maneuvers:** DEORBIT, LANDING, DOCK
  - **All maneuvers have associated controllers** assigned using the effective_controller logic.
  
- **Other Event Types:**
  - **Anomaly Events:** Subsystem failures (introducing procedural delays), in-flight emergencies (e.g., sick passenger), navigation errors, and near misses.
  - **Small Talk:** Spontaneous inter-ship chatter to introduce variability in dialogue.

- **Dialogue Presentation:**
  - **Speaker Labels:** Rendered as all-uppercase versions of character names (using a helper method like `allcaps()`).
  - **Dialogue Text:** Preserves natural case (e.g., "Venus Control, this is Lima VI…").
  - **Hidden Context:** Dialogue passed behind the scenes in a context-rich JSON blob   

### 2.2 Character Generation

- **Actor System:**
  - **Base Actor Class:** A unified model for all character types (Pilots, Controllers) with shared attributes but different roles.
  - **Attributes:** Name, Role, Archetype, and a short Character Description (e.g., attention to detail, risk tolerance, tradition adherence).
  - **Generation:** Initially can be procedural or hand-curated. Future iterations may integrate local LLMs to generate richer descriptive backstories influenced by personality parameters.
  - **Voice Models:** Each Actor will eventually be assigned a specific voice template for TTS integration.

### 2.3 Mission and Scheduling System

- **Mission Structure:**
  - **Mission Class:** Encapsulates a narrative-driven journey with a Ship, Pilot (Actor), start Location, end Location, and for transport missions, a Cargo.
  - **Route Generation:** Each Mission generates a route with a series of NavigationEvents using the three-pass planning approach.
  - **Dialogue Events:** Navigation events are transformed into time-stamped dialogue events between the ship's Pilot and Control Actors along the route.

- **Scheduler and Time Management:**
  - **Simulation Loop:** A game loop that increments simulation time at regular intervals (approximately every 2 seconds).
  - **Event Queue:** The Scheduler maintains a queue of dialogue events, each with a scheduled timestamp.
  - **Time-Based Execution:** As the simulation time advances, dialogue events whose scheduled time has arrived are "popped" from the queue and sent to the view layer.
  - **Reservation Logic:** Before a ship initiates its journey, it "reserves" its communication slots (based on maneuver durations and expected conversation lengths) to ensure no overlapping events. If conflicts occur, the ship's departure is delayed until a conflict-free route is available.

### 2.4 Sound and TTS Integration

- **Ambient Audio:**
  - **Room Tone:** Procedurally generated static that will later vary by ship size (e.g., low, rumbling static for Large ships; high-pitched buzz for Small ships).
  - **Comm Beeps:** Derived from Quindar Tones with slight modulation according to ship characteristics.
  - **Per-Ship "Voice":** A mix of room tone and tailored comm beeps will make each ship distinctive. 
- **TTS Voices:**
  - Each Actor (Pilots and Control) is assigned a specific voice template. Future enhancements will allow these templates to be dynamically modified (i.e., tunable voice avatars) to reflect character traits.
- **Output Views:**
  - **Text Terminal:** Initially, a scrolling terminal-like display in a web browser that shows dialogue events as they are processed by the Scheduler.
  - **Audio Interface:** Future enhancement that will play dialogue events as audio, using the same underlying event queue from the Scheduler.

### 2.5 Admin UI and Controls

- **User Interface:**
  - A non-interactive, ambient scrolling log that displays the narrative dialogue as it unfolds in real-time.
  - An overlay/toolbar with administrative controls meant primarily for debugging and feature testing:
    - **Spawn Mission:** Creates a random mission with a Ship, Pilot, and route, scheduling dialogue events at appropriate times.
    - **Create Anomalous Event:** Injects a maintenance anomaly or similar events into the timeline.
    - **Create Small Talk:** Forces a nearby ship to engage in small talk at the next available time slot.
- **Additional Controls:**
  - **Adjustable Knobs/Sliders** for:
    - **Simulation Speed:** Defaults at approximately 4× real-time.
    - **Event Density:** Adjust the number of communications per minute.
    - **Volume/Mixing Levels:** Controls for TTS voices vs. ambient effects (static/beeps).

### 2.6 Celestial and System Hierarchy

- **Implemented Hierarchy:**
  - **Galaxy → Star System → Star → Planet → Moon → Station**: The system models the hierarchical relationships between these celestial objects.
  - **XML Import/Export:** The universe structure is defined in XML and can be imported/exported using command-line tools.
  
- **Celestial Parameters:**
  - **Orbital Parameters:** Each planet has a median orbital distance (basis for travel time calculations) and an orbital inclination (influencing plane-change maneuvers).
  - **Planetary Types:** Planet classifications (e.g., SILICATE, GAS GIANT, ICE GIANT) which affect available commodity cargo profiles.

- **Navigation and Route Planning:**
  - **Three-Pass Route Planning:**
    - **First Pass:** Create departure and arrival events based on origin and destination types.
    - **Second Pass:** Insert transfer events between intermediate nodes based on the transfer plan, including specialized handling for HYPERSPACE and intra-system transfers.
    - **Third Pass:** Refine navigation events with controller information.
  - **World Building Rules:** Detailed navigation rules govern the generation of routes, ensuring realistic space travel mechanics.

---

## 3. Architecture and Data Handling

### 3.1 Code Organization

- **Modules / Packages:**
  - **`models`:** Data classes for entities such as `Ship`, `Actor`, `Mission`, `NavigationEvent`, `DialogueEvent`, `Planet`, etc.
  - **`services`:** Contains business logic—including `ScriptService`, `RouteService`, `Scheduler`, `CargoService`, and (future) `LLMIntegration`.
  - **`ui`:** User interface components (text log display, admin control panels).
  - **`import_xml.py/export_xml.py`:** XML universe loader and exporter for the celestial hierarchy.
  - **`utils`:** Helper functions (e.g., `allcaps(text: str)`) for common string formatting.
  - **`simulation`:** Contains the simulation engine with the game loop and time management.

### 3.2 Data Flow and Handling

- **XML Universe Data:**
  - Parse XML files to extract systems, stars, planets, and stations. Use robust XML parsing strategies and fallback defaults if data is missing.
  - Support exporting the current universe state back to XML.
- **Mission and Event Generation:**
  - Each Mission generates a route with NavigationEvents using the RouteService.
  - NavigationEvents are transformed into dialogue events with timestamps.
  - The Scheduler queues these events based on their scheduled time.
  - The simulation loop advances time and processes events as their scheduled time arrives.
- **View Layer:**
  - Dialogue events popped from the Scheduler's queue are sent to the appropriate view (initially text, later audio).
  - The view layer is decoupled from the scheduling logic, allowing for different rendering approaches without changing the core simulation.
- **Simulation Config:**
  - Maintain a configuration object for simulation parameters like speed, event density, and audio mixing. These parameters should be dynamically adjustable via the admin UI.

---

## 4. Error Handling Strategies

- **Scheduler & Event Reservations:**
  - **Conflict Resolution:** If a dialogue event's time slot conflicts with another, log the conflict to a debug log (or terminal) and automatically re-attempt scheduling with an adjusted time.
  - **Critical Failures:** Use exceptions to handle unrecoverable scheduling errors, ensuring proper fallback and logging without crashing the simulation.
- **XML Parsing:**
  - Implement XML schema validation. Log warnings and apply defaults when encountering missing or unexpected data.
- **LLM & TTS Integration:**
  - Wrap external calls in try/except blocks. On failure, fall back to pre-generated dialogue templates or default audio rendering.
- **General Robustness:**
  - Ensure that system and admin messages are logged externally (in a log file or terminal) without interfering with the main user-facing UI.

---

## 5. Testing Plan

### 5.1 Unit Testing

- **Module Testing:**
  - Write unit tests for:
    - Each service (e.g., `ScriptService`, `RouteService`) to ensure correct dialogue generation and navigation planning.
    - Model classes (e.g., `Actor`, `Mission`, `NavigationEvent`) to verify proper initialization and behavior.
    - Helper functions (e.g., `allcaps()`).
    - XML parsing modules to handle expected and edge-case XML structures.
- **Route Planning Testing:**
  - Test various navigation scenarios:
    - Direct ascent between neighboring bodies
    - Multi-leg journeys with intermediate stops
    - Hyperspace travel between distant systems
    - Controller assignment and verification

### 5.2 Integration Testing

- **End-to-End Simulation:**
  - Implement integration tests that simulate full missions and verify that the rolling text-based log accurately reflects the expected dialogue sequence over time.
- **Admin UI Testing:**
  - Test administrative functions:
    - Validate that the "Spawn Mission," "Create Anomalous Event," and "Create Small Talk" commands correctly inject events into the schedule.
- **Parameter Adjustments:**
  - Verify that changes to simulation speed, event density, and audio mixing parameters are reflected in the simulation output in real time.

### 5.3 Performance and Robustness Tests

- **Stress Testing:**
  - Simulate high volumes of events to ensure the scheduler and UI remain responsive.
  - Test the simulation loop's performance under different time increment settings.
- **Failure Mode Testing:**
  - Force errors (e.g., invalid XML input, scheduling conflicts) to confirm that error handling routines log errors appropriately and maintain simulation stability.

---

## 6. Future Enhancements

- **LLM Integration:**
  - Integrate local LLMs to generate richer, character-modulated dialogue for Actors.
- **TTS Integration:**
  - Connect local TTS systems for dynamic audio rendering based on Actor voice templates, with procedural adjustments for ambient audio.
- **Universe Builder:**
  - Develop a tool to generate new Universe/Galaxy XML files from a star catalog, with a configurable output file naming and versioning scheme.
- **Enhanced Planetary Fidelity:**
  - Extend the simulation to include more detailed planet types and unique resource distributions for deeper commodity cargo mechanics and specialized maneuver scenarios (e.g., aerobraking).
- **Advanced Mission Types:**
  - Implement different mission subclasses for various narrative scenarios beyond simple transport missions.

---

## 7. Summary

This specification outlines a modular, extensible simulation designed to create an immersive, ambient radio communications environment in space. The key components include:

- **Celestial Hierarchy:** A structure modeling galaxies, star systems, stars, planets, moons, and stations, all defined in XML and stored in the database.
- **NavigationEvent System:** A sophisticated three-pass approach to route planning that creates realistic space travel maneuvers with appropriate controllers.
- **Mission and Actor Modeling:** Narrative-driven missions with Actors (Pilots, Controllers) that generate dialogue events.
- **Time-Based Simulation:** A game loop that advances time and processes dialogue events sequentially.
- **Dynamic Scheduling and Reservation:** A Scheduler that queues dialogue events with timestamps and ensures non-overlapping communication.
- **Dual-View Architecture:** A decoupled view layer that can render dialogue events as text (initially) or audio (future).
- **Admin Controls:** Tools for spawning missions, creating anomalous events, and adjusting simulation parameters.
- **Future Integration Points:** Hooks for local LLM and TTS modules to enhance dialogue variability and audio realism, and a Universe Builder tool for generating complex galaxy XML files.

The development roadmap follows the progression outlined in TODO.md, with initial phases focused on building the core simulation framework, and later phases expanding into character development, audio integration, and advanced procedural generation.

