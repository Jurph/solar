# Station Orbital Positioning

## Overview

Stations need an orbital distance (altitude) from their parent body (Planet or Moon). Unlike celestial bodies, stations don't need mass, radius, or other physical properties - just orbital positioning.

## Orbital Distance Property

**Field**: `orbital_distance_km` - FloatField
- Distance from surface of parent body in kilometers
- In current code, this is stored on `Station` and imported from XML when present
- The decision tree below is a *design* for auto-calculation; it is not fully implemented as a single authoritative placement routine yet

## Current Implementation Status (late Dec 2025)

- ✅ `Station.orbital_distance_km` exists (`mysite/universe/models/station.py`)
- ✅ XML import reads `<station><orbital_distance_km>...</orbital_distance_km></station>` (`mysite/universe/import_xml.py`)
- ❌ `orbit_type` is not implemented as a model field
- ⚠️ Some code paths still contain estimation fallbacks when station orbital altitude is missing; the long-term intent is to have station orbital altitudes explicitly set (especially in test universes)

## Decision Tree for Auto-Calculating Station Orbits

When generating a station's orbital position, follow this priority order:

### 1. Geostationary Orbit (Preferred)
**Condition**: `geostationary_orbit_altitude_km` exists AND is within `hill_sphere_radius_km`

**Calculation**: 
- Use `parent_body.geostationary_orbit_altitude_km`
- Round to nearest 1000 km
- Example: 35,786 km → 36,000 km

**Why**: Geostationary orbits are stable and useful for communication/control stations

### 2. Half-Geostationary Orbit (If geo is outside Hill sphere)
**Condition**: `geostationary_orbit_altitude_km` exists BUT is outside `hill_sphere_radius_km`

**Calculation**: 
- Use `parent_body.geostationary_orbit_altitude_km * 0.5`
- Round to nearest 1000 km
- Example: If geo is 71,572 km → half-geo is 35,786 km → 36,000 km

**Why**: Half-geo gives a half-day orbital period (like GPS satellites), useful for navigation/communication

### 3. L4 Lagrange Point (If planet has moons)
**Condition**: Parent body is a Planet AND has at least one moon

**Calculation**:
- Find the most massive moon: `max(planet.moons.all(), key=lambda m: m.mass_kg)`
- Calculate L4 distance: Distance from planet center ≈ same as moon's orbital distance
- More precisely: L4 is 60° ahead of the moon in its orbit

**Why**: L4 (and L5) are stable Lagrange points, perfect for stations

**Note**: L5 is also stable (60° behind moon), could be an option for multiple stations

### 4. Low Orbit (Fallback)
**Condition**: If half-Hill-sphere is too far or unavailable

**Calculation**:
- Use `parent_body.low_orbit_altitude_km` if available
- Otherwise use `parent_body.min_orbit_altitude_km + 200` (safety margin)

**Why**: Lower altitude, easier to reach, but requires more station-keeping

### 5. Custom/Manual (Override)
**Condition**: User explicitly specifies `orbital_distance_km` in XML or editor

**Calculation**: Use the specified value directly

**Why**: User may want specific positioning for gameplay/story reasons

## Edge Cases

### Station Orbiting a Moon
- Same decision tree applies
- Use moon's orbital zones (min_orbit, low_orbit, etc.)
- L4/L5 not applicable (moons typically don't have sub-moons)
- Usually defaults to half-geo (if geo exists) or low orbit

### Station Orbiting a Star
- Rare, but possible
- Use star's properties (no geostationary, no moons)
- Default to a safe distance (e.g., 0.1 AU or similar)

### Binary Star Systems
- Station orbits the StarSystem center (or one of the stars)
- Use the star's orbital zones if orbiting a specific star
- Otherwise use system-level calculations

## Implementation

### Station Model Addition
```python
class Station(Location):
    # Existing fields...
    orbital_distance_km = models.FloatField(
        null=True,
        blank=True,
        help_text="Orbital distance from parent body surface in km (auto-calculated if not specified)"
    )
    orbit_type = models.CharField(
        max_length=20,
        choices=[
            ('GEO', 'Geostationary'),
            ('HALF_GEO', 'Half-Geostationary'),
            ('L4', 'L4 Lagrange Point'),
            ('L5', 'L5 Lagrange Point'),
            ('LOW', 'Low Orbit'),
            ('CUSTOM', 'Custom/Manual'),
        ],
        null=True,
        blank=True,
        help_text="Type of orbit (auto-determined or manual)"
    )
```

### Calculation Method
```python
def calculate_station_orbit(station: Station, parent_body: Location) -> Tuple[float, str]:
    """
    Calculate optimal orbital distance for a station.
    
    Returns:
        (orbital_distance_km, orbit_type)
    """
    # 1. Check geostationary
    if hasattr(parent_body, 'geostationary_orbit_altitude_km') and \
       hasattr(parent_body, 'hill_sphere_radius_km'):
        geo = parent_body.geostationary_orbit_altitude_km
        hill = parent_body.hill_sphere_radius_km
        if geo and hill:
            if geo < hill:
                return (round(geo / 1000) * 1000, 'GEO')
            else:
                # Geo is outside Hill sphere, use half-geo
                half_geo = geo * 0.5
                return (round(half_geo / 1000) * 1000, 'HALF_GEO')
    
    # 2. Check L4 Lagrange (if planet with moons)
    if isinstance(parent_body, Planet):
        moons = parent_body.moons.all()
        if moons.exists():
            # Find most massive moon
            massive_moon = max(moons, key=lambda m: m.mass_kg or 0)
            if massive_moon.orbital_distance_km:
                l4_distance = massive_moon.orbital_distance_km
                return (round(l4_distance / 1000) * 1000, 'L4')
    
    # 3. Low orbit fallback
    if hasattr(parent_body, 'low_orbit_altitude_km') and parent_body.low_orbit_altitude_km:
        return (round(parent_body.low_orbit_altitude_km / 1000) * 1000, 'LOW')
    
    # 4. Min orbit + safety margin
    if hasattr(parent_body, 'min_orbit_altitude_km') and parent_body.min_orbit_altitude_km:
        return (round((parent_body.min_orbit_altitude_km + 200) / 1000) * 1000, 'LOW')
    
    # Last resort: default to 1000 km
    return (1000.0, 'CUSTOM')
```

## XML Schema

```xml
<station>
  <name>Earth Orbital Control</name>
  <scale>SS</scale>
  <orbital_distance_km>36000</orbital_distance_km>
  <!-- Optional: auto-calculated if not specified -->
  <orbit_type>GEO</orbit_type>
  <!-- Optional: indicates how orbit was determined -->
  <large_berths>5</large_berths>
  <medium_berths>10</medium_berths>
  <small_berths>20</small_berths>
</station>
```

## Notes

1. **Rounding**: All distances rounded to nearest 1000 km for simplicity
2. **Half-Geo**: If geostationary is outside Hill sphere, use half-geo (half-day period, like GPS satellites)
3. **L4 vs L5**: L4 is 60° ahead, L5 is 60° behind. Both are stable. Could support both for multiple stations.
4. **Station-keeping**: Lower orbits require more fuel for station-keeping, but are easier to reach
5. **Multiple stations**: Can have multiple stations at different orbits (e.g., one at GEO, one at half-geo, one at L4, one at low orbit)

