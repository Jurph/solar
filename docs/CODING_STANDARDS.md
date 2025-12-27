# Solar Project Coding Standards

## Basic Python Rules 

We are working with `ruff` which incorporates the best features of `black`, `flake8`, and others. We intend to be bound by the PEP3 standard to the greatest degree practical. Eventually all functions will have docstrings and all imports should prefer to be absolute rather than relative. Where there is a "Pythonic" way to do something we prefer it; when we use object-oriented Python we are guided by experts like Riel and "Uncle Bob" Roberts. This helps keep our software readable by humans and extensible. 

## File & Class Naming

### Models
Models use plain descriptive names, and capture essential things about how the world works. They are for the use of services; code calling them directly is probably wrong:
- `navigation.py`
- `location.py`
- `ship.py`

### Services
Services compose model features together. By pulling in parts of  `ship.py` and `celestial.py` and `navigation.py`, the `route_server.py` can generate routes without risking circular imports. The simulation should be built on services! 

Primary “façade” services use the suffix `_server` and expose a single public façade class:
- `route_server.py` exposes `RouteService`
- `script_server.py` exposes `ScriptService`
- `cargo_server.py` exposes `CargoService`
- ...and so on! 

Smaller helper modules may use `_service.py` naming (e.g. `location_service.py`) or live under a package (e.g. `services/route/`) when the implementation would otherwise become a single large file.

Classes within these files follow the same convention:
```python
class RouteService:
class ScriptService:
```

### Commands
Management commands use descriptive action names:
- `random_journey.py`
- `import_universe.py`

## Import Style
Prefer absolute imports from `mysite.universe...` for clarity. Use local (inside-function) imports to break circular dependencies when needed:
```python
from mysite.universe.models.ship import Ship
from mysite.universe.services.route_server import RouteService
```

## Code Style
- Follow "ruff"s best practices 
- Follow Black formatting
- Follow PEP 8
- Always use type hints
- Always document with docstrings

## Testing
- Test files mirror implementation files
- Use pytest-style tests
- Tests should always provide diagnostic value 
- Include docstrings in test functions
- Test tiny simple things first then build up 
- No degenerate or trivial tests
- No testing other people's code 

## Architecture 
- Build from the bottom up, so that modular pieces with docstrings and strong type hints force your design to be correct 
- Logic that is going to get reused should be in the data model or the service, not at the edge 
- We prefer tiny modular pieces that are well isolated  
- Don't repeat yourself! 
- Helper functions, all day long 