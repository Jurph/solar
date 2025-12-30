# Audio Profile Assignment: Current State and Issues

## Current Behavior

### ✅ New Actors (Created via `.create()`)
- **Pilot.create()**: Calls `assign_audio_profile()` → Creates profile, assigns random voice_template, assigns room_tone based on ship size
- **Controller.create()**: Calls `assign_audio_profile()` → Creates profile, assigns random voice_template, assigns controller room_tone
- **Satellite.create()**: Calls `assign_audio_profile()` → Creates profile, assigns random voice_template, NO room_tone

### ❌ Existing Actors (Created Before Audio Code)
- **No automatic assignment** - They may not have audio profiles at all
- **No migration backfill** - Migrations only create the AudioProfile model, don't assign profiles to existing actors
- **No on-demand assignment** - If profile is missing, code just logs warning and skips

### ⚠️ On-Demand Profile Creation
- **audio_plans.py**: Uses `get_or_create()` to create empty profile if missing, but **doesn't assign voice_template or room_tone**
- **events.py**: Just logs warning if profile missing, **doesn't create one**

## Problems

1. **Existing actors have no voices** - If an actor was created before audio code, they won't have a voice_template assigned
2. **Empty profiles created on-demand** - `audio_plans.py` creates profiles but doesn't populate them
3. **assign_audio_profile() overwrites existing assignments** - If called again, it will reassign voice_template even if one already exists
4. **No idempotency** - `assign_audio_profile()` doesn't check if voice_template is already set

## Code Locations

### Profile Assignment
- **`mysite/universe/models/actor.py`**:
  - `Pilot.assign_audio_profile()` (line 137)
  - `Controller.assign_audio_profile()` (line 237)
  - `Satellite.assign_audio_profile()` (line 330)
  - Called from `Pilot.create()`, `Controller.create()`, `Satellite.create()`

### Profile Usage
- **`mysite/universe/views/events.py`**: Gets profile, logs warning if missing (line 166-170)
- **`mysite/universe/services/audio_plans.py`**: Creates empty profile if missing (line 87-93)

## What Should Happen

1. **On actor creation**: Assign profile with voice_template and room_tone (✅ already does this)
2. **On-demand for existing actors**: If profile missing or incomplete, assign it automatically
3. **Idempotent assignment**: Only assign voice_template if not already set
4. **Migration/backfill**: Optionally create a management command to backfill existing actors

## Recommended Fixes

1. ✅ **Make `assign_audio_profile()` idempotent** - Only assign voice_template if not already set (FIXED)
2. ✅ **Add on-demand assignment in audio pipeline** - If profile missing or incomplete, call `assign_audio_profile()` automatically (FIXED)
3. ⏳ **Create management command** - `assign_audio_profiles` to backfill existing actors (OPTIONAL - on-demand assignment should handle most cases)

## Fixes Applied

### 1. Idempotent Assignment
- **`Pilot.assign_audio_profile()`**: Now checks if `voice_template` is already set before assigning
- **`Controller.assign_audio_profile()`**: Now checks if `voice_template` is already set before assigning
- **`Satellite.assign_audio_profile()`**: Now checks if `voice_template` is already set before assigning
- **Room tone**: Still updates (ship size may change), but voice_template is preserved

### 2. On-Demand Assignment
- **`mysite/universe/views/events.py`**: If profile missing, calls `assign_audio_profile()` automatically
- **`mysite/universe/services/audio_plans.py`**: If profile missing or incomplete (no voice_template), calls `assign_audio_profile()` automatically
- Both check actor type (Pilot/Controller/Satellite) and call the appropriate method

### 3. Behavior
- **New actors**: Get profiles assigned on creation (unchanged)
- **Existing actors**: Get profiles assigned automatically when first used in audio pipeline
- **Incomplete profiles**: Get voice_template assigned automatically if missing
- **Idempotent**: Calling `assign_audio_profile()` multiple times won't overwrite existing voice_template

