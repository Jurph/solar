# Baseball Card Specification for Planets and Moons

## Purpose
The baseball card provides a "pilot pre-mission briefing" - essential information a pilot needs to understand their destination before departure. Think of it like a flight information card: concise, mission-critical, and easy to scan.

## Current Implementation Status

### ✅ Currently Displayed

**Classification:**
- Planet type (Terrestrial, Gas Giant, etc.) or Moon type (Rocky, Icy, Organic, Terrestrial)

**Physical Properties:**
- Mass (formatted: e.g., "5.97×10²⁴ kg")
- Radius (formatted: e.g., "6,371 km")
- Density (kg/m³)
- Surface Gravity (formatted: e.g., "9.81 m/s² (1.00 g)")

**Thermal Properties:**
- Equilibrium Temperature (K and °C)
- Albedo (reflectivity)

**Atmosphere:**
- Presence (Yes/No)
- Type (CO₂ Thin, N₂/O₂, etc.)
- Height (km)
- Surface Pressure (bar)

**Orbital Properties:**
- Distance from parent (AU for planets, km for moons)
- Orbital Period (days/hours with years conversion)
- Eccentricity
- Inclination (degrees)

**Rotation Properties:**
- Day Length (hours)
- Axial Tilt (degrees)
- Tidally Locked (Yes/No)

## Recommended Additions

### 🎯 High Priority (Mission-Critical)

1. **Escape Velocity**
   - **Why:** Critical for takeoff/landing calculations
   - **Formula:** `v_escape = √(2GM/r)` where G = 6.67430e-11, M = mass_kg, r = radius_m
   - **Display:** "11.2 km/s" or "11,200 m/s"
   - **Comparison:** "1.00× Earth" (Earth = 11.186 km/s)

2. **Orbital Velocity at Surface**
   - **Why:** Minimum speed needed to maintain orbit at surface level
   - **Formula:** `v_orbital = √(GM/r)`
   - **Display:** "7.9 km/s" (for Earth)
   - **Note:** Only meaningful if atmosphere doesn't extend beyond surface

3. **Parent Body Context**
   - **For Planets:** "Orbits: [Star Name] ([Star Type])"
   - **For Moons:** "Orbits: [Planet Name] ([Planet Type])"
   - **Why:** Pilots need to know their destination's location in the system

4. **Atmospheric Scale Height**
   - **Why:** Critical for reentry calculations and atmospheric density falloff
   - **Currently stored:** `scale_height_km` in Atmosphere model
   - **Display:** "8.5 km" (for Earth)
   - **Context:** "Density decreases by 1/e every 8.5 km"

5. **Surface Composition Hint**
   - **Derived from:** Planet type + density
   - **Examples:**
     - Terrestrial + high density → "Rocky surface"
     - Gas Giant → "No solid surface"
     - Icy Moon + low density → "Ice/water surface"
   - **Why:** Landing gear and surface operations planning

### 📊 Medium Priority (Useful Context)

6. **Day/Night Cycle Summary**
   - **Derived from:** Rotation period + axial tilt + tidal locking
   - **Examples:**
     - "24-hour day/night cycle"
     - "Tidally locked: permanent day/night sides"
     - "6-month days, 6-month nights" (high axial tilt + long year)
   - **Why:** Mission timing, solar power planning, temperature extremes

7. **Temperature Range Context**
   - **Current:** Only equilibrium temperature shown
   - **Add:** "Surface temp range" based on:
     - Equilibrium temp (base)
     - Albedo (affects absorption)
     - Day/night cycle (affects extremes)
     - Axial tilt (affects seasonal variation)
   - **Display:** "Avg: 15°C, Range: -50°C to 80°C" (if calculable)

8. **Orbital Context for Moons**
   - **Add:** "Distance from [Parent Planet]: [X] km"
   - **Why:** Important for navigation and understanding moon's position

