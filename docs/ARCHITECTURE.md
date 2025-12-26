# Universe Project Architecture

## Project Structure

```
solar/
├── docs/                         # Project documentation
│   ├── ARCHITECTURE.md           # Architecture documentation (this file)
│   ├── TODO.md                   # Future development plans & feature backlog
│   ├── CELESTIAL_MODEL_PLAN.md   # Celestial model refactoring plan
│   ├── STORED_VS_CALCULATED_PROPERTIES.md  # Property storage decisions
│   ├── MIGRATION_MANAGEMENT.md   # Migration best practices
│   └── [other planning docs]
│
├── xml/                          # Universe definition files
│   ├── milkyway-v005.xml         # Main universe definition
│   ├── test_universe.xml         # Test universe
│   └── [other XML files]
│
├── tests/                        # Testing suite for unit & integration tests
│   ├── test_actor.py
│   ├── test_import_export.py
│   ├── test_procedural_generation.py
│   ├── test_route_planning.py
│   ├── test_ship_generation.py
│   ├── test_space_traffic_llm.py
│   ├── test_universe_graph.py
│   ├── test_LLM.py
│   ├── test_dialogue_*.py
│   └── test_dictionary_service.py
│
└── mysite/                       # Django application
    ├── manage.py                 # Django management script
    └── mysite/
        ├── settings.py           # Django settings
        ├── urls.py               # URL routing
        └── universe/             # Core application module
            ├── models/           # Data models
            │   ├── base.py       # Location base model
            │   ├── celestial.py  # Celestial, PhysicalBody, Star, Planet, Moon, Galaxy, StarSystem
            │   ├── physics.py    # Atmosphere model
            │   ├── display.py    # Display formatting utilities
            │   ├── navigation.py # Navigation & route planning
            │   ├── ship.py       # Ship model
            │   ├── station.py    # Station & BerthAssignment
            │   ├── actor.py      # Actor, Pilot, Controller, Satellite
            │   ├── event.py      # DialogueEventLog
            │   ├── broadcast_event.py  # BroadcastEvent
            │   └── scale.py      # Scale enumeration
            │
            ├── services/         # Business logic & integrations
            │   ├── dictionary.py        # Word lists for procedural generation
            │   ├── route_server.py      # Route calculation
            │   ├── script_server.py     # Navigation to dialogue conversion
            │   ├── cargo_server.py      # Cargo assignment
            │   ├── traffic_control.py   # Simulation agent management
            │   ├── dialogue_server.py   # Dialogue event scheduling
            │   ├── llm_service.py       # LLM integration
            │   ├── text_server.py       # Text processing
            │   ├── voice_server.py      # Voice/TTS integration
            │   ├── actor_server.py     # Actor deployment & management
            │   └── dialogue/            # Dialogue system
            │       ├── base.py          # Base dialogue classes
            │       ├── factory.py       # Dialogue factory
            │       └── particles.py    # Dialogue particles (requests, responses)
            │
            ├── simulation/       # Simulation engine & agents
            │   ├── engine.py    # Event-based simulation loop
            │   ├── agents/      # Autonomous agents
            │   │   ├── ship_agent.py
            │   │   └── station_agent.py
            │   └── events/      # Simulation event types
            │       ├── docking.py
            │       ├── maintenance.py
            │       └── movement.py
            │
            ├── views/           # Django views (decomposed by domain concern)
            │   ├── __init__.py  # Re-exports view callables for backward-compatible imports
            │   ├── events.py    # event_feed, event_scroller(+wrapper), clear_events
            │   ├── missions.py  # spawn_mission, run_demo (deprecated)
            │   ├── simulation.py # set_time_scale, skip_to_next_event, get_simulation_status
            │   ├── universe.py  # universe_view, object_details (delegates to serializers)
            │   ├── serializers.py # "baseball card" data shaping (presentation-oriented)
            │   └── audio.py     # placeholder for future audio/TTS endpoints
            │
            ├── templates/        # HTML templates
            │   └── universe/
            │       ├── base.html              # Base template with baseball card JS
            │       ├── index.html             # Universe browser (hierarchical tree)
            │       ├── event_scroller.html     # Event scroller iframe
            │       └── event_scroller_wrapper.html  # Main page with controls
            │
            ├── static/          # Static assets
            │   └── universe/
            │       ├── css/
            │       │   ├── style.css          # Universe browser & baseball card styles
            │       │   ├── event_scroller.css
            │       │   └── event_scroller_wrapper.css
            │       └── js/
            │           └── tree.js            # Tree expansion/collapse
            │
            ├── wordlists/       # Word lists for procedural generation
            │   ├── givennames.txt, surnames.txt
            │   ├── cities.txt, animals.txt, plants.txt
            │   └── [other word lists]
            │
            ├── schemas/        # JSON schemas
            │   └── dialogue_schema.py
            │
            ├── import_xml.py   # XML import utility
            ├── export_xml.py  # XML export utility
            ├── procedural_generation.py  # Procedural universe generation
            ├── generate_celestials.py    # Celestial body generation
            ├── shipping.py     # Shipping/cargo logic
            ├── signals.py      # Django signal handlers
            ├── receivers.py    # Signal receivers
            ├── simulation_queue.py  # Simulation event queue
            │
            └── management/     # Django management commands
                └── commands/
                    ├── import_universe.py      # Import from XML
                    ├── export_universe.py      # Export to XML
                    ├── generate_ships.py       # Generate ships procedurally
                    ├── generate_actors.py      # Generate actors
                    ├── generate_journey.py     # Generate journeys
                    ├── random_journey.py       # Random mission generation
                    ├── llm_journey.py          # LLM-driven journey
                    ├── run_simulation.py      # Run simulation
                    ├── start_simulation_loop.py  # Start simulation loop
                    ├── character_dialogue_demo.py  # Dialogue demo
                    ├── check_superuser.py      # Admin utilities
                    └── comms_check.py         # Communication check
```

