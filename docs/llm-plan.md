# LLM Plan: Space Comms Simulation Integration with Django

This guide provides a detailed, step-by-step blueprint for incrementally developing the Space Comms Simulation project. It builds on our existing Django app, XML import functionality, SimPy simulation engine, and our design documents. Each step comes with a clear objective and an associated prompt for a code-generation LLM. The plan emphasizes test-driven development, integration at each stage, and adherence to our style standards.

---

## Step 1: Verify Project Structure and Testing Framework

**Objective:**  
Confirm that the Django project structure is in place, with the appropriate directories (docs, xml, tests, mysite/universe) and that the testing configuration (Django test runner and pytest) works.

**LLM Prompt:**  
"Verify that the project repository contains the expected structure as outlined in our architecture document. Ensure that the Django project ('mysite') and app ('universe') are set up, with directories for models, services, simulation, templates, management commands, and tests. Create a simple placeholder test in tests/test_placeholder.py that asserts True, and confirm that 'python manage.py test' executes this test successfully."

---

## Step 2: Implement and Integrate Simulation Configuration

**Objective:**  
Extend our simulation configuration by creating a configuration module to manage simulation parameters (simulation speed, event density, audio mixing levels, etc.) that are adjustable via the web UI.

**LLM Prompt:**  
"In the universe app, create a new module (or a utils submodule) named config.py. Define a class 'SimulationConfig' with default parameters such as simulation_speed (default 4.0), event_density, tts_volume, and static_volume. Provide getter/setter methods for these parameters. Write unit tests in tests/test_config.py to verify the default values and modifications. Ensure that this module is wired to allow dynamic configuration changes later via the admin UI."

---

## Step 3: Refine XML Universe Importer

**Objective:**  
Ensure that our existing XML parser and import command (import_universe.py and import_xml.py) robustly parses and validates universe XML data, applying defaults where necessary.

**LLM Prompt:**  
"Review the existing XML importer in mysite/universe/import_xml.py and the management command import_universe.py. Improve XML schema validation and error handling (fallback defaults if data is missing). Write unit tests in tests/test_xml_parser.py that load sample XML files (like milkyway-v004.xml) and verify that systems, stars, planets, and stations are imported correctly."

---

## Step 4: Develop Communication Models

**Objective:**  
Introduce new Django models to represent communication events, dialogue lines, and character information.

**LLM Prompt:**  
"In the universe app's models directory, create a new file called communication.py. Define the following Django models:
- CommunicationEvent: Represents a 10-second radio transmission slot, with fields such as start_time, duration, event_type, and priority.
- Dialogue: Stores dialogue content with fields for speaker (a ForeignKey to Character), message text, timestamp, and any metadata.
- Character: Represents pilots and controllers with attributes like name, archetype, personality description, and voice template.
Write Django model tests in tests/test_communication_models.py to create and validate instances of these models, ensuring proper relationships with existing models (like Ship)."

---

## Step 5: Extend ScriptService for Radio Communication

**Objective:**  
Enhance the ScriptService to generate radio scripts for different ship events and communication scenarios.

**LLM Prompt:**  
"Modify the existing universe/services/script_server.py to extend its functionality. Add new methods to:
- Generate dialogue lines for departure, arrival, maneuver events, and anomalies.
- Format speaker labels in ALL CAPS using the existing allcaps helper.
- Incorporate dynamic dialogue templates that could later be modulated via an LLM.
Write or update unit tests in tests/test_script_server.py to verify that given sample NavigationEvents and CommunicationEvents, the generated dialogue output follows the rules defined in our specification."

---

## Step 6: Enhance the Simulation Engine for Communications

**Objective:**  
Integrate communication scheduling into our SimPy-based simulation engine so that communication events (radio transmissions) are scheduled without conflict alongside movement events.

**LLM Prompt:**  
"Extend the SimulationEngine in universe/simulation/engine.py to integrate a CommunicationManager. This component should:
- Reserve 10-second communication slots for each event.
- Check for scheduling conflicts and automatically adjust event timings.
- Be incorporated as another agent or process in the existing SimPy environment.
Write unit tests in tests/test_simulation_engine.py to simulate overlapping events and confirm that the CommunicationManager resolves conflicts correctly."

---

## Step 7: Implement Stub Services for LLM-Enhanced Dialogue and TTS

**Objective:**  
Provide stub implementations for the Local LLM integration and Text-to-Speech (TTS) service to prepare for dynamic dialogue generation and audio synthesis.

