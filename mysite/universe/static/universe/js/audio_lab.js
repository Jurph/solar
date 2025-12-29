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
  let applyingPreset = false;
  const ENGINE_PRESETS = {
    // Sourced from scripts/*_engine_settings.json (component_1_gain ... component_10_gain)
    small_ship: [0.04, 0.75, 1.0, 0.27, 0.02, 0.06, 0.1, 0.12, 0.0, 0.15],
    medium_ship: [0.73, 0.64, 0.65, 0.3, 0.22, 0.0, 0.0, 0.17, 0.01, 0.72],
    large_ship: [0.65, 0.83, 1.0, 0.17, 0.54, 0.1, 0.27, 0.31, 0.01, 0.9],
    control_station: null, // falls back to medium in applyEnginePreset
  };

  function setStatus(msg) {
    statusEl.textContent = msg || "";
  }

  function buildPayload() {
    const payload = {
      // Force server-side TTS rendering
      mode: "tts",
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
    };

    // Add 10 component gains and voice settings (always send for TTS)
    for (let i = 1; i <= 10; i++) {
      const id = `component${String(i).padStart(2, "0")}Gain`;
      payload[`component_${i}_gain`] = el(id) ? parseFloat(el(id).value) : 0.0;
    }
    payload.quindar_gain = el("quindarGain") ? parseFloat(el("quindarGain").value) : 0.45;
    payload.voice_id = el("voiceSelect") ? el("voiceSelect").value : "";
    payload.tts_gain = el("voiceGain") ? parseFloat(el("voiceGain").value) : 2.0;
    payload.engine_preset = el("enginePreset") ? el("enginePreset").value : "custom";
    payload.engine_bed_gain = el("engineBedGain") ? parseFloat(el("engineBedGain").value) : 1.0;

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

    const descriptiveNames = [
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

    // Load both A and B variants for each component with fallbacks
    for (let i = 1; i <= 10; i++) {
      const num = String(i).padStart(2, "0");
      const name = descriptiveNames[i - 1];

      const candidatesA = [
        `/static/universe/audio/audio-${num}-variant-a.wav`,
        `/static/universe/audio/audio-${num}-${name}.wav`,
        `/static/universe/audio/audio-${num}.wav`,
      ];

      const candidatesB = [
        `/static/universe/audio/audio-${num}-variant-b.wav`,
        `/static/universe/audio/audio-${num}-${name}.wav`,
        `/static/universe/audio/audio-${num}.wav`,
      ];

      let bufferA = null;
      for (const url of candidatesA) {
        try {
          bufferA = await loadAudioFile(url);
          break;
        } catch (err) {
          // Try next candidate
        }
      }
      if (!bufferA) {
        console.warn(`Failed to load any A variant for component ${i}`);
      }
      audioBuffersA[i - 1] = bufferA;

      let bufferB = null;
      for (const url of candidatesB) {
        try {
          bufferB = await loadAudioFile(url);
          break;
        } catch (err) {
          // Try next candidate
        }
      }
      if (!bufferB) {
        bufferB = bufferA; // fallback to A
        console.warn(`Failed to load any B variant for component ${i}, using A`);
      }
      audioBuffersB[i - 1] = bufferB;
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
      let gain = slider ? parseFloat(slider.value) : 0.0;
      // Ensure exactly 0 when slider is at minimum
      if (gain <= 0 || isNaN(gain)) {
        gain = 0.0;
      }

      if (gain > 0.0001 && (audioBuffersA[i] || audioBuffersB[i])) {
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
      
      // If gain becomes 0 or very close to 0, immediately set to 0 and stop sources
      if (gain <= 0.0001) {
        gainNodes[index].gain.cancelScheduledValues(now);
        gainNodes[index].gain.setValueAtTime(0, now); // Immediate, no fade
        gain = 0; // Ensure it's exactly 0
        
        // Stop both variants immediately
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
      } else {
        // For non-zero gain, use smooth fade
        gainNodes[index].gain.setTargetAtTime(gain, now, 0.01);
        
        // Start playback if not already playing
        if (!audioSourcesA[index] && !audioSourcesB[index] && isPlaying) {
          const startTime = audioContext.currentTime;
          nextPlayTimeA[index] = startTime;
          playVariantAAt(index, startTime);
        }
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

  function markCustomEnginePreset() {
    if (applyingPreset) return;
    const presetSelect = el("enginePreset");
    if (presetSelect && presetSelect.value !== "custom") {
      presetSelect.value = "custom";
    }
  }

  function applyEnginePreset(name) {
    const values = ENGINE_PRESETS[name] || ENGINE_PRESETS.medium_ship;
    if (!values || values.length !== 10) return;

    applyingPreset = true;
    values.forEach((val, idx) => {
      const sliderId = `component${String(idx + 1).padStart(2, "0")}Gain`;
      const slider = el(sliderId);
      if (slider) {
        slider.value = val;
        slider.dispatchEvent(new Event("input"));
      }
    });
    applyingPreset = false;
  }

  // Connect sliders to gain nodes for real-time updates
  function connectSlidersToGainNodes() {
    // Component sliders
    for (let i = 1; i <= 10; i++) {
      const sliderId = `component${String(i).padStart(2, "0")}Gain`;
      const slider = el(sliderId);
      if (slider) {
        slider.addEventListener("input", () => {
          let gain = parseFloat(slider.value);
          // Ensure exactly 0 when slider is at minimum
          if (gain <= 0 || isNaN(gain)) {
            gain = 0;
          }
          markCustomEnginePreset();
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

    // Engine preset selector
    const enginePreset = el("enginePreset");
    if (enginePreset) {
      enginePreset.addEventListener("change", () => {
        if (enginePreset.value !== "custom") {
          applyEnginePreset(enginePreset.value);
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

  async function playServerMode() {
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
    // Always render on the server (modem or TTS), then play returned WAV
    await playServerMode();
  }

  function stop() {
    audio.pause();
    audio.currentTime = 0;
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
    });
  });
})();