9. **Visual Appearance**
   - **Color Palette:** If available, show main color
   - **Pattern:** "Banded", "Swirled", etc. (from `color_palette.pattern_name`)
   - **Why:** Visual identification, aesthetic context

10. **Gravity Context**
    - **Already shown:** Surface gravity in g's
    - **Enhancement:** Add "Human tolerance" indicator
      - "Normal" (0.8-1.2 g)
      - "Low gravity" (<0.8 g)
      - "High gravity" (>1.2 g)
    - **Why:** Health and operational considerations

### 🔬 Low Priority (Nice to Have)

11. **Orbital Velocity Comparison**
    - Compare orbital velocity to parent body's orbital velocity
    - **Why:** Understanding relative motion in system

12. **Hill Sphere Radius**
    - **Formula:** `r_H = a * (m/(3M))^(1/3)` where a = semi-major axis, m = moon mass, M = planet mass
    - **Why:** Stability of moon's orbit, maximum distance for stable satellites

13. **Synodic Period** (for moons)
    - Time between same moon phases as seen from parent planet
    - **Why:** Navigation and timing relative to parent planet

14. **Surface Area**
    - **Formula:** `4πr²`
    - **Display:** "510 million km²" (for Earth)
    - **Why:** Mission scope, landing site selection

15. **Volume**
    - **Formula:** `(4/3)πr³`
    - **Display:** "1.08×10¹² km³"
    - **Why:** Less critical, but useful for resource estimation

## Display Organization

### Recommended Section Order (Top to Bottom):

1. **Header**
   - Name (large, prominent)
   - Type (Planet/Moon)
   - Classification (Terrestrial, Rocky, etc.)

2. **Mission Context** (NEW SECTION)
   - Parent body (what it orbits)
   - Distance from parent
   - Orbital period

3. **Physical Properties**
   - Mass, Radius, Density
   - Surface Gravity (with g comparison)
   - Surface Composition (derived hint)

4. **Atmosphere**
   - Presence, Type, Height, Pressure
   - Scale Height (NEW)
   - Reentry considerations (derived from scale height + height)

5. **Orbital Properties**
   - Distance, Period, Eccentricity, Inclination
   - Orbital velocity at surface (NEW, if applicable)

6. **Rotation Properties**
   - Day Length, Axial Tilt, Tidal Locking
   - Day/Night Cycle Summary (NEW)

7. **Thermal Properties**
   - Equilibrium Temperature
   - Temperature Range (NEW, if calculable)
   - Albedo

8. **Mission-Critical Velocities** (NEW SECTION)
   - Escape Velocity (with Earth comparison)
   - Orbital Velocity at Surface (if applicable)

9. **Visual Appearance** (NEW SECTION, if available)
   - Primary Color
   - Surface Pattern

## Implementation Notes

### Calculated Properties (Should be Model Methods)

These should be added as methods on `PhysicalBody` or helper functions in `models/display.py`:

```python
# In PhysicalBody or display.py
def get_escape_velocity_ms(self) -> Optional[float]:
    """Calculate escape velocity in m/s."""
    if not self.mass_kg or not self.radius_km:
        return None
    G = 6.67430e-11
    radius_m = self.radius_km * 1000
    return math.sqrt(2 * G * self.mass_kg / radius_m)

def get_orbital_velocity_ms(self) -> Optional[float]:
    """Calculate orbital velocity at surface in m/s."""
    if not self.mass_kg or not self.radius_km:
        return None
    G = 6.67430e-11
    radius_m = self.radius_km * 1000
    return math.sqrt(G * self.mass_kg / radius_m)

def get_surface_composition_hint(self) -> Optional[str]:
    """Derive surface composition from type and density."""
    # Logic based on planet_type/moon_type and density_kg_m3
    pass

def get_day_night_cycle_summary(self) -> str:
    """Generate human-readable day/night cycle description."""
    # Logic based on rotation_period_hours, axial_tilt_deg, is_tidally_locked
    pass
```

