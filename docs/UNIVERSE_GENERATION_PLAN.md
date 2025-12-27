# Universe Generation, Import/Export, and Editor Plan

## Overview

We need a comprehensive system that handles:
1. **Procedural Generation** - Creating universes from scratch using rules
2. **Manual Specification** - Reproducing real bodies (Earth, Saturn, etc.) with full detail
3. **XML Import/Export** - Round-trip safe transfer of universe data
4. **Web-Based Editor** - UI for creating/editing universes with mandatory/optional fields

---

## Current State

### What Exists:
- ✅ Basic XML import/export (`import_xml.py`, `export_xml.py`)
- ✅ Hand-built XML files (schema has grown beyond name/type/scale; e.g. system coordinates/age and orbital fields are supported)
- ✅ Django admin interface (basic, not specialized)
- ✅ Command-line import tool (`import_universe` management command)
- ✅ Procedural generation utilities exist (`procedural_generation.py`) including seeded RNG helpers

### What's Missing:
- ❌ A single, authoritative “full schema v2” doc (this plan references `universe_schema_v2.md`, but the repo currently has `universe_schema.md`)
- ❌ Seed-based generation integrated end-to-end (XML seed → importer → deterministic generation on missing fields)
- ❌ Web-based universe editor
- ❌ Strong field validation (mandatory vs optional) at import time (beyond basic parsing)
- ❌ Round-trip safety guarantees

---

## Part 1: Procedural Generation Rules

### 1.1 Generation Sequence (from CELESTIAL_MODEL_PLAN.md)

**StarSystem Generation (per system):**
1. Galactic coordinates (galactic_x_ly, galactic_y_ly, galactic_z_ly) = f(seed, system_name)
2. System age (system_age_years) = f(seed) [shared by all bodies in system]

**Star Generation (per star in system):**
1. Star type (random weighted: O/B/A/F/G/K/M)
2. Density = f(type)
3. Radius = f(type)
4. Mass = f(density, radius)
5. Temperature = f(type)
6. Luminosity = f(type)
7. Color palette = f(temperature)

**Habitable Zone Calculation (after all stars in system are generated):**
- Sum all star luminosities in the system
- Calculate habitable zone from total luminosity
- Store on StarSystem (or calculate on-demand)

**Planet Generation (per planet):**
1. Orbital distance (random with spacing)
2. Planet type = f(orbital_distance, star_type)
3. Density = f(planet_type)
4. Radius = f(planet_type)
5. Mass = f(density, radius)
6. Orbital period = f(orbital_distance, star_mass)
6A. Solar angle = f(system_age, orbital_period) [= (age / period) * 360 mod 360]
7. Is tidally locked = f(orbital_distance, star_mass, planet_mass)
8. Rotation period = f(is_tidally_locked, planet_type, orbital_distance)
9. Axial tilt = f(planet_type, is_tidally_locked)
10. Surface gravity = f(mass, radius)
11. Has atmosphere = f(planet_type, mass, orbital_distance)
12. Atmosphere type = f(planet_type, mass, orbital_distance, star_type)
13. Albedo = f(planet_type, atmosphere_type)
14. Equilibrium temperature = f(star_luminosity, orbital_distance, albedo)
15. Composition (iron, ice, methane, sulfur, water, carbon, organic_haze)
16. Color palette = f(composition, temperature)
17. Orbital zones (min, low, geostationary, hill sphere)

**Moon Generation (per moon):**
- Similar sequence but inherits solar_angle from parent planet

**Station Generation (per station):**
1. Determine parent body (Planet or Moon)
2. Calculate orbital distance using decision tree:
   - Priority 1: Geostationary (if within Hill sphere)
   - Priority 2: Half-Geostationary (if geo exists but outside Hill sphere)
   - Priority 3: L4 Lagrange point (if planet has moons)
   - Priority 4: Low orbit (fallback)
   - Priority 5: Custom/Manual (if specified in XML)
3. Round to nearest 1000 km
4. Set orbit_type based on which method was used 

### 1.2 Seed-Based Generation

**Universe Seed Structure:**
```xml
<universe seed="12345">
  <!-- Seed is used to initialize RNG -->
  <!-- Hash of star name provides additional entropy -->
</universe>
```

**Generation Process:**
1. Parse seed from XML (or generate random if missing)
2. Initialize RNG with seed
3. For each StarSystem:
   - Hash system name → additional entropy
   - Generate galactic coordinates (x, y, z in light-years)
   - Generate system_age = f(seed) [shared by all bodies in this system]
4. For each star in system:
   - Hash star name → additional entropy
   - Generate star properties deterministically (type, mass, radius, temperature, luminosity)
