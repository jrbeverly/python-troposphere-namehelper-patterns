"""The result model.

HLD "System Context" and "Validation Is a Product Feature" require the
library to return both an output *and* the diagnostics that explain it,
rather than a bare string. :class:`NameResult` is that structured return
value: it carries the rendered output (when one could be produced), the
:class:`NamePlan` whose choices led to it, and the diagnostic findings
gathered along the way.

The result is a pure data carrier. It deliberately does not embed validation
policy: whether its findings block generation is resolved by
:class:`namehelper.diagnostics.ValidationPolicy` so that decision stays
consistent and caller-controlled.
"""

from __future__ import annotations

from dataclasses import dataclass

from namehelper.core.plan import NamePlan
from namehelper.diagnostics.certainty import Certainty
from namehelper.diagnostics.findings import Finding

__all__ = ["NameResult"]


@dataclass(frozen=True, slots=True)
class NameResult:
    """Structured outcome of planning/validating a name.

    ``rendered`` is the produced name, or ``None`` when no compliant output
    could be produced (e.g. unresolved over-budget). ``plan`` is the
    structured composition that led here, and ``findings`` are the diagnostics
    explaining why the result is safe, unsafe, or approximate.
    """

    plan: NamePlan
    rendered: str | None = None
    findings: tuple[Finding, ...] = ()

    @property
    def certainty(self) -> Certainty:
        """Overall certainty, derived from the plan's composition."""
        return self.plan.certainty

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)
