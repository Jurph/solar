# Universe Project Architecture

## Project Structure
```
mysite/
├── manage.py
└── mysite/
    ├── settings.py
    ├── urls.py
    └── universe/
        ├── models/
        │   ├── __init__.py
        │   ├── celestial.py          # Base celestial objects (Galaxy, Star, Planet)
        │   ├── navigation.py         # Navigation types and rules
        │   └── station.py            # Space station definitions
        │
        ├── services/
        │   ├── __init__.py
        │   ├── route_server.py       # Route planning between locations
        │   └── script_server.py      # Radio communication script generation
        │
        ├── templates/
        │   └── universe/
        │       ├── base.html         # Base template with navigation
        │       ├── index.html        # Universe browser view
        │       └── route.html        # Route planning view
        │
        ├── static/
        │   └── universe/
        │       ├── css/
        │       │   └── style.css     # Universe browser styling
        │       └── js/
        │           └── browser.js    # Tree view interactions
        │
        ├── management/
        │   └── commands/
        │       ├── import_universe.py # XML import command
        │       └── export_universe.py # XML export command
        │
        ├── migrations/              # Database migrations
        │
        ├── docs/                    # Project documentation
        │   ├── ARCHITECTURE.md      # This file
        │   ├── TODO.md              # Future development plans
        │   └── RADIO_PROTOCOLS.md   # Communication standards
        │
        ├── tests/                   # Test suite
        │   ├── __init__.py
        │   ├── test_models.py
        │   └── test_services.py
        │
        ├── admin.py                 # Django admin configuration
        ├── apps.py                  # App configuration
        ├── urls.py                  # URL routing
        └── views.py                 # View controllers
```

## Core Components

### Models
- **Location**: Base class for all celestial objects
- **Galaxy, StarSystem, Star, Planet, Moon**: Celestial hierarchy
- **Station**: Space stations and control facilities
- **Navigation**: Types and rules for space travel

### Services
- **RouteServer**: Generates navigation routes through space
  - Finds common ancestors
  - Plans orbital maneuvers
  - Identifies control authorities
- **ScriptServer**: Generates radio communication scripts
  - Creates dialog between pilots and dispatchers
  - Follows proper radio protocols
  - (Future) Will integrate with LLM and TTS

### Views
- **UniverseBrowser**: Tree view of celestial objects
- **RoutePlanner**: Navigation planning interface

### Data Flow
1. XML files define universe structure
2. Import command populates database
3. Browser view displays hierarchy
4. Route planning:
   - User selects origin/destination
   - RouteServer generates navigation plan
   - ScriptServer generates radio dialog
   - View displays results

## Future Extensions
- Character system for pilots/dispatchers
- Voice generation system
- Radio effects and background noise
- Traffic control system
- Fuel and time calculations
- Emergency procedures

## Development Guidelines
- Follow Django best practices
- Use black for code formatting
- Document all classes and methods
- Write tests for new features
- Keep services modular and focused