5. After all stars in system are generated:
   - Sum all star luminosities
   - Calculate habitable zone from total luminosity
6. For each planet:
   - Hash planet name → additional entropy
   - Generate planet properties deterministically
   - Calculate solar_angle = (system_age / orbital_period_days) * 360 mod 360
7. For each moon:
   - Hash moon name → additional entropy
   - Generate moon properties deterministically
   - Calculate solar_angle = (system_age / orbital_period_around_planet_days) * 360 mod 360

**Benefits:**
- Same seed + same names = same universe
- Can permute by changing seed
- Can reproduce specific universes

---

## Part 2: XML Schema Design

### 2.1 Schema Structure

**Mandatory Fields (for procedural generation):**
- `name` - Always required
- `type` (star_type/planet_type/variety) - Required for generation
- `seed` (at universe level) - Optional, generates random if missing

**Optional Fields (for manual specification):**
- All physical properties (mass, radius, density, etc.)
- All orbital properties
- All atmospheric properties
- All composition properties
- All orbital zones
- Color palette

**Schema Example:**
```xml
<universe seed="12345">
  <galaxy>
    <name>Milky Way</name>
    <type>SB</type>
    <size>L</size>
    
     <system>
       <name>Sol</name>
       <galactic_x_ly>25000</galactic_x_ly>
       <galactic_y_ly>0</galactic_y_ly>
       <galactic_z_ly>20</galactic_z_ly>
       <system_age_years>4.6e9</system_age_years>
       <habitable_zone_inner_au>0.95</habitable_zone_inner_au>
       <habitable_zone_outer_au>1.37</habitable_zone_outer_au>
       
       <star>
        <name>Sun</name>
        <type>G2V</type>
        <!-- Optional: override generated values -->
        <mass_kg>1.989e30</mass_kg>
        <radius_km>696340</radius_km>
        <temperature_k>5778</temperature_k>
         <luminosity_solar>1.0</luminosity_solar>
         <color_palette>
           <main_color>#FFF4EA</main_color>
           <hex_colors>#FFF4EA,#FFFF00,#FF8800</hex_colors>
           <pattern_name>SWIRLED</pattern_name>
         </color_palette>
       </star>
      
      <planet>
        <name>Earth</name>
        <type>TE</type>
        <!-- Optional: full manual specification -->
        <mass_kg>5.972e24</mass_kg>
        <radius_km>6371</radius_km>
        <density_kg_m3>5514</density_kg_m3>
        <orbital_distance_au>1.0</orbital_distance_au>
        <orbital_period_days>365.25</orbital_period_days>
        <rotation_period_hours>24.0</rotation_period_hours>
        <axial_tilt_deg>23.44</axial_tilt_deg>
        <albedo>0.306</albedo>
        <equilibrium_temperature_k>255</equilibrium_temperature_k>
        <atmosphere>
          <has_atmosphere>true</has_atmosphere>
          <atmosphere_type>N2_O2</atmosphere_type>
          <atmosphere_height_km>100</atmosphere_height_km>
          <surface_pressure_bar>1.013</surface_pressure_bar>
        </atmosphere>
        <composition>
          <iron_content>0.32</iron_content>
          <ice_content>0.0</ice_content>
          <has_methane>false</has_methane>
          <has_sulfur>false</has_sulfur>
          <water_coverage>0.71</water_coverage>
          <carbon_content>0.0</carbon_content>
          <organic_haze>0.0</organic_haze>
        </composition>
         <orbital_zones>
           <min_orbit_altitude_km>200</min_orbit_altitude_km>
           <low_orbit_altitude_km>400</low_orbit_altitude_km>
           <geostationary_orbit_altitude_km>35786</geostationary_orbit_altitude_km>
           <hill_sphere_radius_km>1.5e6</hill_sphere_radius_km>
         </orbital_zones>
         <solar_angle_deg>180.5</solar_angle_deg>
         <!-- Optional: override calculated position -->
       </planet>
    </system>
  </galaxy>
</universe>
```

### 2.2 Field Categories

**Category 1: Identity (Always Mandatory)**
- `name`
- `type` (star_type/planet_type/variety)

**Category 2: Generation Seeds (Optional)**
- `seed` (universe level)

**Category 3: Physical Properties (Optional)**
- `mass_kg`, `radius_km`, `density_kg_m3`, `surface_gravity_ms2`

**Category 4: Orbital Properties (Optional for planets/moons)**
- `orbital_distance_au`, `orbital_distance_km`
- `orbital_period_days`, `orbital_period_hours`
- `orbital_eccentricity`, `orbital_inclination_deg`

