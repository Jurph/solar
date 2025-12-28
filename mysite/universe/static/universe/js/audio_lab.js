(() => {
  const el = (id) => document.getElementById(id);
  const statusEl = el("status");
  const modal = el("settingsModal");

  // Legacy HTML5 Audio for modem mode (server-rendered WAV)
  const audio = new Audio();
  audio.preload = "auto";

  // Web Audio API for TTS mode (client-side mixing)
  let audioContext = null;
  let gainNodes = [];
  let audioBuffersA = []; // Variant A buffers
  let audioBuffersB = []; // Variant B buffers
  let audioSourcesA = []; // Currently playing A sources
  let audioSourcesB = []; // Currently playing B sources
  let engineGain = null; // Master gain for all engine noise components
  let masterGain = null; // Master gain for everything
  let voiceGain = null; // Gain for voice clip
  let voiceSource = null;
  let voiceBuffer = null;
  let isPlaying = false;
  let nextPlayTimeA = [];
  let nextPlayTimeB = [];

  function setStatus(msg) {
    statusEl.textContent = msg || "";
  }

  function getMode() {
    const selected = document.querySelector('input[name="mode"]:checked');
    return selected ? selected.value : "modem";
  }

  function buildPayload() {
    const payload = {
      mode: getMode(),
      text: el("labText").value,
      include_quindar: el("includeQuindar").checked,
      include_static: el("includeStatic").checked,
      modem_gain: parseFloat(el("modemGain").value),
      mark_frequency_hz: parseFloat(el("markFreq").value),
      space_frequency_hz: parseFloat(el("spaceFreq").value),
      wow_rate_hz: parseFloat(el("wowRate").value),
      wow_depth_hz: parseFloat(el("wowDepth").value),
      carrier_frequency_hz: parseFloat(el("carrierFreq").value),
      carrier_gain: parseFloat(el("carrierGain").value),
      baud_rate: parseInt(el("baudRate").value, 10),
      static_gain: parseFloat(el("staticGain").value),
      static_intensity: parseFloat(el("staticIntensity").value),
      static_highpass_hz: parseFloat(el("staticHighpass").value),
      static_lowpass_hz: parseFloat(el("staticLowpass").value),

      include_rumble: el("includeRumble").checked,
      rumble_frequency_hz: parseFloat(el("rumbleFreq").value),
      rumble_gain: parseFloat(el("rumbleGain").value),

      include_echo: el("includeEcho").checked,
      echo_delay_ms: parseFloat(el("echoDelay").value),
      echo_decay: parseFloat(el("echoDecay").value),
      echo_wet: parseFloat(el("echoWet").value),
    };

    // Add 10 component gains, master engine gain, and voice gain for TTS mode
    if (getMode() === "tts") {
      for (let i = 1; i <= 10; i++) {
        const id = `component${String(i).padStart(2, "0")}Gain`;
        payload[`component_${i}_gain`] = el(id) ? parseFloat(el(id).value) : 0.0;
      }
      payload.master_engine_gain = el("masterEngineGain") ? parseFloat(el("masterEngineGain").value) : 1.0;
      payload.voice_gain = el("voiceGain") ? parseFloat(el("voiceGain").value) : 1.0;
      payload.loop_engine_noise = el("loopEngineNoise") ? el("loopEngineNoise").checked : true;
    }

    return payload;
  }

  function getSettingsJson() {
    return JSON.stringify(buildPayload(), null, 2);
  }

  function showSettings() {
    el("settingsText").value = getSettingsJson();
    modal.classList.remove("hidden");
  }

  function hideSettings() {
    modal.classList.add("hidden");
  }

  function downloadSettings() {
    const name = (el("profileName").value || "audio_profile").trim();
    const safe = name.replace(/[^a-z0-9_\-]+/gi, "_");
    const blob = new Blob([getSettingsJson()], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${safe}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    setStatus("Downloaded settings JSON");
  }

  async function copySettings() {
    const text = getSettingsJson();
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        setStatus("Copied settings JSON");
        return;
      }
    } catch (_) {}

    // Fallback: select text for manual copy
    el("settingsText").focus();
    el("settingsText").select();
    setStatus("Select-all ready (Ctrl+C)");
  }

  // ============================================================================
  // Web Audio API Functions (for TTS mode - client-side mixing)
  // ============================================================================

  async function initWebAudio() {
    if (audioContext) return audioContext;

    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) {
      throw new Error("Web Audio API not supported in this browser");
    }

    audioContext = new AC();
    masterGain = audioContext.createGain();
    masterGain.connect(audioContext.destination);
    masterGain.gain.value = parseFloat(el("volume").value);

    // Resume context if suspended (browser autoplay policy)
    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }

    return audioContext;
  }

  async function loadAudioFile(url) {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to load ${url}: ${response.statusText}`);
    }
    const arrayBuffer = await response.arrayBuffer();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    return audioBuffer;
  }

  async function loadAllSoundscapeFiles() {
    if (!audioContext) await initWebAudio();

    setStatus("Loading soundscape files...");
    audioBuffersA = [];
    audioBuffersB = [];

    // Component names matching the renamed audio files
    const componentNames = [
      "controls-and-quindars",
      "modems-and-teletypes",
      "burbly-sonar",
      "slower-burbles",
      "engine-hum",
      "engine-thrum",
      "engine-rumble",
      "deep-engine-rumble",
      "infra-engine-rumble",
      "staticky-crickets",
    ];

    // Load both A and B variants for each component
    for (let i = 1; i <= 10; i++) {
      const num = String(i).padStart(2, "0");
      const name = componentNames[i - 1];
      
      // Try WAV variants first (best compatibility), fall back to OGG
      const urls = [
        `/static/universe/audio/audio-${num}-variant-a.wav`,
        `/static/universe/audio/audio-${num}-variant-a.ogg`,
        `/static/universe/audio/audio-${num}-${name}.wav`,
        `/static/universe/audio/audio-${num}.wav`,
      ];
      
      let bufferA = null;
      for (const url of urls) {
        try {
          bufferA = await loadAudioFile(url);
          break;
        } catch (err) {
          // Try next URL
        }
      }
      audioBuffersA[i - 1] = bufferA;
      if (!bufferA) {
        console.warn(`Failed to load variant A for component ${i}`);
      }

      const urlsB = [
        `/static/universe/audio/audio-${num}-variant-b.wav`,
        `/static/universe/audio/audio-${num}-variant-b.ogg`,
        `/static/universe/audio/audio-${num}-${name}.wav`, // Fallback to same file if no B variant
        `/static/universe/audio/audio-${num}.wav`,
      ];
      
      let bufferB = null;
      for (const url of urlsB) {
        try {
          bufferB = await loadAudioFile(url);
          break;
        } catch (err) {
          // Try next URL
        }
      }
      audioBuffersB[i - 1] = bufferB;
      if (!bufferB) {
        console.warn(`Failed to load variant B for component ${i}, using variant A`);
        audioBuffersB[i - 1] = bufferA; // Fallback to A if B not available
      }
    }

    // Load voice clip
    try {
      voiceBuffer = await loadAudioFile("/static/universe/audio/sample_speech_clip.wav");
    } catch (err) {
      console.warn("Failed to load voice clip:", err);
      voiceBuffer = null;
    }

    setStatus("Files loaded");
  }

  // Play variant A at a specific time, schedule B to play when A ends
  function playVariantAAt(componentIndex, startTime) {
    if (!audioBuffersA[componentIndex] || !gainNodes[componentIndex]) return;

    const source = audioContext.createBufferSource();
    source.buffer = audioBuffersA[componentIndex];
    source.connect(gainNodes[componentIndex]);
    
    const duration = source.buffer.duration;
    nextPlayTimeB[componentIndex] = startTime + duration;
    
    source.onended = () => {
      playVariantBAt(componentIndex, nextPlayTimeB[componentIndex]);
    };
    
    source.start(startTime);
    audioSourcesA[componentIndex] = source;
  }

  // Play variant B at a specific time, schedule A to play when B ends
  function playVariantBAt(componentIndex, startTime) {
    if (!audioBuffersB[componentIndex] || !gainNodes[componentIndex]) return;

    const source = audioContext.createBufferSource();
    source.buffer = audioBuffersB[componentIndex];
    source.connect(gainNodes[componentIndex]);
    
    const duration = source.buffer.duration;
    nextPlayTimeA[componentIndex] = startTime + duration;
    
    source.onended = () => {
      playVariantAAt(componentIndex, nextPlayTimeA[componentIndex]);
    };
    
    source.start(startTime);
    audioSourcesB[componentIndex] = source;
  }

  function startWebAudioPlayback() {
    if (!audioContext || isPlaying) return;

    // Stop any existing playback
    stopWebAudioPlayback();

    // Create master engine gain node
    engineGain = audioContext.createGain();
    engineGain.connect(masterGain);
    const masterEngineSlider = el("masterEngineGain");
    engineGain.gain.value = masterEngineSlider ? parseFloat(masterEngineSlider.value) : 1.0;

    // Create gain nodes for each component
    gainNodes = [];
    audioSourcesA = [];
    audioSourcesB = [];
    nextPlayTimeA = [];
    nextPlayTimeB = [];

    const now = audioContext.currentTime;
    const loopEngineNoise = el("loopEngineNoise") ? el("loopEngineNoise").checked : true;

    for (let i = 0; i < 10; i++) {
      const gainNode = audioContext.createGain();
      gainNode.connect(engineGain);
      gainNodes[i] = gainNode;

      // Get slider value
      const sliderId = `component${String(i + 1).padStart(2, "0")}Gain`;
      const slider = el(sliderId);
      const gain = slider ? parseFloat(slider.value) : 0.0;

      if (gain > 0 && (audioBuffersA[i] || audioBuffersB[i])) {
        gainNode.gain.value = gain;
        
        if (loopEngineNoise) {
          // Start with variant A, which will schedule B, which will schedule A, etc.
          nextPlayTimeA[i] = now;
          playVariantAAt(i, now);
        } else {
          // Simple loop (just use variant A)
          const source = audioContext.createBufferSource();
          source.buffer = audioBuffersA[i] || audioBuffersB[i];
          source.loop = true;
          source.connect(gainNode);
          source.start(now);
          audioSourcesA[i] = source;
        }
      }
    }

    // Play voice clip if available and checkbox is set
    const playVoice = el("voiceGain") && parseFloat(el("voiceGain").value) > 0;
    if (playVoice && voiceBuffer) {
      voiceGain = audioContext.createGain();
      voiceGain.connect(masterGain);
      const voiceGainSlider = el("voiceGain");
      voiceGain.gain.value = voiceGainSlider ? parseFloat(voiceGainSlider.value) : 1.0;

      voiceSource = audioContext.createBufferSource();
      voiceSource.buffer = voiceBuffer;
      voiceSource.connect(voiceGain);
      voiceSource.start(now);

      // Voice ending doesn't stop engine noise anymore (continuous loop)
      voiceSource.onended = () => {
        voiceSource = null;
      };
    }

    isPlaying = true;
    setStatus("Playing (continuous loop)");
  }

  function stopWebAudioPlayback() {
    if (!isPlaying) return;

    // Stop all A variant sources
    audioSourcesA.forEach((source) => {
      if (source) {
        try {
          source.stop();
          source.onended = null; // Clear callback to prevent scheduling
        } catch (e) {
          // Source may already be stopped
        }
      }
    });

    // Stop all B variant sources
    audioSourcesB.forEach((source) => {
      if (source) {
        try {
          source.stop();
          source.onended = null; // Clear callback to prevent scheduling
        } catch (e) {
          // Source may already be stopped
        }
      }
    });

    // Stop voice source
    if (voiceSource) {
      try {
        voiceSource.stop();
      } catch (e) {
        // Source may already be stopped
      }
      voiceSource = null;
    }

    audioSourcesA = [];
    audioSourcesB = [];
    isPlaying = false;
    setStatus("");
  }

  function updateComponentGain(index, gain) {
    if (gainNodes[index]) {
      const now = audioContext.currentTime;
      gainNodes[index].gain.setTargetAtTime(gain, now, 0.01); // Smooth fade
      
      // If gain becomes 0, stop playback. If it becomes > 0, start playback.
      if (gain <= 0) {
        // Stop both variants
        if (audioSourcesA[index]) {
          try {
            audioSourcesA[index].stop();
            audioSourcesA[index].onended = null;
          } catch (e) {}
          audioSourcesA[index] = null;
        }
        if (audioSourcesB[index]) {
          try {
            audioSourcesB[index].stop();
            audioSourcesB[index].onended = null;
          } catch (e) {}
          audioSourcesB[index] = null;
        }
      } else if (gain > 0 && !audioSourcesA[index] && !audioSourcesB[index] && isPlaying) {
        // Start playback if not already playing
        const startTime = audioContext.currentTime;
        nextPlayTimeA[index] = startTime;
        playVariantAAt(index, startTime);
      }
    }
  }

  function updateMasterEngineGain(gain) {
    if (engineGain) {
      const now = audioContext.currentTime;
      engineGain.gain.setTargetAtTime(gain, now, 0.01);
    }
  }

  function updateVoiceGain(gain) {
    if (voiceGain) {
      const now = audioContext.currentTime;
      voiceGain.gain.setTargetAtTime(gain, now, 0.01);
    }
  }

  // Connect sliders to gain nodes for real-time updates
  function connectSlidersToGainNodes() {
    // Component sliders
    for (let i = 1; i <= 10; i++) {
      const sliderId = `component${String(i).padStart(2, "0")}Gain`;
      const slider = el(sliderId);
      if (slider) {
        slider.addEventListener("input", () => {
          const gain = parseFloat(slider.value);
          if (isPlaying && audioContext) {
            updateComponentGain(i - 1, gain);
          }
        });
      }
    }

    // Master engine noise gain
    const masterEngineSlider = el("masterEngineGain");
    if (masterEngineSlider) {
      masterEngineSlider.addEventListener("input", () => {
        const gain = parseFloat(masterEngineSlider.value);
        if (isPlaying && audioContext) {
          updateMasterEngineGain(gain);
        }
      });
    }

    // Voice gain
    const voiceSlider = el("voiceGain");
    if (voiceSlider) {
      voiceSlider.addEventListener("input", () => {
        const gain = parseFloat(voiceSlider.value);
        if (isPlaying && audioContext) {
          updateVoiceGain(gain);
        }
      });
    }

    // Master volume control
    el("volume").addEventListener("input", () => {
      const vol = parseFloat(el("volume").value);
      if (masterGain) {
        masterGain.gain.value = vol;
      }
      if (audio) {
        audio.volume = vol;
      }
    });
  }

  // ============================================================================
  // Legacy Server-Side Playback (for modem mode)
  // ============================================================================

  async function playModemMode() {
    setStatus("Rendering…");

    const payload = buildPayload();
    const resp = await fetch(AUDIO_LAB_RENDER_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      let msg = `HTTP ${resp.status}`;
      try {
        const data = await resp.json();
        if (data && data.message) msg = data.message;
      } catch (_) {}
      setStatus(`Error: ${msg}`);
      return;
    }

    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);

    try {
      audio.pause();
      audio.currentTime = 0;
      audio.volume = parseFloat(el("volume").value);
      audio.src = url;
      await audio.play();
      setStatus("Playing");
    } catch (err) {
      setStatus(`Playback blocked: ${err?.message || err}`);
    } finally {
      // Revoke after playback ends or errors.
      const cleanup = () => {
        URL.revokeObjectURL(url);
        audio.removeEventListener("ended", cleanup);
        audio.removeEventListener("error", cleanup);
        setStatus("");
      };
      audio.addEventListener("ended", cleanup);
      audio.addEventListener("error", cleanup);
    }
  }

  // ============================================================================
  // Main Play/Stop Functions
  // ============================================================================

  async function play() {
    const mode = getMode();

    if (mode === "tts") {
      // Client-side Web Audio API mixing
      try {
        if (!audioContext) {
          await initWebAudio();
        }
        if (audioBuffersA.length === 0) {
          await loadAllSoundscapeFiles();
        }
        startWebAudioPlayback();
      } catch (err) {
        setStatus(`Error: ${err.message}`);
        console.error(err);
      }
    } else {
      // Server-side rendering (modem mode)
      await playModemMode();
    }
  }

  function stop() {
    const mode = getMode();

    if (mode === "tts" && isPlaying) {
      stopWebAudioPlayback();
    } else {
      audio.pause();
      audio.currentTime = 0;
    }
    setStatus("");
  }

  // ============================================================================
  // Event Listeners
  // ============================================================================

  connectSlidersToGainNodes();

  el("playBtn").addEventListener("click", () => {
    play().catch((e) => setStatus(`Error: ${e?.message || e}`));
  });

  el("stopBtn").addEventListener("click", stop);

  el("settingsBtn").addEventListener("click", showSettings);
  el("exportBtn").addEventListener("click", downloadSettings);
  el("closeSettingsBtn").addEventListener("click", hideSettings);
  el("downloadSettingsBtn").addEventListener("click", downloadSettings);
  el("copySettingsBtn").addEventListener("click", () => copySettings().catch(() => {}));

  // Close modal if clicking the backdrop.
  modal.addEventListener("click", (e) => {
    if (e.target === modal) hideSettings();
  });

  // Mode change: stop current playback
  document.querySelectorAll('input[name="mode"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      stop();
      if (getMode() === "tts" && audioBuffersA.length === 0) {
        // Preload files when switching to TTS mode
        initWebAudio()
          .then(() => loadAllSoundscapeFiles())
          .catch((err) => console.warn("Preload failed:", err));
      }
    });
  });
})();
