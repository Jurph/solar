# Universe Project Architecture

## Project Structure

```
solar/
├── docs/                         # Project documentation
│   ├── ARCHITECTURE.md           # Architecture documentation (this file)
│   ├── TODO.md                   # Future development plans & feature backlog
│   ├── PHYSICS_BASED_CONTROLLER_RESPONSES.md  # Controller parameter generation notes
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
            │   ├── event.py      # Event, DialogueEvent, NavigationEvent, DialogueEventLog
            │   ├── audio_profile.py # AudioProfile for actor voice configuration
            │   ├── simulation.py # SimulationState for time management
            │   └── scale.py      # Scale enumeration
            │
            ├── services/         # Business logic & integrations
            │   ├── dictionary.py        # Word lists for procedural generation
            │   ├── route_server.py      # Route calculation
            │   ├── script_server.py     # Navigation to dialogue conversion
            │   ├── cargo_server.py      # Cargo assignment
            │   ├── dialogue_server.py   # Dialogue event scheduling
            │   ├── llm_service.py       # LLM integration (Ollama/OpenAI)
            │   ├── tts_service.py       # TTS integration (Chatterbox)
            │   ├── audio_plans.py       # Audio mixing plans per actor type
            │   ├── audio_synth.py       # Audio synthesis (quindars, room tone, modem noise)
            │   ├── actor_server.py      # Actor deployment & management
            │   ├── location_service.py  # Distance calculations & hierarchy queries
            │   ├── maneuver_physics.py  # Physics-based maneuver calculations
            │   ├── controller_physics.py # Physics parameters for controller responses
            │   ├── log_buffer.py        # Circular log buffer for monitoring
            │   └── dialogue/            # Dialogue system
            │       ├── base.py          # Base dialogue classes
            │       ├── factory.py       # Dialogue factory
            │       └── particles.py     # Dialogue particles (requests, responses, readbacks)
            │
            ├── views/           # Django views (decomposed by domain concern)
            │   ├── __init__.py  # Re-exports view callables for backward-compatible imports
            │   ├── events.py    # event_feed, event_scroller(+wrapper), clear_events
            │   ├── missions.py  # spawn_mission only
            │   ├── simulation.py # set_time_scale, skip_to_next_event, get_simulation_status
            │   ├── universe.py  # universe_view, object_details (delegates to serializers)
            │   ├── serializers.py # "baseball card" data shaping (presentation-oriented)
            │   ├── audio.py     # audio_preset, audio_lab UI, audio_lab_render (dev-gated)
            │   ├── logs.py      # /api/logs/ diagnostics tail (dev-gated)
            │   └── dev_guard.py # state_changing_dev_only guard for dev endpoints
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
            ├── export_xml.py   # XML export utility
            ├── procedural_generation.py  # Procedural universe generation
            ├── signals.py      # Django signal handlers
            ├── receivers.py    # Signal receivers (DialogueEvent → DialogueEventLog)
            │
            └── management/     # Django management commands
                └── commands/
                    ├── import_universe.py       # Import from XML
                    ├── export_universe.py       # Export to XML
                    ├── character_dialogue_demo.py  # Terminal-only dialogue demo
                    ├── audio_worker.py          # Background TTS pre-generation worker
                    └── [other utilities]
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
- **ship.py:** Dynamic ship model with procedural naming and cargo management.
- **station.py:** `Station` model and `BerthAssignment` for docking capacity.
- **actor.py:** `Actor` base class with subclasses `Pilot`, `Controller`, `Satellite`
- **audio_profile.py:** `AudioProfile` model for actor voice/audio configuration (quindars, room tone, etc.)
- **event.py:** 
  - Dataclasses: `Event`, `DialogueEvent`, `NavigationEvent`
  - Model: `DialogueEventLog` for persisting dialogue events with audio file tracking
- **simulation.py:** `SimulationState` singleton for time-scaling simulation clock
- **scale.py:** `Scale` enumeration for location scales (GALAXY, STARSYSTEM, STAR, PLANET, MOON, STATION).

### Services

- **route_server.py:** Public façade for route planning (RouteService).
  - Implementation in `services/route/` (plan, controllers, durations, missions, formatting)
- **script_server.py:** Converts `NavigationEvent`s into `DialogueEvent` chains
- **cargo_server.py:** Procedural cargo assignment for ships
- **dialogue_server.py:** Dialogue chain generation and event scheduling
- **llm_service.py:** LLM integration (Ollama/OpenAI) for dialogue generation
- **tts_service.py:** TTS integration (Chatterbox-Turbo) with caching
- **audio_plans.py:** Generates audio mixing plans per actor type (quindars, room tone, modem noise)
- **audio_synth.py:** Audio synthesis engine - renders quindars, modem noise, mixes components
- **actor_server.py:** Actor procedural generation and management
- **location_service.py:** Distance calculations and location hierarchy queries
- **maneuver_physics.py:** Physics-based maneuver timing and orbital mechanics
- **controller_physics.py:** Generates realistic parameters for controller responses
- **log_buffer.py:** Circular log buffer for runtime monitoring
- **dictionary.py:** Word lists for procedural content generation
- **dialogue/:** Dialogue system components
  - **base.py:** `DialogueParticle` base class and prompt building
  - **factory.py:** Particle factory (maps maneuver types to dialogue particles)
  - **particles.py:** Concrete particles (LaunchRequest, RadioResponse, RadioReadback, etc.)

### Audio Pipeline

- **audio_worker.py:** Management command - background worker for TTS pre-generation
  - Actor-based batching (processes one actor's lines at a time)
  - 60-second grace period for events at/near current time
  - Stale lock cleanup on startup (crash recovery)
  - Cleanup of old audio files (>10 min past)
  - Warmup test validates TTS/file I/O on startup
- **Web server:** Serves pre-rendered audio files only (no on-demand TTS generation)
- **Frontend:** Rate-limited HEAD checks (2s per event) to detect when audio is ready

### Views & User Interface

The views are split into multiple modules under `mysite/universe/views/` for clarity and future growth:

- **views/universe.py:** universe browsing + object details
  - **universe_view:** hierarchical universe browser
  - **object_details:** API endpoint for baseball-card JSON (delegates to `views/serializers.py`)
- **views/events.py:** event scroller + event feed + audio serving
  - **event_feed:** JSON API for polling dialogue events (time-gated by SimulationState)
  - **event_audio:** Serves pre-rendered audio (returns 202 if pending)
  - **event_scroller / event_scroller_wrapper:** terminal-style UI
  - **clear_events:** deletes DialogueEventLog rows
- **views/simulation.py:** simulation time control/status APIs
  - **set_time_scale, skip_to_next_event, get_simulation_status**
- **views/missions.py:** mission spawning
  - **spawn_mission:** spawns ship, generates route, creates dialogue chain, schedules events
- **views/audio.py:** Audio endpoints
  - **audio_preset:** Generates procedural audio (quindars, modem noise)
  - **audio_lab:** Dev tool for testing audio synthesis
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
- **receivers.py:** Django post_save receivers that ensure actor audio profiles exist
- **schemas/dialogue_schema.py:** JSON schemas for dialogue validation
- **wordlists/:** Text files with word lists for procedural generation
- **management/commands:** Django management commands
  - `import_universe`: Import from XML
  - `export_universe`: Export to XML
  - `character_dialogue_demo`: Terminal-only demo that replays generated events locally
  - `audio_worker`: Background TTS pre-generation worker
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
3. **Mission Creation:** `spawn_mission` creates ship, plans route, generates dialogue chain.
4. **Audio Pre-Generation:** Background `audio_worker` generates TTS audio 1 hour ahead of playback.
5. **Event Scheduling:** Dialogue events scheduled based on simulation time (stored in `DialogueEventLog`).
6. **Event Feed:** `event_feed` API returns events when simulation time reaches their timestamp.
7. **Presentation:** Events displayed via:
   - Event scroller (scrolling terminal display with TTS audio)
   - JSON API for real-time polling (checks `audio_ready` flag)
   - Control panel for simulation management (time scale, skip, spawn missions)
8. **Export:** Universe state can be exported to XML via `export_universe` command.

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

- **SimulationState:** Singleton model tracks simulation time using anchor point + wall clock elapsed × time scale
- **Time Scaling:** Simulation can run faster or slower than real-time (1x, 60x, 600x, 3600x)
- **Event Queue:** `DialogueEventLog` entries are time-gated by `event_feed` API
- **Background Processing:** `audio_worker` pre-generates audio for events 1 hour ahead
- **Separation of Concerns:** Web server observes simulation state; does not generate audio or run simulation logic

## Development Guidelines

- **Coding Standards:** Follow Black, flake8, and PEP guidelines for Python code.
- **Modularity:** Emphasize separation of concerns and DRY principles with well-defined modules.
- **Testing:** Maintain high test coverage through unit, integration, and XML schema tests.
- **Documentation:** Keep both inline and external documentation up-to-date.
- **Version Control:** Utilize frequent commits and proper versioning for traceability.