# Physics-Based Controller Responses

## Overview

Controllers need to provide realistic orbital mechanics parameters in their clearance responses. These parameters should be derived from the physical properties of the planet or moon they're controlling.

## Available Physical Properties

From `PhysicalBody` (Planet/Moon):
- `mass_kg` - Mass in kilograms
- `radius_km` - Radius in kilometers
- `density_kg_m3` - Density
- `surface_gravity_ms2` - Surface gravity (can be calculated)
- `escape_velocity_ms` - Escape velocity (can be calculated)
- `orbital_velocity_ms` - Orbital velocity at surface (can be calculated)

From `Atmosphere` (if exists):
- `atmosphere_type` - Type of atmosphere
- `atmosphere_height_km` - Height of atmosphere
- `surface_pressure_bar` - Surface pressure
- `scale_height_km` - Atmospheric scale height

From `PhysicalBody` orbital properties:
- `orbital_distance_km` - Distance from parent (for moons)
- `orbital_period_days` - Orbital period
- `orbital_eccentricity` - Eccentricity
- `orbital_inclination_deg` - Inclination
- `axial_tilt_deg` - Axial tilt (for plane changes)
- `rotation_period_hours` - Rotation period

## Maneuver Types and Required Parameters

### 1. LAUNCH / DIRECT_ASCENT

**Purpose**: Launch from surface to suborbital trajectory

**Required Parameters**:
- `azimuth_deg`  - Launch heading (0-360°, can basically be random)
- `inclination_deg` - should be near equatorial within tolerance of the planet's axial tilt 
- `apogee_km` - Target apogee altitude (above surface)

**Rules**:
- Apogee should be **slightly above** the highest appropriate circularization orbit (e.g., if circularizing to 200 km, launch apogee might be 220-250 km)
- Circularization "lanes" are in increments of 10km, adequate spacing to ensure room to divert around debris without cascading emergency maneuvers. 
- Final inclination should be close to solar system's ecliptic plane 

**Derivation from Planet/Moon**:
- `apogee_km` = target_circular_orbit_altitude + (10-50 km buffer)
- `azimuth_deg` = calculate from destination direction or use default (e.g., 90° = east)
- If atmosphere exists: ensure `apogee_km > atmosphere_height_km + 20 km` (safety margin)

**Example Response**:
"Your launch is approved. Head up to 220 kilometers apogee, launch azimuth 090 degrees. Check in when you reach apogee."

---

### 2. CIRCULARIZATION

**Purpose**: Circularize orbit at target altitude

**Required Parameters**:
- `altitude_km` - Target circular orbit altitude (above surface)
- `inclination_deg` - Orbital inclination (0-180°)

**Derivation from Planet/Moon**:
- If atmosphere exists: `min_altitude = 1.5 * atmosphere_height_km` rounded to 10km  
- If no atmosphere: `min_altitude = (radius_km * 0.01)` (1% of radius) rounded up to 10km 
- Correct altitude assignment = `min_altitude + N * 10km` where N is a random number between 1 and 50 (these are "lanes") 

**Example Response**:
"Cleared for circularization burn to 200 kilometers, 94 degrees inclination."

---

### 3. INSERTION

**Purpose**: Insert into orbit around destination planet/moon

**Required Parameters**:
- `altitude_km` - Target insertion orbit altitude
- `inclination_deg` - Orbital inclination

**Rules**:
- Similar to circularization, but for arrival at destination
- Altitude should be in LEO band for destination body
- Inclination may be constrained by approach trajectory
- Should account for destination body's atmosphere (if any)

**Derivation from Planet/Moon**:
- Same as circularization, but use **destination** body's properties
- `min_altitude = destination.atmosphere_height_km + 20 km` (if atmosphere)
- Select from destination's LEO bands

**Example Response**:
"Cleared for insertion burn into Earth orbit. Target 200 kilometers, 28 degrees inclination."

---

### 4. SUBLIGHT / TRANSFER

**Purpose**: Interplanetary transfer between planets

**Required Parameters**:
- `departure_angle_deg` - Departure angle from current orbit

**Rules**:
- Departure angle calculated from Hohmann transfer or similar
- Should account for both origin and destination orbital properties
- Transfer time can be calculated from orbital periods

