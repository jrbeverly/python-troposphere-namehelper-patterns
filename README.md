# Trooposphere NameHelper

> [!WARNING]
> **AI-authored:** This change was autonomously planned and implemented by an AI software factory from a human-authored specification, with possible subsequent human review or modification.

A lightweight Python library for building valid AWS resource names from structured semantic parts, with constraint checking that catches problems before deploy time.

In infrastructure-as-code workflows, resource names often need to encode environment, service, region, and uniqueness context while staying within service-specific length and character limits. Doing this with ad hoc string assembly leads to late validation failures, inconsistent conventions, and names that lose meaning when truncated. `namehelper` treats naming as a planning problem: you describe what goes into a name, and the library tells you whether it fits the target resource's rules, what is risky, and what alternate forms are available if it does not fit.

```bash
make setup
make test
make e2e
make check
```

## Notes

- Names are assembled from ordered components, not glued-together strings.
- A component can be a literal value the caller already knows, a value derived from deploy-time context (stack name, region), or a generated identifier for uniqueness.
- Every component carries a certainty level — exact, bounded, or advisory — which determines how much the library can guarantee about the final name.
- AWS resource rules live in isolated profile objects so the core composition engine stays free of service-specific logic.
- Validation produces stable finding codes (like `over_budget` or `invalid_characters`) with severity levels; callers configure a validation policy that decides whether each code is fatal, a warning, or explicitly ignored.
- When a name is too long, alternate representations are surfaced as suggestions rather than silently applied, so the caller always chooses how to resolve length pressure.
- The library never contacts AWS APIs; it models syntactic naming rules at plan time and is honest about what it cannot verify, like global name availability.
- The core package has no runtime dependencies and all tests run with only the Python standard library.
- Design documents (`PROBLEM.md`, `HLD.md`, `TECHNICAL.md`) are the authoritative source for architectural decisions and drive implementation.
