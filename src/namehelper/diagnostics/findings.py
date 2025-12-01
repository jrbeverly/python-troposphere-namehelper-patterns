"""Diagnostic findings.

HLD "Finding" defines a finding as a diagnostic conclusion produced during
planning or validation. A finding carries its own intrinsic seriousness
(:class:`Severity`); how that finding *behaves* for a given caller (fatal /
warning / ignored) is a separate, policy-controlled decision and lives in
:mod:`namehelper.diagnostics.policy`. Keeping the two apart is what lets the
same finding be a hard failure in a strict CI gate and a tolerated warning in
local exploration.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from namehelper.diagnostics.certainty import Certainty

__all__ = ["Severity", "Finding"]


class Severity(Enum):
    """The intrinsic seriousness of a finding, independent of policy.

    - ``VIOLATION``: a deterministic rule break.
    - ``WARNING``: a risky-but-not-certain condition (e.g. a bounded or
      advisory value that may not fit).
    - ``SUGGESTION``: informational; an alternate representation is available.
    """

    VIOLATION = "violation"
    WARNING = "warning"
    SUGGESTION = "suggestion"


@dataclass(frozen=True, slots=True)
class Finding:
    """An immutable diagnostic conclusion from planning or validation.

    ``code`` is a stable machine identifier (used by validation policy to
    target a specific finding); ``message`` is the human explanation.
    ``certainty`` records the knowledge level the finding was reasoned under
    when that distinction is meaningful, and ``component`` optionally names the
    plan segment the finding concerns so callers can see where constraint
    pressure originates.
    """

    code: str
    message: str
    severity: Severity
    certainty: Certainty | None = None
    component: str | None = None
