# Commands API Design

## Overview
A REST API for controlling the simulation from the web interface. Allows generating journeys, scheduling them, and managing the simulation queue.

## Architecture Requirements

### Global Simulation Queue
- Need a singleton `SimulationQueue` instance that persists across requests
- Simulation loop should run in a background thread/process
- Queue should be thread-safe for concurrent API access

### Command Structure
Each command is a POST request to `/api/commands/` with JSON body:
```json
{
  "command": "command_name",
  "parameters": { ... }
}
```

## Proposed Commands

### 1. `generate_journey`
Generates a ship, pilot, route, and dialogue events for a journey.

**Parameters:**
- `origin` (string, required): Location name for origin (e.g., "Mars")
- `destination` (string, required): Location name for destination (e.g., "Earth")
- `ship_name` (string, optional): Custom ship name (generated if not provided)
- `pilot_name` (string, optional): Custom pilot name (generated if not provided)
- `cargo` (string, optional): Cargo description

**Returns:**
```json
{
  "status": "success",
  "journey_id": "uuid-or-id",
  "ship": {
    "id": 123,
    "name": "Stellar Horizon"
  },
  "pilot": {
    "id": 456,
    "name": "Captain Rodriguez"
  },
  "events": [
    {
      "type": "dialogue",
      "timestamp": 0.0,
      "actor": "Captain Rodriguez",
      "text": "..."
    }
  ],
  "event_count": 7
}
```

### 2. `schedule_journey`
Schedules a journey's events in the simulation queue.

**Parameters:**
- `journey_id` (string, required): ID from generate_journey
- `start_time` (float, optional): Simulation time to start (default: "now" = 0.0 or current sim time)
- `time_offset` (float, optional): Offset from current time (e.g., 10.0 = start 10 seconds from now)

**Returns:**
```json
{
  "status": "scheduled",
  "journey_id": "uuid-or-id",
  "events_scheduled": 7,
  "start_time": 0.0
}
```

### 3. `generate_and_schedule`
Combines generate_journey and schedule_journey in one call.

**Parameters:**
- Same as `generate_journey` plus:
- `start_time` (float, optional): When to start (default: "now")
- `time_offset` (float, optional): Offset from current time

**Returns:**
- Combined response from both commands

### 4. `list_locations`
Get available locations for origin/destination selection.

**Parameters:**
- `scale` (string, optional): Filter by scale (e.g., "STATION", "PLANET", "MOON")

**Returns:**
```json
{
  "locations": [
    {
      "id": 1,
      "name": "Mars",
      "scale": "PLANET"
    },
    {
      "id": 2,
      "name": "Earth",
      "scale": "PLANET"
    }
  ]
}
```

### 5. `get_simulation_status`
Get current simulation state.

**Returns:**
```json
{
  "is_running": true,
  "current_time": 45.2,
  "queue_size": 3,
  "next_event_time": 50.0
}
```

### 6. `start_simulation`
Start the simulation loop if not already running.

**Returns:**
```json
{
  "status": "started",
  "message": "Simulation loop started"
}
```

### 7. `stop_simulation`
Stop the simulation loop.

**Returns:**
```json
{
  "status": "stopped",
  "message": "Simulation loop stopped"
}
```

## Implementation Notes

### Global Simulation Queue
- Create a singleton `GlobalSimulationQueue` class
- Use threading.Lock for thread safety
- Store in a module-level variable or Django cache

### Journey Storage
- Could store journey data temporarily (in-memory dict or cache)
- Or regenerate on schedule (simpler, stateless)

### Time Management
- Simulation time vs real time
- Need to track simulation start time
- Events scheduled with simulation timestamps

## Example Flow

1. User clicks "Generate Journey" in UI
2. UI calls `generate_and_schedule` with origin="Mars", destination="Earth"
3. API:
   - Creates ship and pilot
   - Plans route
   - Generates dialogue events
   - Adds events to global queue with timestamps
4. Simulation loop processes events
5. Events appear in scroller via DialogueEventLog

