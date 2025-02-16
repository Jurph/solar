# Solar Project Coding Standards

## Basic Python Rules 

We are working with `ruff` which incorporates the best features of `black`, `flake8`, and others. We intend to be bound by the PEP3 standard to the greatest degree practical. Eventually all functions will have docstrings and all imports should prefer to be absolute rather than relative. Where there is a "Pythonic" way to do something we prefer it; when we use object-oriented Python we are guided by experts like Riel and "Uncle Bob" Roberts. This helps keep our software readable by humans and extensible. 

## File & Class Naming

### Services
All service-layer components use the suffix `_server` but offer up a class `Service`::
- `route_server.py` exposes `routeService` - Not `route_service.py` or `routeServer`
- `script_server.py` exposes `scriptService` - Not `script_service.py` or `scriptServer`
- `cargo_server.py` exposes `cargoService` - Not `cargo_service.py` or `cargoServer`
- ...and so on! 

Classes within these files follow the same convention:
```python
class RouteServer:  # Not RouteService
class ScriptServer:  # Not ScriptService
```

### Models
Models use plain descriptive names:
- `navigation.py`
- `location.py`
- `ship.py`

### Commands
Management commands use descriptive action names:
- `random_journey.py`
- `import_universe.py`

## Import Style
Use relative imports within the app:
```python
from ...models import Ship
from ...services.route_server import RouteServer
```

## Code Style
- Follow Black formatting
- Follow PEP 8
- Use type hints
- Document with docstrings

## Testing
- Test files mirror implementation files
- Use pytest-style tests
- Include docstrings in test functions