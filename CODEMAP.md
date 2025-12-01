# CODEMAP

Repository-specific structure and conventions for
`python-troposphere-namehelper-patterns`. The architecture is defined by
[`HLD.md`](HLD.md).

## Technology stack

- **Language:** Python (`requires-python >= 3.11`)
- **Packaging:** PEP 621 `pyproject.toml`, setuptools backend, `src/` layout
- **Runtime dependencies:** none (the core stays adapter-agnostic and
  lightweight per `PROBLEM.md` architectural constraints)
- **Tests:** stdlib `unittest` for the zero-dependency baseline loop;
  `pytest` available via the optional `[dev]` extra and pytest-compatible

## Module boundaries

The service scope is `src/namehelper/`. Modules map 1:1 to the HLD
"Repository and Module Shape" seams:

| Package                   | Responsibility                                   |
| ------------------------- | ------------------------------------------------ |
| `namehelper.api`          | Public ergonomic entrypoint (`NameHelper`)       |
| `namehelper.core`         | Composition, planning, budget evaluation         |
| `namehelper.components`   | Literal / derived / generated components         |
| `namehelper.profiles`     | AWS resource-specific constraint profiles        |
| `namehelper.adapters`     | Troposphere/CloudFormation integrations          |
| `namehelper.diagnostics`  | Findings, validation policy, explainability      |

**Dependency direction (one-way):** `api` → `core` → `components` /
`profiles` / `diagnostics`. `adapters` may depend on the core; the core must
never depend on `adapters`. This boundary is asserted by the contract tests.

## Tests

`tests/` mirrors the verification layers from the HLD:

- `tests/unit/` — fast, isolated module tests
- `tests/integration/` — cross-module / public-path behavior
- `tests/contract/` — public-surface and architectural-boundary contracts

## Developer loop

See [`README.md`](README.md#developer-loop). `make help` lists targets;
`make setup | test | e2e | check`. The baseline loop is dependency-free
(`PYTHONPATH=src`, stdlib `unittest`).
