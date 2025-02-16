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
                │   └── station.py      # Station model representing orbital control and docking facilities
                │
                ├── services/         
                │   ├── dictionary.py       # DictionaryServer: Provides word lists for procedural content
                │   ├── route_server.py     # RouteServer: Calculates paths and navigational routes
                │   ├── script_server.py    # ScriptServer: Generates radio communications and simulation scripts
                │   ├── cargo_server.py     # CargoServer: Determines and assigns cargo based on ship properties
                │   └── traffic_control.py  # TrafficControl: Manages simulation agents and real-time ship movement
                │
                ├── simulation/       
                │   ├── engine.py           # Event-driven simulation engine
                │   └── agents/             # Simulation agents (e.g., ShipAgent) for autonomous behavior
                │
                ├── templates/universe/ 
                │   ├── base.html           # Base HTML template for the universe browser
                │   ├── index.html          # Main index page for browsing the universe
                │   └── route.html          # Route planning interface
                │
                ├── management/commands/ 
                │   ├── import_universe.py  # XML import command for loading universe data into the database
                │   ├── export_universe.py  # XML export command for saving the current universe state
                │   ├── generate_ships.py   # Command for generating test ships throughout the universe
                │   └── random_journey.py   # Command for generating random ship journeys (simulation)
                │
                ├── import_xml.py         # Library for importing XML definitions into the database
                ├── export_xml.py         # Library for exporting database state to XML
                ├── migrations/           # Django database migrations for evolving the data model
                ├── admin.py              # Django admin interface for Universe models
                └── views.py              # Django views for rendering and interacting with universe data

## Core Components

### Data Model

The data model defines the structure and relationships of our celestial objects and spacecraft.

- **base.py:** Base model for Location and shared attributes.
- **celestial.py:** Hierarchical structure covering galaxies, star systems, stars, planets, and moons.
- **station.py:** Represents space stations and control centers that orbit celestial bodies.
- **ship.py:** Ships that dynamically manage their status, location, and cargo while incorporating procedural generation.
- **navigation.py:** Encodes navigation logic for determining routes between locations.

### Services

Services expose business logic and integrations that enable a responsive simulation and procedural content.

- **DictionaryServer (dictionary.py):** Supplies word lists for procedural generation (e.g., ship names).
- **RouteServer (route_server.py):** Calculates optimal travel paths through our universe.
- **ScriptServer (script_server.py):** Generates radio communication scripts for in-simulation broadcasts.
- **CargoServer (cargo_server.py):** Determines and assigns cargo appropriate to each ship.
- **TrafficControl (traffic_control.py):** Oversees simulation agents and manages ship traffic.

### Simulation Engine

The simulation engine drives real-time interactions across our universe.

- **engine.py:** Core event-driven simulation logic.
- **agents:** Autonomous agents (such as ShipAgent) that handle ship behavior.
- **Management Commands:** Tools like `generate_ships.py` and `random_journey.py` facilitate testing and simulation runs.

### Data Management

Universe data is defined via XML and imported into our application, with support for export.

- **XML Definitions:** XML files in the `xml/` directory define star systems, celestial bodies, and stations.
- **Import/Export Tools:**
  - **import_universe.py & import_xml.py:** Import universe data from XML into the database.
  - **export_universe.py & export_xml.py:** Export current universe data back to XML.
- **Django Admin & Migrations:** Enable ongoing evolution with an admin interface and controlled schema migrations.

### Testing Suite

Our project is backed by a robust testing framework:

- **Unit Tests:** Validate core functionalities like ship generation and XML import.
- **XML Validation:** Ensure that universe XML files conform to defined schemas.
- **Test Database Setup:** Pytest (or `manage.py test`) automatically configures a test database for isolated testing.

## Data Flow

1. **Import:** Universe structure is defined in XML and imported into the database.
2. **Simulation Setup:** The simulation is populated with ships and celestial data.
3. **Navigation:** Ships calculate routes and navigate the universe.
4. **Traffic Control:** Real-time simulation processes manage ship movement and interactions.
5. **Communication:** Radio scripts and communications are dynamically generated.
6. **Export:** The updated universe state can be exported back to XML.

## Development Guidelines

- **Best Practices:** Follow Django best practices and Python coding standards.
- **Formatting:** Code is formatted using Black for consistency.
- **Documentation:** Comprehensive inline documentation and external documents (like this one) are maintained.
- **Testing:** High test coverage is required via unit, integration, and XML validation tests.
- **Modularity:** Emphasize modular service design to promote reusability and maintainability.
- **Version Control:** Use proper versioning, frequent commits, and code reviews to ensure stability.