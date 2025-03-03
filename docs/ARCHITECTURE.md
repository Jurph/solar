# Universe Project Architecture

## Project Structure

    solar/
    ├── docs/                         # Project documentation
    │   ├── ARCHITECTURE.md          # Project architecture documentation (this file)
    │   ├── TODO.md                  # Future development plans and feature backlog
    │   └── RADIO_PROTOCOLS.md       # Communication and radio protocols documentation
    │
    ├── xml/                         # Universe definition files & templates
    │   ├── milkyway.xml             # Sample universe definition (Milky Way)
    │   └── templates/               # XML templates for generating new universe content
    │
    ├── tests/                       # Testing suite for unit and integration tests
    │   ├── test_ship_generation.py  # Tests for ship name and cargo generation
    │   ├── test_universe_import.py  # Tests for XML universe import functionality
    │   └── test_xml/                # XML validation and schema tests
    │
    └── mysite/                      # Django application root
        ├── manage.py               # Django management script
        └── mysite/                 
            ├── settings.py         # Django settings configuration
            ├── urls.py             # URL routing for the application
            └── universe/           
                ├── models/        
                │   ├── base.py         # Base Location model and common utilities
                │   ├── celestial.py    # Hierarchical celestial structure: galaxies, systems, stars, planets & moons
                │   ├── navigation.py   # Navigation types and routing logic
                │   ├── ship.py         # Ship model with dynamic status, locations, and procedural name generation
                │   ├── station.py      # Station model representing orbital control and docking facilities
                │   ├── actor.py        # Actor model for Pilots and Controllers with personality traits
                │   ├── mission.py      # Mission model for narrative-driven journeys
                │   └── dialogue.py     # DialogueEvent model for time-stamped communications
                │
                ├── services/         
                │   ├── dictionary.py       # DictionaryServer: Provides word lists for procedural content
                │   ├── route_server.py     # RouteServer: Calculates paths and navigational routes
                │   ├── script_server.py    # ScriptServer: Generates radio communications and simulation scripts
                │   ├── cargo_server.py     # CargoServer: Determines and assigns cargo based on ship properties
                │   ├── scheduler.py        # Scheduler: Manages time-stamped dialogue events
                │   └── traffic_control.py  # TrafficControl: Manages simulation agents and real-time ship movement
                │
                ├── simulation/       
                │   ├── engine.py           # Event-driven simulation engine with time-based game loop
                │   └── agents/             # Simulation agents (e.g., ShipAgent) for autonomous behavior
                │
                ├── ui/
                │   ├── terminal_view.py    # Text-based terminal view for displaying dialogue events
                │   └── audio_view.py       # (Future) Audio playback view for dialogue events
                │
                ├── templates/universe/ 
                │   ├── base.html           # Base HTML template for the universe browser
                │   ├── index.html          # Main index page for browsing the universe
                │   ├── route.html          # Route planning interface
                │   └── terminal.html       # Scrolling terminal display for dialogue events
                │
                ├── management/commands/    
                │   ├── import_universe.py  # XML import command for loading universe data into the database
                │   ├── export_universe.py  # XML export command for saving the current universe state
                │   ├── generate_ships.py   # Command for generating test ships throughout the universe
                │   └── random_mission.py   # Command for generating random missions (simulation)
                │
                ├── import_xml.py         # Library for importing XML definitions into the database
                ├── export_xml.py         # Library for exporting database state to XML
                ├── migrations/           # Django database migrations for evolving the data model
                ├── admin.py              # Django admin interface for Universe models
                └── views.py              # Django views for rendering and interacting with universe data

## Core Components

### Data Model

The data model defines the structure and relationships of our celestial objects, spacecraft, and narrative elements.

- **base.py:** Base model for Location and shared attributes.
- **celestial.py:** Hierarchical structure covering galaxies, star systems, stars, planets, and moons.
- **station.py:** Represents space stations and control centers that orbit celestial bodies.
- **ship.py:** Ships that dynamically manage their status, location, and cargo while incorporating procedural generation.
- **navigation.py:** Encodes navigation logic for determining routes between locations.
- **actor.py:** Unified model for character types (Pilots, Controllers) with personality traits and voice templates.
- **mission.py:** Narrative-driven journeys with Ships, Actors, and routes that generate dialogue events.
- **dialogue.py:** Time-stamped dialogue events that represent communications between Actors.

### Services

