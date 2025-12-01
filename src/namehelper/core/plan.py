"""Structured naming plans.

HLD "Structured Names, Not Flat Strings" and TECHNICAL.md "Composition and
Planning Behavior" require a name to be modeled as an ordered composition of
meaningful parts rather than a single string. :class:`NamePlan` is that
structured artifact: the planning choices a caller proposed, which the
planning and validation layers reason about and which a :class:`NameResult`
carries alongside its rendered output.

A plan segment records the chosen value, how well it is known, and which
representation form produced it. Recording the form keeps the result
traceable: a caller can see *which* representation each segment used (e.g. the
full vs. a shortened form) rather than only its resolved value, which is
required for the visible constraint-resolution loop. The component and
alternate-representation system itself lives in :mod:`namehelper.components`;
this layer only references the form enum, never its selection logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from namehelper.components.component import RepresentationForm
from namehelper.diagnostics.certainty import Certainty

__all__ = ["PlanSegment", "NamePlan"]


@dataclass(frozen=True, slots=True)
class PlanSegment:
    """One ordered, named part of a planned name.

    ``role`` is the semantic position (e.g. ``"env"``, ``"service"``),
    ``value`` is the chosen value for planning, and ``certainty`` records how
    well that value is known. ``form`` is the representation the planner
    selected for this segment; it is ``None`` when the segment was not built
    from a component (so nothing was selected) and is otherwise the concrete
    form, preserving which representation was used.
    """

    role: str
    value: str
    certainty: Certainty = Certainty.EXACT
    form: RepresentationForm | None = None


@dataclass(frozen=True, slots=True)
class NamePlan:
    """An ordered composition of segments joined by a separator.

    The plan is declarative: it describes what the caller proposed, not a
    normalized final string. Its overall :attr:`certainty` is the weakest of
    its segments — a plan is only as certain as its least-certain part.
    """

    segments: tuple[PlanSegment, ...] = ()
    separator: str = "-"

    @property
    def certainty(self) -> Certainty:
        """Combined certainty across all segments (weakest wins)."""
        return Certainty.weakest(*(s.certainty for s in self.segments))

    @property
    def roles(self) -> tuple[str, ...]:
        """The segment roles in composition order."""
        return tuple(s.role for s in self.segments)