### Backend vs Frontend

- **Backend (models/display.py):** All calculations and formatting
- **Frontend (base.html):** Only display logic, no calculations
- **API (views/universe.py + views/serializers.py):** Return formatted strings, not raw numbers

### Missing Data Handling

- Show "N/A" or "Unknown" for missing data
- Don't show sections if all data in that section is missing
- Use conditional rendering (already implemented)

## Example: Earth's Baseball Card

```
EARTH
Planet - Terrestrial

Mission Context
Orbits: Sun (G-type)
Distance: 1.00 AU
Orbital Period: 365.26 days (1.00 years)

Physical Properties
Mass: 5.97×10²⁴ kg
Radius: 6,371 km
Density: 5,514 kg/m³
Surface Gravity: 9.81 m/s² (1.00 g)
Surface: Rocky, with liquid water

Atmosphere
Type: N₂/O₂ (Earth-like)
Height: 100 km
Surface Pressure: 1.000 bar
Scale Height: 8.5 km
Reentry: Standard atmospheric entry profile

Orbital Properties
Distance: 1.00 AU
Period: 365.26 days
Eccentricity: 0.017
Inclination: 0.00°

Rotation Properties
Day Length: 24.00 hours
Axial Tilt: 23.44°
Tidally Locked: No
Day/Night: 24-hour day/night cycle with seasonal variation

Thermal Properties
Equilibrium Temp: 255 K (-18°C)
Surface Temp Range: -50°C to 50°C (typical)
Albedo: 0.306

Mission-Critical Velocities
Escape Velocity: 11.2 km/s (1.00× Earth)
Orbital Velocity: 7.9 km/s

Visual Appearance
Primary Color: #4A90E2 (Blue)
Pattern: Swirled (oceans and clouds)
```

## Example: Luna's Baseball Card

```
LUNA
Moon - Rocky

Mission Context
Orbits: Earth (Terrestrial)
Distance: 384,400 km
Orbital Period: 27.32 days (655.7 hours)

Physical Properties
Mass: 7.35×10²² kg
Radius: 1,737 km
Density: 3,344 kg/m³
Surface Gravity: 1.62 m/s² (0.17 g)
Surface: Rocky, heavily cratered

Atmosphere
Type: None
Height: N/A
Surface Pressure: N/A

Orbital Properties
Distance: 384,400 km
Period: 27.32 days
Eccentricity: 0.055
Inclination: 5.15°

Rotation Properties
Day Length: 655.7 hours (27.32 days)
Axial Tilt: 6.68°
Tidally Locked: Yes
Day/Night: Permanent day/night sides (14 Earth days each)

Thermal Properties
Equilibrium Temp: 270 K (-3°C)
Surface Temp Range: -173°C to 127°C (extreme)
Albedo: 0.136

Mission-Critical Velocities
Escape Velocity: 2.38 km/s (0.21× Earth)
Orbital Velocity: 1.68 km/s

Visual Appearance
Primary Color: #8C7853 (Gray-brown)
Pattern: Uniform (no atmosphere)
```

## Priority Implementation Order

1. **Phase 1 (Essential):**
   - Escape velocity calculation and display
   - Parent body context (what it orbits)
   - Atmospheric scale height display

2. **Phase 2 (Very Useful):**
   - Orbital velocity at surface
   - Surface composition hint
   - Day/night cycle summary

3. **Phase 3 (Nice to Have):**
   - Temperature range context
   - Visual appearance (color palette)
   - Additional calculated properties

## Questions for Discussion

1. Should we show escape velocity in km/s or m/s? (km/s is more readable)
2. Should we include Hill sphere radius for moons? (Useful but complex)
3. Should we show surface area/volume? (Less critical for pilots)
4. How detailed should the day/night cycle summary be? (Simple vs. detailed)
5. Should we add "hazard warnings" derived from properties? (e.g., "Extreme temperature variation", "No atmosphere - EVA required")

