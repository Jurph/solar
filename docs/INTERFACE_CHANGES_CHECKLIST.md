# Interface Changes: Systematic Checklist

## The Problem

**Common LLM coding failure:** Change one side of an interface without checking what depends on it.

**Examples:**
- Add function → forget to export it
- Remove DOM element → forget to remove JS references  
- Add constant → forget to define it
- Rename function → forget to update callers
- Delete endpoint → forget client still calls it

---

## The Checklist

Before committing an interface change, verify ALL of these:

### 1. Exports & Visibility
- [ ] If you added a function to a module, is it exported where needed?
- [ ] If you renamed/deleted something, are all imports updated?
- [ ] If you made something public/private, does visibility match usage?

### 2. Callers & References  
- [ ] Use grep/search to find ALL references to this name
- [ ] Check if any callers will break with your change
- [ ] Verify both direct calls and indirect references (configs, templates, etc.)

### 3. Dependencies (Both Directions)
- [ ] **Inputs:** What does this code depend on? Still available?
- [ ] **Outputs:** What depends on this code? Will it break?
- [ ] Check upstream AND downstream

### 4. Related State & Lifecycle
- [ ] If you added a variable, where is it initialized?
- [ ] If you added a resource, where is it cleaned up?
- [ ] If you changed a data structure, are all accessors updated?

---

## Illustrative Example

**Task:** Add a new API endpoint.

### ❌ Incomplete (breaks at runtime)
```python
# Step 1: Add function to api/user.py
def get_preferences(request):
    return {"theme": "dark"}

# Step 2: Add route
route("/api/preferences/", handler=get_preferences)
```

**BROKEN:** Function not exported from package, route can't find it.

### ✅ Complete (checklist followed)
```python
# Step 1: Add function
def get_preferences(request):
    return {"theme": "dark"}

# Step 2: Export in __init__.py
from .user import get_preferences

# Step 3: Add route  
route("/api/preferences/", handler=get_preferences)

# Step 4: grep "get_preferences" - verify no conflicts
```

---

## When to Apply This Rule

**Always check both sides when you:**
- Add/remove/rename functions or classes
- Add/remove HTML elements referenced in JavaScript
- Add/remove constants or configuration values
- Change function signatures (parameters, return types)
- Modify shared data structures
- Add/remove API endpoints or routes
- Change database schemas or models

---

## Red Flags (Pause & Check)

- **"Just added a function"** → Did you export it? Did you add the route?
- **"Just removed that element"** → Does JavaScript still reference it?
- **"Just renamed that"** → Did you grep and update ALL callers?
- **"This should be fine"** → No. Grep for ALL references first.
- **"Quick refactor"** → Interface changes are never quick if done correctly.

---

## The One-Sentence Rule

**When you change an interface, grep for all references and systematically verify both sides still connect.**

Interfaces have two sides - producer and consumer. Change one without checking the other = broken code.

---

## Real-World Failures from Dec 31, 2025

1. Added `health_check()` function → forgot export → `AttributeError: no attribute 'health_check'`
2. Removed `<span id="ttsQueueDisplay">` → forgot to remove JS references → `ReferenceError: ttsQueueDisplay is not defined`
3. Added `let ttsQueuePending` → already existed → `SyntaxError: redeclaration of let`
4. Removed `HEALTH_POLL_INTERVAL` → still referenced in `setInterval()` → `ReferenceError: HEALTH_POLL_INTERVAL is not defined`

All preventable by grepping before changing.
