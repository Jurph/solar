        // Configuration
        const POLL_INTERVAL = 1000; // Poll for new events every 1 second
        const STATUS_POLL_INTERVAL = 2000; // Poll server for status every 2 seconds
        const DISPLAY_UPDATE_INTERVAL = 200; // Update display at 5Hz for smooth countdown
        
        // State
        // Cursor for event pagination:
        // We use (timestamp, id) so insertion order can't cause permanently skipped events.
        let lastEventCursor = null; // { timestamp: number, id: number } | null
        let isPolling = true;
        let eventQueue = []; // Queue for events to type out sequentially
        let isTyping = false; // Track if we're currently typing an event
        let isFetching = false; // Prevent concurrent fetches
        let currentTimeScale = 1.0;
        let currentSimTime = 0.0;
        let displayedEventIds = new Set(); // Track which events have been displayed
        let pageLoadSimTime = null; // Simulation time when page loaded (for catch-up mode)
        let catchUpComplete = false; // True once we've caught up to real-time
        
        // For smooth countdown interpolation
        let lastStatusFetchTime = null; // Wall-clock time of last status fetch
        let lastFetchedSimTime = null; // Sim time at last fetch
        let nextEventTimestamp = null; // Timestamp of next pending event
        let pendingEventCount = 0; // Number of pending events
        let ttsQueuePending = 0; // Number of events waiting for TTS generation
        let ttsQueueCached = 0; // Number of events with TTS already cached
        let waitingAudio = new Map(); // event_id -> {event: Event, addedAt: number} awaiting audio_ready
        let lastAudioCheck = new Map(); // event_id -> timestamp of last HEAD request
        let inflightAudioChecks = new Set(); // event IDs currently being checked
        // NO TIMEOUT: If audio is enabled, we wait indefinitely for TTS. If TTS is stuck, we debug it.
        
        // DOM elements
        const eventLog = document.getElementById('eventLog');
        const eventContainer = document.getElementById('eventContainer');
        const clearEventsButton = document.getElementById('clearEventsButton');
        const clearDisplayButton = document.getElementById('clearDisplayButton');
        const spawnCargoShipButton = document.getElementById('spawnCargoShipButton');
        const spawnNavsatButton = document.getElementById('spawnNavsatButton');
        const skipToNextButton = document.getElementById('skipToNextButton');
        const simTimeDisplay = document.getElementById('simTimeDisplay');
        const timeScaleDisplay = document.getElementById('timeScaleDisplay');
        const llmStatusDisplay = document.getElementById('llmStatusDisplay');
        const ttsStatusDisplay = document.getElementById('ttsStatusDisplay');
        const pendingEventsDisplay = document.getElementById('pendingEventsDisplay');
        const nextEventDisplay = document.getElementById('nextEventDisplay');
        const scaleBtns = document.querySelectorAll('.scale-btn');
        const audioEnableButton = document.getElementById('audioEnableButton');
        const audioVolumeInput = document.getElementById('audioVolume');

        // Audio (playback only; synthesis is defined in Python and served as WAV)
        const audioPlayer = new AudioPlayer();
        const AUDIO_STORAGE_KEYS = {
            volume: "events_audio_volume",
            enabledHint: "events_audio_enabled_hint",
            muted: "events_audio_muted",
        };

        function audioPresetUrl(preset, params) {
            let url = AUDIO_PRESET_URL_TEMPLATE.replace("__PRESET__", preset);
            if (params && typeof params === 'object') {
                const queryParams = new URLSearchParams();
                for (const [key, value] of Object.entries(params)) {
                    if (value !== null && value !== undefined) {
                        queryParams.append(key, String(value));
                    }
                }
                if (queryParams.toString()) {
                    url += '?' + queryParams.toString();
                }
            }
            return url;
        }

        function audioRequired() {
            return audioPlayer.isEnabled() && !audioPlayer.isMuted();
        }

        function moveEventToWaitingAudio(event, reason, { requeue = false } = {}) {
            console.warn(
                `[WAITING] Event ${event.id} moved to waitingAudio: ${reason} ` +
                `(audio_url=${!!event.audio_url}, audio_ready=${event.audio_ready})`
            );
            waitingAudio.set(event.id, { event: event, addedAt: Date.now() });
            if (requeue) {
                eventQueue.unshift(event);
            }
        }

        function findNextWaitingAudioCandidate(now = Date.now()) {
            let nextEvent = null;
            let nextEventId = null;

            for (const [id, waitingData] of waitingAudio.entries()) {
                const ev = waitingData.event;
                const waitTime = now - waitingData.addedAt;

                if (!nextEvent || ev.timestamp < nextEvent.timestamp) {
                    nextEvent = ev;
                    nextEventId = id;
                }

                if (!ev.audio_ready && waitTime > 10000 && waitTime % 5000 < 100) {
                    console.warn(
                        `[WAITING] Event ${id} still waiting for audio after ${Math.floor(waitTime / 1000)}s`
                    );
                }
            }

            return { nextEvent, nextEventId };
        }

        function resetClientEventState({ keepDisplay = false, catchUpFromCurrentTime = true } = {}) {
            if (!keepDisplay) {
                eventLog.innerHTML = '';
                eventContainer.scrollTop = 0;
            }

            eventQueue = [];
            displayedEventIds.clear();
            lastEventCursor = null;
            waitingAudio.clear();
            lastAudioCheck.clear();
            inflightAudioChecks.clear();
            isTyping = false;
            isFetching = false;

            pageLoadSimTime = currentSimTime;
            catchUpComplete = catchUpFromCurrentTime;
        }

        function updateHealthIndicator(element, label, service) {
            if (!service) {
                element.textContent = '❓';
                element.title = `${label}: no health data`;
                return;
            }

            if (service.status === 'ok') {
                element.textContent = '🟢';
            } else if (service.status === 'idle') {
                element.textContent = '🟡';
            } else {
                element.textContent = '🔴';
            }

            element.title = `${label}: ${service.message}`;
        }

        async function triggerMissionSpawn(button, { missionType, idleLabel, busyLabel, noun }) {
            button.disabled = true;
            button.textContent = busyLabel;

            try {
                const response = await fetch(`${SPAWN_MISSION_ENDPOINT}?mission_type=${encodeURIComponent(missionType)}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.message || `Failed to spawn ${noun}`);
                }

                const data = await response.json();
                console.log(`${noun} spawned:`, data.message);
            } catch (error) {
                console.error(`Error spawning ${noun}:`, error);
                alert(`Failed to spawn ${noun}. Check console for details.`);
            } finally {
                button.disabled = false;
                button.textContent = idleLabel;
            }
        }

        async function enqueueEventAudio(event, useFastMode) {
            console.log(`[AUDIO] enqueueEventAudio called: event=${event.id}, useFastMode=${useFastMode}, audio_ready=${event.audio_ready}`);
            
            if (useFastMode) {
                console.log(`[AUDIO] Fast mode - allowing text without audio`);
                return true; // Fast mode - allow text (historical events)
            }
            
            if (!audioRequired()) {
                console.log(`[AUDIO] Audio disabled/muted - allowing text without audio`);
                return true; // Audio disabled/muted - allow text
            }
            
            if (!event || !event.audio_url) {
                console.warn(`[AUDIO] No audio URL for event ${event?.id} - blocking text`);
                return false; // No audio URL - fail
            }
            
            // By the time we reach here, audio_ready should be true (checked by caller)
            // Just enqueue the audio URL directly without redundant HEAD check
            console.log(`[AUDIO] Enqueueing WAV URL: ${event.audio_url}`);
            
            try {
                audioPlayer.enqueueWavUrl(event.audio_url);
                console.log(`[AUDIO] Audio enqueued successfully for event ${event.id}`);
                return true;
            } catch (e) {
                console.error(`[AUDIO] Failed to enqueue audio for event ${event.id}:`, e);
                return false;
            }
        }

        // Restore volume preference (safe: doesn't start audio)
        const storedVolume = window.localStorage.getItem(AUDIO_STORAGE_KEYS.volume);
        if (storedVolume !== null) {
            audioVolumeInput.value = storedVolume;
        }
        audioPlayer.setVolume(parseFloat(audioVolumeInput.value));

        // Audio starts disabled (browser autoplay policy requires user interaction)
        // Button reflects actual state: user must click to enable
        const savedEnabled = window.localStorage.getItem(AUDIO_STORAGE_KEYS.enabledHint) === "1";
        audioEnableButton.textContent = savedEnabled 
            ? "Audio: Click to Enable" 
            : "Audio: Muted";

        audioVolumeInput.addEventListener("input", () => {
            const v = parseFloat(audioVolumeInput.value);
            audioPlayer.setVolume(v);
            window.localStorage.setItem(AUDIO_STORAGE_KEYS.volume, audioVolumeInput.value);
        });

        audioEnableButton.addEventListener("click", async () => {
            audioEnableButton.disabled = true;
            try {
                // Enable audio on first click (satisfies browser autoplay policy)
                if (!audioPlayer.isEnabled()) {
                    await audioPlayer.enable();
                    audioPlayer.setMuted(false); // Enable AND unmute on first click
                    window.localStorage.setItem(AUDIO_STORAGE_KEYS.enabledHint, "1");
                    window.localStorage.setItem(AUDIO_STORAGE_KEYS.muted, "0");
                    audioEnableButton.textContent = "Audio: Live";
                    
                    // Play confirmation tone to verify audio is working
                    audioPlayer.enqueueWavUrl(audioPresetUrl("quindar_start"));
                } else {
                    // Subsequent clicks toggle mute/unmute
                    const nowMuted = !audioPlayer.isMuted();
                    audioPlayer.setMuted(nowMuted);
                    window.localStorage.setItem(AUDIO_STORAGE_KEYS.muted, nowMuted ? "1" : "0");
                    audioEnableButton.textContent = nowMuted ? "Audio: Muted" : "Audio: Live";
                    
                    // Play confirmation tone when unmuting
                    if (!nowMuted) {
                        audioPlayer.enqueueWavUrl(audioPresetUrl("quindar_start"));
                    }
                }
            } catch (error) {
                console.error("Failed to enable audio:", error);
                alert(`Failed to enable audio: ${error?.message || error}`);
                audioEnableButton.textContent = "Audio: Error";
            } finally {
                audioEnableButton.disabled = false;
            }
        });

        /**
         * Enqueue audio actions for a given trigger from an event's audio_plan.
         */
        function enqueueAudioForTrigger(event, trigger, useFastMode) {
            if (useFastMode) return;
            if (!audioRequired()) return;
            if (!event || !Array.isArray(event.audio_plan)) return;

            for (const action of event.audio_plan) {
                if (!action || action.trigger !== trigger) continue;
                
                if (action.preset) {
                    // Procedurally generated audio (quindar, modem noise, static)
                    const url = audioPresetUrl(action.preset, action.params);
                    audioPlayer.enqueueWavUrl(url);
                } else if (action.wav_url) {
                    // Pre-generated WAV file (room tone, etc.)
                    audioPlayer.enqueueWavUrl(action.wav_url);
                }
            }
        }
        
        /**
         * Format timestamp as HH:MM:SS (relative to an epoch)
         */
        function formatTimestamp(timestamp) {
            // For display, we show time relative to when simulation started
            // This gives us a nice incrementing clock
            const hours = Math.floor(timestamp / 3600) % 100;
            const minutes = Math.floor((timestamp % 3600) / 60);
            const seconds = Math.floor(timestamp % 60);
            return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }
        
        /**
         * Format simulation time for display
         */
        function formatSimTime(simTime) {
            // Show as days, hours, minutes since simulation epoch
            const totalSeconds = simTime;
            const days = Math.floor(totalSeconds / 86400);
            const hours = Math.floor((totalSeconds % 86400) / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const seconds = Math.floor(totalSeconds % 60);
            
            if (days > 0) {
                return `D${days} ${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
            }
            return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }
        
        /**
         * Format time until next event for display
         */
        function formatTimeUntil(seconds) {
            if (seconds === null || seconds === undefined) {
                return '--';
            }
            if (seconds <= 0) {
                return 'now';
            }
            if (seconds < 60) {
                return `${Math.ceil(seconds)}s`;
            }
            if (seconds < 3600) {
                const mins = Math.floor(seconds / 60);
                const secs = Math.floor(seconds % 60);
                return `${mins}m ${secs}s`;
            }
            if (seconds < 86400) {
                const hrs = Math.floor(seconds / 3600);
                const mins = Math.floor((seconds % 3600) / 60);
                return `${hrs}h ${mins}m`;
            }
            const days = Math.floor(seconds / 86400);
            const hrs = Math.floor((seconds % 86400) / 3600);
            return `${days}d ${hrs}h`;
        }
        
        /**
         * Type out text character by character (like a serial/modem feed)
         * @param {Element} element - DOM element to type into
         * @param {string} text - Text to type
         * @param {function} callback - Called when typing completes
         * @param {boolean} fastMode - If true, use rapid typing for catch-up
         */
        function typeText(element, text, callback, fastMode = false) {
            // In fast mode, display instantly
            if (fastMode) {
                element.textContent = text;
                if (callback) callback();
                return;
            }
            
            let index = 0;
            
            function typeChar() {
                if (index < text.length) {
                    const char = text[index];
                    element.textContent += char;
                    
                    // Variable delay: faster for spaces, slower for punctuation
                    // Slightly slower for a more relaxed teletype effect
                    let delay = 12; // Default 12ms for regular characters
                    if (char === ' ') {
                        delay = 3; // Quick for spaces
                    } else if (char.match(/[.,!?;:]/)) {
                        delay = 20; // Slight pause for punctuation
                    } else if (char === '\n') {
                        delay = 15; // Brief pause for newlines
                    }
                    
                    index++;
                    setTimeout(typeChar, delay);
                } else {
                    if (callback) callback();
                }
            }
            
            typeChar();
        }
        
        /**
         * Create and type out an event line element
         * @param {Object} event - Event data to display
         * @param {function} callback - Called when display completes
         * @param {boolean} fastMode - If true, use rapid display for catch-up
         */
        function typeEventLine(event, callback, fastMode = false) {
            const line = document.createElement('div');
            line.className = 'event-line';
            
            // Timestamp (appears immediately)
            const timestamp = document.createElement('span');
            timestamp.className = 'event-timestamp';
            timestamp.textContent = `[${formatTimestamp(event.timestamp)}] `;
            line.appendChild(timestamp);
            
            // Add line to DOM immediately (so it appears, even if empty)
            eventLog.appendChild(line);
            
            // Speaker name (types out)
            const speakerContainer = document.createElement('span');
            speakerContainer.className = 'event-speaker';
            line.appendChild(speakerContainer);
            
            // Type speaker name, then the message text
            typeText(speakerContainer, `${event.actor_name}: `, () => {
                // After speaker name is typed, type the message text
                const textContainer = document.createElement('span');
                textContainer.className = 'event-text';
                line.appendChild(textContainer);
                typeText(textContainer, event.text, () => {
                    // Auto-scroll to bottom after message completes
                    eventContainer.scrollTop = eventContainer.scrollHeight;
                    // Call callback when this event is completely done
                    if (callback) callback();
                }, fastMode);
            }, fastMode);
        }
        
        /**
         * Process the next event in the queue
         * CRITICAL: If audio is enabled and not muted, events MUST have audio_url AND audio_ready=true
         * No legacy beep path - if TTS isn't ready, we wait indefinitely.
         */
        async function processNextEvent() {
            if (isTyping || eventQueue.length === 0) {
                return; // Already typing or queue is empty
            }
            
            isTyping = true;
            const event = eventQueue.shift();
            
            // Use fast mode for historical events (before page load time)
            // Once we've caught up, all subsequent events use normal speed
            const useFastMode = !catchUpComplete && pageLoadSimTime !== null && 
                                event.timestamp < pageLoadSimTime;
            
            // If this event is at or after page load time, we've caught up
            if (pageLoadSimTime !== null && event.timestamp >= pageLoadSimTime) {
                catchUpComplete = true;
            }

            // CRITICAL: If audio is enabled and not muted, events MUST have audio_url AND audio_ready=true
            // No legacy beep path - if TTS isn't ready, we wait.
            if (audioRequired()) {
                if (!event.audio_url || !event.audio_ready) {
                    moveEventToWaitingAudio(event, 'processNextEvent requires ready audio', { requeue: true });
                    isTyping = false;
                    setTimeout(processNextEvent, 200);
                    return; // Do NOT display text without TTS
                }
                
                // Enqueue fully-mixed audio (server returns quindars + TTS + room tone + modem noise all mixed)
                const audioEnqueued = await enqueueEventAudio(event, useFastMode);
                if (!audioEnqueued) {
                    moveEventToWaitingAudio(event, 'audio enqueue failed', { requeue: true });
                    isTyping = false;
                    setTimeout(processNextEvent, 200);
                    return; // Do NOT display text without TTS
                }
            } else {
                // Audio is disabled or muted - display text without audio (silent mode)
                // No audio enqueueing
            }
            
            typeEventLine(event, () => {
                // No legacy beep path - if we got here with audio enabled, we have TTS
                // This event is done, process the next one
                isTyping = false;
                // In fast mode, add a tiny delay between lines for visual effect
                // (rapid scroll rather than instant flash)
                if (useFastMode && eventQueue.length > 0) {
                    setTimeout(processNextEvent, 50); // 50ms between rapid lines
                } else {
                    processNextEvent();
                }
            }, useFastMode);
        }
        
        /**
         * Append events to the log with trickle effect (queued sequentially)
         */
        function appendEvents(events) {
            // Filter out events we've already displayed (prevent duplicates)
            const newEvents = events.filter(e => !displayedEventIds.has(e.id));
            
            if (newEvents.length === 0) {
                if (events.length > 0) {
                    console.log(`[APPEND] All ${events.length} events already displayed (IDs: ${events.map(e => e.id).join(', ')})`);
                }
                return;
            }
            
            console.log(`[APPEND] Adding ${newEvents.length} new events (IDs: ${newEvents.map(e => e.id).join(', ')})`);
            
            // Mark these events as displayed
            newEvents.forEach(e => displayedEventIds.add(e.id));
            
            // Add to queue or waiting list depending on audio readiness
            // CRITICAL: If audio is enabled and not muted, events MUST have audio_url AND audio_ready=true
            // No legacy beep path - if TTS isn't ready, we wait.
            for (const ev of newEvents) {
                if (audioRequired()) {
                    // Audio is enabled - require both audio_url and audio_ready
                    if (!ev.audio_url || !ev.audio_ready) {
                        moveEventToWaitingAudio(ev, 'appendEvents received event before audio was ready');
                        continue; // Do NOT add to eventQueue - wait for TTS
                    } else {
                        waitingAudio.delete(ev.id);
                    }
                }
                // Only add to eventQueue if:
                // - Audio is disabled/muted, OR
                // - Audio is enabled and audio_url AND audio_ready are both true
                eventQueue.push(ev);
            }
            // Start processing if not already typing
            processNextEvent();
        }
        
        /**
         * Fetch new events from the API
         */
        async function fetchEvents() {
            if (!isPolling) return;
            if (isFetching) return; // Prevent concurrent fetches
            
            isFetching = true;
            try {
                const url = lastEventCursor
                    ? `${API_ENDPOINT}?after_ts=${encodeURIComponent(lastEventCursor.timestamp)}&after_id=${encodeURIComponent(lastEventCursor.id)}&limit=100`
                    : `${API_ENDPOINT}?limit=100`;
                
                const response = await fetch(url);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                console.log(`[FETCH] Response: ${data.events.length} events, debug:`, data.debug);
                if (data.events.length > 0) {
                    console.log(`[FETCH] First event:`, data.events[0]);
                }
                
                // Update simulation time from response
                if (data.simulation_time !== undefined) {
                    currentSimTime = data.simulation_time;
                }
                
                // Store values for display interpolation
                if (data.debug) {
                    pendingEventCount = data.debug.pending_events || 0;
                    nextEventTimestamp = data.debug.next_event_timestamp;
                    // TTS queue status
                    if (data.debug.audio) {
                        ttsQueueCached = data.debug.audio.cached || 0;
                        ttsQueuePending = data.debug.audio.pending || 0;
                    }
                    // Update current sim time from the authoritative source
                    if (data.simulation_time) {
                        lastFetchedSimTime = data.simulation_time;
                        lastStatusFetchTime = Date.now();
                    }
                }
                
                if (data.events && data.events.length > 0) {
                    console.log(`[FETCH] Got ${data.events.length} events, cursor was ${lastEventCursor ? `${lastEventCursor.timestamp}/${lastEventCursor.id}` : 'null'}, will be ${data.latest_cursor ? `${data.latest_cursor.timestamp}/${data.latest_cursor.id}` : 'null'}`);
                    
                    // Update waitingAudio with fresh audio_ready flags from server
                    for (const freshEvent of data.events) {
                        if (waitingAudio.has(freshEvent.id)) {
                            const waitingData = waitingAudio.get(freshEvent.id);
                            // Update with fresh data from server
                            waitingData.event.audio_ready = freshEvent.audio_ready;
                            waitingData.event.audio_url = freshEvent.audio_url;
                            waitingData.event.audio_duration_s = freshEvent.audio_duration_s;
                        }
                    }
                    
                    appendEvents(data.events);
                    // Update cursor from the response (preferred)
                    if (data.latest_cursor) {
                        lastEventCursor = data.latest_cursor;
                    } else if (data.latest_id && data.events[data.events.length - 1]?.timestamp !== undefined) {
                        // Fallback for older servers
                        lastEventCursor = { timestamp: data.events[data.events.length - 1].timestamp, id: data.latest_id };
                    }
                } else if (data.debug && data.debug.pending_events > 0) {
                    // Events are pending but not returned - might be an ID tracking issue
                    console.log(`[FETCH] No events returned but ${data.debug.pending_events} pending. cursor=${lastEventCursor ? `${lastEventCursor.timestamp}/${lastEventCursor.id}` : 'null'}, sim_time=${data.simulation_time?.toFixed(1)}, next_event=${data.debug.next_event_timestamp?.toFixed(1)}`);
                }
                // Note: If no events returned, we just wait for next poll.
                // User can click "Clear Display" to reset if needed.
            } catch (error) {
                console.error('Error fetching events:', error);
            } finally {
                isFetching = false;
                // Check if waiting events are now ready
                // CRITICAL: Process in queue order - check ONLY the next (earliest) event
                if (waitingAudio.size > 0) {
                    const now = Date.now();
                    const { nextEvent, nextEventId } = findNextWaitingAudioCandidate(now);
                    
                    // For the NEXT event in queue, check if audio is ready
                    if (nextEvent && nextEvent.audio_url && !nextEvent.audio_ready) {
                        // Rate limit: Don't check same event more than once every 2 seconds
                        const lastCheck = lastAudioCheck.get(nextEventId) || 0;
                        const timeSinceCheck = now - lastCheck;
                        
                        // Prevent duplicate concurrent requests
                        if (inflightAudioChecks.has(nextEventId)) {
                            return; // Already checking this event
                        }
                        
                        if (timeSinceCheck >= 2000) {
                            // Make HEAD request to check if worker has generated audio
                            lastAudioCheck.set(nextEventId, now);
                            inflightAudioChecks.add(nextEventId);
                            
                            fetch(nextEvent.audio_url, { method: 'HEAD' })
                                .then(resp => {
                                    if (resp.status === 200) {
                                        // Audio is ready! (Explicit 200 check, not resp.ok which includes 202)
                                        const waitData = waitingAudio.get(nextEventId);
                                        if (waitData) {
                                            const waitTime = now - waitData.addedAt;
                                            console.log(`[WAITING] Audio ready for event ${nextEventId} after ${Math.floor(waitTime/1000)}s, promoting to queue`);
                                            nextEvent.audio_ready = true;
                                            eventQueue.push(nextEvent);
                                            waitingAudio.delete(nextEventId);
                                            processNextEvent();
                                        }
                                    } else if (resp.status === 202) {
                                        // Worker is actively generating - keep waiting
                                        console.log(`[WAITING] Event ${nextEventId} audio being generated (HEAD returned 202)`);
                                    } else if (resp.status === 404) {
                                        // Shouldn't happen with new code, but handle it
                                        console.warn(`[WAITING] Event ${nextEventId} returned 404 (unexpected)`);
                                    } else {
                                        console.warn(`[WAITING] Event ${nextEventId} returned unexpected status ${resp.status}`);
                                    }
                                })
                                .catch(err => {
                                    console.error(`[WAITING] Failed to check audio for event ${nextEventId}:`, err);
                                })
                                .finally(() => {
                                    inflightAudioChecks.delete(nextEventId);
                                });
                        }
                    } else if (nextEvent && nextEvent.audio_ready && nextEvent.audio_url) {
                        // Already marked ready (from previous check or fresh fetch)
                        const waitData = waitingAudio.get(nextEventId);
                        if (waitData) {
                            const waitTime = now - waitData.addedAt;
                            console.log(`[WAITING] Promoting event ${nextEventId} (already ready)`);
                            eventQueue.push(nextEvent);
                            waitingAudio.delete(nextEventId);
                            processNextEvent();
                        }
                    }
                }
            }
        }
        
        /**
         * Fetch simulation status (time and scale) from server
         */
        async function fetchStatus() {
            try {
                const response = await fetch(STATUS_ENDPOINT);
                if (!response.ok) return;
                
                const data = await response.json();
                currentSimTime = data.simulation_time;
                currentTimeScale = data.time_scale;
                
                // Store for interpolation
                lastStatusFetchTime = Date.now();
                lastFetchedSimTime = currentSimTime;
                
                // Capture page load time on first status fetch (for catch-up mode)
                if (pageLoadSimTime === null) {
                    pageLoadSimTime = currentSimTime;
                    console.log(`Page loaded at sim time ${pageLoadSimTime.toFixed(1)} - historical events will display rapidly`);
                }
                
                // Highlight active scale button
                scaleBtns.forEach(btn => {
                    const btnScale = parseFloat(btn.dataset.scale);
                    btn.classList.toggle('active', Math.abs(btnScale - currentTimeScale) < 0.01);
                });
                
                // Update display immediately
                updateDisplays();
            } catch (error) {
                console.error('Error fetching status:', error);
            }
        }
        
        /**
         * Check service health via backend health check endpoint
         */
        async function fetchHealth() {
            try {
                const response = await fetch(HEALTH_ENDPOINT);
                if (!response.ok) {
                    llmStatusDisplay.textContent = '❓';
                    ttsStatusDisplay.textContent = '❓';
                    return;
                }
                
                const health = await response.json();

                updateHealthIndicator(llmStatusDisplay, 'LLM', health.llm);
                updateHealthIndicator(ttsStatusDisplay, 'TTS', health.audio_worker);
            } catch (error) {
                console.error('Error fetching health:', error);
                llmStatusDisplay.textContent = '❓';
                ttsStatusDisplay.textContent = '❓';
            }
        }
        
        /**
         * Update display with interpolated time (called at 5Hz for smooth countdown)
         */
        function updateDisplays() {
            // Interpolate current sim time based on wall clock elapsed since last fetch
            if (lastStatusFetchTime !== null && lastFetchedSimTime !== null) {
                const wallElapsed = (Date.now() - lastStatusFetchTime) / 1000;
                currentSimTime = lastFetchedSimTime + (wallElapsed * currentTimeScale);
            }
            
            // Update sim time display
            simTimeDisplay.textContent = formatSimTime(currentSimTime);
            timeScaleDisplay.textContent = `${currentTimeScale}x`;
            
            // Update pending events display
            pendingEventsDisplay.textContent = `${pendingEventCount} pending`;
            pendingEventsDisplay.classList.toggle('has-pending', pendingEventCount > 0);
            
            // Update time until next event (interpolated)
            if (nextEventTimestamp !== null) {
                const timeUntil = nextEventTimestamp - currentSimTime;
                nextEventDisplay.textContent = formatTimeUntil(timeUntil > 0 ? timeUntil : 0);
                nextEventDisplay.classList.toggle('imminent', timeUntil > 0 && timeUntil < 60);
                
                // If an event is due (time <= 0), trigger a fetch immediately
                if (timeUntil <= 0 && !isFetching) {
                    console.log(`[DISPLAY] Event due! Triggering immediate fetch. timeUntil=${timeUntil.toFixed(1)}`);
                    fetchEvents();
                }
            } else {
                nextEventDisplay.textContent = '--';
                nextEventDisplay.classList.remove('imminent');
            }
            
            // Disable skip button if no pending events
            skipToNextButton.disabled = pendingEventCount === 0;
        }
        
        /**
         * Set time scale
         */
        async function setTimeScale(scale) {
            try {
                const response = await fetch(TIME_SCALE_ENDPOINT, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ time_scale: scale })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    currentTimeScale = data.time_scale;
                    currentSimTime = data.simulation_time;
                    timeScaleDisplay.textContent = `${currentTimeScale}x`;
                    console.log(`Time scale set to ${currentTimeScale}x`);
                }
            } catch (error) {
                console.error('Error setting time scale:', error);
            }
        }
        
        /**
         * Start polling for events
         */
        function startPolling() {
            // Initial fetch
            fetchEvents();
            fetchStatus();
            fetchHealth();
            
            // Set up intervals
            setInterval(fetchEvents, POLL_INTERVAL);  // Poll events every 1s
            setInterval(fetchStatus, STATUS_POLL_INTERVAL);  // Poll server status every 2s
            setInterval(fetchHealth, 10000);  // Poll health every 10s
            setInterval(updateDisplays, DISPLAY_UPDATE_INTERVAL);  // Update display at 5Hz
        }
        
        /**
         * Clear the display only (keeps database events)
         */
        clearDisplayButton.addEventListener('click', () => {
            resetClientEventState({ keepDisplay: false, catchUpFromCurrentTime: false });
        });
        
        /**
         * Clear ALL events from database (fresh start)
         */
        clearEventsButton.addEventListener('click', async () => {
            if (!confirm('Clear ALL events from the database? This cannot be undone.')) {
                return;
            }
            
            clearEventsButton.disabled = true;
            clearEventsButton.textContent = 'Clearing...';
            
            try {
                const response = await fetch(CLEAR_EVENTS_ENDPOINT, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    console.log('Events cleared:', data.message);
                    resetClientEventState({ keepDisplay: false, catchUpFromCurrentTime: true });
                    console.log('All client state cleared - ready for new events');
                } else {
                    throw new Error('Failed to clear events');
                }
            } catch (error) {
                console.error('Error clearing events:', error);
                alert('Failed to clear events. Check console for details.');
            } finally {
                clearEventsButton.disabled = false;
                clearEventsButton.textContent = 'Clear All Events';
            }
        });
        
        /**
         * Spawn a cargo mission (ship + cargo + journey)
         */
        spawnCargoShipButton.addEventListener('click', async () => {
            await triggerMissionSpawn(spawnCargoShipButton, {
                missionType: 'cargo',
                idleLabel: 'Spawn Cargo Ship',
                busyLabel: 'Generating route & dialogue...',
                noun: 'cargo mission',
            });
        });
        
        /**
         * Spawn a nav broadcast mission (satellite navigation update)
         */
        spawnNavsatButton.addEventListener('click', async () => {
            await triggerMissionSpawn(spawnNavsatButton, {
                missionType: 'nav_broadcast',
                idleLabel: 'Spawn Navsat',
                busyLabel: 'Generating nav broadcast...',
                noun: 'nav broadcast',
            });
        });
        
        /**
         * Skip to the next pending event
         */
        skipToNextButton.addEventListener('click', async () => {
            skipToNextButton.disabled = true;
            skipToNextButton.textContent = 'Skipping...';
            
            try {
                const response = await fetch(SKIP_TO_NEXT_ENDPOINT, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    console.log('Skip response:', data);
                    if (data.status === 'success') {
                        console.log(`Skipped ${data.skipped_seconds.toFixed(1)}s to ${data.next_event_actor}, new sim_time: ${data.simulation_time}`);
                        // Update simulation status immediately
                        await fetchStatus();
                        // Small delay to ensure backend state is consistent
                        await new Promise(resolve => setTimeout(resolve, 100));
                        // Reset fetch guard and fetch events
                        isFetching = false;
                        await fetchEvents();
                    } else {
                        console.log('No events to skip to');
                    }
                } else {
                    throw new Error('Failed to skip to next event');
                }
            } catch (error) {
                console.error('Error skipping to next event:', error);
            } finally {
                skipToNextButton.disabled = false;
                skipToNextButton.textContent = '⏭ Skip to Next';
            }
        });

        /**
         * Time scale button handlers
         */
        scaleBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const scale = parseFloat(btn.dataset.scale);
                setTimeScale(scale);
            });
        });
        
        // Start polling when page loads
        document.addEventListener('DOMContentLoaded', startPolling);
