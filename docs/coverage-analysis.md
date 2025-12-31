# Coverage Analysis - What to Shore Up

**Overall:** 76% coverage (4607/6074 statements)

## 🔴 Dead Code Status

All identified dead code has been removed:

| File | Status |
|------|--------|
| `text_server.py` | ✅ Deleted |
| `shipping.py` | ✅ Deleted |
| `broadcast_event.py` | ✅ Deleted |
| `voice_server.py` | ✅ Deleted |
| `traffic_control.py` | ✅ Deleted |
| `simulation/*` | ✅ Deleted (entire old architecture) |
| `simulation_queue.py` | ✅ Deleted |
| `generate_celestials.py` | ✅ Deleted |

**Codebase is now clean of dead code.**

---

## 🟡 Dead Code Removed (Dec 31, 2025)

The following were confirmed dead and deleted:

| File | Lines | Reason |
|------|-------|--------|
| `simulation/agents/ship_agent.py` | 32 | Old architecture, never imported |
| `simulation/agents/station_agent.py` | 30 | Old architecture, never imported |
| `simulation/engine.py` | 21 | Old architecture, never imported |
| `simulation/events/*.py` | ~100 | Old architecture, never imported |
| `simulation_queue.py` | 67 | Superseded by SimulationQueue in start_simulation_loop.py |
| `generate_celestials.py` | 544 | Never imported |
| `traffic_control.py` | 26 | Only used by dead run_simulation.py |
| `run_simulation.py` | 29 | Dead management command |

**Total: ~840 lines removed, 386 tests still passing.**

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
✅ **DONE** - All dead code removed (Dec 31, 2025)

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

