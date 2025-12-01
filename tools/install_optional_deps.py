#!/usr/bin/env python3
"""Install optional dependency groups into a repo-local package directory."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import tomllib


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
TARGET = ROOT / ".python_packages"
DEFAULT_GROUPS = ("dev", "examples")


def _load_optional_dependencies() -> dict[str, list[str]]:
    data: dict[str, Any] = tomllib.loads(PYPROJECT.read_text())
    project = data.get("project", {})
    optional = project.get("optional-dependencies", {})
    return {
        str(group): list(requirements)
        for group, requirements in optional.items()
    }


def _resolve_groups(
    available: dict[str, list[str]], requested: list[str]
) -> list[str]:
    groups = requested or list(DEFAULT_GROUPS)
    missing = [group for group in groups if group not in available]
    if missing:
        supported = ", ".join(sorted(available))
        raise SystemExit(
            "Unknown optional dependency group(s): "
            f"{', '.join(missing)}. Supported: {supported}"
        )
    return groups


def _dedupe(requirements: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for requirement in requirements:
        if requirement in seen:
            continue
        seen.add(requirement)
        ordered.append(requirement)
    return ordered


def main(argv: list[str]) -> int:
    available = _load_optional_dependencies()
    groups = _resolve_groups(available, argv[1:])

    requirements: list[str] = []
    for group in groups:
        requirements.extend(available[group])
    requirements = _dedupe(requirements)

    if not requirements:
        print("No optional dependencies selected.")
        return 0

    TARGET.mkdir(exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--target",
        str(TARGET),
        *requirements,
    ]
    print(
        "Installing optional dependency groups "
        f"{', '.join(groups)} into {TARGET}"
    )
    subprocess.run(cmd, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
