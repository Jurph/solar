# Testing

Solar's test suite has three practical tiers. Keep new tests in the narrowest
tier that proves project behavior.

## Fast Suite

Run the default diagnostic suite with:

```powershell
.\venv\Scripts\python.exe -m pytest tests -m "not slow and not external" -q
```

Fast tests should be deterministic and project-local. They may use Django's test
database, temporary files, mocks, or in-process services, but they should not
depend on a running Ollama server, a loaded LLM model, GPU availability, or host
performance.

## Integration Suite

Use integration tests for Django/database/service wiring where the behavior is
still controlled by the test process:

```powershell
.\venv\Scripts\python.exe -m pytest tests -m "not slow and not external"
```

Prefer public service or view behavior over private-helper coverage. If a test
needs heavy patching to make a view usable, consider whether the production code
needs a service boundary instead.

## External-System Suite

External-system tests must be marked with `external` and one or more narrower
markers such as `llm`, `ollama`, `tts`, or `performance`.

Examples:

```powershell
.\venv\Scripts\python.exe -m pytest tests -m external
.\venv\Scripts\python.exe -m pytest tests -m "external and llm"
.\venv\Scripts\python.exe -m pytest tests -m "external and tts"
```

These tests are useful for local confidence checks, benchmark runs, and hardware
validation, but they should not be treated as failures of project-local logic
when Ollama, Chatterbox, CUDA, or voice-model assets are unavailable.

## Test Quality Expectations

- Assert public behavior at the boundary users or services rely on.
- Avoid tests that mainly assert implementation line coverage.
- Use mocks to isolate slow or nondeterministic collaborators, not to recreate
  the implementation under test.
- Dialogue tests should prefer semantic invariants over brittle keyword lists.
- Coverage gains are only useful when the failing assertion would identify a
  real product regression.
