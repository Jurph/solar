# CI/CD Setup - CircleCI & Codecov

## Overview

Solar uses CircleCI for continuous integration and Codecov for coverage tracking.

---

## CircleCI Configuration

### What It Does
- Runs on every push to GitHub
- Installs dependencies from `requirements.txt`
- Runs full test suite (excluding slow TTS tests: `-m "not slow"`)
- Generates coverage report
- Uploads to Codecov

### Configuration File
`.circleci/config.yml`

**Note:** Uses Codecov CLI (not orb) to avoid requiring "Allow uncertified public orbs" setting.

### Running Tests Locally (Same as CI)
```bash
# Activate venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Run tests with coverage
pytest tests -m "not slow" --cov=mysite/universe --cov-report=xml --cov-report=term -v
```

### Excluded Tests
**Slow tests (`@pytest.mark.slow`)** are excluded from CI:
- `test_chatterbox_performance.py` - Loads real TTS model (60s+ GPU warmup)
- Some LLM integration tests

**Why:** CI environment doesn't have GPU, and these tests require heavy models.

---

## Codecov Configuration

### Coverage Targets
- **Project coverage:** 80% target (72% threshold)
- **Patch coverage:** 70% target for new code
- **Range:** 70-100% (yellow below 70%, green above 80%)

### Ignored Paths
- `mysite/universe/migrations/` - Auto-generated Django migrations
- `mysite/manage.py` - Django boilerplate
- `mysite/wsgi.py` - WSGI entry point
- `tests/**` - Test files themselves
- `**/conftest.py` - Pytest configuration

### Configuration File
`.codecov.yml`

---

## Badges

Added to `README.md`:
- **CircleCI:** Build status (passing/failing)
- **Codecov:** Coverage percentage

```markdown
[![CircleCI](https://dl.circleci.com/status-badge/img/circleci/Jurph/solar/tree/main.svg?style=shield)](https://dl.circleci.com/status-badge/redirect/circleci/Jurph/solar/tree/main)
[![codecov](https://codecov.io/gh/Jurph/solar/branch/main/graph/badge.svg)](https://codecov.io/gh/Jurph/solar)
```

---

## First-Time Setup

### 1. Enable CircleCI
1. Go to https://circleci.com/
2. Sign in with GitHub
3. Add project: "Jurph/solar"
4. CircleCI will automatically detect `.circleci/config.yml`

### 2. Enable Codecov
1. Go to https://codecov.io/
2. Sign in with GitHub
3. Add repository: "Jurph/solar"
4. Copy the upload token from Codecov repository settings
5. In CircleCI Project Settings:
   - Go to Environment Variables
   - Add variable: `CODECOV_TOKEN` = [paste token from Codecov]

**Token is required for authenticated uploads.**

### 3. Push to GitHub
```bash
git add .circleci/config.yml .codecov.yml README.md requirements.txt
git commit -m "Add CircleCI and Codecov integration"
git push
```

CircleCI will automatically run tests on push.

---

## Maintaining Coverage

### Current Coverage: 82%

**Well-covered (>90%):**
- Core models (celestial, navigation, display, simulation)
- Audio profiles
- Route planning
- LLM service
- Procedural generation

**Needs improvement (<70%):**
- Audio worker (50% - infinite loop and error paths not measured)
- Some dialogue particles (content variations not all exercised)
- TTS service (66% - model loading paths require GPU)

### Coverage Goals

**Target: 85%+** for core functionality

**Don't chase 100%:**
- Entry points (`manage.py`, `wsgi.py`) - Django boilerplate
- Infinite loops (audio worker main loop)
- Error paths requiring hardware failures (GPU OOM, disk full)
- Some procedural generation branches (random variations)

---

## Troubleshooting

### Tests Pass Locally But Fail in CI

**Common causes:**
1. **Missing dependency** in `requirements.txt`
2. **File paths** (CI uses Linux, you use Windows)
3. **Database differences** (CI uses in-memory SQLite)
4. **Environment variables** not set in CI

**Debug:**
- Check CircleCI build logs
- Look for import errors or missing modules
- Verify pytest.ini settings work on Linux

### Coverage Drops Below Target

**Expected drops:**
- New code not yet tested
- Refactoring that adds branches

**Action:**
1. Check Codecov PR comment for affected files
2. Add tests for new functionality
3. Don't chase trivial lines (error messages, logging)

### Slow Test Suite

**Current:** ~80 seconds for 387 tests (excluding slow tests)

**If it gets slower:**
- Check for database-heavy tests (use transactions)
- Look for network calls without mocks
- Profile with `pytest --durations=10`

---

## Related Documentation

- `audio_worker_design.md` - Audio worker architecture
- `ARCHITECTURE.md` - System architecture
- `INTERFACE_CHANGES_CHECKLIST.md` - Interface change procedures

**Last Updated:** December 31, 2025
