# Coding Standards

The project favors clear, typed boundaries without pretending every legacy
helper already meets that bar. Apply the standard to new code and touched code;
do not churn unrelated modules just to satisfy style rules.

## Required For New Or Touched Code

- Public module functions, service methods, view helpers, and model helpers
  should have type annotations for parameters and return values.
- Public APIs, domain services, management commands, and non-obvious helpers
  should have docstrings that explain behavior or constraints.
- Tests should use descriptive names and assert behavior that can fail for a
  product reason. Avoid tests that only restate implementation details.
- Prefer absolute imports. Use local imports only to break circular imports or
  avoid optional heavy dependencies during module import.

## Accepted Legacy Debt

Older modules still contain untyped helpers and missing docstrings. Those are
accepted as legacy debt unless the code is being changed for product behavior.
When touching a legacy function, improve its signature or docstring if doing so
reduces ambiguity without expanding the scope of the change.

## Enforcement

- Review new and modified code against this document.
- Run the fast test suite before merging behavior changes.
- Use `ruff` formatting and linting when the local environment has it
  installed; do not mix broad mechanical lint rewrites with functional fixes.

This keeps code review focused on meaningful behavior while still raising the
standard at active boundaries.