## Core Components

### Data Model

- **base.py:** Base `Location` model with `get_concrete_instance()` and `get_type_name()` methods.
- **celestial.py:** 
  - Abstract: `Celestial`, `PhysicalBody` (with mass, radius, density, albedo, orbital properties)
  - Concrete: `Galaxy`, `StarSystem`, `Star`, `Planet`, `Moon`
  - All celestial bodies inherit from `PhysicalBody` → `Celestial` → `Location`
- **physics.py:** `Atmosphere` model (separate table, linked via ContentType to Planet/Moon)
- **display.py:** Display formatting utilities (format_number, format_distance_km, etc.)
- **navigation.py:** Navigation graph, route planning, and orbital mechanics utilities.
- **ship.py:** Dynamic ship model with procedural naming and status management.
- **station.py:** `Station` model and `BerthAssignment` for docking capacity.
- **actor.py:** `Actor` base class, `Pilot`, `Controller`, `Satellite` with personality traits.
- **event.py:** `DialogueEventLog` for time-stamped dialogue events.
- **broadcast_event.py:** `BroadcastEvent` for system-wide communications.
- **scale.py:** `Scale` enumeration for location scales (GALAXY, STARSYSTEM, STAR, PLANET, MOON, STATION).

### Services

- **dictionary.py:** Provides word lists for procedural content generation.
- **route_server.py:** Public façade for route planning (RouteService).
  - Implementation lives in `services/route/` (plan/controllers/durations/missions/formatting) to avoid a single large blob.
- **script_server.py:** Converts navigation events into dialogue scripts.
- **cargo_server.py:** Determines and assigns cargo to ships.
- **traffic_control.py:** Oversees simulation agents and real-time ship movement.
- **dialogue_server.py:** Manages dialogue event scheduling and processing.
- **llm_service.py:** LLM integration for structured output and dialogue generation.
- **text_server.py:** Text processing and formatting utilities.
- **voice_server.py:** Voice/TTS integration for audio output.
- **actor_server.py:** Actor deployment and management (Controllers, Pilots).
- **dialogue/:** Dialogue system components
  - **base.py:** Base dialogue classes and interfaces
  - **factory.py:** Dialogue factory for creating dialogue instances
  - **particles.py:** Dialogue particles (requests, responses, etc.)

### Simulation Engine

- **engine.py:** Drives the event-based simulation loop.
- **agents/:** Autonomous agents that execute simulation behavior
  - **ship_agent.py:** Ship movement and behavior agent
  - **station_agent.py:** Station operations agent
- **events/:** Simulation event types
  - **docking.py:** Docking/undocking events
  - **maintenance.py:** Maintenance and anomaly events
  - **movement.py:** Ship movement events
- **simulation_queue.py:** Event queue management for simulation timing.

### Views & User Interface

The views are split into multiple modules under `mysite/universe/views/` for clarity and future growth:

- **views/universe.py:** universe browsing + object details
  - **universe_view:** hierarchical universe browser
  - **object_details:** API endpoint for baseball-card JSON (delegates to `views/serializers.py`)
- **views/events.py:** event scroller + event feed
  - **event_feed:** JSON API for polling dialogue events (time-gated by SimulationState)
  - **event_scroller / event_scroller_wrapper:** terminal-style UI
  - **clear_events:** deletes DialogueEventLog rows
- **views/simulation.py:** simulation time control/status APIs
  - **set_time_scale, skip_to_next_event, get_simulation_status**
