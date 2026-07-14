# Code Quality and Test Architecture Review - 2026-06-03

> **Archived 2026-07-13 — historical snapshot.** Several findings below are
> fixed in the current codebase: `Scale`/Python 3.12 (`models/scale.py`), the
> `SOLAR_LLM_BENCH_DISABLE` fixture (`tests/conftest.py`), optional ML import
> isolation (`services/tts_service.py`), stale `audio_ready` handling
> (`views/events.py`), direct-ascent route duplication
> (`services/route/plan.py`), and dev-endpoint gating (`views/dev_guard.py`).
> Verify remaining items against current code before acting on them.

Scope: review only. No implementation fixes were made as part of this pass.

## Verification Snapshot

- `.\venv\Scripts\python.exe -m pytest tests -m "not slow" -q`
  - `863 passed, 3 skipped, 13 deselected, 43 subtests passed`
- `.\venv\Scripts\python.exe -m pytest tests -m "not slow" --cov=mysite/universe --cov-report=term-missing:skip-covered -q`
  - overall app coverage: 91%
  - notable low-coverage module: `mysite/universe/services/tts_service.py` at 6%
- `SOLAR_LLM_BENCH_DISABLE=1` single-test repro:
  - `.\venv\Scripts\python.exe -m pytest tests\test_actor.py::ActorModelTests::test_controller_creation -q`
  - fails during fixture setup with `ValueError: _install_llm_benchmark_hooks did not yield a value`

## Findings

### P1: `Scale` is tied to Python 3.10 behavior

`mysite/universe/models/scale.py` defines `Scale(models.TextChoices)` members using `OrderedScale(int)` values at lines 38-51. On Python 3.12 this fails during Django setup with `TypeError: 6 is not a string`; on Python 3.10 it is tolerated and coerced.

Impact:
- The project currently needs uv-managed Python 3.10 unless `Scale` is refactored.
- A future dependency or interpreter bump can break Django import before any tests run.

Clean direction:
- Store actual `TextChoices` values as strings (`"GX"`, `"SY"`, etc.).
- Keep ordering in a separate map/helper, not in the enum value type.
- Add a small import/startup test that makes this failure obvious if Python support changes.

### P1: `SOLAR_LLM_BENCH_DISABLE=1` breaks the whole pytest suite

`tests/conftest.py` makes `_install_llm_benchmark_hooks()` a generator fixture because it yields at line 177. But the disabled path returns before yielding at lines 70-72. Pytest treats that as an invalid generator fixture and errors before tests run.

Impact:
- The environment variable intended to disable benchmark logging is unsafe.
- This is the kind of test-harness bug that can be mistaken for widespread app failure.

Clean direction:
- In disabled/no-import paths, yield once and return after the yield, or split the fixture so non-generator paths are not mixed with generator cleanup.

### P2: Optional ML dependencies are not isolated at import boundaries

`mysite/universe/services/tts_service.py` imports `torch` and `torchaudio` at module import time (lines 21-22). The base/dev venv does not install those packages. Importing `mysite.universe.services.tts_service` in that venv raises `ModuleNotFoundError: No module named 'torch'`.

`mysite/universe/management/commands/audio_worker.py` also imports `ChatterboxTTSService` at module import time (line 36), so the management command cannot even reach its graceful `try/except` initialization path when ML extras are missing.

Impact:
- The optional `ml` extra is not actually optional for any code path that imports these modules.
- Fast tests mostly hide this by using `pytest.importorskip("torch")` or `sys.modules` mocks.

Clean direction:
- Move `torch` / `torchaudio` imports inside methods that actually need them.
- Let `tts_service.py` import in the base/dev environment and report TTS unavailable explicitly.
- Keep ML integration tests, but add a non-ML import test for the degraded path.

### P2: `spawn_mission` is a service hidden inside a Django view

`mysite/universe/views/missions.py` puts substantial mission business logic inside `spawn_mission()`:
- background thread definition and lifecycle: lines 68-70 and 339-343
- NavSat system selection and satellite creation: lines 75-151
- NavSat cadence/collision scheduling: lines 152-182
- event persistence and metadata mutation: lines 183-237
- cargo mission route/dialogue orchestration and persistence: lines 244-334

