# myNoise.net Spaceship Noise Generator - Implementation Analysis

## Overview
Downloaded and analyzed the JavaScript code from https://mynoise.net/NoiseMachines/spaceshipNoiseGenerator.php

## Key Findings

### Audio File Structure
- **20 audio files total**: 10 sliders × 2 variants (A and B)
- Files are named: `0a`, `0b`, `1a`, `1b`, ... `9a`, `9b`
- Format: `.mp3` or `.ogg` (browser-dependent)
- Hosted at: `https://mynoise.world/Data/SPACESHIP/`

### Architecture

#### 1. Web Audio API Setup
```javascript
var context = new (window.AudioContext || window.webkitAudioContext)();
var sourceA = new Array();  // 10 sources for variant A
var sourceB = new Array();  // 10 sources for variant B
var gainNode = new Array(); // 10 gain nodes (one per slider)
var bufferList = new Array(); // 20 buffers (10 A + 10 B)
```

#### 2. Loading Audio Files
- Uses `XMLHttpRequest` with `responseType='arraybuffer'`
- Decodes with `context.decodeAudioData()`
- Stores decoded buffers in `bufferList[i]` (0-9 for A variants, 10-19 for B variants)

#### 3. Playback Strategy: Alternating A/B Variants
**Key insight**: Each slider has TWO audio files that alternate to create seamless loops!

```javascript
// When A variant ends, schedule B variant
sourceA[i].onended = function() { webAudioPlayBAt(i, nextB[i]); };

// When B variant ends, schedule A variant  
sourceB[i].onended = function() { webAudioPlayAAt(i, nextA[i]); };
```

This creates **seamless looping** without gaps or clicks.

#### 4. Gain Control (Slider → Volume)
```javascript
// Each slider controls one gainNode
sourceA[i].connect(gainNode[i]);
sourceB[i].connect(gainNode[i]);
gainNode[i].connect(masterGain); // or mergerNode for stereo
```

When a slider moves:
```javascript
gainNode[i].gain.setTargetAtTime(newLevel, context.currentTime, fAUDIOFADETIME);
```

#### 5. Master Gain Chain
```
sourceA/B[i] → gainNode[i] → mergerNode → dynCompressor → context.destination
```

### Key Functions

1. **`loadWebAudioSound(url, i)`**: Loads audio file via XHR, decodes to buffer
2. **`startWebAudio(i)`**: Starts playback of slider i (begins with variant A)
3. **`webAudioPlayAAt(i, time)`**: Schedules variant A to play at specific time
4. **`webAudioPlayBAt(i, time)`**: Schedules variant B to play at specific time
5. **`restartWebAudio(i)`**: Restarts a specific slider's playback

### Advanced Features

- **Synchronization**: Sliders can be grouped to sync playback (`sSYNCHRO` string)
- **Animation**: Can automatically modulate gain values over time
- **Stretch factor**: Controls timing between A/B variants
- **Playback rate**: Can change pitch/speed (`playbackFactor[i]`)
- **Dynamic compressor**: Master output goes through a compressor for leveling

### Differences from Our Current Approach

| myNoise.net | Our Current Implementation |
|-------------|---------------------------|
| Client-side (Web Audio API) | Server-side (Python synthesis) |
| 20 files (10 A + 10 B variants) | 10 files (single loop each) |
| Alternating A/B for seamless loops | Single file looping |
| Real-time slider updates | Requires server round-trip |
| Browser handles decoding | We decode server-side |

### Recommendations for Our Implementation

1. **Keep server-side approach** for now (simpler, no browser compatibility issues)
2. **Consider A/B variants** if we want seamless loops (requires 20 files instead of 10)
3. **Add client-side Web Audio API version** as optional enhancement for real-time mixing
4. **Current single-file loops are fine** - A/B variants are a nice-to-have, not essential

## Code Location
- **Full JavaScript**: `mynoise_spaceship_script.js` (129KB, ~2900 lines) - extracted from downloaded HTML
- **Original PHP file**: `docs/spaceshipNoiseGenerator.php` (5980 lines) - the actual source file from myNoise.net

## Important Note: PHP vs JavaScript

**The file is named `.php` but contains HTML + JavaScript, not server-side PHP audio processing.**

- The `.php` extension is used because PHP can inject dynamic content (presets, user settings, etc.)
- **All audio mixing happens client-side** using JavaScript Web Audio API
- No server-side audio processing - PHP only generates the HTML/JavaScript page
- The browser downloads 20 audio files and mixes them in real-time using Web Audio API

This is a common pattern: PHP generates the page, JavaScript handles the audio.

