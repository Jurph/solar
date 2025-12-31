# Coverage Analysis - What to Shore Up

**Overall:** 76% coverage (4607/6074 statements)

## 🔴 Dead Code Status

| File | Status | Action |
|------|--------|--------|
| `text_server.py` | **Already deleted** | ✅ Done |
| `shipping.py` | **Already deleted** | ✅ Done |
| `broadcast_event.py` | **Already deleted** | ✅ Done |
| `traffic_control.py` | **Still used** by `run_simulation.py` | Keep |
| `voice_server.py` | Empty file (1 blank line) | **DELETE** |

**Note:** Coverage report is stale (Dec 30). Run `pytest --cov` to refresh.

---

## 🟡 Future/Stub Features (0% coverage, not wired up yet)

| File | Statements | Notes |
|------|------------|-------|
| `simulation/agents/ship_agent.py` | 22 | Agent system not active |
| `simulation/agents/station_agent.py` | 21 | Agent system not active |
| `simulation/engine.py` | 14 | Agent engine not active |
| `simulation_queue.py` | 26 | Queue system not active |
| `generate_celestials.py` | 156 | Procedural generation, separate feature |

**Recommendation:** Keep, but don't test until these features are wired up.

---

## 🔴 Critical System Components Needing Tests

These are **actively used** in the working audio pipeline:

| File | Coverage | Missing | Priority |
|------|----------|---------|----------|
| `dialogue_server.py` | **16%** | 100 | HIGH - core dialogue generation |
| `views/events.py` | **69%** | 74 | HIGH - event_audio endpoint |
| `tts_service.py` | **58%** | 66 | HIGH - TTS we just fixed |
| `audio_plans.py` | **67%** | 30 | MEDIUM - audio plan generation |
| `dialogue/base.py` | **50%** | 60 | MEDIUM - dialogue particle base |
| `dialogue/particles.py` | **61%** | 160 | MEDIUM - dialogue particles |

---

## 🟢 Well-Tested Components (keep as-is)

| File | Coverage |
|------|----------|
| `audio_profile.py` | 100% |
| `audio_synth.py` | 85% |
| `procedural_generation.py` | 95% |
| `navigation.py` | 96% |
| `llm_service.py` | 95% |
| `script_server.py` | 85% |

---

## Recommended Actions

### 1. Clean Up Dead Code
```
- mysite/universe/services/voice_server.py (DELETE - empty file)
```
*(text_server.py, shipping.py, broadcast_event.py already deleted)*

### 2. Add Tests for Critical Audio Path
The audio pipeline we just fixed needs better test coverage:

1. **`dialogue_server.py` (16%)** - Test the actual dialogue generation flow
2. **`views/events.py` (69%)** - Add tests for edge cases in event_audio
3. **`tts_service.py` (58%)** - Mock-based tests for TTS error handling

### 3. Add Tests for Supporting Components
Lower priority but worth covering:

1. **`audio_plans.py` (67%)** - Test all actor type audio plans
2. **`dialogue/base.py` (50%)** - Test base particle functionality
3. **`controller_physics.py` (26%)** - Physics calculations need validation

---

## What NOT to Test

- Migrations (100% or not meaningful to test)
- Empty `__init__.py` files
- Stub/future features that aren't wired up yet
- Generated code

