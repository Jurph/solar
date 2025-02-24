# Missions 

## Some vocabulary 

- A **mission** is the combination of a **ship**, origin, destination, and **cargo**.   
- A **cargo** is just a text string describing the contents of a ship, but it is one of the most tangible and evocative strings in our universe. "What are they carrying (and to where, and why)" drives the sense of place, and if we do this exceptionally well the world will be exciting and evocative; if we do it badly it will be boring and ungreebled.   
- A **path** is purely a navigational concept - the path between an origin and destination (it's literally just a list of graph nodes in our celestial map). 
- A set of **navigation events** (mostly "maneuvers" or "burns" for now, but later on things like "scans" or "inspections" or "local stellar survey") is a **route** and will eventually drive the **script**.  
- The **script** is the dialogue that the **characters** say (either in text or in audio) 
- We will need to be careful to deconflict how we talk about **events** as we get into the simulation, but when we do eventually have a game loop and timing, the **route** is the level at which a **path** inherits a sense of time.   

## How to Build a Mission 

But for all of that to come together, our **missions** need to be realistic. We need to avoid the "Coals to Newcastle" problem. A small ship won't carry "Bulk regolith" from a planet up to a rocky moon. We can't have bullshit origins: a "star system" is not a place you start a mission (although it might be a valid destination for a survey-and-return mission). To that end, some rules about missions, which we need to eventually capture as requirements: 

1. Missions will depend on the scale of their origin. A planet or a moon is more likely to ship bulk minerals than a space station.
2. Cargo will depend on the class of their origin. A rocky moon or silicate planet is more likely to ship bulk silicates than, say, a Gas Giant planet, or its ocean moon.
3. A cargo and path should be assigned to the right ship. Carrying diplomatic mail should be done in a very small vessel, for example, whether the path is long or short.   
4. The destination matters, too: a "local shuttle" mission almost guarantees that you are talking about a small vessel moving completely within a planet's sphere of influence - planet-to-moon, moon-to-moon, etc.
5. For now missions (and therefore paths, routes, etc.) only start and end at the planet-or-below scale.  

### Example Mission Types: 

- Local Shuttle (always small, never leaves a planetary system's local area)  
- Express Shuttle (creates a new maneuver type, DIRECT ASCENT, always small, may go planet to planet)  
- Commercial Passenger (5/75/20 large/medium/small)  
- Courier (90/10 medium/small)  
- Packaged Freight (50/40/10 large/medium/small)  
- Bulk Freight (85/15 large/medium, never leaves from a Station, only from a Planet or Moon)  
- Survey Mission (50/50 medium/small - always out to a Star or Star System carrying "Survey Crew", then back home carrying "Survey Data")  

## Selecting Cargos 

But many cargos are valid for many missions in a non-one-to-one mapping. I don't want "Medical Goods" or "Ship Parts" or "Passengers" or "Survey Data" to show up on lots of different tables ("Don't Repeat Yourself"). I want them to appear once in the data. So ultimately the right approach -- at least for now -- is to list a set of valid **mission types** and then build out from there: 

1. Generate a mission type which in turn defines constraints (e.g. "bulk freight")
2. Choose an appropriate origin for the mission type ("not a space station")
3. From the ships already at the origin planet, reach into a random grab-bag and pick an appropriate ship, or if `None` generate a random ship (this has the nice property of generating realistic ships on demand - for "bulk freight" we probably generate 85% Large ships and 15% Medium). 
4. Based on the constraints of that mission type, choose a destination ("from the set of all planets and moons that are at least 5 hops distant, pick a destination")
5. Based on the choice of origin, destination, and ship, identify which "cargo tables" the mission type can select from

### Examples of Cargo Tables 

So then I might have the following tables:
- Shuttle Passengers (Diplomats, Flight Crew, Mining Crew, Science Survey Team, Exobiologists, Commercial Passengers, Dignitaries, etc.)
- Courier Mail (Mail, Diplomatic Mail, Medical Supplies, Survey Data)
- Dense Goods (Computer parts, Mining machines, Electronics, Engine Components, "Finished Goods", Luxury Goods, Colony Supplies, etc.)
- Raw Materials ("Bulk rubidium", Fine Silicates, Regolith, Water Ice, Fuel, Liquid Methane, Grain, etc.)
- Easter Eggs / Wild Cards (Xenomorph Eggs, 3000km of Flight Line, etc.)
- Silicate Planet (regolith, sand, iron, steel, carbon fiber, etc.)
- Ice Giant Planet (water ice, methane ice, ammonia, etc.)

## Orbits and Transfers as Events 

- Departing from a Station requires that you UNDOCK before a local TRANSFER using reaction engines 
- Departing froma Moon or Planet you LAUNCH instead 
- After a LAUNCH you nearly always CIRCULARIZE with reaction engines (unless your LAUNCH maneuver is actually a DIRECT ASCENT maneuver, which takes you from one local body straight into the landing pattern of another, or straight out to a TRANSFER. A DIRECT ASCENT is disruptive and dangerous!)
- To travel between two Planets you need to do a PLANE CHANGE and then a TRANSFER, but this lets you skip the intervening Star / StarSystem - in other words, you don't really need to orbit Sol in order to go from Jupiter to Mars. Interplanetary travel within-system is done on sublight engines (.95C)  
- Entering a Planet's sphere of influence after a sublight TRANSFER you'll need to CIRCULARIZE, again on reaction engines. 
- If you are headed for a nearby Moon you can then TRANSFER directly (later on we'll check inclination to decide if a plane change is necessary). 
- After you have CIRCULARIZEd at the Planet or Moon closest to your destination you can either DOCK (at a Station) or LAND (at a Moon or Planet)
- If you need to change StarSystems, it's polite to TRANSFER to Solar Orbit around the nearest Star on sublight engines, then use a HYPERSPACE maneuver, but just like a TRANSFER lets you go planet-to-planet, a HYPERSPACE lets you go from star-to-star without ascending up to the intervening StarSystem or Galaxy node(s). You don't want to use your HYPERSPACE drive too close to a planet because the gravity well messes up the inertial calculations.   
- If you arrive in a planetary system with no colonies, no Dispatch, and no Control, it's polite to broadcast your intentions - "This is PUMA SWEDE, broadcasting my intention to land. I'll be on 57 degrees inclination inbound in one hour." But if there's no colony... why are you taking cargo there? 

## A Cleaner and More Complete List of Maneuver Rules 

1. If your path starts with a Station, UNDOCK then do an INSERTION burn and then CIRCULARIZE to orbit.  
2. If your path starts with a Moon or Planet, and the destination is a neighbor, you can do a DIRECT ASCENT followed by whatever arrival is appropriate (DOCK, or DEORBIT and LAND). This lets you skip the INSERTION and CIRCULARIZE steps, since your trip is so short.     
3. If your path starts with a Moon or Planet and your destination is not a neighbor, you'll need to LAUNCH, do an INSERTION burn, and then CIRCULARIZE to achieve orbit. 
4. Once in orbit, evaluate the scales of the two bodies that are next in your list. Transfers in the local area around a Planet (from Luna to Earth, for example, or Mars to Phobos) are SUBLIGHT and don't require a PLANE CHANGE. You can shorthand this as "if the next object in the path is a Planet, no PLANE CHANGE required".   
5. Transfers from a Planet or a Dwarf Planet (a Moon directly orbiting a Star) to anywhere outside the Planet's local scale but within the same StarSystem (Mars to Earth, Mars to Jupiter, etc.) require a PLANE CHANGE. Basically, if the next object on the path is a Star, skip the Star and deal with the StarSystem scale. Do a PLANE CHANGE and then a SUBLIGHT transfer within the StarSystem. You don't have to orbit the Star or look for a controller here! It's a Hohmann transfer and now you're at the StarSystem scale.  
6. If the object after the StarSystem is still in the same StarSystem, skip the Star and begin the arrival process. 
7. If the object after the StarSystem is in a different StarSystem, do a HYPERDRIVE transfer, skip the other StarSystem's Star, and start the arrival process.  
8. As you work your way back down the path from Star scale to your destination's scale, you'll need to finish your transfers with an INSERTION burn and then CIRCULARIZE around the Planet. You're coming from a long way away, so do a PLANE CHANGE to prepare for the rest of your trip.    
9. If the Planet is your destination you can then DEORBIT and LAND.
10. If a station in orbit around the Planet is your destination, you can DOCK.  
11. If you need to travel to the planet's Moon next, do a SUBLIGHT transfer. 
12. If the Moon is your destination, you can DEORBIT and LAND.  
13. If a station around the Moon is your destination, you can CIRCULARIZE around the Moon, do a PLANE CHANGE, and then DOCk.  


## Radio etiquette 

- Always lead with who you are talking to, and then who you are: "Control, this is PUMA SWEDE..." 
- On departure from a station you should announce your ship's name, cargo, and destination ("Control, this is PUMA SWEDE carrying Sulfur bound for Jupiter, requesting a departure time and launch vector.") 
- On arrival to a new Planet, you should also announce your name, cargo, and destination. Planetary Control stations may do a customs scan or not; their choice. 