**Category 4b: Coordinate Systems**
- `galactic_x_ly`, `galactic_y_ly`, `galactic_z_ly` (for StarSystem - relative to galactic center)
- `system_age_years` (for StarSystem - derived from seed, shared by all bodies in system)
- `solar_angle_deg` (for planets/moons - current orbital position 0-359°)
- `habitable_zone_inner_au`, `habitable_zone_outer_au` (for StarSystem - calculated from sum of all star luminosities)

**Category 5: Rotation Properties (Optional)**
- `rotation_period_hours`, `axial_tilt_deg`, `is_tidally_locked`

**Category 6: Thermal Properties (Optional)**
- `albedo`, `equilibrium_temperature_k`

**Category 7: Atmospheric Properties (Optional)**
- `atmosphere` element with nested properties

**Category 8: Composition (Optional)**
- `composition` element with nested properties

**Category 9: Orbital Zones (Optional)**
- `orbital_zones` element with nested properties

**Category 10: Visual Properties (Optional)**
- `color_palette` element

---

## Part 3: Import/Export Functions

### 3.1 Import Strategy

**Import Process:**
1. Parse XML
2. Extract seed (or generate random)
3. For each body:
   - Check if properties are specified in XML
   - If specified: use XML values (manual specification)
   - If missing: generate using procedural rules (procedural generation)
   - Validate all fields
   - Create/update database record

**Import Function Signature:**
```python
def import_universe(
    xml_path: str,
    seed: Optional[int] = None,
    generate_missing: bool = True,
    validate: bool = True
) -> UniverseImportResult:
    """
    Import universe from XML.
    
    Args:
        xml_path: Path to XML file
        seed: Override seed from XML (optional)
        generate_missing: If True, generate missing properties procedurally
        validate: If True, validate all fields before import
    
    Returns:
        UniverseImportResult with stats and any errors
    """
```

### 3.2 Export Strategy

**Export Process:**
1. Query all universe objects from database
2. For each object:
   - Export all fields (even if generated)
   - Include seed if universe was procedurally generated
   - Preserve field order and structure
3. Generate XML with proper formatting

**Export Function Signature:**
```python
def export_universe(
    output_path: str,
    galaxy_filter: Optional[str] = None,
    system_filter: Optional[str] = None,
    include_generated: bool = True,
    compact: bool = False
) -> str:
    """
    Export universe to XML.
    
    Args:
        output_path: Path to write XML file
        galaxy_filter: Only export specific galaxy (optional)
        system_filter: Only export specific system (optional)
        include_generated: Include procedurally generated fields
        compact: Use compact XML format (no pretty-printing)
    
    Returns:
        Path to exported XML file
    """
```

### 3.3 Round-Trip Safety

**Requirements:**
1. Import → Export → Import should produce identical database state
2. All fields should be preserved
3. Seed should be preserved

**Implementation:**
- Always export all fields (even if generated)
- Use deterministic generation (same seed = same values)
- Validate on import to catch schema changes
- **No field tracking**: We don't mark which fields were generated
  - If field is in XML → use it (authoritative)
  - If field is missing → generate it procedurally
  - This keeps XML clean and human-readable

---

## Part 4: Web-Based Editor

### 4.1 Editor Requirements

**Features:**
1. **Universe Browser** - Navigate galaxies/systems/stars/planets/moons
2. **Field Editor** - Edit individual fields with validation
3. **Field Indicators** - Show mandatory vs optional fields
4. **Randomize Button** - Generate missing fields procedurally
5. **Import/Export** - Upload XML, download XML
6. **Seed Control** - View/edit universe seed

### 4.2 Field Display

**Field Categories:**
- **Mandatory** (red asterisk) - Required for generation (`name`, `type`)
- **Optional** (no indicator) - Can be left blank (will be generated if missing)
- **Present** (blue indicator) - Field is present in XML (authoritative override)
- **Generated** (green indicator) - Field was generated (not in XML, computed from seed)

**Field Editor:**
- Text inputs for strings/numbers
- Dropdowns for enums (star_type, planet_type, etc.)
- Checkboxes for booleans
- Nested forms for complex objects (atmosphere, composition, etc.)

### 4.3 Randomize Functionality

**Randomize Options:**
1. **Randomize All Missing** - Generate all optional fields
2. **Randomize Selected** - Generate only selected fields
3. **Randomize from Seed** - Use current seed
4. **Randomize New Seed** - Generate new seed and regenerate

**Implementation:**
- Call procedural generation service
- Update form fields with generated values
- User can override any generated value (becomes authoritative)
- On save: only fields explicitly set by user are included in XML
- On export: all fields are included (both user-set and generated)

### 4.4 Django Admin vs Custom Editor

**Option A: Enhance Django Admin**
- Pros: Already exists, familiar interface
- Cons: Limited customization, not specialized for universe editing

