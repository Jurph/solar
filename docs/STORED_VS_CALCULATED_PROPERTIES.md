# Stored vs Calculated Properties Analysis

## Principles

**Store in DB when:**
- Source data that can't be derived (mass_kg, radius_km, orbital_distance_au)
- Values that might be manually overridden (e.g., from XML imports)
- Values used in database queries/filters
- Values that are expensive to calculate but frequently accessed (with caching option)
- Values that come from external authoritative sources (NASA data, XML imports)

**Calculate via methods when:**
- Simple unit conversions (kg ↔ solar masses, km ↔ solar radii, days ↔ hours)
- Derived values from stored data (surface gravity, escape velocity, orbital velocity)
- Context-dependent values (orbital velocity at specific altitude)
- Values rarely accessed
- Values that depend on relationships (equilibrium temperature needs parent star)

---

## Current State Analysis

### ✅ SHOULD BE STORED (Source Data)

#### Physical Properties
- `mass_kg` - **STORE** - Primary source data, can't be derived
- `radius_km` - **STORE** - Primary source data, can't be derived
- `density_kg_m3` - **STORE** - Can be calculated, but often comes from composition/type and may be manually specified
- `albedo` - **STORE** - Material property, not derivable from other fields
- `orbital_distance_au` (Planet) - **STORE** - Primary orbital parameter
- `orbital_distance_km` (Moon) - **STORE** - Primary orbital parameter
- `orbital_eccentricity` - **STORE** - Primary orbital parameter
- `orbital_inclination_deg` - **STORE** - Primary orbital parameter
- `rotation_period_hours` - **STORE** - Primary rotation parameter
- `axial_tilt_deg` - **STORE** - Primary rotation parameter
- `is_tidally_locked` - **STORE** - Boolean state, not calculable

#### Star-Specific
- `star_type` - **STORE** - Classification
- `star_magnitude` - **STORE** - Observed magnitude
- `temperature_k` - **STORE** - Measured/observed temperature

#### Planet/Moon-Specific
- `planet_type` - **STORE** - Classification
- `variety` (Moon) - **STORE** - Classification

---

### ❌ SHOULD BE CALCULATED (Remove from DB)

#### Unit Conversions
- `mass_solar` - **CALCULATE** - Simple conversion: `mass_kg / 1.989e30`
- `radius_solar` - **CALCULATE** - Simple conversion: `radius_km / 696340.0`
- `orbital_period_hours` (from days) - **CALCULATE** - Simple conversion: `orbital_period_days * 24`
- `orbital_period_days` (from hours) - **CALCULATE** - Simple conversion: `orbital_period_hours / 24`
- `orbital_distance_km` (from AU) - **CALCULATE** - Simple conversion: `orbital_distance_au * 1.496e8`
- `orbital_distance_au` (from km) - **CALCULATE** - Simple conversion: `orbital_distance_km / 1.496e8`

#### Derived Physical Properties
- `surface_gravity_ms2` - **CALCULATE** - Formula: `g = GM/r²` where G = 6.67430e-11
- `escape_velocity_km_s` - **CALCULATE** - Formula: `v_esc = sqrt(2GM/R)`
- `orbital_velocity_km_s(altitude_km)` - **CALCULATE** - Formula: `v = sqrt(GM/(R+h))` where h is altitude
- `density_kg_m3` (if not stored) - **CALCULATE** - Formula: `ρ = M/(4/3 * π * r³)`

#### Derived Thermal Properties
- `equilibrium_temperature_k` - **CALCULATE** - Depends on parent star's temperature/luminosity and orbital distance
  - Formula: `T_eq = T_star * sqrt(R_star / (2 * d)) * (1 - albedo)^0.25`
  - **Note**: Requires access to parent star, so this is context-dependent

#### Orbital Zone Properties (for Controllers)
- `min_orbit_altitude_km` - **CALCULATE** - `atmosphere_height_km + safety_margin` (e.g., 50km)
- `low_orbit_altitude_km` - **CALCULATE** - Typically `radius_km * 0.025` (LEO equivalent)
- `geostationary_orbit_altitude_km` - **CALCULATE** - From rotation period: `r_geo = (GM * T² / (4π²))^(1/3) - radius_km`
- `hill_sphere_radius_km` - **CALCULATE** - Depends on parent body's mass and distance

---

### ⚠️ DEBATABLE (Store with Calculate Fallback)

#### Density
- **Current**: Stored as `density_kg_m3`
- **Recommendation**: **STORE** but provide `calculate_density()` method
  - Reason: Density often comes from composition/type (not just mass/volume)
  - May be manually specified in XML
  - Can be calculated if missing: `density = mass_kg / (4/3 * π * (radius_km * 1000)³)`

