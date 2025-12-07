# Citation Inventory and Bibliography Cross-Reference

This document inventories all peer-reviewed citations found in the codebase and cross-references them with the bibliography folder.

## Citations Found in Codebase

### procedural_generation.py

#### Star Generation
- **Baraffe et al. 2015** - Star mass ranges (line 261)
  - Status: ❌ NOT in bibliography

#### Planet Type Generation
- **Seager et al. 2007** - Mass-radius relationships showing composition zones (line 334)
  - Status: ❌ NOT in bibliography (but Seager & Deming 2010 is)
- **Fulton et al. 2017** - "Radius gap" at ~1.5-2.0 Earth radii (line 336)
  - Status: ❌ NOT in bibliography
- **Petigura et al. 2022** - Small planets (<1.4 R_Earth) peak around 1-2 Earth radii (line 337)
  - Status: ❌ NOT in bibliography
- **Petigura et al. 2013** - Close-in planets tend to be rocky or "hot Jupiters" (line 349)
  - Status: ❌ NOT in bibliography
- **Batygin et al. 2016** - Cthonian (stripped gas giant cores) (line 354)
  - Status: ❌ NOT in bibliography
- **Howard et al. 2012** - Planet occurrence peaks for small planets at short periods (line 360)
  - Status: ❌ NOT in bibliography
- **Fressin et al. 2013** - Super-Earths most common (line 363)
  - Status: ❌ NOT in bibliography
- **Dressing & Charbonneau 2015** - Earth-sized planets common in HZ of M-dwarfs (line 370)
  - Status: ❌ NOT in bibliography
- **Cumming et al. 2008** - Giant planet frequency ~10-20% of stars (line 391)
  - Status: ❌ NOT in bibliography
- **Johnson et al. 2010** - Giant planet occurrence increases with stellar metallicity (line 338, 482)
  - Status: ❌ NOT in bibliography
- **Laughlin et al. 2004** - M-dwarfs have fewer gas giants (line 483)
  - Status: ❌ NOT in bibliography

#### Orbital Mechanics
- **Domingos et al. 2006** - Stable orbits typically exist only within ~1/3 to 1/2 of Hill radius (line 752)
  - Status: ❌ NOT in bibliography
- **Murray & Dermott 1999** - Tidal locking timescale (line 782, 798)
  - Status: ❌ NOT in bibliography

#### Atmosphere Generation
- **Zahnle & Catling 2017** - Atmospheric evolution of terrestrial planets (line 847)
  - Status: ✅ IN bibliography (`2017 - Zahnle + Catling - Cosmic Shoreline.pdf`)
- **Seager & Deming 2010** - Exoplanet atmospheres composition and retention (line 848)
  - Status: ✅ IN bibliography (`2010 - Seager + Deming - Exoplanet Atmospheres.pdf`)
- **Lopez & Fortney 2014** - H/He envelope retention on super-Earths (line 849)
  - Status: ❌ NOT in bibliography
- **Owen & Wu 2017** - Atmospheric escape and the radius valley (line 850)
  - Status: ✅ IN bibliography (`2019 - Owen - Atmospheric Escape and the Evolution of Close-in Exoplanets.pdf`)
  - Note: Year mismatch (2017 vs 2019) - may be different paper
- **Kasting et al. 1993** - Habitable zones and atmospheric limits (line 851)
  - Status: ❌ NOT in bibliography (but Kopparapu et al. 2013 on habitable zones is)
- **Walker 1977** - Jeans escape criterion (mentioned in `can_retain_atmosphere()`)
  - Status: ❌ NOT in bibliography

### MILKYWAY_V005_DATA_SOURCES.md

- **Burgasser & Mamajek 2017** - TRAPPIST-1 age (~7.6 Gyr) (line 73)
  - Status: ❌ NOT in bibliography
- **Pagano et al. 2015** - Tau Ceti age (~5.8 Gyr) (line 74)
  - Status: ❌ NOT in bibliography

## Bibliography Folder Contents

1. ✅ **2010 - Seager + Deming - Exoplanet Atmospheres.pdf**
   - Used in: procedural_generation.py (atmosphere generation)

2. ✅ **2013 - Kopparapu et al - Habitable Zones Around Main-Sequence Stars.pdf**
   - Not directly cited in code, but related to Kasting et al. 1993

3. ✅ **2017 - Zahnle + Catling - Cosmic Shoreline.pdf**
   - Used in: procedural_generation.py (atmosphere generation)

4. ✅ **2018 - Schlichting - Formation of Super-Earths.pdf**
   - Not directly cited in code

5. ✅ **2019 - Owen - Atmospheric Escape and the Evolution of Close-in Exoplanets.pdf**
   - Used in: procedural_generation.py (cited as "Owen & Wu 2017" - year mismatch)

6. ✅ **2023 - Affolter et al - Planetary Evolution with Atmospheric Photoevaporation II.pdf**
   - Not directly cited in code

## Missing from Bibliography

### High Priority (Directly Used in Code)
1. **Baraffe et al. 2015** - Star mass ranges
2. **Seager et al. 2007** - Mass-radius relationships (different from Seager & Deming 2010)
3. **Fulton et al. 2017** - Radius gap
4. **Petigura et al. 2013** or **Petigura et al. 2022** - Planet occurrence statistics
5. **Johnson et al. 2010** - Giant planet occurrence vs. metallicity
6. **Laughlin et al. 2004** - M-dwarf gas giant frequency
7. **Lopez & Fortney 2014** - H/He envelope retention on super-Earths
8. **Murray & Dermott 1999** - Tidal locking timescale (textbook)
9. **Domingos et al. 2006** - Hill sphere stability
10. **Walker 1977** - Jeans escape criterion

### Medium Priority (Supporting Data)
11. **Batygin et al. 2016** - Cthonian planets
12. **Howard et al. 2012** - Planet occurrence at short periods
13. **Fressin et al. 2013** - Super-Earth frequency
14. **Dressing & Charbonneau 2015** - M-dwarf habitable zone planets
15. **Cumming et al. 2008** - Giant planet frequency
16. **Kasting et al. 1993** - Habitable zones (classic paper, may be superseded by Kopparapu et al. 2013)

### Low Priority (Data Sources, Not Generation)
17. **Burgasser & Mamajek 2017** - TRAPPIST-1 age
18. **Pagano et al. 2015** - Tau Ceti age

## Recommendations

1. **Add missing high-priority papers** to bibliography folder, especially:
   - Baraffe et al. 2015 (star masses)
   - Seager et al. 2007 (mass-radius relationships)
   - Fulton et al. 2017 (radius gap)
   - Johnson et al. 2010 (giant planet occurrence)
   - Lopez & Fortney 2014 (super-Earth atmospheres)
   - Murray & Dermott 1999 (tidal locking - textbook)

2. **Clarify citation year mismatch**: 
   - Code cites "Owen & Wu 2017" but bibliography has "2019 - Owen"
   - Verify if these are the same paper or different

3. **Consider adding**:
   - Walker 1977 (Jeans escape - classic paper)
   - Domingos et al. 2006 (Hill sphere stability)

4. **Update code citations** to match bibliography filenames where appropriate