Impact:
- The view owns routing, scheduling, persistence, threading, and error policy.
- The endpoint returns `200` once the thread starts, while most failures happen after the HTTP response and are only logged.
- Tests rely heavily on patching fake services and immediate thread execution, which checks some side effects but not a clean mission-spawn contract.

Clean direction:
- Extract a `MissionSpawnService` and a `NavBroadcastScheduler`.
- Make the view parse HTTP input and return a job/result status, not own the mission algorithm.
- Give the service a direct, synchronous API for deterministic tests.

### P2: Direct-ascent routing policy is duplicated and can diverge

`mysite/universe/services/route/plan.py` has two direct-ascent implementations:
- an inline two-node special case in `plan_route()` at lines 82-164
- `_plan_direct_ascent_route()` at lines 184-248, used by `determine_maneuvers()` at lines 271-278

The helper handles station destinations with `DOCK` (lines 231-232). The inline two-node path always appends `DEORBIT` and `LANDING` after direct ascent (lines 138-159), with no station-destination branch.

Impact:
- Route behavior can differ depending on whether direct ascent entered through `plan_route()` or through a crafted `determine_maneuvers()` transfer plan.
- Tests at `tests/test_route_planning.py` lines 1150-1296 explicitly exercise private/internal branch shapes with crafted transfer plans, but that does not prove the public route-level behavior is correct.

Clean direction:
- Make `plan_route()` delegate all direct-ascent cases to the helper.
- Add route-level tests for station destination cases instead of only private transfer-plan tests.

### P2: `event_feed.audio_ready` can disagree with `event_audio`

`mysite/universe/views/events.py` reports feed readiness using:

```python
bool(event.audio_file) or event.id in cached_event_ids
```

at lines 233-237. That checks whether the file field has a name, not whether the file can be opened.

`event_audio()` does the stronger check: it tries to open the file and falls through to cache/pending if the file is missing (lines 426-443 and 460-474).

Impact:
- A stale `audio_file` path can make the feed tell the frontend audio is ready, while the audio endpoint returns `202 pending`.
- `tests/test_event_feed.py` lines 385-442 says it verifies file existence, but only covers the happy path where a saved file still exists. It does not cover stale file paths.

Clean direction:
- Align the feed's readiness policy with `event_audio()`.
- Add a feed-level stale-file test; audio endpoint stale-file tests are not enough.

### P2: State-changing dev controls are unauthenticated and CSRF-exempt

Several state-changing endpoints are `@csrf_exempt`, including:
- `spawn_mission()` in `views/missions.py` lines 27-29
- `run_demo()` in `views/missions.py` lines 357-359
- `clear_events()` in `views/events.py` lines 320-322
- `set_time_scale()` and `skip_to_next_event()` in `views/simulation.py` lines 46-98
- `audio_lab_render()` in `views/audio.py` lines 237-239

`clear_events()` deletes dialogue rows and audio files (events.py lines 336-354). `settings.py` is also explicitly development-only: hard-coded secret key at line 34, `DEBUG = True` at line 37, and `ALLOWED_HOSTS = []` at line 39.

Impact:
- This is probably acceptable for a local toy/dev server, but it is not cleanly separated from deployable app code.
- If the server is exposed beyond localhost, destructive controls are reachable without authentication or CSRF protection.

Clean direction:
- Gate dev controls behind staff/admin auth or an explicit dev-mode setting.
- Keep the audio lab and destructive reset endpoints out of any production URL set.

### P3: Coding standards are aspirational, not enforced

`CLAUDE.md` says all functions require type hints and docstrings. A quick AST scan excluding migrations found:
- 133 functions missing type annotations out of 512 functions
- 106 functions missing docstrings

Examples with notable gaps:
- `management/commands/start_simulation_loop.py`
- `models/actor.py`
- `models/celestial.py`
- `services/script_server.py`
- `models/base.py`

Impact:
- The stated code standard does not match the codebase.
- Reviewers and future agents may waste effort trying to conform locally while the repo has no consistent enforcement.

