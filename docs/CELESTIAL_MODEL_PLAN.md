# Celestial Model Refactoring Plan

## Overview
Refactor the celestial body models (Star, Planet, Moon) to:
1. Eliminate duplication through shared base classes/mixins
2. Add comprehensive physical properties needed for realistic orbital mechanics
3. Store physics lookup tables for procedural generation
4. Provide clean API for Controllers to access orbital parameters

---

## Phase 1: Identify Common Properties & Create Base Classes

### 1.1 Celestial Abstract Base Model (Top-Level)
**File**: `mysite/universe/models/physics.py` (new)

Create `Celestial` abstract Django model - the top-level class for all celestial bodies:
- All celestial bodies share: name, scale, basic location properties
- This is the common ancestor for Star, Planet, Moon

**Inherits from**: `Location`

### 1.2 Physical Properties Abstract Base Model
**File**: `mysite/universe/models/physics.py` (new)

Create `PhysicalBody` abstract Django model with common properties:
- `mass_kg` / `mass_solar` (with conversion methods)
- `radius_km` / `radius_solar` (with conversion methods)
- `density_kg_m3` (calculated or stored)
- `surface_gravity_ms2` (calculated from mass/radius)
- `albedo` (for thermal calculations)
- `equilibrium_temperature_k` (calculated from star distance/albedo)

**Methods**:
- `get_orbital_velocity(altitude_km)` - Calculate orbital speed at given altitude
- `get_escape_velocity()` - Calculate escape velocity
- `get_surface_gravity()` - Calculate surface gravity (if not stored)

### 1.2 Orbital Properties Abstract Base Model
**File**: `mysite/universe/models/physics.py` (new)

