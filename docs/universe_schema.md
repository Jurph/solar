# Universe XML Schema Reference

## Overview
This schema defines the permanent structure of the universe: galaxies, star systems, stars, planets, moons, and stations.

## Example Structure
```xml
<universe>
  <galaxy>
    <name>Milky Way</name>
    <scale>GX</scale>
    <type>SB</type>  <!-- Barred Spiral -->
    <size>L</size>   <!-- Large -->
    
    <system>
      <name>Sol</name>
      <scale>SY</scale>
      
      <star>
        <name>Sun</name>
        <scale>SR</scale>
        <type>G2V</type>
        <magnitude>4.31</magnitude>
        
        <planet>
          <name>Earth</name>
          <scale>PL</scale>
          <type>TE</type>  <!-- Terrestrial -->
          
          <moon>
            <name>Luna</name>
            <scale>MN</scale>
            <variety>R</variety>  <!-- Rocky -->
          </moon>
          
          <station>
            <name>International Space Station</name>
            <scale>SS</scale>
            <large_berths>1</large_berths>
            <medium_berths>2</medium_berths>
            <small_berths>8</small_berths>
          </station>
        </planet>
      </star>
    </system>
  </galaxy>
</universe>
```

## Valid Values

### Scale Types (Location.Scale)
- GX: Galaxy
- SY: Star System
- SR: Star
- PL: Planet
- MN: Moon
- SS: Space Station

### Galaxy Types
- CD: Supergiant Elliptical Type cD
- DW: Dwarf
- E0: Elliptical - Sphere
- E7: Elliptical - Elongated
- IR: Irregular Type i
- IT: Irregular Type ii
- LN: Lenticular
- SB: Barred Spiral
- SH: Elliptical Shell
- SP: Spiral Arm
- SS: Superluminous Spiral
- UD: Ultra Diffuse

### Galaxy Sizes
- D: Dwarf
- S: Small
- M: Medium
- L: Large
- X: Extra Large
- G: Supergiant

### Planet Types
- MP: Mesoplanet (e.g. Pluto, Ceres)
- SI: Silicate (e.g. Mercury, Mars)
- TE: Terrestrial (e.g. Earth)
- SE: Super-earth (e.g. HD 20794 d) 
- CT: Cthonian (see https://en.wikipedia.org/wiki/Chthonian_planet)
- IG: Ice Giant (e.g. Uranus and Neptune)
- GG: Gas Giant (e.g. Jupiter)
- AB: Asteroid Belt (e.g. Kuiper Belt)

### Moon Varieties
- R: Rocky (e.g., Luna)
- I: Icy (e.g., Europa)
- O: Organic (e.g., Titan)
- T: Terrestrial ("Earth-like")

## Validation Rules
1. All elements must include name and scale attributes
2. Stations may only be attached to Stars, Planets, or Moons
3. Moons may orbit any celestial body (Planet or Star)
4. Each object must have valid parent relationship (orbits)
5. Scale types must match their element type
6. All enumerated values must match their defined choices