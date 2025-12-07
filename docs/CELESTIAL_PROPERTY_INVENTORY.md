# Celestial Model Property Inventory

## Inheritance Hierarchy

```
Location (concrete)
  └── Celestial (abstract)
      └── PhysicalBody (abstract)
          └── OrbitalBody (abstract)
              └── Planet (concrete)
              └── Moon (concrete)
          └── Star (concrete)
```

---

## Level 1: Location (Concrete Model)
**File**: `mysite/universe/models/base.py` (already exists)

**Properties**:
- `name` - CharField(max_length=255)
- `scale` - CharField (GALAXY, STARSYSTEM, STAR, PLANET, MOON, STATION)

**Methods** (already exist):
- `get_concrete_instance()`
- `get_type_name()`

**Notes**: This is the base for ALL locations (celestial bodies, stations, etc.)

---

## Level 2: Celestial (Abstract Base Model)
**File**: `mysite/universe/models/physics.py` (new)

**Purpose**: Top-level class for all celestial bodies (Star, Planet, Moon)

**Properties**:
- None currently - all celestial-specific properties are in PhysicalBody or below
- **Future consideration**: Could add common celestial properties here if needed (e.g., discovery_date, catalog_number)

**Methods**:
- None currently

**Notes**: 
- This level exists primarily for organizational clarity
- If we find properties common to ALL celestial bodies (not just physical ones), they go here
- Currently serves as a semantic marker: "this is a celestial body, not a station"

---

## Level 3: PhysicalBody (Abstract Base Model)
**File**: `mysite/universe/models/physics.py` (new)

**Purpose**: All celestial bodies have mass, radius, and physical properties

**Properties**:
- `mass_kg` - FloatField (null=True, blank=True)
- `mass_solar` - FloatField (null=True, blank=True) - Alternative unit, calculated from mass_kg
- `radius_km` - FloatField (null=True, blank=True)
- `radius_solar` - FloatField (null=True, blank=True) - Alternative unit, calculated from radius_km
- `density_kg_m3` - FloatField (null=True, blank=True) - Can be calculated from mass/radius
- `surface_gravity_ms2` - FloatField (null=True, blank=True) - Can be calculated from mass/radius
- `albedo` - FloatField (null=True, blank=True, help_text="Bond albedo 0.0-1.0")
- `equilibrium_temperature_k` - FloatField (null=True, blank=True) - Calculated from star distance/albedo

**Methods**:
- `get_orbital_velocity(altitude_km: float) -> float` - Calculate orbital speed at given altitude
- `get_escape_velocity() -> float` - Calculate escape velocity
- `get_surface_gravity() -> float` - Calculate surface gravity (if not stored)
- `convert_mass_to_solar() -> float` - Convert mass_kg to solar masses
- `convert_radius_to_solar() -> float` - Convert radius_km to solar radii

**Inherited by**: Star, OrbitalBody (which Planet/Moon inherit from)

---

## Level 4: OrbitalBody (Abstract Base Model)
**File**: `mysite/universe/models/physics.py` (new)

**Purpose**: Bodies that orbit something (Planets orbit Stars, Moons orbit Planets)

**Properties**:
- `orbital_distance_au` - FloatField (null=True, blank=True) - Semi-major axis in AU
- `orbital_distance_km` - FloatField (null=True, blank=True) - Alternative unit, calculated from AU
- `orbital_period_days` - FloatField (null=True, blank=True) - Orbital period in Earth days
- `orbital_period_hours` - FloatField (null=True, blank=True) - Alternative unit, calculated from days
- `orbital_eccentricity` - FloatField (default=0.0, help_text="0.0=circular, 0.0-1.0=elliptical")
- `orbital_inclination_deg` - FloatField (null=True, blank=True, help_text="Tilt relative to reference plane")
- `axial_tilt_deg` - FloatField (null=True, blank=True, help_text="CRITICAL: Rotation axis tilt for plane change calculations")
- `rotation_period_hours` - FloatField (null=True, blank=True, help_text="Day length")
- `is_tidally_locked` - BooleanField (default=False)

**Orbital Zone Properties** (CRITICAL for Controllers - both Planet and Moon need these):
- `min_orbit_altitude_km` - FloatField (null=True, blank=True, help_text="Minimum safe orbit (atmosphere + safety margin)")
- `low_orbit_altitude_km` - FloatField (null=True, blank=True, help_text="Typical LEO equivalent (e.g., 150-400km for Earth)")
- `geostationary_orbit_altitude_km` - FloatField (null=True, blank=True, help_text="GEO altitude (calculated from rotation period)")
- `hill_sphere_radius_km` - FloatField (null=True, blank=True, help_text="Maximum stable orbit distance")