#### Equilibrium Temperature
- **Current**: Stored as `equilibrium_temperature_k`
- **Recommendation**: **CALCULATE** (remove from DB)
  - Reason: Depends on parent star which may change or be queried differently
  - Formula requires: parent star temperature, parent star radius, orbital distance, albedo
  - Context-dependent, not a fixed property

---

## Proposed Helper Methods for PhysicalBody

```python
class PhysicalBody(Celestial):
    # ... existing fields ...
    
    # ===== UNIT CONVERSIONS =====
    def get_mass_solar(self) -> Optional[float]:
        """Convert mass_kg to solar masses."""
        if self.mass_kg is None:
            return None
        return self.mass_kg / 1.989e30
    
    def get_radius_solar(self) -> Optional[float]:
        """Convert radius_km to solar radii."""
        if self.radius_km is None:
            return None
        return self.radius_km / 696340.0
    
    def get_density_kg_m3(self) -> Optional[float]:
        """Get density, calculating if not stored."""
        if self.density_kg_m3 is not None:
            return self.density_kg_m3
        # Calculate from mass and radius
        if self.mass_kg and self.radius_km:
            volume_m3 = (4/3) * 3.14159 * ((self.radius_km * 1000) ** 3)
            return self.mass_kg / volume_m3
        return None
    
    # ===== DERIVED PHYSICAL PROPERTIES =====
    def get_surface_gravity_ms2(self) -> Optional[float]:
        """Calculate surface gravity: g = GM/r²"""
        if not self.mass_kg or not self.radius_km:
            return None
        G = 6.67430e-11  # m³/kg/s²
        radius_m = self.radius_km * 1000
        return (G * self.mass_kg) / (radius_m ** 2)
    
    def get_escape_velocity_km_s(self) -> Optional[float]:
        """Calculate escape velocity: v_esc = sqrt(2GM/R)"""
        if not self.mass_kg or not self.radius_km:
            return None
        G = 6.67430e-11  # m³/kg/s²
        radius_m = self.radius_km * 1000
        v_esc_ms = (2 * G * self.mass_kg / radius_m) ** 0.5
        return v_esc_ms / 1000  # Convert to km/s
    
    def get_orbital_velocity_km_s(self, altitude_km: float) -> Optional[float]:
        """Calculate orbital velocity at given altitude: v = sqrt(GM/(R+h))"""
        if not self.mass_kg or not self.radius_km:
            return None
        G = 6.67430e-11  # m³/kg/s²
        radius_m = self.radius_km * 1000
        altitude_m = altitude_km * 1000
        v_ms = (G * self.mass_kg / (radius_m + altitude_m)) ** 0.5
        return v_ms / 1000  # Convert to km/s
    
    # ===== ORBITAL ZONE PROPERTIES (for Controllers) =====
    def get_safe_altitude(self, maneuver_type: str) -> Optional[float]:
        """Get safe altitude for maneuver type (reentry, insertion, etc.)"""
        if not self.radius_km:
            return None
        
        # Check for atmosphere
        atmosphere_height = None
        try:
            from django.contrib.contenttypes.models import ContentType
            from mysite.universe.models import Atmosphere
            content_type = ContentType.objects.get_for_model(self.__class__)
            try:
                atmosphere = Atmosphere.objects.get(content_type=content_type, object_id=self.id)
                atmosphere_height = atmosphere.atmosphere_height_km
            except Atmosphere.DoesNotExist:
                pass
        except Exception:
            pass
        
        if maneuver_type == "reentry":
            # Reentry: atmosphere height + safety margin
            if atmosphere_height:
                return atmosphere_height + 50  # 50km safety margin
            return self.radius_km * 0.1  # 10% of radius as fallback
        elif maneuver_type == "insertion":
            # Orbital insertion: low orbit altitude
            return self.radius_km * 0.025  # ~2.5% of radius (LEO equivalent)
        elif maneuver_type == "geostationary":
            # Geostationary: calculated from rotation period
            if not self.rotation_period_hours:
                return None
            return self.get_geostationary_altitude_km()
        return None
    
    def get_geostationary_altitude_km(self) -> Optional[float]:
        """Calculate geostationary orbit altitude."""
        if not self.mass_kg or not self.radius_km or not self.rotation_period_hours:
            return None
        G = 6.67430e-11  # m³/kg/s²
        T_s = self.rotation_period_hours * 3600  # Convert to seconds
        r_geo_m = ((G * self.mass_kg * T_s**2) / (4 * 3.14159**2)) ** (1/3)
        return (r_geo_m / 1000) - self.radius_km  # Altitude above surface
    
    def get_hill_sphere_radius_km(self) -> Optional[float]:
        """Calculate Hill sphere radius (requires parent body)."""
        # This needs parent body's mass and distance
        # Implementation depends on how we access parent
        # For now, return None - this is context-dependent
        return None
    
    # ===== THERMAL PROPERTIES =====
    def get_equilibrium_temperature_k(self) -> Optional[float]:
        """Calculate equilibrium temperature from parent star."""
        # This requires parent star's properties
        # For Planet: get parent Star
        # For Moon: get parent Planet, then its parent Star
        # Implementation depends on relationship structure
        return None  # TODO: Implement when we have parent access pattern
    
    # ===== ORBITAL PERIOD CONVERSIONS =====
    def get_orbital_period_hours(self) -> Optional[float]:
        """Get orbital period in hours (convert from days if needed)."""
        if self.orbital_period_hours is not None:
            return self.orbital_period_hours
        if self.orbital_period_days is not None:
            return self.orbital_period_days * 24.0
        return None
    
    def get_orbital_period_days(self) -> Optional[float]:
        """Get orbital period in days (convert from hours if needed)."""
        if self.orbital_period_days is not None:
            return self.orbital_period_days
        if self.orbital_period_hours is not None:
            return self.orbital_period_hours / 24.0
        return None
    
    def get_orbital_distance_km(self) -> Optional[float]:
        """Get orbital distance in km (convert from AU if needed)."""
        if self.orbital_distance_km is not None:
            return self.orbital_distance_km
        if hasattr(self, 'orbital_distance_au') and self.orbital_distance_au is not None:
            return self.orbital_distance_au * 1.496e8  # 1 AU = 1.496e8 km
        return None
    
    def get_orbital_distance_au(self) -> Optional[float]:
        """Get orbital distance in AU (convert from km if needed)."""
        if hasattr(self, 'orbital_distance_au') and self.orbital_distance_au is not None:
            return self.orbital_distance_au
        if self.orbital_distance_km is not None:
            return self.orbital_distance_km / 1.496e8  # 1 AU = 1.496e8 km
        return None
```

