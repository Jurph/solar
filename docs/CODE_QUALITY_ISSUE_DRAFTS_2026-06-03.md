# Code Quality Issue Drafts - 2026-06-03

> **Archived 2026-07-13 — historical snapshot.** Derived from the (also
> archived) 2026-06-03 review; several drafted issues are already fixed in the
> current codebase. Re-verify against current code before filing any of these.

These drafts are derived from `docs/CODE_QUALITY_REVIEW_2026-06-03.md`.

Attempted ticket creation in `Jurph/solar` failed with:

```text
GitHub API error 403: Resource not accessible by integration
```

Fetched issues #39-#41 show the repo currently uses `enhancement` for architecture, quality, race, and data-integrity cleanup. Use `enhancement` unless a more specific repo label is available in the GitHub UI.

## 1. Refactor Scale enum values for Python 3.12 compatibility

Labels: `enhancement`

## Summary

The `Scale(models.TextChoices)` definition stores `OrderedScale(int)` values. The project currently needs Python 3.10 because Django setup fails under Python 3.12 with:

```text
TypeError: 6 is not a string
```

This makes the runtime version constraint implicit and brittle. The model should not depend on Python-version-specific enum coercion behavior.

## Where in the codebase

- **`mysite/universe/models/scale.py:38-51`** - `Scale(models.TextChoices)` uses `OrderedScale(int)` values
- **`CLAUDE.md`** currently documents the Python 3.10 workaround

## Why it matters

Solar's dev environment can be rebuilt with uv, but it is pinned operationally to Python 3.10 until this is cleaned up. Future agents or contributors may reasonably try Python 3.12+ and hit a Django import-time failure before tests can run.

## Suggested fix

Refactor `Scale` so the Django database values are stable strings, and keep ordering as a separate explicit mapping or property. Preserve existing stored values via a migration if needed.

## Acceptance criteria

- Django setup/import succeeds on Python 3.12+
- Existing scale ordering behavior remains covered by tests
- Any required migration is explicit and backwards-compatible
- The Python 3.10-only workaround can be removed from project docs

## 2. Fix SOLAR_LLM_BENCH_DISABLE pytest fixture path

Labels: `enhancement`

## Summary

The `_install_llm_benchmark_hooks()` fixture in `tests/conftest.py` is implemented as a generator fixture, but the disabled path returns before reaching `yield`.

With `SOLAR_LLM_BENCH_DISABLE=1`, pytest setup fails with:

```text
ValueError: _install_llm_benchmark_hooks did not yield a value
```

## Where in the codebase

- **`tests/conftest.py:70-72`** - disabled path returns early
- **`tests/conftest.py:177`** - generator fixture yield occurs only on the enabled path

## Why it matters

This is a test-harness bug, not an application bug. It blocks a reasonable CI/local mode for disabling benchmark logging, and it makes test configuration less trustworthy.

## Suggested fix

Always yield from the fixture. For the disabled path, yield immediately and do no patch installation.

## Acceptance criteria

- `SOLAR_LLM_BENCH_DISABLE=1 .\venv\Scripts\python.exe -m pytest tests -m "not slow" -q` completes without fixture setup errors
- Benchmark logging still works when not disabled
- Add a focused test or fixture-level check so the disabled path cannot regress

## 3. Make TTS services importable without ML extras

Labels: `enhancement`

## Summary

`tts_service.py` imports optional ML dependencies at module import time. In the base/dev environment, `torch` and `torchaudio` are not installed, so importing `mysite.universe.services.tts_service` fails with `ModuleNotFoundError`.

`audio_worker.py` imports `ChatterboxTTSService` at module import time, which means command startup can fail before reaching the existing graceful degradation paths.

## Where in the codebase

- **`mysite/universe/services/tts_service.py:21-22`** - imports `torch` and `torchaudio` at module import time
- **`mysite/universe/management/commands/audio_worker.py:36`** - imports `ChatterboxTTSService` eagerly

## Why it matters