**Methods**:
- `get_orbital_speed() -> float` - Mean orbital velocity
- `get_synodic_period(other_body: OrbitalBody) -> float` - Relative orbital period
- `is_in_hill_sphere(distance_km: float) -> bool` - Check if object is within stable orbit range
- `convert_orbital_distance_to_km() -> float` - Convert AU to km
- `convert_orbital_period_to_hours() -> float` - Convert days to hours
- `calculate_orbital_zones() -> Dict[str, float]` - Compute all altitude zones (for both Planet and Moon)
- `get_orbital_speed_at_altitude(altitude_km: float) -> float` - Speed for circular orbit at given altitude
- `get_plane_change_delta_v(inclination_change_deg: float, altitude_km: float) -> float` - Delta-V for plane change
- `get_geostationary_altitude() -> float` - Calculate GEO altitude from rotation period
- `has_atmosphere() -> bool` - Check if atmosphere relationship exists
- `get_atmospheric_density(altitude_km: float) -> Optional[float]` - Get atmospheric density if atmosphere exists, else None

**Inherited by**: Planet, Moon

**Notes**: 
- Star does NOT inherit from this (stars are orbited, they don't orbit)
- `axial_tilt_deg` is CRITICAL for plane change maneuver calculations

---

## Level 5a: Star (Concrete Model)
**File**: `mysite/universe/models/celestial.py`

**Inherits from**: PhysicalBody → Celestial → Location

**Star-Specific Properties**:
- `orbits` - ForeignKey(StarSystem) - Keep existing
- `star_type` - CharField(max_length=10, default="G2V") - Keep existing
- `star_magnitude` - DecimalField(max_digits=8, decimal_places=2, default=4.31) - Keep existing
- `temperature_k` - FloatField (null=True, blank=True) - Derived from star_type via lookup table
- `luminosity_solar` - FloatField (null=True, blank=True) - Derived from star_type via lookup table
- `habitable_zone_inner_au` - FloatField (null=True, blank=True) - Calculated from luminosity
- `habitable_zone_outer_au` - FloatField (null=True, blank=True) - Calculated from luminosity
- `color_hex` - CharField(max_length=7, default="#FFFF00") - For rendering, derived from temperature

**Methods**:
- `calculate_habitable_zone() -> Dict[str, float]` - Compute inner/outer edges
- `get_effective_temperature(distance_au: float) -> float` - Temperature at given distance from star

**Inherited Properties** (from PhysicalBody):
- mass_kg, mass_solar
- radius_km, radius_solar
- density_kg_m3
- surface_gravity_ms2
- albedo
- equilibrium_temperature_k

**Does NOT have**:
- Orbital properties (stars don't orbit)
- Atmosphere (stars are plasma, not gas)

---

## Level 5b: Planet (Concrete Model)
**File**: `mysite/universe/models/celestial.py`

**Inherits from**: OrbitalBody → PhysicalBody → Celestial → Location

**Planet-Specific Properties**:
- `orbits` - ForeignKey(Star) - Keep existing
- `planet_type` - CharField (choices: MESOPLANET, SILICATE, TERRESTRIAL, SUPEREARTH, CTHONIAN, ICEGIANT, GASGIANT, ASTEROIDBELT) - Keep existing
- `iron_content` - FloatField (default=0.3, null=True, blank=True, help_text="Iron content fraction 0.0-1.0")
- `color_palette` - JSONField (default=list, blank=True, help_text="List of hex colors for rendering")
- `pattern_type` - CharField (choices: UNIFORM, BANDED, SPLOTCHED, SWIRLED, default='UNIFORM')

**Atmosphere Relationship**:
- `atmosphere` - OneToOneField(Atmosphere, null=True, blank=True, related_name='planet')

**Methods**:
- None planet-specific (all orbital zone methods are inherited from OrbitalBody)

**Inherited Properties** (from OrbitalBody):
- orbital_distance_au, orbital_distance_km
- orbital_period_days, orbital_period_hours
- orbital_eccentricity
- orbital_inclination_deg
- axial_tilt_deg (CRITICAL for plane changes)
- rotation_period_hours
- is_tidally_locked

**Inherited Properties** (from PhysicalBody):
- mass_kg, mass_solar
- radius_km, radius_solar
- density_kg_m3
- surface_gravity_ms2
- albedo
- equilibrium_temperature_k

---

## Level 5c: Moon (Concrete Model)
**File**: `mysite/universe/models/celestial.py`

**Inherits from**: OrbitalBody → PhysicalBody → Celestial → Location

**Moon-Specific Properties**:
- `orbits` - ForeignKey(Location) - Keep existing (can orbit Planet or another Moon)
- `variety` - CharField (choices: R=Rocky, I=Icy, O=Organic, T=Terrestrial, default='R') - Keep existing

**Atmosphere Relationship**:
- `atmosphere` - OneToOneField(Atmosphere, null=True, blank=True, related_name='moon')

**Methods**:
- `get_parent_planet() -> Optional[Planet]` - Return the Planet this moon orbits (if applicable)
- `get_orbital_speed_around_parent() -> float` - Speed relative to parent body

**Inherited Properties** (from OrbitalBody):
- Same as Planet (all orbital properties, including orbital zones)

**Inherited Properties** (from PhysicalBody):
- Same as Planet (all physical properties)

**Notes**:
- Most moons won't have an atmosphere (atmosphere relationship will be None)
- Moons have the same orbital zone properties as planets (inherited from OrbitalBody)
- Both Planet and Moon can be orbited, so both need orbital zone calculations for traffic control

---

## Level 6: Atmosphere (Concrete Model - Separate Table)
**File**: `mysite/universe/models/physics.py` (new)

**Purpose**: Optional atmospheric properties for Planets and Moons

**Properties**:
- `atmosphere_type` - CharField (choices: CO2_ThIN, CO2_THICK, N2_O2, H2_HE, N2_CH4, SO2, etc.)
- `atmosphere_height_km` - FloatField (null=True, blank=True, help_text="Height of atmosphere above surface")
- `surface_pressure_bar` - FloatField (null=True, blank=True, help_text="Surface pressure in bars")
- `scale_height_km` - FloatField (null=True, blank=True, help_text="Atmospheric scale height (density falloff)")

**Relationships**:
- Relationship to Planet/Moon is via OneToOneField on Planet/Moon side (not here)
- Access via: `atmosphere.planet` or `atmosphere.moon` (via related_name)

**Methods**:
- `get_atmospheric_density(altitude_km: float) -> float` - Density at given altitude
- `get_drag_coefficient(altitude_km: float) -> float` - For reentry calculations
- `get_parent_body() -> Union[Planet, Moon]` - Return the Planet or Moon this atmosphere belongs to

**Notes**:
- Only created when a Planet/Moon actually has an atmosphere
- Most moons will not have an Atmosphere record
- Some planets (gas giants) will always have one
- Some planets (rocky, no atmosphere) will not have one

---

## Summary by Property Type

### Physical Properties (PhysicalBody level)
- Mass: `mass_kg`, `mass_solar`
- Size: `radius_km`, `radius_solar`
- Density: `density_kg_m3`
- Gravity: `surface_gravity_ms2`
- Thermal: `albedo`, `equilibrium_temperature_k`

### Orbital Properties (OrbitalBody level)
- Distance: `orbital_distance_au`, `orbital_distance_km`
- Period: `orbital_period_days`, `orbital_period_hours`
- Shape: `orbital_eccentricity`
- Orientation: `orbital_inclination_deg`, `axial_tilt_deg`
- Rotation: `rotation_period_hours`, `is_tidally_locked`

### Atmospheric Properties (Atmosphere model - optional)
- Type: `atmosphere_type`
- Extent: `atmosphere_height_km`
- Pressure: `surface_pressure_bar`
- Structure: `scale_height_km`

### Star-Specific Properties
- Classification: `star_type`, `star_magnitude`
- Physical: `temperature_k`, `luminosity_solar`
- Habitability: `habitable_zone_inner_au`, `habitable_zone_outer_au`
- Visual: `color_hex`

### Planet-Specific Properties
- Classification: `planet_type`
- Visual: `iron_content`,`color_palette`, `pattern_type`
- Atmosphere: `atmosphere` (OneToOne relationship)

### Orbital Zone Properties (OrbitalBody level - shared by Planet and Moon)
- `min_orbit_altitude_km` - Minimum safe orbit
- `low_orbit_altitude_km` - Typical LEO equivalent
- `geostationary_orbit_altitude_km` - GEO altitude
- `hill_sphere_radius_km` - Maximum stable orbit

### Moon-Specific Properties
- Classification: `variety`
- Atmosphere: `atmosphere` (OneToOne relationship)

---

## Design Decisions

### Why Celestial Level Exists
- Currently empty, but provides semantic clarity
- Future: Could add properties common to ALL celestial bodies (discovery info, catalog numbers, etc.)
- Makes the hierarchy clear: "This is a celestial body, not a station"

### Why PhysicalBody is Separate from OrbitalBody
- Star has physical properties but NO orbital properties
- Planet and Moon have BOTH physical AND orbital properties
- This separation prevents Star from inheriting unnecessary orbital fields

### Why Atmosphere is Separate Table
- Most moons have no atmosphere → saves space
- Only create records when needed
- Clean queries: `Planet.objects.filter(atmosphere__isnull=False)`
- Natural Python check: `if planet.atmosphere:`

### Why Orbital Zones are on OrbitalBody (not Planet-specific)
- Both Planet and Moon can be orbited by spacecraft/stations
- Both need orbital zone calculations for traffic control and navigation planning
- Controllers need to know safe altitudes for both planets and moons
- Placing them on OrbitalBody ensures both Planet and Moon inherit them

---

## Migration Strategy

1. Create abstract base models (Celestial, PhysicalBody, OrbitalBody)
2. Create Atmosphere model (separate table)
3. Migrate Star to inherit from PhysicalBody
4. Migrate Planet to inherit from OrbitalBody, add orbital zone fields, add atmosphere relationship
5. Migrate Moon to inherit from OrbitalBody, add atmosphere relationship
6. Populate physical properties from lookup tables
7. Calculate derived properties (orbital zones, habitable zones, etc.)