**Derivation from Planet/Moon**:
# NOTE: we don't need to do this yet, but picking a solar "north" that is the "zero azimuth", and then letting all the planets move around their orbits (theta) at their normal radius (rho) means that we can calculate a (rho, theta) position for each planet easily that is a function of the date/time/age of the solar system ... and then calculate the azimuth relative to zero that a straight-line flight would take. We don't need to explicitly store a planet's (rho, theta) position because its rho is always its radius in AU, and its theta is always (age of solar system / orbital period) modulo 360. You might need a function like travel(pointA, pointB) that yields a (distance, departure azimuth) pair. Later on we can complicate it with hohmann(pointA, pointB) but for now the angle of a straight-line shot is probably fine, since we're hypothesizing a sublight travel mode that is hours-or-days between planets rather than months or years. 

**Example Response**:
"You are go for sublight burn to Earth. Departure angle 45 degrees, transfer time approximately 180 days."

---

### 5. PLANE_CHANGE

**Purpose**: Change orbital plane (inclination change)

**Required Parameters**:
- `target_inclination_deg` - Desired new inclination

**Rules**:
- Plane changes are expensive (high delta-V)
- Should be done at nodes (where planes intersect)
- Target inclination often matches destination's orbital plane or axial tilt

**Derivation from Planet/Moon**:
- `target_inclination` = destination's `orbital_inclination_deg` or `axial_tilt_deg`, subtracted from current nav_Context inclination 

**Example Response**:
"Cleared for plane change maneuver. Target inclination 23.5 degrees, execute at ascending node."

---

### 6. DEORBIT

**Purpose**: Deorbit from orbit to surface approach

**Required Parameters**:
- `deorbit_altitude_km` - Altitude to begin deorbit burn
- `entry_angle_deg` - Atmospheric entry angle (if atmosphere exists)

**Rules**:
- Deorbit burn typically at apogee (to bring perigee down)
- For bodies with atmosphere:
  - Entry angle critical (too steep = too hot, too shallow = skip out)
  - Typical entry angle: 6-7 degrees
  - Entry interface = atmosphere height
- For airless bodies:
  - Direct descent, entry angle less critical
  - Should use powered descent

**Derivation from Planet/Moon**:
- If atmosphere exists:
 - Calculate a safe `entry_angle_deg` from the atmospheric height, surface pressure, and scale height. 
 - Use NASA-approved equations for this if practical, otherwise default to an answer in between 5 and 10 degrees chosen randomly 
 - Approve a retro burn to bring perigee below `atmospheric_height_km`. 

**Example Response**:
"Cleared for deorbit burn. Entry interface at 100 kilometers, entry angle 6.5 degrees."

---

### 7. LANDING / DOCK

**Purpose**: Final approach and landing/docking

**Required Parameters**:
- `approach_heading_deg` - Final approach heading
- `landing_site` - Landing coordinates or docking bay

**Rules**:
- For stations: specific docking bay assignment
- For planets: coordinates or landing zone

**Derivation from Planet/Moon**:
- `approach_heading` = calculate from current position to landing site
- `landing_site` = from mission parameters or default landing zone
- `approach_speed` = function of surface gravity (higher gravity = faster approach)

**Example Response**:
"Cleared for landing approach. Heading 270 degrees, landing zone Alpha. Final approach speed 50 meters per second."

---

## Implementation Plan

### Phase 1: Helper Methods on PhysicalBody

Add methods to calculate orbital parameters:

-- rewrite based on my instructions above -- 

### Phase 2: Controller Response Parameter Generation

Create a service or helper that generates physics-based parameters:

-- rewrite -- 


### Phase 3: Integration with ControllerResponse Particle

Modify `ControllerResponse.get_examples()` to:
1. Get the controller's location (planet/moon)
2. Use `ControllerPhysicsService` to generate parameters
3. Format parameters into examples

-- rewrite -- 

## Next Steps

1. **Review and refine rules** - User should review the maneuver rules and adjust as needed
2. **Implement helper methods** - Add `get_min_safe_orbit_km()`, `get_leo_bands()`, etc. to `PhysicalBody`
3. **Create ControllerPhysicsService** - Implement parameter generation logic
4. **Integrate with particles** - Update `ControllerResponse.get_examples()` to use physics service
5. **Test with real data** - Verify parameters are realistic for Earth, Mars, etc.

