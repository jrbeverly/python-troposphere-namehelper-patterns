"""Composition and planning core.

Responsibility (HLD "Composition and Planning Core"): model the name as a
structured plan and reconcile it against the selected constraint profile;
reserve budget for separators and fixed segments; identify where the plan is
valid, risky, or impossible.

Boundaries: this layer must stay deterministic and side-effect free. It must
*not* embed resource-specific AWS details (see :mod:`namehelper.profiles`) and
must *not* depend on :mod:`namehelper.adapters`. The findings, certainty, and
policy vocabulary lives in :mod:`namehelper.diagnostics`; the core depends on
it one-way (never the reverse).

:func:`plan_name` is the deterministic planning and visible
constraint-resolution engine; the plan / result types are the structured
artifacts it produces and that callers reason about. :func:`render` (HLD
"Normalization and Rendering Layer") is the dedicated string-shaping step the
planner delegates to so visible-structure decisions stay explainable in one
place; it produces a :class:`RenderedName`.
"""

from namehelper.core.plan import NamePlan, PlanSegment
from namehelper.core.planner import plan_name
from namehelper.core.rendering import NamingStyle, RenderedName, render
from namehelper.core.result import NameResult

__all__ = [
    "PlanSegment",
    "NamePlan",
    "NameResult",
    "plan_name",
    "NamingStyle",
    "RenderedName",
    "render",
]
