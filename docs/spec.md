# Space Comms Simulation Specification

## 1. Overview

This ambient simulation creates a radio-like environment for ship communications in a procedurally generated universe. The simulation features:

- **Ambient Radio Traffic:** A rolling, text-only log of scripted dialogue resembling police scanners or ATC radios.
- **Ship Events:** A variety of events (launch, docking, landing, hyperspace jumps, subsystem failures, in-flight emergencies, navigation errors, near misses, and small talk) that generate narrative communications.
- **Pilot & Control Characters:** Characters with a name, personality archetype, and a simple backstory. Their dialogue is generated from a fixed script "skeleton" and later modulated by a local LLM and text-to-speech (TTS) system.
- **Scheduling and Reservations:** A global (or per star system) scheduler that reserves discrete 10-second communication "chunks" so that no two events conflict.
- **Simulation Parameters:** Adjustable knobs for simulation speed (acceleration factor), event density (e.g., average comms per minute), and audio mixing (TTS volume vs. ambient static/beeps). These parameters will eventually influence dynamic audio generation.
- **Planetary & System Fidelity:** Initially uses an XML file for the Milky Way (e.g., `milkyway-v004.xml`). For planetary fidelity, the focus is on orbital parameters (median orbital distance, orbital inclination) that influence travel times and maneuver requirements. Later extensions will incorporate planet types, resource lists, and commodity cargo profiles.

---

## 2. Requirements

### 2.1 Ship Events and Communications

- **Core Event Types:**
  - **Departure Events:** Launch, circularization, and docking.
  - **Arrival Events:** Landing and undocking.
  - **Maneuver Events:** Hyperspace jumps and plane changes (influenced by orbital inclinations).
  - **Anomaly Events:** Subsystem failures (introducing procedural delays), in-flight emergencies (e.g., sick passenger), navigation errors, and near misses.
  - **Small Talk:** Spontaneous inter-ship chatter to introduce variability in dialogue.

- **Dialogue Presentation:**
  - **Speaker Labels:** Rendered as all-uppercase versions of character names (using a helper method like `allcaps()`).
  - **Dialogue Text:** Preserves natural case (e.g., "Venus Control, this is Lima VI…").

### 2.2 Character Generation

- **Pilot & Control Characters:**
  - **Attributes:** Name, Archetype, and a short Character Description (e.g., attention to detail, risk tolerance, tradition adherence).
  - **Generation:** Initially can be procedural or hand-curated. Future iterations may integrate local LLMs to generate richer descriptive backstories influenced by personality parameters.

### 2.3 Scheduling and Communication "Chunks"

- **Global Scheduling:**
  - Uses a global (or per star system) queue.
  - **Time Chunks:** Each dialogue event reserves a 10-second time slot.
  - **Reservation Logic:** Before a ship initiates its journey, it "reserves" its communication slots (based on known leg durations and expected conversation lengths) to ensure no overlapping events. If conflicts occur, the ship's departure is delayed until a conflict-free route is available.

### 2.4 Sound and TTS Integration

- **Ambient Audio:**
  - **Room Tone:** Procedurally generated static that will later vary by ship size (e.g., low, rumbling static for Large ships; high-pitched buzz for Small ships).
  - **Comm Beeps:** Derived from Quindar Tones with slight modulation according to ship characteristics.
- **TTS Voices:**
  - Each character (Pilots and Control) is assigned a specific voice template. Future enhancements will allow these templates to be dynamically modified (i.e., tunable voice avatars) to reflect character traits.
- **Initial Output:**
  - The simulation begins as a text-only streaming interface (a rolling log resembling a retro terminal). Future plans include integrating generated audio streams with procedural effects.

### 2.5 Admin UI and Controls

- **User Interface:**
  - A non-interactive, ambient scrolling log that displays the narrative dialogue.
  - An overlay/toolbar with administrative controls meant primarily for debugging and feature testing:
    - **Spawn Ship Journey:** Creates a random ship departure to a random destination, reserving the earliest available timeslot.
    - **Create Anomalous Event:** Injects a maintenance anomaly or similar events.
    - **Create Small Talk:** Forces a nearby ship to engage in small talk.
- **Additional Controls:**
  - **Adjustable Knobs/Sliders** for:
    - **Simulation Speed:** Defaults at approximately 4× real-time.
    - **Event Density:** Adjust the number of communications per minute.
    - **Volume/Mixing Levels:** Controls for TTS voices vs. ambient effects (static/beeps).

### 2.6 Planetary and System Fidelity

- **Planetary Parameters:**
  - **Orbital Parameters:** Each planet has a median orbital distance (basis for travel time calculations) and an orbital inclination (influencing plane-change maneuvers).
  - **Future Enhancements:**
    - Add planet types (e.g., SILICATE, GAS GIANT, ICE GIANT) which will affect available commodity cargo profiles.
    - Incorporate resource lists and custom cargo modifiers to allow for unique planetary profiles.
