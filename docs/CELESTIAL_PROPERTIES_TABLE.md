# Celestial Body Properties Table

This table shows which properties apply to Stars, Planets, Moons, and Stations for realistic orbital mechanics and procedural generation.

**Note**: Stations are included for orbital positioning, but don't have physical properties (mass, radius, etc.).

| Property | Star | Planet | Moon | Station | Notes |
|----------|------|--------|------|---------|-------|
| **Basic Identity** |
| name | YES | YES | YES | YES | Inherited from Location |
| scale | YES | YES | YES | YES | Inherited from Location |
| **Physical Properties** |
| density_kg_m3 | YES | YES | YES | Fundamental property (derived from type) |
| mass_kg | YES | YES | YES | Calculated from density and radius |
| radius_km | YES | YES | YES | Fundamental property |
| surface_gravity_ms2 | YES | YES | YES | Calculated from mass/radius |
| **Visual Properties** |
| color_palette | YES | YES | YES | ColorPalette dataclass (main_color, hex_colors, pattern_name) |
| **Star-Specific** |
| star_type | YES | | | O/B/A/F/G/K/M classification |
| star_magnitude | YES | | | Apparent magnitude |
| temperature_k | YES | | | Surface temperature |
| luminosity_solar | YES | | | Luminosity in solar units |
| habitable_zone_inner_au | YES | | | Calculated from sum of all star luminosities in system |
| habitable_zone_outer_au | YES | | | Calculated from sum of all star luminosities in system |
| **StarSystem-Specific (not in table above - applies to StarSystem model)** |
| galactic_x_ly | YES | | | X coordinate relative to galactic center (light-years) |
| galactic_y_ly | YES | | | Y coordinate relative to galactic center (light-years) |
| galactic_z_ly | YES | | | Z coordinate relative to galactic center (light-years) |
| system_age_years | YES | | | System age derived from seed (shared by all bodies in system) |
| **Orbital Properties (for bodies that orbit)** |
| orbital_distance_au | | YES | OPT | Semi-major axis (AU for planets) |
| orbital_distance_km | | YES | YES | Semi-major axis (km for moons) |
| orbital_period_days | | YES | OPT | Orbital period |
| orbital_period_hours | | YES | YES | Alternative unit |
| orbital_eccentricity | | YES | YES | 0.0=circular, 0.0-1.0=elliptical |
| orbital_inclination_deg | | YES | YES | Tilt relative to reference plane |
| **Solar System Coordinates (for Planets/Moons)** |
| solar_angle_deg | | YES | YES | Current orbital position (0-359°, calculated from system_age and period) |
| **Rotation Properties** |
| rotation_period_hours | | YES | YES | Day length (not applicable to stars) |
| axial_tilt_deg | | YES | YES | CRITICAL for plane change calculations |
| is_tidally_locked | | YES | YES | Usually true for moons |
| **Thermal Properties** |
| albedo | | YES | YES | Reflectivity (affects temperature) |
| equilibrium_temperature_k | | YES | YES | Calculated from star distance/albedo |
| **Atmospheric Properties** |
| has_atmosphere | | YES | OPT | Boolean flag |
| atmosphere_type | | YES | OPT | CO2_Thin, N2_O2, H2_He, etc. |
| atmosphere_height_km | | YES | OPT | Top of atmosphere |
| surface_pressure_bar | | YES | OPT | Surface atmospheric pressure |
| scale_height_km | | YES | OPT | Atmospheric density falloff |
| mean_molecular_mass | | YES | OPT | For atmospheric calculations |
| **Orbital Zones (for traffic control)** |
| min_orbit_altitude_km | | YES | YES | Minimum safe orbit (atmosphere + margin) |
| low_orbit_altitude_km | | YES | YES | Typical LEO equivalent |
| geostationary_orbit_altitude_km | | YES | YES | GEO altitude (calculated) |
| hill_sphere_radius_km | | YES | YES | Maximum stable orbit distance |
| **Planet-Specific** |
| planet_type | | YES | | MESOPLANET, TERRESTRIAL, GASGIANT, etc. |
| **Moon-Specific** |
| variety | | | YES | Rocky/Icy/Organic/Terrestrial |
| **Composition (drives color generation)** |
| iron_content | | YES | YES | Float 0.0-1.0 |
| ice_content | | YES | YES | Float 0.0-1.0 |
| has_methane | | YES | YES | Boolean |
| has_sulfur | | YES | YES | Boolean |
| water_coverage | | YES | YES | Float 0.0-1.0 (surface coverage) |
| carbon_content | | YES | YES | Float 0.0-1.0 |
| organic_haze | | YES | YES | | Float 0.0-1.0 |
| **Station-Specific** |
| orbital_distance_km | | | | YES | Distance from parent body surface (km) |
| orbit_type | | | | OPT | GEO/HALF_GEO/L4/L5/LOW/CUSTOM |
| large_berths | | | | YES | Number of large docking berths |
| medium_berths | | | | YES | Number of medium docking berths |
| small_berths | | | | YES | Number of small docking berths |