Create `OrbitalBody` abstract Django model:
- `orbital_distance_au` / `orbital_distance_km` (with conversion)
- `orbital_period_days` / `orbital_period_hours` (with conversion)
- `orbital_eccentricity` (0.0 = circular, 0.0-1.0 = elliptical)
- `orbital_inclination_deg` (tilt relative to reference plane)
- `axial_tilt_deg` (planet's rotation axis tilt - CRITICAL for plane changes)
- `rotation_period_hours` (day length)
- `is_tidally_locked` (boolean)

**Orbital zone properties** (CRITICAL for Controllers - both Planet and Moon need these):
- `min_orbit_altitude_km` - Minimum safe orbit (atmosphere + safety margin)
- `low_orbit_altitude_km` - Typical LEO equivalent (e.g., 150-400km for Earth)
- `geostationary_orbit_altitude_km` - GEO altitude (calculated from rotation period)
- `hill_sphere_radius_km` - Maximum stable orbit distance

**Methods**:
- `get_orbital_speed()` - Mean orbital velocity
- `get_synodic_period(other_body)` - Relative orbital period
- `is_in_hill_sphere(distance_km)` - Check if object is within stable orbit range
- `calculate_orbital_zones()` - Compute all altitude zones (for both Planet and Moon)
- `get_orbital_speed_at_altitude(altitude_km)` - Speed for circular orbit at given altitude
- `get_plane_change_delta_v(inclination_change_deg, altitude_km)` - Delta-V for plane change
- `get_geostationary_altitude()` - Calculate GEO altitude from rotation period
- `has_atmosphere() -> bool` - Check if atmosphere relationship exists
- `get_atmospheric_density(altitude_km) -> Optional[float]` - Get atmospheric density if atmosphere exists, else None

### 1.3 Optional Atmosphere Model (Separate Table)
**File**: `mysite/universe/models/physics.py` (new)

Create `Atmosphere` concrete Django model (separate table):
- `atmosphere_type` (enum: CO2_Thin, CO2_Thick, N2_O2, H2_He, N2_CH4, SO2, etc.)
- `atmosphere_height_km`
- `surface_pressure_bar`
- `scale_height_km` (atmospheric density falloff)
- Note: Relationship to Planet/Moon is via OneToOneField on Planet/Moon side (see Relationship Pattern below)

**Why Separate Table?**
- Most moons have no atmosphere (saves space in Planet/Moon tables)
- Only create `Atmosphere` records when needed
- Clean separation: "Does this body have an atmosphere?" → check if `atmosphere` relationship exists

**Relationship Pattern**:
Since `OrbitalBody` is abstract, we can't use a direct OneToOne to it. Instead:
- `Planet` has: `atmosphere = OneToOneField(Atmosphere, null=True, blank=True, related_name='planet')`
- `Moon` has: `atmosphere = OneToOneField(Atmosphere, null=True, blank=True, related_name='moon')`
- `Atmosphere` model doesn't need a reverse FK - it can use `related_name` to find its parent
- Alternative: Use `GenericForeignKey` with ContentType for a single relationship pattern

**Methods**:
- `get_atmospheric_density(altitude_km)` - Density at given altitude
- `get_drag_coefficient(altitude_km)` - For reentry calculations
- `get_parent_body()` - Return the Planet or Moon this atmosphere belongs to (via related_name)

**Usage Pattern**:
```python
# Check if planet has atmosphere
if planet.atmosphere:
    density = planet.atmosphere.get_atmospheric_density(100)  # 100km altitude
else:
    # No atmosphere - no drag, no reentry heating, etc.
    pass

# Query planets with atmospheres
planets_with_atmosphere = Planet.objects.filter(atmosphere__isnull=False)

# From Atmosphere, find parent (if using related_name)
atmosphere = Atmosphere.objects.first()
parent = atmosphere.planet or atmosphere.moon  # One will be set
```

---

## Phase 2: Refactor Existing Models

### 2.1 Star Model
**File**: `mysite/universe/models/celestial.py`

**Inherit from**: `PhysicalBody` (which inherits from `Celestial` → `Location`)

**Star-specific properties**:
- `star_type` (O, B, A, F, G, K, M, N) - Keep existing
- `star_magnitude` - Keep existing
- `temperature_k` - Add (derived from star_type via lookup table)
- `luminosity_solar` - Add (derived from star_type)
- `habitable_zone_inner_au` - Add (calculated from luminosity)
- `habitable_zone_outer_au` - Add (calculated from luminosity)
- `color_hex` - Add (for rendering, derived from temperature)

**Methods**:
- `calculate_habitable_zone()` - Compute inner/outer edges
- `get_effective_temperature(distance_au)` - Temperature at given distance

### 2.2 OrbitalBody Abstract Base Model (Shared by Planet and Moon)
**File**: `mysite/universe/models/physics.py` (new)

**Inherit from**: `PhysicalBody` (which inherits from `Celestial` → `Location`)

**Purpose**: Planet and Moon both orbit something, so they share orbital properties. This is the common parent for both.

### 2.3 Planet Model
**File**: `mysite/universe/models/celestial.py`

**Inherit from**: `OrbitalBody` (which inherits from `PhysicalBody` → `Celestial` → `Location`)

**Planet-specific properties**:
- `planet_type` - Keep existing enum
- `iron_content` - Add (for visual/composition)
- `color_palette` - Add (JSON array of hex colors)
- `pattern_type` - Add (Uniform, Banded, Splotched, Swirled)

**Planet-specific methods**:
- None (all orbital zone methods are inherited from OrbitalBody)

### 2.4 Moon Model
**File**: `mysite/universe/models/celestial.py`

**Inherit from**: `OrbitalBody` (same parent as Planet - they're both orbital bodies!)

**Moon-specific properties**:
- `variety` - Keep existing (Rocky, Icy, Organic, Terrestrial)
- `orbital_distance_km` - Distance from parent planet (not AU)
- Simplified atmosphere (most have none)

**Methods**:
- `get_parent_planet()` - Return the Planet this moon orbits
- `get_orbital_speed_around_parent()` - Speed relative to parent

---

## Phase 3: Physics Lookup Tables

### 3.1 Star Properties Table
**File**: `mysite/universe/data/star_properties.py` (new)

**Structure**: Dictionary mapping star types to physical properties

```python
STAR_PROPERTIES = {
    'O': {
        'mass_solar': (15.0, 90.0),  # Range for procedural generation
        'radius_solar': (6.6, 10.0),
        'temperature_k': (30000, 50000),
        'luminosity_solar': (30000, 1000000),
        'lifetime_years': (1e6, 10e6),
        'color_hex': '#9BB0FF',
    },
    'G': {
        'mass_solar': (0.8, 1.1),
        'radius_solar': (0.96, 1.15),
        'temperature_k': (5200, 6000),
        'luminosity_solar': (0.6, 1.5),
        'lifetime_years': (1e10, 1e11),
        'color_hex': '#FFF4EA',
    },
    # ... etc for all types
}
```

**Usage**: When creating/updating a Star, use this table to populate physical properties based on `star_type`.

### 3.2 Planet Properties Table
**File**: `mysite/universe/data/planet_properties.py` (new)

**Structure**: Dictionary mapping planet types to typical properties

```python
PLANET_PROPERTIES = {
    'TE': {  # Terrestrial
        'mass_earth': (0.1, 2.0),
        'radius_earth': (0.5, 1.5),
        'density_kg_m3': (4000, 5500),
        'typical_atmosphere': 'N2_O2',
        'typical_albedo': (0.2, 0.4),
    },
    'GG': {  # Gas Giant
        'mass_earth': (10.0, 300.0),
        'radius_earth': (3.0, 15.0),
        'density_kg_m3': (500, 2000),
        'typical_atmosphere': 'H2_HE',
        'typical_albedo': (0.3, 0.6),
    },
    # ... etc
}
```

**Usage**: When creating/updating a Planet, use this table + orbital distance to populate properties.

### 3.3 Orbital Mechanics Constants
**File**: `mysite/universe/data/constants.py` (new)

**Structure**: Physical constants for calculations

```python
G = 6.67430e-11  # Gravitational constant (m³/kg/s²)
SOLAR_MASS_KG = 1.989e30
EARTH_MASS_KG = 5.972e24
EARTH_RADIUS_KM = 6371.0
AU_TO_KM = 1.496e8
```

---

## Phase 4: Controller Access API

### 4.1 Orbital Parameters Service
**File**: `mysite/universe/services/orbital_physics.py` (new)

**Purpose**: Provide clean API for Controllers to query orbital parameters

**Key Methods**:

```python
class OrbitalPhysicsService:
    @staticmethod
    def get_orbital_altitudes(planet: Planet) -> Dict[str, float]:
        """Return all orbital altitude zones for a planet."""
        return {
            'min_safe': planet.min_orbit_altitude_km,
            'low_orbit': planet.low_orbit_altitude_km,
            'geostationary': planet.geostationary_orbit_altitude_km,
            'hill_sphere': planet.hill_sphere_radius_km,
        }
    
    @staticmethod
    def get_orbital_speed(planet: Planet, altitude_km: float) -> float:
        """Calculate orbital speed at given altitude."""
        return planet.get_orbital_speed_at_altitude(altitude_km)
    
    @staticmethod
    def get_plane_change_requirements(
        planet: Planet,
        current_inclination_deg: float,
        target_inclination_deg: float,
        altitude_km: float
    ) -> Dict[str, float]:
        """Calculate delta-V and burn duration for plane change."""
        delta_v = planet.get_plane_change_delta_v(
            abs(target_inclination_deg - current_inclination_deg),
            altitude_km
        )
        return {
            'delta_v_ms': delta_v,
            'inclination_change_deg': abs(target_inclination_deg - current_inclination_deg),
            'estimated_burn_duration_sec': delta_v / 9.81,  # Rough estimate
        }
    
    @staticmethod
    def get_axial_tilt(planet: Planet) -> float:
        """Get planet's axial tilt (needed for plane change calculations)."""
        return planet.axial_tilt_deg
    
    @staticmethod
    def get_rotation_period(planet: Planet) -> float:
        """Get planet's rotation period (for geostationary calculations)."""
        return planet.rotation_period_hours
```

### 4.2 Integration with Dialogue System
**File**: `mysite/universe/services/dialogue/particles.py`

**Update**: `CircularizationRequest`, `InsertionRequest`, etc. to use `OrbitalPhysicsService` to get realistic altitude values from `nav_context['destination']` (which is a Planet/Moon object).

**Example**:
```python
# In CircularizationRequest.get_examples()
destination = self.nav_context.get("destination")
if isinstance(destination, Planet):
    altitudes = OrbitalPhysicsService.get_orbital_altitudes(destination)
    altitude_km = altitudes['low_orbit']  # Use realistic value
```

---

## Phase 5: Database Migrations

### 5.1 Add Physical Properties to Star
- `mass_solar`, `radius_solar`, `temperature_k`, `luminosity_solar`
- `habitable_zone_inner_au`, `habitable_zone_outer_au`
- `color_hex`

### 5.2 Add Physical Properties to Planet
- All `Celestial` fields (inherited from Location)
- All `PhysicalBody` fields (inherited) - includes mass, radius, etc.
- All `OrbitalBody` fields (inherited, including `axial_tilt_deg` - CRITICAL)
- All orbital zone fields (inherited from OrbitalBody): `min_orbit_altitude_km`, `low_orbit_altitude_km`, `geostationary_orbit_altitude_km`, `hill_sphere_radius_km`
- Visual properties: `iron_content`, `color_palette`, `pattern_type`
- `atmosphere` - OneToOneField to `Atmosphere` model (optional, null=True)

### 5.3 Add Physical Properties to Moon
- All `Celestial` fields (inherited from Location)
- All `PhysicalBody` fields (inherited) - includes mass, radius, etc.
- All `OrbitalBody` fields (inherited) - includes all orbital properties
- All orbital zone fields (inherited from OrbitalBody): `min_orbit_altitude_km`, `low_orbit_altitude_km`, `geostationary_orbit_altitude_km`, `hill_sphere_radius_km`
- `atmosphere` - OneToOneField to `Atmosphere` model (optional, null=True)
- Note: Most moons won't have an atmosphere, so this will be None for most

### 5.4 Create Atmosphere Table
- Separate `Atmosphere` model with its own table
- OneToOne relationship to `OrbitalBody` (via ContentType or direct FK to Planet/Moon)
- Only create `Atmosphere` records when a body actually has an atmosphere

---

## Phase 6: Procedural Generation

### 6.1 Star Generation
**File**: `mysite/universe/services/celestial_generator.py` (new)

**Method**: `generate_star_properties(star_type: str) -> Dict`
- Look up `star_type` in `STAR_PROPERTIES`
- Generate random values within ranges
- Calculate derived properties (habitable zone, etc.)
- Return dict for model population

### 6.2 Planet Generation
**File**: `mysite/universe/services/celestial_generator.py` (new)

**Method**: `generate_planet_properties(planet_type: str, orbital_distance_au: float, parent_star: Star) -> Dict`
- Look up `planet_type` in `PLANET_PROPERTIES`
- Generate mass/radius within ranges
- Calculate density from mass/radius
- Calculate surface gravity
- Calculate equilibrium temperature from star distance
- Calculate orbital zones
- Return dict for model population

### 6.3 Moon Generation
**File**: `mysite/universe/services/celestial_generator.py` (new)

**Method**: `generate_moon_properties(variety: str, parent_planet: Planet) -> Dict`
- Similar to planet but simpler
- Use parent planet's properties to constrain generation

---

## Phase 7: XML Import/Export Updates

### 7.1 Update XML Schema
**File**: `xml/test_universe.xml` (or schema definition)

**Add fields**:
- Physical properties (mass, radius, etc.)
- Orbital properties (inclination, eccentricity, axial tilt)
- Atmospheric properties
- Orbital zones (or calculate on import)

### 7.2 Update Importer
**File**: `mysite/universe/import_xml.py`

**Update**: `import_planet()`, `import_star()`, `import_moon()` to:
- Read new XML fields
- Populate physical properties
- Calculate derived properties if not provided
- Use procedural generation for missing values

---

## Implementation Order

1. **Phase 1**: Create abstract base models (foundation)
2. **Phase 3**: Create lookup tables (data source)
3. **Phase 2**: Refactor models to use mixins (structure)
4. **Phase 5**: Database migrations (persistence)
5. **Phase 4**: Controller access API (usage)
6. **Phase 6**: Procedural generation (automation)
7. **Phase 7**: XML updates (data import)

---

## Key Design Decisions

### Why Abstract Base Models Instead of Mixins or ABCs?

**ABCs (Abstract Base Classes)**:
- Python's `abc.ABC` is for defining interfaces/contracts
- Good for: "This class must implement these methods"
- Bad for Django models: Can't define model fields, no database table
- Example: `Event` class in `event.py` uses ABC because it's a dataclass, not a model

**Mixins**:
- Regular Python classes designed to be inherited alongside other classes
- Good for: Adding methods/functionality without creating a database table
- Problem: Can't easily share Django model fields (you'd need to duplicate field definitions)
- Example: If we had utility methods only (no fields), mixins would work

**Abstract Base Models (Django's `Meta.abstract = True`)**:
- Django models that don't create their own database table
- Good for: Sharing model fields AND methods across multiple models
- Perfect for: Our use case - we want to share fields (mass, radius, etc.) AND methods
- Example: `Location` is already a concrete model, but we can create abstract models that inherit from it

**Why Abstract Base Models Win Here**:
1. **Share fields**: All physical properties (mass, radius, etc.) are Django model fields - abstract models let us define them once
2. **Share methods**: Calculation methods can live on the abstract base
3. **Database efficiency**: Django's multi-table inheritance handles this efficiently
4. **Type safety**: Full Django ORM support, migrations work correctly
5. **Inheritance chain**: `Location` → `PhysicalBody` → `OrbitalBody` → `AtmosphericBody` → `Planet`/`Moon`

**The Inheritance Chain**:
```
Location (concrete - has table)
  └── Celestial (abstract - no table, top-level for all celestial bodies)
      └── PhysicalBody (abstract - no table, adds mass/radius fields)
          └── OrbitalBody (abstract - no table, adds orbital fields)
              └── Planet (concrete - has table with physical + orbital fields)
                  └── atmosphere (OneToOne to Atmosphere model - optional!)
              └── Moon (concrete - has table with physical + orbital fields)
                  └── atmosphere (OneToOne to Atmosphere model - optional!)
          └── Star (concrete - has physical properties but no orbital/atmosphere)
```

**Atmosphere is Optional**:
```
Atmosphere (concrete - separate table)
  └── OneToOne relationship to Planet or Moon (null=True, blank=True)
      - Only created if the body has an atmosphere
      - Query: `planet.atmosphere` returns None if no atmosphere
      - Query: `Planet.objects.filter(atmosphere__isnull=False)` finds planets with atmospheres
```

### Where to Store Lookup Tables?
- **Option A**: Python files in `mysite/universe/data/` (current plan)
  - Pros: Easy to edit, version controlled, no DB overhead
  - Cons: Requires code changes to update
  
- **Option B**: JSON/YAML files in `data/` directory
  - Pros: Non-programmers can edit, easier to version
  - Cons: Need parsing, validation
  
- **Option C**: Django models (database tables)
  - Pros: Can be edited via admin, queryable
  - Cons: Overhead, harder to version control

**Recommendation**: Start with Option A (Python files), migrate to Option B (YAML) if we need non-programmer editing.

### Calculation vs. Storage
- **Store**: Mass, radius, orbital distance (fundamental properties)
- **Calculate**: Surface gravity, orbital speed, habitable zone (derived properties)
- **Hybrid**: Orbital zones (calculate once, store for performance)

### Controller Access Pattern
- Controllers should access via `OrbitalPhysicsService`, not directly on models
- This provides:
  - Consistent API
  - Caching opportunities
  - Unit conversion
  - Error handling

---

## Testing Strategy

1. **Unit Tests**: Physics calculations (orbital speed, delta-V, etc.)
2. **Integration Tests**: Controller queries orbital parameters for dialogue
3. **Data Tests**: Lookup tables have valid ranges, no missing keys
4. **Migration Tests**: Existing data survives migration, new fields populated

---

## Future Enhancements (Out of Scope for Now)

- Lagrange point calculations
- Tidal heating calculations
- Atmospheric composition details (percentages of gases)
- Geological features (volcanoes, craters, etc.)
- Resource distribution maps
- Climate zones (for habitable planets)

## Sequential Dependencies 

### Star Generation 

1. **Star type** (random weighted draw: O/B/A/F/G/K/M)
2. **Star mass** = f(type)
3. **Star radius** = f(type)
4. N/A 
5. N/A 
6. N/A 
7. N/A 
8. N/A 
9. N/A
10. **Color** = f(temperature) for stars - store in a palette table with main color, palette colors, and pattern (Swirl, spots, etc.) 

### Planet Generation (per planet)

11. **Orbital distance** (random with spacing constraints, measured in AU?)
12. **Planet type** = f(orbital_distance, star_type)
13. **Density** = f(planet_type) [small random range]
14. **Radius** = f(planet_type) [random in range]
15. **Mass** = f(density, radius) [= (4/3)πR³ρ]
16. **Orbital period** = f(orbital_distance, star_mass) [Kepler's 3rd law]
17. N/A 
18. **Rotation period** = f(planet_type, orbital_distance) [check tidal locking]
19. **Is tidally locked** = f(orbital_distance, star_mass, planet_mass) [if very close]
20. **Axial tilt** = f(planet_type, is_tidally_locked) [0° if locked, else random]
21. **Surface gravity** = f(mass, radius) [= GM/R²] 

22. **Has Atmosphere** (True / False)
23. **Atmosphere type** = f(planet_type, mass, orbital_distance, star_type)
24. **Mean molecular mass** = f(atmosphere_type)
25. **Albedo** = f(planet_type, atmosphere_type)
26. **Equilibrium temperature** = f(star_luminosity, orbital_distance, albedo)
27. **Iron content** = f(planet_type) [for rocky planets only]
28. **Surface pressure** = f(atmosphere_type, mass) [if atmosphere exists]
29. **Scale height** = f(temperature, mean_molecular_mass, surface_gravity) [if atmosphere]
30. **Atmosphere height** = f(scale_height) [= 7-10 × scale_height]

31. **Min orbit altitude** = f(atmosphere_height) [= atmosphere_top + 100km]
32. **Low orbit altitude** = f(min_orbit_altitude) [= min + 200-500km]
33. **Geostationary orbit altitude** = f(mass, rotation_period) [= ∛(GMT²/4π²) - R]
34. **Hill sphere radius** = f(orbital_distance, planet_mass, star_mass)
35. **Color** = f(planet_type, atmosphere_type, iron_content, temperature)
36. **Pattern type** = f(planet_type, atmosphere_type)

### Moon Generation (per moon, optional)

36. **Should have moons?** = f(planet_type, planet_mass)
37. **Number of moons** = f(planet_type, planet_mass)

**Per individual moon:**

38. **Orbital distance from planet** (random with spacing)
39. **Moon variety** = f(planet_type, orbital_distance_from_star) [Rocky/Icy/Organic/Terrestrial]
40. **Density** = f(moon_variety)
41. **Radius** = f(moon_variety) [random in range, smaller than planet]
42. **Mass** = f(density, radius)
43. **Orbital period around planet** = f(orbital_distance, planet_mass)
44. **Is tidally locked** = True [almost always for moons]
45. **Rotation period** = orbital_period [if locked]
46. **Axial tilt** = 0° [if locked]
47. **Surface gravity** = f(mass, radius)

48. **Has atmosphere?** = f(moon_variety, mass) [usually false]
49. **Atmosphere type** = f(moon_variety) [if has_atmosphere]
50. **Albedo** = f(moon_variety, has_atmosphere, ice_content)
51. **Temperature** = f(star_luminosity, orbital_distance_from_star, albedo)
52. **Ice content** = f(moon_variety, temperature)
53. **Atmosphere height** = f(atmosphere_type, surface_gravity) [if has_atmosphere]
54. **Min orbit altitude** = f(atmosphere_height or radius)
55. **Low orbit altitude** = f(min_orbit_altitude)
56. **Hill sphere radius** = f(orbital_distance_from_planet, moon_mass, planet_mass)
57. **Color palette** = f(moon_variety, ice_content, temperature)
58. **Pattern type** = f(moon_variety)

---

## Key Dependency Clusters

**Chain 1 (Mass/Gravity):** Type → Density & Radius → Mass → Surface Gravity

**Chain 2 (Thermal):** Star Luminosity + Orbital Distance + Albedo → Temperature

**Chain 3 (Atmosphere):** Type + Mass + Distance → Atmosphere Type → Molecular Mass + Pressure → Scale Height → Atmosphere Top

**Chain 4 (Orbits):** Mass + Rotation Period → Geostationary; Atmosphere Top → Min Orbit

**Chain 5 (Tidal Locking):** Orbital Distance + Masses → Is Locked → Rotation Period & Axial Tilt

This sequence ensures each variable is calculated only after all its dependencies are known!