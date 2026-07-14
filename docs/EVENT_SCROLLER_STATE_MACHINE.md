# Event Scroller State Machine

The event scroller is a time-gated display loop with an audio-ready gate in
front of normal text rendering. Its job is to show mission dialogue in
simulation order without letting text outrun the pre-rendered radio audio.

## Core State

- `lastEventCursor`: `(timestamp, id)` cursor for paginated event polling.
- `eventQueue`: events ready for display and optional audio playback.
- `waitingAudio`: events due for display but blocked on rendered audio.
- `lastAudioCheck`: per-event rate limiter for audio readiness checks.
- `inflightAudioChecks`: guards against duplicate HEAD checks for one event.
- `displayedEventIds`: client-side duplicate suppression.

## Waiting Audio Enqueue

An event enters `waitingAudio` when it is due for display, audio is enabled, and
the server says its audio is not ready yet. The scroller stores the event with
an `addedAt` timestamp so it can log long waits and eventually time out to
text-only display.

Historical catch-up mode is the exception: events from before page load can
display quickly without waiting for audio. Muted or disabled audio also bypasses
the audio gate.

## HEAD 202 Retry

The scroller only probes the earliest waiting event. It sends a `HEAD` request
to that event's `audio_url` no more than once every two seconds, and it will not
start another request while one is already in flight for the same event.

Status meanings:

- `200`: audio is ready; promote the event to `eventQueue`.
- `202`: worker is still generating; keep the event in `waitingAudio`.
- `404`: unexpected missing audio URL target; keep waiting and log it.
- other status or fetch error: log the failure and retry on a later poll.

## Promotion On 200

When a HEAD request returns `200`, the scroller marks the event `audio_ready`,
pushes it onto `eventQueue`, removes it from `waitingAudio`, and calls
`processNextEvent()`. `processNextEvent()` enqueues the WAV before typing the
line so playback and text stay aligned.

Fresh `/api/events/` poll responses can also update a waiting event's
`audio_ready`, `audio_url`, and duration fields. If the earliest waiting event
is already marked ready by a poll response, it is promoted without another HEAD
request.

## Clear-All Reset

After `clear-all-events` succeeds, the client calls `resetClientEventState()`.
That clears:

- displayed DOM lines
- `eventQueue`
- `displayedEventIds`
- `lastEventCursor`
- `waitingAudio`
- `lastAudioCheck`
- `inflightAudioChecks`
- typing and fetch guards

The reset sets `pageLoadSimTime` to the current simulation time and treats the
next poll as a fresh timeline. The JavaScript expects the backend event table to
be empty or repopulated with new events after this point; old cursor state must
not survive the reset.