Services expose business logic and integrations that enable a responsive simulation and procedural content.

- **DictionaryServer (dictionary.py):** Supplies word lists for procedural generation (e.g., ship names).
- **RouteServer (route_server.py):** Calculates optimal travel paths through our universe.
- **ScriptServer (script_server.py):** Transforms navigation events into dialogue events with appropriate timing.
- **CargoServer (cargo_server.py):** Determines and assigns cargo appropriate to each ship.
- **Scheduler (scheduler.py):** Manages a queue of time-stamped dialogue events, ensuring they are processed at the correct simulation time.
- **TrafficControl (traffic_control.py):** Oversees simulation agents and manages ship traffic.

### Simulation Engine

The simulation engine drives real-time interactions across our universe.

- **The Game Loop (engine.py):** A time-based simulation loop that advances simulation time at regular intervals (approximately every 2 seconds).
- **Event Processing:** As the simulation time advances, the engine checks for dialogue events whose scheduled time has arrived and sends them to the appropriate view.
- **Agents:** Autonomous agents (such as ShipAgent) that handle ship behavior and mission execution.

### User Interface

The UI layer provides different views of the simulation's output.

- **Terminal View (terminal_view.py):** A scrolling, terminal-like display in a web browser that shows dialogue events as they are processed.
- **Audio View (audio_view.py):** (Future) An audio playback interface that will play dialogue events as speech with ambient effects.
- **Admin Controls:** Tools for spawning missions, creating anomalous events, and adjusting simulation parameters.

### Data Management

Universe data is defined via XML and imported into our application, with support for export.

- **XML Definitions:** XML files in the `xml/` directory define star systems, celestial bodies, and stations.
- **Import/Export Tools:**
  - **import_universe.py & import_xml.py:** Import universe data from XML into the database.
  - **export_universe.py & export_xml.py:** Export current universe data back to XML.
- **Django Admin & Migrations:** Enable ongoing evolution with an admin interface and controlled schema migrations.

### Testing Suite

Our project is backed by a robust testing framework:

- **Unit Tests:** Validate core functionalities like ship generation, mission creation, and dialogue event scheduling.
- **XML Validation:** Ensure that universe XML files conform to defined schemas.
- **Test Database Setup:** Pytest (or `manage.py test`) automatically configures a test database for isolated testing.

## Data Flow

1. **Universe Setup:** Universe structure is defined in XML and imported into the database.
2. **Mission Creation:** Missions are created with Ships, Pilots (Actors), and routes between locations.
3. **Dialogue Event Generation:** The ScriptService transforms navigation events into time-stamped dialogue events.
4. **Event Scheduling:** The Scheduler queues dialogue events based on their scheduled time.
5. **Simulation Loop:** The game loop advances simulation time and processes events as their scheduled time arrives.
6. **View Rendering:** Processed events are sent to the appropriate view (text terminal or future audio interface).
7. **Export:** The updated universe state can be exported back to XML.

## Simulation Time Management

The simulation operates on a time-based model:

1. **Time Increments:** The game loop advances simulation time at regular intervals (approximately every 2 seconds).
2. **Event Queue:** Dialogue events are queued with scheduled timestamps.
3. **Event Processing:** As simulation time advances, events whose scheduled time has arrived are processed and sent to the view layer.
4. **Conflict Resolution:** The Scheduler ensures that no two dialogue events overlap by adjusting their scheduled times if conflicts are detected.

## View Layer Architecture

The view layer is decoupled from the core simulation logic:

1. **Terminal View:** Initially, a scrolling terminal-like display shows dialogue events as they are processed.
2. **Audio View:** (Future) An audio playback interface will play dialogue events as speech with ambient effects.
3. **View Independence:** Both views consume the same dialogue events from the Scheduler, allowing for different rendering approaches without changing the core simulation.

## Development Guidelines

- **Best Practices:** Follow Django best practices and Python coding standards.
- **Formatting:** Code is formatted using Black for consistency.
- **Documentation:** Comprehensive inline documentation and external documents (like this one) are maintained.
- **Testing:** High test coverage is required via unit, integration, and XML validation tests.
- **Modularity:** Emphasize modular service design to promote reusability and maintainability.
- **Version Control:** Use proper versioning, frequent commits, and code reviews to ensure stability.
- **Separation of Concerns:** Maintain clear boundaries between models, services, simulation logic, and views.
- **DRY Principles:** Avoid code duplication by creating reusable components and abstractions.