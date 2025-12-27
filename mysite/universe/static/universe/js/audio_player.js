/*
Minimal audio player: fetch a WAV from the backend and play it.

No synthesis logic lives here; synthesis is defined in Python and returned as a
rendered waveform (audio/wav).
*/

(function (global) {
  function _clamp01(x) {
    const n = Number(x);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(1, n));
  }

  class AudioPlayer {
    constructor() {
      this._enabled = false;
      this._muted = true;
      this._volume = 0.2;
      this._audio = null;
      this._playChain = Promise.resolve();
    }

    isEnabled() {
      return this._enabled;
    }

    isMuted() {
      return this._muted;
    }

    setMuted(muted) {
      this._muted = Boolean(muted);
    }

    setVolume(volume) {
      this._volume = _clamp01(volume);
      if (this._audio) {
        this._audio.volume = this._volume;
      }
    }

    async enable() {
      // Enable by creating an <audio> element. Playback still requires a user gesture,
      // but calling enable() from a click handler satisfies that in practice.
      if (!this._audio) {
        this._audio = new Audio();
        this._audio.volume = this._volume;
      }
      this._enabled = true;
    }

    enqueueWavUrl(url) {
      if (!this._enabled || !this._audio) return Promise.resolve();
      if (this._muted) return Promise.resolve();

      this._playChain = this._playChain
        .then(() => this._playOnce(url))
        .catch((err) => {
          // Don't break the chain on errors; log and continue.
          console.error("Audio playback failed:", err);
        });

      return this._playChain;
    }

    async _playOnce(url) {
      if (!this._enabled || !this._audio) return;
      if (this._muted) return;

      // Fetch the bytes so we can avoid cache/seek weirdness across rapid calls.
      const resp = await fetch(url, { cache: "force-cache" });
      if (!resp.ok) {
        throw new Error(`Audio fetch failed: HTTP ${resp.status}`);
      }
      const blob = await resp.blob();
      const objectUrl = URL.createObjectURL(blob);

      try {
        this._audio.pause();
        this._audio.currentTime = 0;
        this._audio.src = objectUrl;
        await this._audio.play();

        // Await completion so queued playback is sequential.
        await new Promise((resolve) => {
          const cleanup = () => {
            this._audio.removeEventListener("ended", onEnded);
            this._audio.removeEventListener("error", onError);
            resolve();
          };
          const onEnded = () => cleanup();
          const onError = () => cleanup();
          this._audio.addEventListener("ended", onEnded, { once: true });
          this._audio.addEventListener("error", onError, { once: true });
        });
      } finally {
        URL.revokeObjectURL(objectUrl);
      }
    }
  }

  global.AudioPlayer = AudioPlayer;
})(window);