## Legend
- **YES**: Always applicable/stored
- **OPT**: Optional (may or may not apply, stored if present)
- **Blank**: Not applicable

## Design Decisions

### Orbit as Dataclass?
**Question**: Should orbital properties be stored in a dataclass (e.g., `planet.orbit.inclination_deg`) with helper methods for unit conversion?

**Consideration**: 
- **Pros**: Clean API, unit conversion helpers, type safety
- **Cons**: Extra layer of indirection, Django ORM doesn't natively support nested dataclasses in fields, would need custom field type or JSONField
- **Recommendation**: **NO** - Keep as direct model fields. Unit conversion can be handled via methods on the model (e.g., `planet.get_orbital_distance_km()`). The ORM benefits of direct fields outweigh the API cleanliness of a dataclass.

### Atmosphere as Dataclass?
**Question**: Should atmospheric properties be in a dataclass (e.g., `if planet.atmosphere: reentry()`)?

**Consideration**:
- **Pros**: Clean conditional logic, groups related properties
- **Cons**: Most moons have no atmosphere - separate table is more efficient (OneToOne relationship)
- **Recommendation**: **YES** - Use a separate `Atmosphere` model with OneToOne relationship. This allows:
  - `if planet.atmosphere:` for conditional checks
  - `planet.atmosphere.get_atmospheric_density(altitude)` for methods
  - Efficient storage (only create Atmosphere records when needed)
  - Clean separation: "Does this body have an atmosphere?" → check if relationship exists

## Notes

1. **Density is fundamental** - It's derived from type and used to calculate mass. Mass flows from density × volume.

2. **Unit storage** - We store only in base units (kg, km). Solar units are calculated on-demand if needed.

3. **Stars** don't orbit, so no orbital properties. They also don't need rotation_period_hours (we're not landing on them, no day/night cycle).

4. **Planets** have the full suite of orbital, atmospheric, and orbital zone properties needed for traffic control.

5. **Moons** are similar to planets but:
   - Usually no atmosphere (OPT)
   - Usually tidally locked (YES)
   - Orbital distance in km (not AU)
   - Full composition tracking for color generation

6. **Orbital zones** are critical for Controllers - both Planet and Moon need these since spacecraft can orbit either.

7. **Color palette** applies to all three - stars have temperature-based colors, planets/moons have composition-based colors.

8. **Composition variables** drive color generation for planets and moons. All seven variables (iron_content, ice_content, has_methane, has_sulfur, water_coverage, carbon_content, organic_haze) apply to both planets and moons.

9. **Stations** have minimal properties:
   - Only need orbital positioning (`orbital_distance_km`)
   - No physical properties (mass, radius, etc.)
   - Orbit determined by decision tree: GEO → Half-GEO → L4 → Low → Custom
   - See `docs/STATION_ORBITAL_POSITIONING.md` for full algorithm

10. **Coordinate Systems:**
   - **StarSystem**: Galactic coordinates (galactic_x_ly, galactic_y_ly, galactic_z_ly) relative to galactic center in light-years
   - **StarSystem**: System age (system_age_years) derived from seed, shared by all bodies in the system
   - **Planets/Moons**: Solar angle (solar_angle_deg, 0-359°) relative to system center, calculated from system_age and the parent planet's orbital_period
   - **Binary Systems**: Multiple stars can share a StarSystem; habitable zone calculated from sum of all star luminosities
   - **Distance calculation**: Can measure 3D Euclidean distances between star systems and estimate travel times
   - **Solar angle calculation**: `solar_angle_deg = (system_age_years / orbital_period_days) * 360 mod 360`
   - All planets start at 0° and advance based on system age (no elliptical orbits or ecliptic tilt for now)

