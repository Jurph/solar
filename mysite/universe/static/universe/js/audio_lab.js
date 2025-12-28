(() => {
  const el = (id) => document.getElementById(id);
  const statusEl = el("status");
  const modal = el("settingsModal");

  const audio = new Audio();
  audio.preload = "auto";

  function setStatus(msg) {
    statusEl.textContent = msg || "";
  }

  function getMode() {
    const selected = document.querySelector('input[name="mode"]:checked');
    return selected ? selected.value : "modem";
  }

  function buildPayload() {
    return {
      mode: getMode(),
      text: el("labText").value,
      include_quindar: el("includeQuindar").checked,
      include_static: el("includeStatic").checked,
      tts_gain: el("ttsGain") ? parseFloat(el("ttsGain").value) : 1.0,
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

  async function play() {
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

  function stop() {
    audio.pause();
    audio.currentTime = 0;
    setStatus("");
  }

  el("volume").addEventListener("input", () => {
    audio.volume = parseFloat(el("volume").value);
  });

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
})();


