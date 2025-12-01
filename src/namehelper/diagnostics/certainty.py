"""The knowledge / certainty model.

HLD "Knowledge and Certainty Model" requires the system to treat values
according to how well they are known, and TECHNICAL.md makes this a
first-class abstraction. Collapsing it into a boolean ("known?") or a
free-form string would lose the distinction the rest of the system reasons
about, so the three levels are modeled as a closed enum.

This lives in :mod:`namehelper.diagnostics` (not :mod:`namehelper.core`)
because both the planning core and the diagnostics layer depend on it, and
the one-way dependency direction allows ``core -> diagnostics`` but never the
reverse.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["Certainty"]


class Certainty(Enum):
    """How well a value is known during planning.

    - ``EXACT``: fully known now; deterministic validation and exact budget
      accounting are possible.
    - ``BOUNDED``: not exactly known, but a meaningful upper bound / shape is
      known; conservative guardrails are possible.
    - ``ADVISORY``: only loosely predictable; no hard guarantees, warnings and
      suggestions are the primary tools.
    """

    EXACT = "exact"
    BOUNDED = "bounded"
    ADVISORY = "advisory"

    @classmethod
    def weakest(cls, *values: "Certainty") -> "Certainty":
        """Return the least-certain level among ``values``.

        A composition is only as certain as its least-certain part: any
        ``ADVISORY`` part makes the whole advisory; otherwise any ``BOUNDED``
        part makes it bounded; only an all-``EXACT`` set stays exact. With no
        values the result is ``EXACT`` (nothing unknown has been introduced).
        """
        order = (cls.EXACT, cls.BOUNDED, cls.ADVISORY)
        if not values:
            return cls.EXACT
        return max(values, key=order.index)
