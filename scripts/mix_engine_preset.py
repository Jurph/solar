"""
Mix engine noise components into a single preset WAV file.

Usage:
    python mix_engine_preset.py <preset_name> <duration_seconds> <settings_json>
    
Example:
    python mix_engine_preset.py medium_engine_noise 30.0 '{"component_1_gain": 0.73, ...}'
"""

import json
import os
import sys
import wave
import struct
from pathlib import Path

# Import audio utilities from the project
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "mysite"))
from mysite.universe.services.audio_synth import _read_wav_mono_float, _resample_linear


def mix_engine_preset(preset_name: str, duration_seconds: float, settings: dict, output_dir: str = "audio"):
    """
    Mix the 10 engine noise components into a single looped WAV file.
    
    Args:
        preset_name: Output filename (without .wav extension)
        duration_seconds: Duration of the output file in seconds
        settings: Dictionary with component_1_gain through component_10_gain
        output_dir: Directory to save the output file
    """
    sample_rate = 48000
    num_samples = int(duration_seconds * sample_rate)
    
    # Initialize mix buffer
    mix = [0.0] * num_samples
    
    # Base directory for audio files
    base_dir = Path(__file__).parent
    static_audio_dir = base_dir / "mysite" / "universe" / "static" / "universe" / "audio"
    root_audio_dir = base_dir / "audio"
    
    # Load and mix each component
    for i in range(1, 11):
        gain_key = f"component_{i}_gain"
        gain = float(settings.get(gain_key, 0.0))
        
        if gain <= 0.0:
            continue  # Skip components with zero gain
        
        # Try to find the variant-a file
        num_str = f"{i:02d}"
        variant_file = f"audio-{num_str}-variant-a.wav"
        
        # Try static directory first, then root audio directory
        variant_path = None
        for audio_dir in [static_audio_dir, root_audio_dir]:
            candidate = audio_dir / variant_file
            if candidate.exists():
                variant_path = str(candidate)
                break
        
        if not variant_path:
            print(f"Warning: Could not find {variant_file}, skipping component {i}")
            continue
        
        try:
            # Load the audio file
            src_sr, samples = _read_wav_mono_float(variant_path)
            
            # Resample if needed
            if src_sr != sample_rate:
                samples = _resample_linear(samples, src_sr, sample_rate)
            
            # Loop the samples to fill the duration
            sample_idx = 0
            for j in range(num_samples):
                mix[j] += samples[sample_idx % len(samples)] * gain
                sample_idx += 1
            
            print(f"Mixed component {i} (gain={gain:.2f}) from {variant_path})")
            
        except Exception as e:
            print(f"Error loading component {i} from {variant_path}: {e}")
            continue
    
    # Normalize to prevent clipping (simple peak normalization)
    max_amplitude = max(abs(s) for s in mix) if mix else 1.0
    if max_amplitude > 1.0:
        normalize_factor = 0.99 / max_amplitude
        mix = [s * normalize_factor for s in mix]
        print(f"Normalized by factor {normalize_factor:.4f} to prevent clipping")
    
    # Write WAV file
    output_path = Path(output_dir) / f"{preset_name}.wav"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        
        # Convert float samples to 16-bit PCM
        for sample in mix:
            # Clamp to [-1.0, 1.0] and convert to 16-bit integer
            clamped = max(-1.0, min(1.0, sample))
            pcm_value = int(clamped * 32767)
            wf.writeframes(struct.pack("<h", pcm_value))
    
    print(f"Saved preset to {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nAlternatively, provide a JSON file path as the third argument.")
        sys.exit(1)
    
    preset_name = sys.argv[1]
    duration_seconds = float(sys.argv[2])
    
    # If third arg is a file path, load from file; otherwise parse as JSON string
    if len(sys.argv) >= 4:
        if os.path.exists(sys.argv[3]):
            with open(sys.argv[3], "r") as f:
                settings = json.load(f)
        else:
            try:
                settings = json.loads(sys.argv[3])
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}")
                sys.exit(1)
    else:
        # Default: look for preset_name_settings.json
        settings_file = f"{preset_name}_settings.json"
        if os.path.exists(settings_file):
            with open(settings_file, "r") as f:
                settings = json.load(f)
        else:
            print(f"Error: No settings provided and {settings_file} not found")
            sys.exit(1)
    
    mix_engine_preset(preset_name, duration_seconds, settings)

