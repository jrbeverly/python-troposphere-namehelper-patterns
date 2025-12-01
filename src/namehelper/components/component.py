"""The component and representation model.

HLD "Component Model" requires the system to represent the different kinds of
naming inputs (``literal`` / ``derived`` / ``generated``) and the alternate
forms each input can take, exposing known bounds and uncertainty. TECHNICAL.md
"Structured Components" / "Representations" makes representations a core
technical abstraction rather than a convenience, and PROBLEM.md "Semantic Loss
Through Naive Shortening" is the reason: callers must be able to move from
"too long or too risky" to "acceptable" by *choosing a different known
representation*, never by silent truncation.

This layer only describes inputs and their forms. It deliberately does not
select a representation, account for a whole-name budget, or know any
resource-specific (AWS) rule — that planning behaviour lives in
:mod:`namehelper.core` and the rules live in :mod:`namehelper.profiles`.
Keeping the component layer rule-free is what lets a later planner ask "which
alternate representations exist?" generically.

It depends only on the :mod:`namehelper.diagnostics` certainty vocabulary
(one-way dependency direction; never the reverse).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from namehelper.diagnostics.certainty import Certainty

__all__ = [
    "ComponentSource",
    "RepresentationForm",
    "UniquenessStrategy",
    "Representation",
    "Component",
]


class ComponentSource(Enum):
    """How a component's value originates.

    - ``LITERAL``: a known, caller-supplied semantic value.
    - ``DERIVED``: produced from deployment / resource context (stack name,
      stack id, region, resource-derived segments) — often only known at
      deploy time.
    - ``GENERATED``: produced for uniqueness (e.g. a UUID-like fragment); the
      concrete value is not known until generation.
    """

    LITERAL = "literal"
    DERIVED = "derived"
    GENERATED = "generated"


class RepresentationForm(Enum):
    """A usable form a component can be rendered as.

    These are the forms TECHNICAL.md "Representations" enumerates. The system
    exposes them so a caller or planner can trade context for length
    *visibly*; it must never silently substitute a shorter form (PROBLEM.md
    "Semantic Loss Through Naive Shortening").

    - ``FULL``: full semantic form (most context preserved; the default).
    - ``SHORTENED``: a shortened symbolic form (deterministic abbreviation).
    - ``BOUNDED_FRAGMENT``: a length-bounded fragment of the value.
    - ``GENERATED_UNIQUENESS``: a generated uniqueness form.
    """

    FULL = "full"
    SHORTENED = "shortened"
    BOUNDED_FRAGMENT = "bounded-fragment"
    GENERATED_UNIQUENESS = "generated-uniqueness"


class UniquenessStrategy(Enum):
    """The practical uniqueness a component is intended to contribute.

    HLD "Uniqueness Strategy" / PROBLEM.md "Uniqueness Is Practical, Not
    Absolute" require uniqueness to be *explicit* and its budget *planned for*,
    while being honest that the project does not solve global availability or
    external reservation. This records which practical strategy (if any) a
    component embodies so a planner can reserve budget for it and diagnostics
    can state how strong the resulting claim is — it never asserts the value is
    actually unique in AWS.

    These mirror the strategy types the HLD enumerates:

    - ``NONE``: not a uniqueness source (the default for ordinary semantic
      values).
    - ``CALLER_PROVIDED``: a caller-supplied identifier the caller asserts is
      unique; only as strong as the caller's own discipline.
    - ``STACK_DERIVED``: derived from deploy-time stack identity (e.g. the
      stack id); scoped to that stack and only known at deploy time.
    - ``UUID_FRAGMENT``: a bounded partition of a UUID-like value;
      collision-resistant but not externally reserved.
    - ``GENERATED``: a freshly generated bounded suffix;
      collision-resistant but not externally reserved.
    """

    NONE = "none"
    CALLER_PROVIDED = "caller-provided"
    STACK_DERIVED = "stack-derived"
    UUID_FRAGMENT = "uuid-fragment"
    GENERATED = "generated"


@dataclass(frozen=True, slots=True)
class Representation:
    """One usable form of a component, with its caller-visible tradeoff.

    ``value`` is the concrete string for an ``EXACT`` form, or an illustrative
    placeholder for a ``BOUNDED`` / ``ADVISORY`` form whose real value is only
    known later. ``certainty`` records how well that value is known.

    ``min_length`` / ``max_length`` expose *known* length bounds so a later
    planner can do budget accounting without this layer doing it. Either may
    be omitted: an ``EXACT`` form with no explicit bounds is exactly
    ``len(value)``; a ``None`` ``max_length`` on a weaker form means the upper
    bound is unknown (unbounded / advisory). ``tradeoff`` is the human-visible
    cost of choosing this form (e.g. "drops the team prefix"); the full form
    usually has none.
    """

    form: RepresentationForm
    value: str
    certainty: Certainty = Certainty.EXACT
    min_length: int | None = None
    max_length: int | None = None
    tradeoff: str = ""

    def __post_init__(self) -> None:
        """Fail fast on inconsistent bounds (core principle #10)."""
        if self.min_length is not None and self.min_length < 0:
            raise ValueError(
                f"{self.form.value}: min_length must be >= 0, "
                f"got {self.min_length}"
            )
        if self.max_length is not None and self.max_length < 0:
            raise ValueError(
                f"{self.form.value}: max_length must be >= 0, "
                f"got {self.max_length}"
            )
        if (
            self.min_length is not None
            and self.max_length is not None
            and self.max_length < self.min_length
        ):
            raise ValueError(
                f"{self.form.value}: max_length {self.max_length} is "
                f"less than min_length {self.min_length}"
            )

    @property
    def length_bounds(self) -> tuple[int, int | None]:
        """Resolved ``(min, max)`` character length for budget reasoning.

        Explicit bounds always win. With none given, an ``EXACT`` form is
        exactly ``len(value)``; a weaker form reports ``min == 0`` and
        ``max is None`` (no known upper bound) so a conservative planner can
        see the uncertainty rather than assume a length.
        """
        exact = self.certainty is Certainty.EXACT
        if self.min_length is not None:
            lo = self.min_length
        else:
            lo = len(self.value) if exact else 0
        if self.max_length is not None:
            hi: int | None = self.max_length
        else:
            hi = len(self.value) if exact else None
        return (lo, hi)

    @property
    def is_bounded_length(self) -> bool:
        """Whether a finite upper length bound is known for this form."""
        return self.length_bounds[1] is not None


@dataclass(frozen=True, slots=True)
class Component:
    """A named naming input and the alternate forms it can take.

    ``role`` is the semantic position the value occupies in a name (e.g.
    ``"service"``, ``"env"``, ``"uid"``); ``source`` is how the value
    originates. ``representations`` lists the usable forms in preference
    order: the first is the primary / default. The system never *silently*
    swaps in a shorter form (PROBLEM.md), so a caller or planner must request
    an alternate explicitly through the accessors below.

    ``strategy`` records the practical uniqueness this component is intended to
    contribute (default :attr:`UniquenessStrategy.NONE`). It is an intrinsic
    property of the input, not a resource rule: whether a *resource* requires
    uniqueness lives in :mod:`namehelper.profiles`; a planner reconciles the
    two and reserves budget accordingly.

    No AWS or resource-specific logic lives here — a planner reconciles these
    representations against a :mod:`namehelper.profiles` envelope; the
    component only reports what forms exist and their metadata.
    """

    role: str
    source: ComponentSource
    representations: tuple[Representation, ...]
    strategy: UniquenessStrategy = UniquenessStrategy.NONE

    def __post_init__(self) -> None:
        """Fail fast on a malformed component (core principle #10)."""
        if not self.representations:
            raise ValueError(
                f"component {self.role!r} needs at least one representation"
            )
        forms = [r.form for r in self.representations]
        if len(forms) != len(set(forms)):
            raise ValueError(
                f"component {self.role!r} has duplicate representation forms"
            )

    @property
    def primary(self) -> Representation:
        """The default form (first; conventionally the full semantic form)."""
        return self.representations[0]

    @property
    def certainty(self) -> Certainty:
        """Knowledge level of the default form.

        A component is reasoned about through its primary representation
        unless a planner explicitly switches; its certainty is therefore the
        primary form's certainty, not a rollup across alternates.
        """
        return self.primary.certainty

    @property
    def provides_uniqueness(self) -> bool:
        """Whether this component is intended as a practical uniqueness source.

        ``True`` for every strategy other than
        :attr:`UniquenessStrategy.NONE`. It only states *intent*; it is never a
        claim that the value is actually unique in AWS (PROBLEM.md "Uniqueness
        Is Practical, Not Absolute").
        """
        return self.strategy is not UniquenessStrategy.NONE

    @property
    def forms(self) -> tuple[RepresentationForm, ...]:
        """All available representation forms, in preference order."""
        return tuple(r.form for r in self.representations)

    @property
    def alternates(self) -> tuple[Representation, ...]:
        """Representations other than the primary.

        These are what a later planner may switch to when the primary form
        does not fit a profile. The component does not rank or choose among
        them; that decision is the planner's and stays free of AWS logic
        here.
        """
        return self.representations[1:]

    def has_form(self, form: RepresentationForm) -> bool:
        """Whether this component exposes ``form``."""
        return any(r.form is form for r in self.representations)

    def representation(self, form: RepresentationForm) -> Representation:
        """The representation for ``form``.

        Raises :class:`KeyError` if this component does not expose that form,
        so a planner asking for an unavailable representation fails explicitly
        rather than silently degrading.
        """
        for r in self.representations:
            if r.form is form:
                return r
        raise KeyError(
            f"component {self.role!r} has no {form.value!r} representation; "
            f"available: {', '.join(f.value for f in self.forms)}"
        )
