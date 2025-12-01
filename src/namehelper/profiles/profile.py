"""The constraint-profile abstraction.

HLD "Constraint Profile" and "Constraint Profile Catalog" require
resource-specific naming rules to be encoded as a self-contained, declarative
envelope rather than scattered through the planner or component model.
PROBLEM.md "Resource Constraints Are Not Uniform" explains why a single
generic rule set would be either unsafe or useless; TECHNICAL.md "Constraint
Profiles" enumerates the dimensions a profile must be able to express.

:class:`ConstraintProfile` is that envelope. It is pure data plus one
deterministic predicate (:meth:`ConstraintProfile.permits`) that evaluates a
concrete candidate value against the *encoded rules of the profile itself*.
It deliberately does **not** reconcile a :class:`namehelper.core.NamePlan`,
choose representations, account for budget, or emit findings — that planning
and validation behavior is a separate workstream. Keeping the profile a
declarative, isolated unit is what lets resource coverage grow by adding
profiles instead of rewriting the core.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from namehelper.diagnostics.certainty import Certainty

__all__ = [
    "Casing",
    "Uniqueness",
    "SupportLevel",
    "ConstraintProfile",
]


@lru_cache(maxsize=None)
def _compiled(pattern: str) -> re.Pattern[str]:
    """Compile and cache a profile regex (patterns are a small fixed set)."""
    return re.compile(pattern)


class Casing(Enum):
    """The casing expectation a profile imposes on a final value.

    - ``ANY``: mixed case is permitted.
    - ``LOWER``: the value must be entirely lower-case.
    - ``UPPER``: the value must be entirely upper-case.
    """

    ANY = "any"
    LOWER = "lower"
    UPPER = "upper"


class Uniqueness(Enum):
    """The scope at which a resource expects its name to be unique.

    This records an *expectation* the caller must plan for (it drives how much
    uniqueness budget a name needs); the library does not verify availability
    against AWS (HLD "Uniqueness Strategy" / PROBLEM.md "Uniqueness Is
    Practical, Not Absolute").

    - ``NONE``: no uniqueness requirement (name need not be distinct).
    - ``ACCOUNT``: unique within an AWS account.
    - ``ACCOUNT_REGION``: unique within an account and region.
    - ``GLOBAL``: globally unique across all AWS accounts.
    """

    NONE = "none"
    ACCOUNT = "account"
    ACCOUNT_REGION = "account-region"
    GLOBAL = "global"


class SupportLevel(Enum):
    """How completely this profile models its AWS surface.

    HLD Risk 3 / acceptance criteria require partially-supported surfaces to
    be represented *explicitly* rather than silently treated as fully modeled.

    - ``SUPPORTED``: the resource's naming envelope is modeled with reasonable
      proof-of-concept fidelity.
    - ``PARTIAL``: only a conservative subset of the real rules is modeled;
      callers should treat verdicts as indicative, not authoritative.
    """

    SUPPORTED = "supported"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class ConstraintProfile:
    """A resource-aware naming envelope.

    Fields cover the dimensions TECHNICAL.md "Constraint Profiles" requires a
    profile to express:

    - ``resource``: stable identifier of the AWS surface (catalog key).
    - ``max_length`` / ``min_length``: length ceiling and floor.
    - ``allowed_pattern``: regex (unanchored body) the *whole* value must
      fully match — this carries both character restrictions and structural
      formatting requirements.
    - ``forbidden_pattern``: optional regex that, if it matches anywhere,
      rejects the value (authors anchor it as needed). Used for formatting
      restrictions such as "must not look like an IP" or reserved prefixes.
    - ``casing``: required casing of the final value.
    - ``separators``: separator characters considered valid for this surface.
    - ``uniqueness``: the uniqueness scope the caller must plan for.
    - ``max_validation_certainty``: the strongest knowledge level at which
      this profile yields a deterministic verdict. Syntactic profiles can
      reason exactly about a concrete string; weaker inputs degrade what the
      profile can honestly claim (HLD "Knowledge and Certainty Model").
    - ``support``: whether the rules are fully or only partially modeled.
    - ``notes``: human explanation of curation choices and known gaps.
    """

    resource: str
    max_length: int
    allowed_pattern: str
    min_length: int = 1
    forbidden_pattern: str | None = None
    casing: Casing = Casing.ANY
    separators: tuple[str, ...] = ("-",)
    uniqueness: Uniqueness = Uniqueness.NONE
    max_validation_certainty: Certainty = Certainty.EXACT
    support: SupportLevel = SupportLevel.SUPPORTED
    notes: str = ""

    def __post_init__(self) -> None:
        """Fail fast on a mis-declared profile (core principle #10)."""
        if not 1 <= self.min_length <= self.max_length:
            raise ValueError(
                f"{self.resource}: invalid length bounds "
                f"min={self.min_length} max={self.max_length}"
            )
        # Surface a bad pattern at import time, not on first use.
        _compiled(self.allowed_pattern)
        if self.forbidden_pattern is not None:
            _compiled(self.forbidden_pattern)

    def permits(self, value: str) -> bool:
        """Whether ``value`` satisfies this profile's encoded envelope.

        Deterministic and side-effect free: checks only the rules this profile
        declares (length, allowed/forbidden patterns, casing). It is the
        operational form of the encoded rules, not the planning engine — it
        takes a concrete final string and answers yes/no.
        """
        if not self.min_length <= len(value) <= self.max_length:
            return False
        if _compiled(self.allowed_pattern).fullmatch(value) is None:
            return False
        if (
            self.forbidden_pattern is not None
            and _compiled(self.forbidden_pattern).search(value) is not None
        ):
            return False
        if self.casing is Casing.LOWER and value != value.lower():
            return False
        if self.casing is Casing.UPPER and value != value.upper():
            return False
        return True
