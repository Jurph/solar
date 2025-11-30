# Scrolling Text Window Feature - Implementation Plan

## Overview
Implement a real-time scrolling text display that shows dialogue events as they occur in the simulation. The display will poll for new events and append them to a terminal-like interface, providing an ambient view of space traffic communications.

## Architecture Approach
- **Data Layer**: Django model to persist dialogue events to database
- **Signal Layer**: Django signal receiver to capture processed dialogue events
- **API Layer**: JSON endpoint for polling new events
- **View Layer**: Template-based HTML page with JavaScript polling
- **Presentation**: Terminal-style CSS styling

---

## Task 1: Create Dialogue Event Persistence Model

### Objective
Create a simple Django model to store dialogue events temporarily in SQLite for real-time display. Events are ephemeral and don't need long-term persistence.

### Requirements
- Store minimal dialogue event data: timestamp, actor name, message text
- Include created_at timestamp for ordering and potential cleanup
- Simple structure suitable for SQLite
- No complex relationships needed (events are temporary)

### Implementation Details
- **File**: `mysite/universe/models/event.py` (add Django model class)
- **Model Name**: `DialogueEventLog` (to avoid conflict with existing `DialogueEvent` dataclass)
- **Fields**:
  - `timestamp` (FloatField) - Simulation time when event occurred
  - `actor_name` (CharField, max_length=200) - Name of the speaking actor
  - `text` (TextField) - The dialogue message
  - `created_at` (DateTimeField, auto_now_add=True) - Database insertion time for ordering/cleanup
- **Indexes**: Simple index on `timestamp` for query performance (optional but recommended)
- **Note**: No ForeignKey relationships needed - actor_name as string is sufficient for ephemeral storage

### Dependencies
- Django models infrastructure (already exists)
- SQLite database (default Django setup)

### Acceptance Criteria
- Model can be created via migrations
- Model can store dialogue events with timestamp, actor_name, and text
- Queries by timestamp work correctly

---

## Task 2: Implement Signal Receiver for Event Persistence

### Objective
Automatically save dialogue events to the database when they are processed by the simulation queue.