- **views/missions.py:** mission spawning
  - **spawn_mission:** spawns a mission and schedules dialogue into DialogueEventLog
  - **run_demo:** deprecated demo endpoint
- **templates/universe/:** HTML templates
  - **base.html:** Base template with baseball card JavaScript
  - **index.html:** Universe browser with hierarchical tree view
  - **event_scroller.html:** Event scroller iframe content
  - **event_scroller_wrapper.html:** Main simulation interface with controls
- **static/universe/:** Static assets
  - **css/style.css:** Universe browser and baseball card styling
  - **css/event_scroller*.css:** Event scroller styling
  - **js/tree.js:** Tree expansion/collapse JavaScript

### Management & Integration

- **import_xml.py:** XML import utility (`UniverseImporter` class)
  - Imports galaxies, systems, stars, planets, moons, stations
  - Handles physical properties (mass, radius, density, etc.)
  - Imports atmosphere data via ContentType
  - Idempotent (can run multiple times safely)
- **export_xml.py:** XML export utility for round-trip data transfer
- **procedural_generation.py:** Procedural universe generation with seeded RNG
  - Star, planet, moon generation functions
  - Atmosphere generation
  - Composition and physical property generation
- **generate_celestials.py:** Celestial body generation utilities
- **shipping.py:** Shipping and cargo management logic
- **signals.py & receivers.py:** Django signal handlers and receivers
- **schemas/dialogue_schema.py:** JSON schemas for dialogue validation
- **wordlists/:** Text files with word lists for procedural generation
- **management/commands:** Django commands for universe data manipulation and simulation control
  - `import_universe`: Import from XML (with --clear option)
  - `export_universe`: Export to XML
  - `generate_ships`: Procedurally generate ships
  - `generate_actors`: Generate pilots and controllers
  - `run_simulation`: Run simulation loop
  - `start_simulation_loop`: Start background simulation
  - `llm_journey`: LLM-driven journey generation
  - And more...
- **admin.py & migrations:** Django admin interface and schema migrations

## Data Flow

1. **Import:** Universe definitions are loaded from XML files via `import_universe` command.
   - XML parsed and converted to Django models
   - Physical properties (mass, radius, etc.) imported
   - Atmosphere data imported and linked via ContentType
   - Idempotent: can be run multiple times safely
2. **Universe Browser:** Users navigate hierarchical tree (`/universe/`)
   - Click celestial objects to view details
   - Baseball card displays physical properties, atmosphere, orbital data
   - API endpoint `/api/universe/<type>/<id>/` provides JSON data
3. **Mission Creation:** Missions/journeys generated using ships, actors, and navigation routes.
4. **Event Scheduling:** Dialogue and navigation events are queued based on simulation time.
5. **Simulation Loop:** The engine processes events as their scheduled times are reached.
6. **Presentation:** Processed events are rendered via:
   - Event scroller (scrolling terminal display)
   - JSON API for real-time polling
   - Control panel for simulation management
7. **Export:** The updated universe state can be exported back to XML via `export_universe` command.

## Key Features

### Universe Browser
- Hierarchical tree view of galaxies → systems → stars → planets → moons → stations
- Expandable/collapsible nodes
- Click any object to view detailed "baseball card" with:
  - Physical properties (mass, radius, density, surface gravity)
  - Orbital properties (period, eccentricity, inclination, etc.)
  - Atmospheric data (type, height, pressure)
  - Thermal properties (temperature, albedo)
  - Rotation properties (day length, axial tilt, tidal locking)

### Baseball Card System
- Dynamic detail view for celestial objects
- Server-side formatting (business logic in `models/display.py`)
- Real-time data via AJAX API
- Comprehensive stats for "pilot pre-mission briefing"

### Inheritance Hierarchy
```
Location (concrete)
  └── Celestial (abstract)
      └── PhysicalBody (abstract)
          ├── Planet (concrete)
          ├── Moon (concrete)
          └── Star (concrete)
```

### Atmosphere Model
- Separate table linked via ContentType (generic foreign key)
- Only created when body has atmosphere
- Supports both Planet and Moon

## Simulation Time Management

- **Time Increments:** The simulation loop advances at regular intervals.
- **Event Queue:** Events are scheduled and processed as their timestamps are reached.
- **Conflict Resolution:** The scheduler adjusts event timings to avoid overlaps.

## Development Guidelines

- **Coding Standards:** Follow Black, flake8, and PEP guidelines for Python code.
- **Modularity:** Emphasize separation of concerns and DRY principles with well-defined modules.
- **Testing:** Maintain high test coverage through unit, integration, and XML schema tests.
- **Documentation:** Keep both inline and external documentation up-to-date.
- **Version Control:** Utilize frequent commits and proper versioning for traceability.