- **Star and System Information:**
  - Use provided XML (e.g., `milkyway-v004.xml`) for the Milky Way system.
  - Each system should include recognizable star names, correct stellar types, and proper distances from the galactic center.
  - Future plans include a universe builder that generates XML files from a star catalog, allowing for different output filenames and multiple universe iterations.

---

## 3. Architecture and Data Handling

### 3.1 Code Organization

- **Modules / Packages:**
  - **`models`:** Data classes for entities such as `Ship`, `NavigationEvent`, `Planet`, etc.
  - **`services`:** Contains business logic—including `ScriptService`, `Scheduler`, `AudioService`, and (future) `LLMIntegration`.
  - **`ui`:** User interface components (text log display, admin control panels).
  - **`data`:** XML universe loader for the Milky Way and the (future) Universe builder.
  - **`utils`:** Helper functions (e.g., `allcaps(text: str)`) for common string formatting.

### 3.2 Data Flow and Handling

- **XML Universe Data:**
  - Parse the Milky Way XML file to extract systems, stars, planets, and stations. Use robust XML parsing strategies and fallback defaults if data is missing.
- **Event Scheduling:**
  - Each ship's journey is broken down into a series of scheduled events with associated metadata:
    - **Planned Start Time**
    - **Duration:** Based on 10-second dialogue chunks.
    - **Event Type** and **Priority**
  - The scheduler reserves time slots, and if conflicts are detected, it adjusts (delays) subsequent events to maintain a non-overlapping, coherent communication stream.
- **Simulation Config:**
  - Maintain a configuration object for simulation parameters like speed, event density, and audio mixing. These parameters should be dynamically adjustable via the admin UI.

---

## 4. Error Handling Strategies

- **Scheduler & Event Reservations:**
  - **Conflict Resolution:** If a ship's time slot reservation conflicts with another, log the conflict to a debug log (or terminal) and automatically re-attempt scheduling with an adjusted departure time.
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
    - Each service (e.g., `ScriptService`) to ensure correct dialogue generation.
    - Helper functions (e.g., `allcaps()`).
    - XML parsing modules to handle expected and edge-case XML structures.
- **Scheduler Testing:**
  - Simulate various scheduling scenarios:
    - Verify that time slot reservations are conflict-free.
    - Ensure proper delay and rescheduling on conflicts.

### 5.2 Integration Testing

- **End-to-End Simulation:**
  - Implement integration tests that simulate full ship journeys and verify that the rolling text-based log accurately reflects the expected dialogue sequence.
- **Admin UI Testing:**
  - Test administrative functions:
    - Validate that the "Spawn Ship Journey," "Create Anomalous Event," and "Create Small Talk" commands correctly inject events into the schedule.
- **Parameter Adjustments:**
  - Verify that changes to simulation speed, event density, and audio mixing parameters are reflected in the simulation output in real time.

### 5.3 Performance and Robustness Tests

- **Stress Testing:**
  - Simulate high volumes of events to ensure the scheduler and UI remain responsive.
- **Failure Mode Testing:**
  - Force errors (e.g., invalid XML input, scheduling conflicts) to confirm that error handling routines log errors appropriately and maintain simulation stability.

---

## 6. Future Enhancements

- **LLM Integration:**
  - Integrate local LLMs to generate richer, character-modulated dialogue.
- **TTS Integration:**
  - Connect local TTS systems for dynamic audio rendering based on character voice templates, with procedural adjustments for ambient audio.
- **Universe Builder:**
  - Develop a tool to generate new Universe/Galaxy XML files from a star catalog, with a configurable output file naming and versioning scheme.
- **Enhanced Planetary Fidelity:**
  - Extend the simulation to include planet types and unique resource distributions for deeper commodity cargo mechanics and specialized maneuver scenarios (e.g., aerobraking).

---

## 7. Summary

This specification outlines a modular, extensible simulation designed to create an immersive, ambient radio communications environment in space. The key components include:

- **Ship and Planet Event Modeling:** Where ship journeys and planetary orbital parameters affect narrative communication.
- **Dynamic Scheduling and Reservation:** Featuring a global scheduler that allocates discrete communication time slots.
- **Ambient UI and Admin Controls:** An initial text-only log interface with admin tools for event injection and simulation parameter adjustment.
- **Future Integration Points:** Hooks for local LLM and TTS modules to enhance dialogue variability and audio realism, and a Universe Builder tool for generating complex galaxy XML files.

Developers should begin by implementing foundational services (Scheduler, ScriptService, XML parser, and basic UI), then incrementally add features as outlined in the future enhancements.

Happy coding and enjoy building the space comms simulation! 