### Requirements
- Listen to `dialogue_event_processed` signal
- Convert `DialogueEvent` dataclass to `DialogueEventLog` model instance
- Handle errors gracefully (log but don't crash simulation)
- Support both structured and unstructured metadata

### Implementation Details
- **File**: `mysite/universe/signals.py` (add receiver function) or create new `mysite/universe/receivers.py`
- **Signal**: `dialogue_event_processed` (already defined in `mysite/universe/signals.py`)
- **Receiver Function**: `save_dialogue_event_to_db(sender, event, **kwargs)`
- **Logic**:
  - Extract actor name from `event.actor.name`
  - Extract text from `event.text`
  - Extract timestamp from `event.timestamp`
  - Create `DialogueEventLog` instance with minimal fields
  - Save to database with error handling (log errors but don't crash simulation)

### Dependencies
- Task 1 complete (DialogueEventLog model exists)
- `dialogue_event_processed` signal (already exists)
- Django signals infrastructure

### Acceptance Criteria
- Dialogue events are automatically saved when processed
- Errors in saving don't interrupt simulation
- All dialogue event fields are preserved

---

## Task 3: Create Event Feed API Endpoint

### Objective
Provide a JSON API endpoint that returns dialogue events for the web interface to poll.

### Requirements
- Return events ordered by timestamp
- Support pagination or "since timestamp" filtering
- Return only essential fields (id, timestamp, actor_name, text)
- Handle empty result sets gracefully
- Efficient querying (index on timestamp recommended)

### Implementation Details
- **File**: `mysite/universe/views/events.py` (already exists, needs completion)
- **Function**: `event_feed(request)` (already defined, needs implementation)
- **URL Route**: `/api/events/` (uncomment in `mysite/urls.py`)
- **Query Parameters**:
  - `since` (optional float) - Return events with timestamp >= since
  - `limit` (optional int, default=100) - Maximum events to return
- **Response Format**:
  ```json
  {
    "events": [
      {
        "id": 1,
        "timestamp": 123.45,
        "actor_name": "PILOT NAME",
        "text": "Control, this is PILOT NAME, requesting clearance."
      }
    ],
    "latest_timestamp": 123.45
  }
  ```
- **Query Logic**:
  - Filter `DialogueEventLog.objects` by timestamp if `since` provided
  - Order by `timestamp` ascending
  - Limit results
  - Return JSON response

### Dependencies
- Task 1 complete (DialogueEventLog model exists)
- Django views infrastructure
- URL routing configured

### Acceptance Criteria
- Endpoint returns valid JSON
- Events are ordered chronologically
- Filtering by timestamp works correctly
- Empty result sets return empty array
- Response format matches specification

---

## Task 4: Create Event Scroller View and Template

### Objective
Create the HTML page that displays the scrolling dialogue log.

### Requirements
- Render a full-page template with scrolling text area
- Include JavaScript for polling the API
- Display events in chronological order
- Auto-scroll to newest events
- Format speaker names in ALL CAPS (per spec)
- Show timestamps in readable format

### Implementation Details
- **View File**: `mysite/universe/views/events.py`
- **Function**: `event_scroller(request)` (already defined, needs template)
- **Template File**: `mysite/universe/templates/universe/event_scroller.html` (create new)
- **Template Structure**:
  - Extends `base.html` or standalone
  - Container div for event log
  - JavaScript section for polling logic
- **JavaScript Requirements**:
  - Poll `/api/events/` every 1-2 seconds
  - Track last seen timestamp to avoid duplicates
  - Append new events to DOM
  - Auto-scroll container to bottom
  - Format: `[HH:MM:SS] SPEAKER_NAME: message text`
- **URL Route**: `/events/` (uncomment in `mysite/urls.py`)

### Dependencies
- Task 3 complete (event_feed API working)
- Django templates infrastructure
- Base template (if extending)

### Acceptance Criteria
- Page loads and displays events
- New events appear automatically
- Speaker names are in ALL CAPS
- Timestamps are human-readable
- Auto-scrolling works smoothly

---

## Task 5: Implement Terminal Styling

### Objective
Style the event scroller to look like a terminal/console interface.

### Requirements
- Monospace font family
- Dark background (black or dark gray)
- Light text (green, amber, or white)
- Scrollable container with fixed height
- Optional: subtle visual effects (scanlines, glow)

### Implementation Details
- **File**: `mysite/universe/static/universe/css/event_scroller.css` (create new)
- **Or**: Add styles to existing `mysite/universe/static/universe/css/style.css`
- **CSS Classes**:
  - `.event-scroller-container` - Main container with fixed height, overflow-y scroll
  - `.event-line` - Individual event line styling
  - `.event-timestamp` - Timestamp styling (muted color)
  - `.event-speaker` - Speaker name styling (ALL CAPS, bold, distinct color)
  - `.event-text` - Message text styling
- **Color Scheme**:
  - Background: `#000000` or `#0a0a0a`
  - Text: `#00ff00` (green) or `#ffff00` (amber) or `#ffffff` (white)
  - Timestamp: Muted version of text color
  - Speaker: Distinct color or bold variant

### Dependencies
- Task 4 complete (template exists)
- Django static files infrastructure

### Acceptance Criteria
- Page looks like a terminal/console
- Text is readable
- Scrolling is smooth
- Styling is consistent

---

## Task 6: Wire Up URL Routing

### Objective
Enable the event scroller and API endpoints via URL configuration.

### Requirements
- Uncomment existing route definitions
- Ensure proper URL patterns
- Test that routes are accessible

### Implementation Details
- **File**: `mysite/urls.py`
- **Changes**:
  - Uncomment `path("events/", event_scroller, name="event_scroller")`
  - Uncomment `path("api/events/", event_feed, name="event_feed")`
  - Ensure imports are correct from `mysite.universe.views.events`

### Dependencies
- Task 3 complete (event_feed function)
- Task 4 complete (event_scroller function)
- Django URL routing

### Acceptance Criteria
- `/events/` loads the scroller page
- `/api/events/` returns JSON
- URLs are accessible without errors

---

## Testing Checklist

### Unit Tests
- [ ] DialogueEventLog model can be created and queried
- [ ] Signal receiver saves events correctly
- [ ] event_feed returns correct JSON format
- [ ] event_feed filters by timestamp correctly

### Integration Tests
- [ ] Events processed by simulation appear in database
- [ ] API endpoint returns events in correct order
- [ ] JavaScript polling retrieves new events
- [ ] Page displays events correctly

### Manual Testing
- [ ] Start simulation with `character_dialogue_demo` command
- [ ] Open `/events/` in browser
- [ ] Verify events appear as they are processed
- [ ] Verify auto-scrolling works
- [ ] Verify styling looks like terminal

---

## Implementation Order

1. **Task 1** - Create model (foundation)
2. **Task 2** - Wire up signal receiver (data flow)
3. **Task 3** - Create API endpoint (data access)
4. **Task 6** - Wire up URLs (enable endpoints)
5. **Task 4** - Create template and JavaScript (user interface)
6. **Task 5** - Add styling (polish)

---

## Notes

- The existing `DialogueEvent` dataclass in `models/event.py` should remain unchanged - it's the in-memory representation
- The new `DialogueEventLog` model is a simple ephemeral storage solution for real-time display
- Signal receiver bridges the gap between in-memory events and database storage
- Events are temporary - no need for complex relationships or extensive metadata
- Optional: Add a cleanup mechanism (e.g., delete events older than 1 hour) if database grows too large
- Consider adding a simple index on `timestamp` for query performance
- Future enhancement: WebSocket/SSE for real-time updates instead of polling
- Future enhancement: Pause/play controls for the scroller
- Future enhancement: Filter by actor or event type