---

## Migration Plan

### Phase 1: Add Helper Methods
1. Add all helper methods to `PhysicalBody`
2. Update code to use methods instead of direct field access for calculated values
3. Keep existing DB fields for backward compatibility

### Phase 2: Remove Calculated Fields from DB
1. Create migration to remove:
   - `mass_solar`
   - `radius_solar`
   - `equilibrium_temperature_k` (if we decide to calculate it)
2. Update all code references to use helper methods
3. Update XML importer to not set these fields

### Phase 3: Update Views/API
1. Update `object_details` view to use helper methods
2. Update display formatting to use helper methods
3. Ensure backward compatibility during transition

---

## Summary Table

| Property | Current | Recommendation | Reason |
|----------|---------|----------------|--------|
| `mass_kg` | Stored | **STORE** | Source data |
| `mass_solar` | Stored | **CALCULATE** | Unit conversion |
| `radius_km` | Stored | **STORE** | Source data |
| `radius_solar` | Stored | **CALCULATE** | Unit conversion |
| `density_kg_m3` | Stored | **STORE** (with calc fallback) | May be manually specified |
| `surface_gravity_ms2` | Calculated | **CALCULATE** | Derived from mass/radius |
| `escape_velocity_km_s` | Not stored | **CALCULATE** | Derived from mass/radius |
| `orbital_velocity_km_s` | Not stored | **CALCULATE** | Context-dependent (altitude) |
| `albedo` | Stored | **STORE** | Material property |
| `equilibrium_temperature_k` | Stored | **CALCULATE** | Depends on parent star |
| `orbital_distance_au` | Stored | **STORE** | Source data (Planet) |
| `orbital_distance_km` | Stored | **STORE** | Source data (Moon) |
| `orbital_period_days` | Stored | **STORE** | Source data (Planet) |
| `orbital_period_hours` | Stored | **CALCULATE** | Unit conversion (Moon) |
| `orbital_eccentricity` | Stored | **STORE** | Source data |
| `orbital_inclination_deg` | Stored | **STORE** | Source data |
| `rotation_period_hours` | Stored | **STORE** | Source data |
| `axial_tilt_deg` | Stored | **STORE** | Source data |
| `is_tidally_locked` | Stored | **STORE** | Boolean state |
| `min_orbit_altitude_km` | Not stored | **CALCULATE** | Derived (atmosphere + margin) |
| `low_orbit_altitude_km` | Not stored | **CALCULATE** | Derived (radius * 0.025) |
| `geostationary_orbit_altitude_km` | Not stored | **CALCULATE** | Derived (rotation period) |
| `hill_sphere_radius_km` | Not stored | **CALCULATE** | Context-dependent (parent) |