Optional ML support should be optional. The app and most tests should be importable in a lean dev environment, while ML-specific behavior should fail clearly only when actually invoked.

## Suggested fix

Move optional ML imports behind a lazy dependency boundary, or split the interface from the concrete Chatterbox implementation. Return a clear health/error state when ML extras are missing.

## Acceptance criteria

- `import mysite.universe.services.tts_service` succeeds in the base/dev environment without `torch` installed
- `audio_worker` can start far enough to report a useful TTS-unavailable health state
- ML-backed rendering still works when the ML extras are installed
- Tests cover missing-ML-dependency behavior without requiring `torch`

## 4. Unify direct-ascent route planning semantics

Labels: `enhancement`

## Summary

Direct-ascent routing policy exists in two places with subtly different behavior:

- `plan_route()` has an inline two-node direct-ascent branch
- `_plan_direct_ascent_route()` has separate logic used by `determine_maneuvers()`

The helper handles station destinations with `DOCK`, while the inline branch always appends `DEORBIT` and `LANDING`. Tests currently exercise private crafted transfer plans more than the public route-level station-destination behavior.

## Where in the codebase

- **`mysite/universe/services/route/plan.py:82-164`** - inline direct-ascent branch in `plan_route()`
- **`mysite/universe/services/route/plan.py:184-248`** - `_plan_direct_ascent_route()` helper
- **`mysite/universe/services/route/plan.py:271-278`** - helper used from `determine_maneuvers()`
- **`tests/test_route_planning.py:1150-1296`** - tests focus on crafted/private transfer-plan behavior

## Why it matters

Route planning is core domain logic. Duplicated policy increases the chance that two public flows disagree for the same mission shape, especially around station destinations and terminal maneuvers.

## Suggested fix

Move direct-ascent maneuver construction into one shared policy path. Then add public route-level tests that cover station and non-station destinations.

## Acceptance criteria

- Direct-ascent maneuver selection is implemented in one place
- Public `plan_route()` behavior and `determine_maneuvers()` agree for equivalent direct-ascent inputs
- Station destinations end with `DOCK`, not `DEORBIT`/`LANDING`
- Tests cover public route-level behavior, not only private helper internals

## 5. Make event_feed audio_ready reflect actual audio availability

Labels: `enhancement`

## Summary

`event_feed` can mark an event as `audio_ready` when the underlying audio file is missing. The feed logic checks `bool(event.audio_file)` or a cache key, but `event_audio()` later opens the file and falls through on `FileNotFoundError`.

The existing file-existence test coverage exercises a happy-path saved file, not a stale FileField pointing at a missing file.

## Where in the codebase

- **`mysite/universe/views/events.py:233-237`** - `audio_ready` uses FileField truthiness/cache state
- **`mysite/universe/views/events.py:426-443`** - `event_audio()` opens the stored file path and handles missing files
- **`mysite/universe/views/events.py:460-474`** - further audio response fallback paths
- **`tests/test_event_feed.py:385-442`** - happy-path file-existence coverage, missing stale-file case not proven

## Why it matters

The frontend can be told audio is ready, then fail when it asks for the file. That creates misleading UI state and weakens confidence in the audio pipeline tests.

## Suggested fix

Make `event_feed` use the same availability predicate as `event_audio()`, or extract a shared helper that checks both DB state and actual file availability.

## Acceptance criteria

- An event with a stale `audio_file` path and no file on disk reports `audio_ready: false`
- `event_feed` and `event_audio()` agree on readiness for ready, generating, stale, and missing states
- Tests cover the stale-file path explicitly

## 6. Extract mission spawning orchestration out of the view layer

Labels: `enhancement`

## Summary

`spawn_mission` and `process_mission_in_background()` contain substantial domain orchestration inside `mysite/universe/views/missions.py`: background thread management, ship/pilot creation, NavSat scheduling, route planning, dialogue generation, and event persistence.

Several existing issues target symptoms in this area, but the architecture keeps making those bugs hard to isolate and test.

## Where in the codebase