**LLM Prompt:**  
"In the universe app's services directory, create:
- llm_integration.py: Define a class LLMIntegration with a method 'generate_dialogue(script: str, character_description: str)' that returns the script appended with a placeholder (e.g., '[LLM Variation]').
- tts_service.py: Define a class TTSService with a method 'synthesize(text: str, voice_template: str)' that logs the call and returns dummy audio data.
Write tests for these modules in tests/test_llm_integration.py and tests/test_tts_service.py, ensuring that stub outputs meet expectations. Additionally, wire these stub services into the ScriptService so that generated dialogue passes through LLMIntegration and TTSService as placeholders."

---

## Step 8: Develop the Web-Based Admin and Simulation UI

**Objective:**  
Create a Django-based web UI that displays a rolling (terminal-style) log of communication events and provides administrative controls for injecting events and adjusting simulation parameters.

**LLM Prompt:**  
"Within the universe app, implement Django views and URL routes (in views.py and urls.py) that render a web UI for the simulation. Develop templates (in templates/universe/) to present:
- A scrolling log that displays the generated radio dialogue.
- An overlay or control panel with admin functions such as 'Spawn Ship Journey', 'Create Anomalous Event', and 'Create Small Talk'.
- Adjustable UI inputs (such as sliders) for simulation speed, event density, and audio mixing levels.
Write integration tests (or manual testing scripts) to simulate admin actions and verify that the UI invokes the corresponding backend services appropriately. Ensure that this UI is prepared for future audio playback via a browser widget."

---

## Step 9: Add a Universe Builder Stub for Future Expansion

**Objective:**  
Develop a prototype tool for generating new universe XML files from a star catalog, to be integrated later with advanced procedural generation.

**LLM Prompt:**  
"In the universe app's services directory, create a file named universe_builder.py. Implement a class UniverseBuilder with a method 'build_universe(star_catalog_path: str, output_filename: str)' that logs the universe build request and writes a dummy XML file with basic structure to the specified output file. Write unit tests in tests/test_universe_builder.py to confirm that the file is created and contains the expected placeholder content. Document that this module is a stub for future development of a full universe generation tool."

---

## Step 10: Integrate Simulation Parameter Controls with the Web UI

**Objective:**  
Ensure that changes made in the web UI (e.g., simulation speed adjustments, event density, volume controls) dynamically update the simulation behavior.

**LLM Prompt:**  
"Modify the main simulation loop (which may be launched through a Django management command, e.g., run_simulation.py) to fetch parameters from the SimulationConfig module. Wire the web UI controls to update these configuration settings (via Django views and AJAX calls or form submissions), so that simulation adjustments are reflected in real time. Write integration tests in tests/test_simulation_parameters.py to simulate parameter changes and verify their effects on event scheduling and log outputs."

---

## Step 11: Comprehensive End-to-End Integration Testing & Finalization

**Objective:**  
Perform thorough integration testing to ensure that all modules (models, services, simulation engine, UI, LLM and TTS stubs) work harmoniously as a complete system.

**LLM Prompt:**  
"Develop an end-to-end integration test in tests/test_integration.py that:
- Launches the simulation loop (via a Django management command or background task).
- Simulates the injection of various ship events and communications (including departures, maneuvers, anomalies, and small talk).
- Uses the web UI endpoints or API calls to adjust simulation parameters.
- Verifies that the ScriptService produces correctly formatted dialogue, the CommunicationManager resolves scheduling conflicts, and stub services (LLM and TTS) are invoked appropriately.
Document how to run these tests and interpret their output, ensuring that all features are integrated without conflicts."

---

## Final Summary

This plan organizes our work into the following sequence:
1. Confirm project structure and testing framework.
2. Implement a dynamic simulation configuration module.
3. Refine our XML universe importer.
4. Develop new communication-related models (CommunicationEvent, Dialogue, Character).
5. Enhance ScriptService to generate radio dialogue.
6. Extend the SimulationEngine to incorporate communication scheduling.
7. Implement stub services for LLM dialogue enhancement and TTS.
8. Create a web-based simulation and admin UI.
9. Build a stub for a future Universe Builder.
10. Wire simulation parameter controls to the UI.
11. Conduct comprehensive end-to-end integration testing.

Each step is incremental, testable, and integrated with existing functionality. This guide can be used to prompt an LLM to generate code in a modular, best-practice-driven manner as we build toward the full, integrated space comms simulation.

Happy coding and steady progress!