**Option B: Custom Editor Views**
- Pros: Full control, specialized UI, better UX
- Cons: More development work

**Recommendation: Custom Editor Views**
- Create dedicated views for universe editing
- Use Django admin for basic CRUD
- Custom editor for advanced features

---

## Part 5: Implementation Plan

### Phase 1: Procedural Generation Service
**File**: `mysite/universe/services/celestial_generator.py`

**Tasks:**
1. Create generation rules based on CELESTIAL_MODEL_PLAN.md
2. Implement seed-based RNG
3. Implement star generation
4. Implement planet generation
5. Implement moon generation
6. Unit tests for deterministic generation

### Phase 2: Expanded XML Schema
**Files**: 
- `docs/universe_schema.md` (schema documentation)
- Update `import_xml.py`
- Update `export_xml.py`

**Tasks:**
1. Define full XML schema with all fields
2. Update import to read all fields
3. Update export to write all fields
4. Add validation
5. Test round-trip safety

### Phase 3: Import/Export Enhancement
**Files**: 
- `mysite/universe/import_xml.py` (enhanced)
- `mysite/universe/export_xml.py` (enhanced)

**Tasks:**
1. Add seed support
2. Add procedural generation integration
3. Add field validation
4. Add round-trip testing
5. Update management commands

### Phase 4: Web-Based Editor
**Files**:
- `mysite/universe/views.py` (new editor views)
- `mysite/universe/templates/universe/editor/` (new templates)
- `mysite/universe/urls.py` (new routes)

**Tasks:**
1. Create universe browser view
2. Create field editor view
3. Add randomize functionality
4. Add import/export UI
5. Add seed control
6. Add field validation UI

### Phase 5: Testing & Validation
**Files**:
- `tests/test_universe_generation.py`
- `tests/test_xml_roundtrip.py`
- `tests/test_universe_editor.py`

**Tasks:**
1. Test procedural generation (deterministic)
2. Test XML round-trip safety
3. Test editor functionality
4. Test field validation
5. Integration tests

---

## Part 6: File Structure

```
mysite/universe/
├── services/
│   ├── celestial_generator.py      # NEW: Procedural generation
│   └── universe_seed.py           # NEW: Seed management
├── import_xml.py                  # ENHANCED: Full field import
├── export_xml.py                  # ENHANCED: Full field export
├── views.py                        # ENHANCED: Editor views
├── templates/universe/
│   ├── editor/
│   │   ├── browser.html           # NEW: Universe browser
│   │   ├── edit_star.html         # NEW: Star editor
│   │   ├── edit_planet.html       # NEW: Planet editor
│   │   └── edit_moon.html         # NEW: Moon editor
│   └── ...
├── management/commands/
│   ├── import_universe.py         # ENHANCED: Seed support
│   └── export_universe.py         # NEW: Export command
└── ...

docs/
├── universe_schema.md             # Schema docs
├── UNIVERSE_GENERATION_PLAN.md    # This file
└── ...
```

---

## Part 7: Key Design Decisions

### 7.1 Seed Storage
**Decision**: Store seed at universe level in XML, not per-body
**Rationale**: Simpler, allows per-body entropy via name hashing

### 7.2 Generated Field Tracking
**Decision**: Don't track which fields were generated (no `is_generated` flags)
**Rationale**: 
- Simpler, round-trip safe, user can override any field
- Keeps XML clean and human-readable (no boolean bloat)
- Rule: If field present in XML → use it (authoritative). If missing → generate it.
- Export always includes all fields, but we don't mark them as generated

### 7.3 Mandatory vs Optional
**Decision**: Only `name` and `type` are mandatory
**Rationale**: Everything else can be generated procedurally

### 7.4 Editor Location
**Decision**: Custom views, not Django admin
**Rationale**: Better UX, specialized for universe editing

---

## Part 8: Next Steps

1. **Review this plan** - Confirm approach
2. **Implement Phase 1** - Procedural generation service
3. **Implement Phase 2** - Expanded XML schema
4. **Implement Phase 3** - Enhanced import/export
5. **Implement Phase 4** - Web-based editor
6. **Implement Phase 5** - Testing

---

## Questions to Resolve

1. **Web Editor Priority**: Should we build the web editor now, or focus on import/export first?
2. **Seed Granularity**: Per-universe seed, or per-body seeds?
3. **Generated Field Marking**: ~~Should we mark which fields were generated in XML?~~ **RESOLVED**: No marking - if field present, use it; if missing, generate it.
4. **Validation Strictness**: How strict should field validation be?
5. **Editor UI Framework**: Use Django templates, or something more modern (React, etc.)?

