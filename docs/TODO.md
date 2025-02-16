# Solar 
## a procedural space system builder 

## vision:

The air in the cockpit smells like azide and sweat and hot electronics. The nav computer's analog display rattles as the new course rolls across the console and gradually emerges from the chaos of clacking. The comm chirps a friendly tone and a welcoming voice says "Commercial tanker PULP NOVELLA, this is Titan Control, please acknowledge." 

The grimy cluttered controls of a real commercial aircraft, of the interior of the Millenium Falcon, of the crew's mess in the NOSTROMO; the sounds of modems and elevators and public transportation and rocket launches. The painstaking precision of NASA astronauts going over hour-long preflight checklists, and the almost-bored voices of fighter pilots as they report the loss of an engine out over open water. The lullabye singsong of the Shipping News reporting dangerous weather off Dogger Bank in a terse jargon that might be another language. The constant fight against rust and mechanical failure. A galaxy where space travel is casual but still perilous, and where the routine of hundreds of other ships following it can inspire you to try something boring for fun. 

## Features on my road-map: 

- Project infrastructure 
    - "Installer" scripts that make deploying straight from Git reliable 
    - Unit Tests that Always Pass (doo-dah, doo-dah)
    - Maybe some kind of CI/CD setup 
    - Figure out how to interact with Django and the sqlite DB for testing 

- Stars, planets, moons, and space stations 
    - Just our solar system first ✓
    - XML import/export tooling ✓
    - Planetary science and classification
        - Define taxonomy of planet types (terrestrial, gas giant, etc.) ✓
        - Geological composition and features
        - Atmospheric conditions
        - Resource distributions
    - Procedurally generated via physics rules later 
        - Add orbital parameters to celestial bodies
            - Mean orbital distance (AU) for basic sorting
            - Full Keplerian elements (eccentricity, inclination)
            - Orbital period calculations
        - Automatic sorting of bodies by orbital distance
        - Lagrange point calculations
        - Transfer orbit planning
        - Generate realistic planetary compositions
    - Data management
        - Exports based on planetary minerals 
        - Imports based on regional economy/scarcity 
- Ships 
    - "Grab bag" random naming at first ✓
    - Very little concept of roles/classes/sizes ✓
    - Procedurally named with random cargos & missions ✓  
    - Eventually assigned economically-relevant cargos & missions 
    - Eventually procedurally generated as make/model, sold by particular shipyards, more common "near home" 

- Events 
    - Grab bag procedural at first 
    - Anomalies a great place to explore complexity 
    - When ships have parts, some anomalies will come from "cheap" parts or "too new" technologies 
    - Eventually generated in response to a ship moving along its journey 
    - Until we have text-to-speech or pilot voices, a scrolling "terminal" you can read 

- Comms 
    - Text first, voice soon! ✓
    - Meant to sound like air traffic control ✓
    - Scripted or procedural at first ✓
    - Uses GPT-style generative dialogue eventually 
    - Text-to-voice? Pilot personalities? 
    - Realistic static, Apollo-style BEEPs, modem noises 

- Characters
    - Procedurally generated pilots and dispatchers 
    - Generate a character name, personality sketch, "sloppiness" concept 
    - Use this to build a prompt for a tiny local LLM 
    - LLM uses the scripted lines as a guide but reads them "in character", responding to the previous message
    - Ideally each character also gets a fixed voice model configuration that sticks with them 

- Playing the game 
    - What game? This is literally an enormous complex procedural generation engine to create realistic shipping traffic so I can have a relaxing futuristic background. This will be v1.0 **playable** when I can listen to ships talking to one another like a long relaxing radio drama, with no idea what will happen next.  

## TODO: 

### One - Fiat Lux ✓
- Successfully populate a solar system data structure ✓
- Randomly generate a solar system other than earth's ✓
- Visualize a simple universe ✓

### Two - First Flight 
- Procedurally generate ship names for scripted events ✓
- Move a ship from one planet to another with a random cargo ✓
- Script the "arrival" and "departure" event categories ✓
- Orchestrator/timer/scheduler fires off randomized events 
- Visualize ship traffic 

### Three - the Leap to ML 
- Script a small number of "anomalies" with simple resolutions 
- Build out source files for ship names, planets, stars &c. ✓
- Persistent characters with personality notes 
- Get a local LLM to respond to dialogue prompts "in character" 

### Four - Vox Populi 
- Text to speech first efforts 
- Are SOTA voices good enough? 
- Simple sound generation 
- Beeps, garbles, other fun trimmings 
- Could theoretically _live stream_ this output for fun 

### Five - Fiat Luxury 
- Identify physics process for realistic solar system creation 
- Try something else procedural: ship classes and designs maybe? 
- Add a shipping economy so traffic feels more realistic 

### Six - Let's Get Real 
- J.R. probably won't finish this game on his own 
- Persistent ships? Letting players follow ships to different places to hear more of the story? Who knows? 