#!/usr/bin/env python3
"""Check Solar's declared top-level dependencies against known usage."""

from __future__ import annotations

import ast
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
SCAN_DIRS = ("mysite", "tests", "scripts")


DEPENDENCY_IMPORTS = {
    "Django": {"django"},
    "networkx": {"networkx"},
    "openai": {"openai"},
    "pydantic": {"pydantic"},
    "PyYAML": {"yaml"},
    "requests": {"requests"},
    "torch": {"torch"},
    "torchaudio": {"torchaudio"},
    "chatterbox-tts": {"chatterbox"},
}

TOOLING_DEPS = {
    "codecov-cli",
    "pytest",
    "pytest-cov",
    "pytest-django",
    "pytest-timeout",
    "tomli",
}


def _normalize_dependency_name(spec: str) -> str:
    match = re.match(r"[A-Za-z0-9_.-]+", spec.strip())
    if not match:
        raise ValueError(f"Could not parse dependency spec: {spec!r}")
    return match.group(0)


def _load_declared_dependencies() -> set[str]:
    data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    project = data.get("project", {})
    optional = project.get("optional-dependencies", {})

    declared = set()
    for spec in project.get("dependencies", []):
        declared.add(_normalize_dependency_name(spec))
    for group_specs in optional.values():
        for spec in group_specs:
            declared.add(_normalize_dependency_name(spec))
    return declared


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for directory in SCAN_DIRS:
        root = REPO_ROOT / directory
        if not root.exists():
            continue
        files.extend(
            path for path in root.rglob("*.py") if "__pycache__" not in path.parts
        )
    return files


def _collect_import_roots() -> set[str]:
    roots: set[str] = set()
    interesting_roots = {
        root for values in DEPENDENCY_IMPORTS.values() for root in values
    }

    for path in _iter_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in interesting_roots:
                        roots.add(root)
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                if root in interesting_roots:
                    roots.add(root)
    return roots


def main() -> int:
    declared = _load_declared_dependencies()
    observed_import_roots = _collect_import_roots()

    used_declared = {
        dependency
        for dependency, import_roots in DEPENDENCY_IMPORTS.items()
        if dependency in declared and import_roots & observed_import_roots
    }

    expected_declared = used_declared | (declared & TOOLING_DEPS)
    unused = sorted(declared - expected_declared)

    observed_declared_roots = set()
    for dependency in declared:
        observed_declared_roots.update(DEPENDENCY_IMPORTS.get(dependency, set()))

    missing = sorted(
        dependency
        for dependency, import_roots in DEPENDENCY_IMPORTS.items()
        if import_roots & observed_import_roots and dependency not in declared
    )

    if not unused and not missing:
        print("Dependency audit passed: declared dependencies match known usage.")
        return 0

    if unused:
        print("Unused top-level dependencies:")
        for dependency in unused:
            print(f"  - {dependency}")

    if missing:
        print("Missing top-level dependencies:")
        for dependency in missing:
            print(f"  - {dependency}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
