# Universe Project Architecture

## Project Structure

```
solar/
├── docs/                         # Project documentation
│   ├── ARCHITECTURE.md           # Architecture documentation (this file)
│   ├── TODO.md                   # Future development plans & feature backlog
│   └── RADIO_PROTOCOLS.md        # Communication & radio protocols
│
├── xml/                          # Universe definition files & templates
│   ├── milkyway.xml              # Sample universe definition
│   └── templates/                # XML templates for universe content
│
├── tests/                        # Testing suite for unit & integration tests
│   ├── test_actor.py
│   ├── test_import_export.py
│   ├── test_queue_functions.py
│   ├── test_route_planning.py
│   ├── test_ship_generation.py
│   ├── test_space_traffic_llm.py
│   ├── test_universe_graph.py
│   ├── test_LLM.py
│   └── test_dictionary_service.py
│
└── mysite/                       # Django application
    ├── manage.py                 # Django management script
    └── mysite/
        ├── settings.py           # Django settings
        ├── urls.py               # URL routing
        ├── admin.py              # Django admin interface
        ├── views.py              # Django views
        ├── import_xml.py         # XML import utility
        ├── export_xml.py         # XML export utility
        ├── migrations/           # Database migrations
        └── universe/             # Core application module
            ├── models/           # Data models
            │   ├── base.py
            │   ├── celestial.py
            │   ├── navigation.py
            │   ├── ship.py
            │   ├── station.py
            │   ├── actor.py
            │   ├── mission.py
            │   └── dialogue.py
            │
            ├── services/         # Business logic & integrations
            │   ├── dictionary.py
            │   ├── route_server.py
            │   ├── script_server.py
            │   ├── cargo_server.py
            │   ├── scheduler.py
            │   └── traffic_control.py
            │
            ├── simulation/       # Simulation engine & agents
            │   ├── engine.py
            │   └── agents/
            │
            ├── ui/               # User interface components
            │   ├── terminal_view.py
            │   └── audio_view.py
            │
            ├── templates/        # HTML templates
            │   └── universe/
            │       ├── base.html
            │       ├── index.html
            │       ├── route.html
            │       └── terminal.html
            │
            └── management/       # Django management commands
                └── commands/
                    ├── import_universe.py
                    ├── export_universe.py
                    ├── generate_ships.py
                    └── random_mission.py
```

## Core Components

### Data Model

- **base.py:** Base model for Location and shared utilities.
- **celestial.py:** Defines galaxies, star systems, stars, planets, and moons.
- **navigation.py:** Contains navigation and route planning logic.
- **ship.py:** Dynamic ship model with procedural naming and status management.
- **station.py:** Represents docking stations and orbital control centers.
- **actor.py:** Models Pilots, Controllers, and their personality traits.
- **mission.py:** Defines narrative-driven missions integrating actors, ships, and routes.
- **dialogue.py:** Handles time-stamped dialogue events for in-simulation communications.

### Services

- **dictionary.py:** Provides word lists for procedural content generation.
- **route_server.py:** Calculates optimal travel paths.
- **script_server.py:** Converts navigation events into dialogue scripts.
- **cargo_server.py:** Determines and assigns cargo to ships.
- **scheduler.py:** Manages the scheduling and processing of dialogue events.
- **traffic_control.py:** Oversees simulation agents and real-time ship movement.

### Simulation Engine

- **engine.py:** Drives the event-based simulation loop.
- **agents:** Autonomous agents (e.g., ShipAgent) that execute simulation behavior.

### User Interface

- **terminal_view.py:** Provides a scrolling terminal display of dialogue events.
- **audio_view.py:** (Planned) Audio playback interface for dialogue events.

### Management & Integration

- **import_xml.py & export_xml.py:** Utilities for importing/exporting universe data.
- **management/commands:** Django commands for universe data manipulation and simulation control.
- **admin.py & migrations:** Django admin interface and schema migrations for database management.

## Data Flow

1. **Import:** Universe definitions are loaded from XML files.
2. **Mission Creation:** Missions are generated using ships, actors, and navigation routes.
3. **Event Scheduling:** Dialogue and navigation events are queued based on simulation time.
4. **Simulation Loop:** The engine processes events as their scheduled times are reached.
5. **Presentation:** Processed events are rendered via the terminal view (and future audio view).
6. **Export:** The updated universe state can be exported back to XML.

## Simulation Time Management

- **Time Increments:** The simulation loop advances at regular intervals (e.g., every 2 seconds).
- **Event Queue:** Events are scheduled and processed as their timestamps are reached.
- **Conflict Resolution:** The scheduler adjusts event timings to avoid overlaps.

## Development Guidelines

- **Coding Standards:** Follow Black, flake8, and PEP guidelines for Python code.
- **Modularity:** Emphasize separation of concerns and DRY principles with well-defined modules.
- **Testing:** Maintain high test coverage through unit, integration, and XML schema tests.
- **Documentation:** Keep both inline and external documentation up-to-date.
- **Version Control:** Utilize frequent commits and proper versioning for traceability.