- **`mysite/universe/views/missions.py:68-343`** - mission orchestration and background processing
- **`mysite/universe/views/missions.py:302-305`** - daemon thread spawned from the view path
- Related existing issues: #37, #39, #40

## Why it matters

Views should adapt HTTP to application services. Keeping mission orchestration in the view layer makes transaction boundaries, concurrency, retries, and diagnostics harder to reason about. Current tests patch a large amount of behavior around the view instead of asserting service-level outcomes.

## Suggested fix

Extract a mission service boundary, for example:

- request parsing and HTTP response remain in the view
- mission scheduling/orchestration moves to a service module
- persistence happens through explicit transactional units
- background execution is behind an injectable runner/queue interface

## Acceptance criteria

- `spawn_mission` view is thin and delegates to a service
- Cargo and NavSat mission paths are covered through service-level tests
- Thread/queue behavior is injectable in tests
- Existing issue fixes for mission lifecycle/concurrency can be implemented without adding more view complexity

## 7. Gate or remove CSRF-exempt state-changing dev endpoints

Labels: `enhancement`

## Summary

Several state-changing endpoints are CSRF-exempt and/or unauthenticated. That may be acceptable for a local-only prototype, but the repo should make that boundary explicit and enforce it in code or configuration.

## Where in the codebase

- **`mysite/universe/views/missions.py:27-29`** - `spawn_mission`
- **`mysite/universe/views/missions.py:357-359`** - `run_demo`
- **`mysite/universe/views/events.py:320-322`** - `clear_events`
- **`mysite/universe/views/events.py:336-354`** - deletes event rows/files
- **`mysite/universe/views/simulation.py:46-98`** - `set_time_scale` / `skip_to_next_event`
- **`mysite/universe/views/audio_lab.py:237-239`** - `audio_lab_render`
- **`mysite/mysite/settings.py:34-39`** - hard-coded secret, `DEBUG=True`, empty `ALLOWED_HOSTS`

## Why it matters

These controls mutate simulation state, delete files/rows, or trigger expensive work. If this project is ever bound beyond localhost or run with a broader network surface, the current defaults are risky.

## Suggested fix

Decide and encode the intended deployment model:

- If local-only: add explicit local/dev guards and document that these endpoints are not production-safe
- If remotely accessible: add authentication/authorization and restore CSRF protection where applicable

## Acceptance criteria

- State-changing endpoints have an explicit access-control story
- `clear_events` and audio rendering cannot be triggered cross-site in an unintended environment
- Settings make local-only assumptions explicit, or production settings override them safely
- Tests cover denied access for whichever guard is chosen

## 8. Make coding standards enforceable or update the documented standard

Labels: `enhancement`

## Summary

The repo's coding standards are aspirational today. A quick AST scan excluding migrations found many functions without type annotations or docstrings, including in active app modules.

Approximate review snapshot:

- 133 functions missing type annotations out of 512
- 106 functions missing docstrings

## Example areas

- **`mysite/universe/models/actor.py`**
- **`mysite/universe/models/celestial.py`**
- **`mysite/universe/models/base.py`**
- **`mysite/universe/services/script_server.py`**
- **`mysite/universe/management/commands/start_simulation_loop.py`**

## Why it matters

A standard that is not enforced creates noisy reviews and inconsistent expectations for agents/contributors. Either the standard should become executable, or the docs should be softened to match the project's actual style.

## Suggested fix

Choose one direction:

1. Enforce a narrower standard with tooling/CI for new or touched code
2. Update the docs to describe the actual conventions and reserve stricter requirements for public APIs/domain services

## Acceptance criteria

- Project docs clearly state which functions require annotations/docstrings
- Tooling or review guidance enforces the chosen standard for new work
- Existing violations are either tracked by module or explicitly accepted as legacy debt

## 9. Split procedural_generation.py into focused modules

Labels: `enhancement`

## Summary

`mysite/universe/procedural_generation.py` is one of the largest files in the app and mixes several responsibilities: generation rules, naming/color decisions, object construction, and persistence-facing behavior.