Clean direction:
- Either relax the documented rule or enforce it with tooling.
- Prefer enforcing signatures on service/view boundaries first rather than trying to annotate everything at once.

### P3: `procedural_generation.py` is under-reviewed relative to its size

`mysite/universe/procedural_generation.py` is the largest application source file. It mixes RNG utilities, distribution helpers, star/planet/moon generation, atmosphere generation, orbital calculations, and presentation color helpers.

The bottom of the file still has placeholder color generation TODOs at lines 1850-1902.

Impact:
- Coverage is high, but the module has too many reasons to change.
- Future edits risk unrelated churn and weaker review focus.

Clean direction:
- Split by responsibility when the next real procedural-generation feature lands: RNG/distributions, body generation, atmosphere, orbital math, and presentation palettes.

### P3: Tracked audio assets create repo hygiene friction

The repo tracks 105 audio/voice files under `audio/` and `mysite/universe/static/universe/voices/`, totaling about 138 MB. `.gitignore` now ignores `*.wav`, which does not untrack existing files but does make future voice/audio updates easy to miss unless `git add -f` is used.

Impact:
- This may be acceptable if voice prompts are canonical test/runtime fixtures.
- The policy is unclear: tracked canonical voice assets and ignored WAVs point in opposite directions.

Clean direction:
- Document which audio assets are canonical and should remain tracked.
- Move generated examples and scratch playback files fully out of version control.

## Unit Test Quality Assessment

### Real diagnostic value

The fast suite is not just smoke tests. Strong areas:
- route planning has many route/maneuver behavior checks
- event/audio degraded-state tests are much stronger than before
- simulation time re-anchoring tests check real invariants
- audio synthesis tests validate local DSP helpers without needing ML
- actor/event bookkeeping tests protect important persistence invariants

### Coverage theater / weak signal

There is still a meaningful amount of test code that is more about coverage count than app confidence:
- `tests/test_route_planning.py` has private branch tests tied to line numbers and crafted transfer plans.
- `tests/test_dialogue_particles.py` has many keyword/diversity assertions; these catch some regressions but do not prove operationally correct dialogue.
- `tests/test_spawn_mission.py` uses heavy patching around the view, thread, route service, script service, ship creation, pilot creation, and LLM service. These tests are useful for side effects, but they also reflect that `spawn_mission()` is too hard to test naturally.

### Tests that exercise other people's code

These should be treated as environment/integration smoke checks, not core regression signal:
- `tests/test_LLM.py` calls real local LLM endpoints and asks factual yes/no questions.
- `tests/test_ollama_structured_outputs.py` directly tests Ollama structured-output behavior.
- `tests/test_chatterbox_performance.py` measures local Chatterbox latency and writes artifacts.

These can be useful, but failures usually mean "local infrastructure changed" more than "Solar application logic regressed."

### Tests masking true corner cases

The clearest example is `event_feed.audio_ready`: the test name and comments claim file-existence validation, but the production code only checks FileField truthiness. The matching audio endpoint handles stale files correctly, so the feed and endpoint can disagree.

The direct-ascent route tests have a similar shape: private branch tests prove the helper behaves for a crafted internal plan, while the public `plan_route()` branch has its own duplicated logic.

### Slow/optional tests are not enough for TTS confidence

TTS tests are split between skipped mock-based tests and slow environment tests. In the base/dev environment, `torch` and `torchaudio` are absent, `tts_service.py` cannot import, and the worker command import path is not gracefully exercised.

That means the current suite has good confidence in audio planning/synthesis/serving, but weak confidence in the actual TTS service boundary.

## Recommended Cleanup Order

1. Fix the test harness disable flag.
2. Make `tts_service.py` importable without ML extras.
3. Unify direct-ascent routing through one helper and add public route-level tests.
4. Align `event_feed.audio_ready` with `event_audio()` and add stale-file feed tests.
5. Extract mission spawning and NavSat scheduling out of the view.
6. Decide whether CSRF-exempt dev controls are local-only forever or need auth/gating.
7. Make the type-hint/docstring standard enforceable or soften the standard.
8. Split `procedural_generation.py` opportunistically when touching procedural generation again.
