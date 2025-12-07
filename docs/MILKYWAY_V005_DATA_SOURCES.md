# Milkyway v005 Data Sources

## Overview
This document lists the sources for astronomical data used in `xml/milkyway-v005.xml`.

## Coordinate System
- **Galactocentric Cartesian coordinates**: X points from galactic center toward Sol, Y in direction of galactic rotation, Z toward north galactic pole
- **Sol position**: X ≈ 27,000 ly from galactic center, Z ≈ 65 ly above galactic plane
- **Other star positions**: Calculated from galactic longitude (l), latitude (b), and distance using standard spherical-to-Cartesian conversion, then translated to galactocentric frame

## Sol System Data Sources

### Primary Sources
- **NASA Planetary Fact Sheets**: https://nssdc.gsfc.nasa.gov/planetary/factsheet/
- **JPL Solar System Dynamics**: https://ssd.jpl.nasa.gov/
- **IAU Astronomical Constants**: https://www.iau.org/

### Solar Data
- Mass, radius, temperature, luminosity: NASA Sun Fact Sheet

### Planetary Data
- Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune: NASA Planetary Fact Sheets
- Orbital elements: JPL Horizons ephemeris system

### Moon Data
- Luna: NASA Moon Fact Sheet
- Galilean moons (Io, Europa, Ganymede, Callisto): NASA Jupiter Moons Fact Sheet
- Titan, Enceladus: NASA Saturn Moons Fact Sheet
- Uranian moons: NASA Uranus Moons Fact Sheet
- Triton: NASA Neptune Moons Fact Sheet
- Phobos, Deimos: NASA Mars Moons Fact Sheet

### Dwarf Planet Data
- Pluto: NASA Pluto Fact Sheet, New Horizons mission data
- Ceres: NASA Ceres Fact Sheet, Dawn mission data

## Stellar Neighbor Data Sources

### Primary Sources
- **SIMBAD Astronomical Database**: https://simbad.u-strasbg.fr/
- **Gaia DR3 Catalog**: ESA Gaia mission parallax and position data
- **RECONS (Research Consortium on Nearby Stars)**: http://www.recons.org/

### Individual Stars
| Star | Distance (ly) | Primary Source |
|------|---------------|----------------|
| Proxima Centauri | 4.24 | Gaia DR3 |
| Alpha Centauri A/B | 4.37 | Gaia DR3, SIMBAD |
| Barnard's Star | 5.96 | Gaia DR3 |
| Wolf 359 | 7.9 | Gaia DR3 |
| Sirius A/B | 8.6 | Gaia DR3, SIMBAD |
| Epsilon Eridani | 10.5 | Gaia DR3 |
| 61 Cygni A/B | 11.4 | Gaia DR3 |
| Tau Ceti | 11.9 | Gaia DR3 |
| Altair | 16.7 | Gaia DR3 |
| Vega | 25.0 | Gaia DR3 |
| Fomalhaut | 25.1 | Gaia DR3 |
| Gliese 581 | 20.4 | Gaia DR3 |
| TRAPPIST-1 | 39.6 | Gaia DR3, TRAPPIST survey |
| HD 40307 | 42 | Gaia DR3 |
| Kepler-186 | 582 | Kepler mission, Gaia DR3 |

### Stellar Properties
- Spectral types, magnitudes: SIMBAD
- Masses, radii: Derived from spectral type or direct measurement where available
- Temperatures, luminosities: Derived from spectral type using standard stellar models
- Ages: Various sources (noted below)

### Stellar Age Sources
- Sol: Radioactive dating of meteorites (~4.6 Gyr)
- Proxima Centauri: Activity-based age estimates (~4.9 Gyr)
- Alpha Centauri: Chromospheric activity, asteroseismology (~5-6 Gyr)
- TRAPPIST-1: Burgasser & Mamajek 2017 (~7.6 Gyr)
- Tau Ceti: Pagano et al. 2015 (~5.8 Gyr)
- Sirius: Age of Sirius B white dwarf + main sequence lifetime (~240 Myr)
- Barnard's Star: Kinematics suggest thick disk membership (~10 Gyr)
- Other stars: Standard age-activity-rotation relationships

## Exoplanet Data
- Exoplanet properties left minimal (type only) for procedural generation
- Planet types assigned based on confirmed/candidate status from NASA Exoplanet Archive

## Composition Data

### Earth Composition
- Iron content (~32% by mass): Geochemical models
- Water coverage (71%): USGS/NOAA satellite data

### Other Bodies
- Composition estimates based on:
  - Spectroscopic observations
  - Density measurements
  - Theoretical models
  - Mission data (Cassini, Juno, New Horizons, Dawn, etc.)

## Notes

### Uncertainties
- Exoplanet data has significant uncertainties; values left for procedural generation
- Some stellar ages are estimates with large error bars
- Galactic coordinates computed from observational data with inherent parallax uncertainties

### Updates
- Data reflects knowledge as of 2024
- Some values rounded for practical use in simulation

