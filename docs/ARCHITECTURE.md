# Universe Project Architecture

## Project Structure

    solar/
    ├── docs/                         # Project documentation
    │   ├── ARCHITECTURE.md          # This file
    │   ├── TODO.md                  # Future development plans
    │   └── RADIO_PROTOCOLS.md       # Communication standards
    │
    ├── xml/                         # Universe definition files
    │   ├── milkyway.xml            # Current Milky Way definition
    │   └── templates/              # XML templates for new content
    │
    ├── tests/                       # Python unit tests
    │   └── test_xml/              # XML validation tests
    │
    └── mysite/                      # Django application
        ├── manage.py
        └── mysite/
            ├── settings.py
            ├── urls.py
            └── universe/
                ├── models/
                │   ├── base.py          # Base Location model
                │   ├── celestial.py     # Celestial objects
                │   ├── navigation.py    # Navigation types
                │   ├── ship.py          # Ship model
                │   └── station.py       # Station model
                │
                ├── services/
                │   ├── route_server.py      # Route planning
                │   ├── script_server.py     # Radio script generation
                │   ├── ship_generator.py    # Procedural ship creation
                │   └── traffic_control.py   # Simulation control
                │
                ├── simulation/
                │   ├── engine.py            # Simulation engine
                │   └── agents/              # Simulation agents
                │
                ├── templates/universe/
                │   ├── base.html            # Base template
                │   ├── index.html           # Universe browser
                │   └── route.html           # Route planning
                │
                ├── management/commands/
                │   ├── import_universe.py    # XML import
                │   ├── export_universe.py    # XML export
                │   └── run_simulation.py     # Simulation runner
                │
                ├── migrations/             # Database migrations
                ├── admin.py               # Admin interface
                └── views.py               # View controllers

## Core Components

### Data Model
- Hierarchical celestial structure (Galaxy → System → Star → Planet → Moon)
- Space stations can orbit any celestial body
- Ships with dynamic status and location
- Navigation steps and maneuver types

### Services
- **RouteServer**: Calculates paths through space
- **ScriptServer**: Generates radio communications
- **ShipGenerator**: Creates procedural ships
- **TrafficControl**: Manages simulation agents

### Simulation Engine
- Event-driven simulation core
- Ship agents with autonomous behavior
- Traffic control coordination
- Command-line simulation runner

### Data Management
- XML-based universe definition
- Import/export tools
- Django admin interface
- Database migrations

## Data Flow
1. Universe structure defined in XML
2. Data imported to database
3. Simulation populated with ships
4. Ships navigate via route planning
5. Traffic control manages movements
6. Radio communications generated

## Development Guidelines
- Django best practices
- Black for Python formatting
- Comprehensive documentation
- Test coverage required
- Modular service design