The review also found placeholder/TODO-style color palette areas in the lower portion of the file.

## Where in the codebase

- **`mysite/universe/procedural_generation.py`** - large multi-responsibility module
- **`mysite/universe/procedural_generation.py:1850-1902`** - placeholder color palette/TODO area from review snapshot

## Why it matters

Generation logic is domain-heavy and likely to keep growing. Keeping it in one broad module makes targeted testing and safe extension harder, especially for future work around planets, stations, hazards, and mission variety.

## Suggested fix

Split opportunistically along domain boundaries as code is touched. Candidate boundaries:

- naming and textual flavor
- color/palette selection
- body/system generation rules
- persistence/adaptation helpers

Avoid a large mechanical rewrite unless there is a concrete feature or bugfix that benefits from it.

## Acceptance criteria

- At least one high-churn generation responsibility is extracted into a focused module
- Public behavior is covered by characterization tests before extraction
- The remaining module has clearer responsibility boundaries
- Placeholder palette TODOs are either resolved or tracked with narrower tickets

## 10. Decide policy for tracked and generated audio assets

Labels: `enhancement`

## Summary

The repo contains a large amount of tracked audio/voice data, while `.gitignore` now ignores `*.wav`. The review snapshot found roughly 105 audio/voice files totaling about 138 MB under paths such as:

- `audio/`
- `mysite/universe/static/universe/voices/`

Because existing files remain tracked, `.gitignore` does not remove them. It can also hide future intentional voice updates unless contributors remember to force-add them.

## Why it matters

Audio assets may be legitimate source material, generated artifacts, or local cache output. Mixing those categories makes repository size, reproducibility, and contributor workflow worse.

## Suggested fix

Define an asset policy:

- committed seed/source voice clips that are intentionally versioned
- generated audio output that should never be committed
- large or replaceable assets that should move to releases, LFS, or a documented download step

Then align `.gitignore` and tracked files with that policy.

## Acceptance criteria

- Repo docs explain which audio files are source assets vs generated output
- `.gitignore` no longer conflicts with the intended workflow
- Future voice prompt updates are not accidentally hidden by ignore rules
- Generated audio output is kept out of normal commits

## 11. Tighten low-signal tests and isolate external-system checks

Labels: `enhancement`

## Summary

The review found valuable tests in the suite, but also several low-signal patterns that can create false confidence:

- tests tied to private helpers or line-number-shaped coverage targets rather than public behavior
- heavily patched view tests around mission spawning
- keyword/diversity assertions in dialogue tests that are brittle but not strongly diagnostic
- tests that exercise external systems or other people's code, such as local LLM/Ollama and Chatterbox performance checks

## Example areas

- **`tests/test_route_planning.py`** - some direct-ascent coverage targets crafted/private transfer-plan behavior instead of public route outcomes
- **`tests/test_spawn_mission.py`** - high patch/mock density around a view that owns too much orchestration
- **`tests/test_dialogue_particles.py`** - many keyword/diversity assertions with limited diagnostic value
- **`tests/test_LLM.py`**, **`tests/test_ollama_structured_outputs.py`**, **`tests/test_chatterbox_performance.py`** - environment/external-system checks need clear isolation

## Why it matters

A large test suite is only useful if failures point at real product regressions. Tests that mostly validate mocks, third-party behavior, or incidental wording can slow development without improving confidence.

## Suggested fix

Create explicit test tiers and expectations:

- fast deterministic unit/domain tests for project logic
- integration tests for Django/database/service wiring
- optional local environment tests for LLM/TTS/Ollama behavior
- slow/performance tests that are opt-in and clearly marked

Then refactor the weakest tests as affected code is touched.

## Acceptance criteria

- External-system tests are clearly marked and excluded from the default fast suite
- Route and mission tests assert public behavior at the correct service boundary
- Dialogue tests prioritize semantic invariants over brittle keyword matching
- Coverage increases are not accepted unless the new tests have clear diagnostic value
