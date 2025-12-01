"""The planning and visible constraint-resolution engine.

HLD "Composition and Planning Core" and "Constraint Resolution Model" require
more than joining components: the core must evaluate an ordered composition
against a selected :class:`~namehelper.profiles.ConstraintProfile`, reserve
budget for separators / fixed segments / uniqueness, decide whether the plan
is valid, risky, or impossible, and *surface* alternate representations for
the caller to choose rather than silently applying them (VISION "Visible
Constraint-Resolution Vision"; PROBLEM.md "Semantic Loss Through Naive
Shortening").

:func:`plan_name` is that engine. It is pure and deterministic: the same
components, profile, separator, and representation selections always produce
the same :class:`~namehelper.core.NameResult` and the same findings (HLD
"Determinism Builds Trust"). It never mutates the plan toward a shorter form;
it only reports the levers via :data:`ALTERNATE_REPRESENTATION` suggestions so
the caller can re-run the planner with a different selection — the visible
plan -> findings -> choice -> revalidate loop.

Boundaries: this layer reconciles components against a profile envelope but
embeds no AWS-specific rule (those live in :mod:`namehelper.profiles`) and
never depends on :mod:`namehelper.adapters`. It also does not own
string-shaping: producing the final string (style, separator normalization,
permitted sanitization) is delegated to :mod:`namehelper.core.rendering` so
that visible-structure decisions stay in one explainable place (HLD
"Normalization and Rendering Layer"; acceptance criterion). How a finding
*behaves* for a given caller (fatal / warn / ignored) is the separate,
policy-controlled decision in :mod:`namehelper.diagnostics.policy`; this
engine only produces the intrinsic findings so that mapping stays consistent
and caller-controlled.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from namehelper.components.component import (
    Component,
    Representation,
    RepresentationForm,
)
from namehelper.core.plan import NamePlan, PlanSegment
from namehelper.core.rendering import render
from namehelper.core.result import NameResult
from namehelper.diagnostics.certainty import Certainty
from namehelper.diagnostics.findings import Finding, Severity
from namehelper.profiles.profile import Casing, ConstraintProfile, Uniqueness

# Stable machine identifiers for the findings this engine emits. They are the
# contract callers and validation policy target (HLD "Finding"); keep them
# stable across changes.
SEPARATOR_UNSUPPORTED = "separator_unsupported"
IMPOSSIBLE_OVER_BUDGET = "impossible_over_budget"
OVER_BUDGET = "over_budget"
UNBOUNDED_LENGTH = "unbounded_length"
BELOW_MIN_LENGTH = "below_min_length"
INVALID_CHARACTERS = "invalid_characters"
VALIDATION_CONSERVATIVE = "validation_conservative"
PRACTICAL_UNIQUENESS = "practical_uniqueness"
ALTERNATE_REPRESENTATION = "alternate_representation"

__all__ = [
    "plan_name",
    "SEPARATOR_UNSUPPORTED",
    "IMPOSSIBLE_OVER_BUDGET",
    "OVER_BUDGET",
    "UNBOUNDED_LENGTH",
    "BELOW_MIN_LENGTH",
    "INVALID_CHARACTERS",
    "VALIDATION_CONSERVATIVE",
    "PRACTICAL_UNIQUENESS",
    "ALTERNATE_REPRESENTATION",
]

# Finding codes that mean the plan is under length / character pressure, i.e.
# choosing a different representation could plausibly help. Used to decide
# when surfacing alternates is actionable rather than noise.
_PRESSURE_CODES = frozenset(
    {
        IMPOSSIBLE_OVER_BUDGET,
        OVER_BUDGET,
        UNBOUNDED_LENGTH,
        BELOW_MIN_LENGTH,
        INVALID_CHARACTERS,
    }
)


def plan_name(
    components: Sequence[Component],
    profile: ConstraintProfile,
    *,
    separator: str = "-",
    selections: Mapping[str, RepresentationForm] | None = None,
) -> NameResult:
    """Plan an ordered ``components`` composition against ``profile``.

    ``separator`` is the join string reserved between segments. ``selections``
    chooses, per component ``role``, which :class:`RepresentationForm` that
    component contributes; a role omitted from the mapping uses the
    component's primary (default) representation. Selecting a form a component
    does not expose raises :class:`KeyError` (fail fast; core principle #10).

    Returns a :class:`NameResult` carrying the structured plan, the rendered
    string when (and only when) the whole composition is exactly known and
    has no deterministic violation, and the diagnostic findings explaining the
    verdict. Budget for separators, fixed segments, and uniqueness reservations
    is accounted conservatively from each selected representation's known
    length bounds. When a component marked with a uniqueness strategy is used
    against a profile that expects uniqueness, the reserved uniqueness budget
    and the (always practical, never absolute) strength of that claim are
    surfaced as a :data:`PRACTICAL_UNIQUENESS` confidence finding. Alternate
    compliant representations are surfaced as :data:`ALTERNATE_REPRESENTATION`
    suggestions, never silently applied.
    """
    comps = tuple(components)
    if not comps:
        raise ValueError("plan_name requires at least one component")
    roles = [c.role for c in comps]
    if len(roles) != len(set(roles)):
        raise ValueError(
            f"components have duplicate roles: {sorted(roles)}; roles must "
            f"be unique so selections and findings are unambiguous"
        )

    selections = selections or {}
    selected: list[tuple[Component, Representation]] = []
    for comp in comps:
        form = selections.get(comp.role)
        rep = comp.representation(form) if form is not None else comp.primary
        selected.append((comp, rep))

    sep_total = max(0, len(comps) - 1) * len(separator)
    bounds = [rep.length_bounds for _, rep in selected]
    plan_lower = sum(lo for lo, _ in bounds) + sep_total
    unbounded = any(hi is None for _, hi in bounds)
    plan_upper = (
        None
        if unbounded
        else sum(hi for _, hi in bounds if hi is not None) + sep_total
    )

    plan = NamePlan(
        segments=tuple(
            PlanSegment(comp.role, rep.value, rep.certainty, rep.form)
            for comp, rep in selected
        ),
        separator=separator,
    )
    effective = Certainty.weakest(
        plan.certainty, profile.max_validation_certainty
    )
    deterministic = effective is Certainty.EXACT

    findings: list[Finding] = []

    if len(comps) > 1 and separator and separator not in profile.separators:
        findings.append(
            Finding(
                SEPARATOR_UNSUPPORTED,
                f"separator {separator!r} is not valid for "
                f"{profile.resource}; allowed: "
                f"{', '.join(map(repr, profile.separators))}",
                Severity.VIOLATION,
            )
        )

    # Length budget. The minimum-length overflow is impossible regardless of
    # certainty: no deploy-time value can shrink a composition below its own
    # floor, so it is always a deterministic violation.
    if plan_lower > profile.max_length:
        driver = _dominant(selected, by_upper=False)
        findings.append(
            Finding(
                IMPOSSIBLE_OVER_BUDGET,
                f"minimum composed length {plan_lower} exceeds the "
                f"{profile.resource} limit of {profile.max_length}; the plan "
                f"cannot fit under any value (largest fixed driver: "
                f"{driver!r})",
                Severity.VIOLATION,
                component=driver,
            )
        )
    elif plan_upper is not None and plan_upper > profile.max_length:
        driver = _dominant(selected, by_upper=True)
        verb = "exceeds" if deterministic else "may exceed"
        findings.append(
            Finding(
                OVER_BUDGET,
                f"composed length {plan_upper} {verb} the "
                f"{profile.resource} limit of {profile.max_length} "
                f"(largest driver: {driver!r})",
                Severity.VIOLATION if deterministic else Severity.WARNING,
                certainty=None if deterministic else effective,
                component=driver,
            )
        )
    elif unbounded:
        driver = next(
            comp.role for (comp, _), (_, hi) in zip(selected, bounds)
            if hi is None
        )
        findings.append(
            Finding(
                UNBOUNDED_LENGTH,
                f"component {driver!r} has no known upper length bound, so "
                f"fitting the {profile.resource} limit of "
                f"{profile.max_length} cannot be guaranteed",
                Severity.WARNING,
                certainty=Certainty.ADVISORY,
                component=driver,
            )
        )

    # Length floor. With an exact plan lower == upper, so the first branch
    # covers it; a non-exact plan whose range straddles the floor is only a
    # risk, not a certainty.
    if plan_upper is not None and plan_upper < profile.min_length:
        findings.append(
            Finding(
                BELOW_MIN_LENGTH,
                f"composed length {plan_upper} is below the "
                f"{profile.resource} minimum of {profile.min_length}",
                Severity.VIOLATION if deterministic else Severity.WARNING,
                certainty=None if deterministic else effective,
            )
        )
    elif (
        not unbounded
        and not deterministic
        and plan_lower < profile.min_length <= (plan_upper or plan_lower)
    ):
        findings.append(
            Finding(
                BELOW_MIN_LENGTH,
                f"composed length may fall as low as {plan_lower}, below the "
                f"{profile.resource} minimum of {profile.min_length}",
                Severity.WARNING,
                certainty=effective,
            )
        )

    # Character / casing / format validity is only knowable when the final
    # string is known exactly. Length problems are reported above; do not
    # double-report them here.
    all_exact = all(
        rep.certainty is Certainty.EXACT for _, rep in selected
    )
    # Delegate string-shaping to the rendering layer rather than owning the
    # join here (acceptance criterion / HLD "Normalization and Rendering
    # Layer"). The default call requests no style and no sanitization, so for
    # an ordinary single-separator composition it reproduces the plain join
    # and emits no findings; any separator normalization it does decide is
    # surfaced, never hidden.
    shaped = render(
        [(comp.role, rep.value) for comp, rep in selected],
        separator=separator,
        profile=profile,
    )
    findings.extend(shaped.findings)
    candidate = shaped.value
    if all_exact:
        length_ok = (
            profile.min_length <= len(candidate) <= profile.max_length
        )
        if length_ok and not profile.permits(candidate):
            findings.append(
                Finding(
                    INVALID_CHARACTERS,
                    f"composed value {candidate!r} is not permitted by the "
                    f"{profile.resource} profile (character, casing, or "
                    f"format rule)",
                    Severity.VIOLATION,
                    component=_casing_offender(selected, profile.casing),
                )
            )

    has_violation = any(
        f.severity is Severity.VIOLATION for f in findings
    )
    rendered = (
        candidate if all_exact and not has_violation else None
    )

    # Honesty about certainty: if nothing else flagged the plan but it could
    # not be validated exactly, say so rather than implying a hard guarantee
    # (TECHNICAL.md "Validation Behavior").
    if not findings and not deterministic:
        findings.append(
            Finding(
                VALIDATION_CONSERVATIVE,
                f"plan fits the {profile.resource} envelope under worst-case "
                f"bounds, but inputs are {effective.value}; this is a "
                f"conservative verdict, not an exact guarantee",
                Severity.WARNING,
                certainty=effective,
            )
        )

    uniqueness = _practical_uniqueness_finding(selected, profile)
    if uniqueness is not None:
        findings.append(uniqueness)

    if any(f.code in _PRESSURE_CODES for f in findings):
        findings.extend(_alternate_suggestions(selected))

    return NameResult(plan=plan, rendered=rendered, findings=tuple(findings))


def _dominant(
    selected: Sequence[tuple[Component, Representation]],
    *,
    by_upper: bool,
) -> str:
    """Role of the component contributing the most length pressure.

    ``by_upper`` ranks by worst-case (max) contribution; otherwise by the
    guaranteed (min) contribution. Ties resolve to the earliest component in
    composition order, keeping the choice deterministic.
    """
    best_role = selected[0][0].role
    best = -1
    for comp, rep in selected:
        lo, hi = rep.length_bounds
        contrib = (hi if hi is not None else lo) if by_upper else lo
        if contrib > best:
            best = contrib
            best_role = comp.role
    return best_role


def _casing_offender(
    selected: Sequence[tuple[Component, Representation]],
    casing: Casing,
) -> str | None:
    """First component whose value breaks the profile's casing rule.

    Casing is the one character rule attributable to a single segment without
    re-deriving the profile's grammar; pattern / forbidden failures stay a
    whole-name finding so attribution is never guessed.
    """
    if casing is Casing.LOWER:
        for comp, rep in selected:
            if rep.value != rep.value.lower():
                return comp.role
    elif casing is Casing.UPPER:
        for comp, rep in selected:
            if rep.value != rep.value.upper():
                return comp.role
    return None


def _practical_uniqueness_finding(
    selected: Sequence[tuple[Component, Representation]],
    profile: ConstraintProfile,
) -> Finding | None:
    """Reserve uniqueness budget explicitly and rate the resulting claim.

    HLD "Uniqueness Strategy": uniqueness must be explicit, must be planned
    for in the budget, and its tradeoff must be visible in diagnostics — while
    the proof of concept never claims external reservation or global
    availability (PROBLEM.md "Uniqueness Is Practical, Not Absolute"). When the
    selected composition contributes one or more uniqueness sources against a
    profile that *expects* uniqueness, this accounts for their reserved length
    budget explicitly and returns a confidence-channel finding — a ``WARNING``
    carrying a non-exact ``certainty``, so it is kept distinct from syntactic
    structural validity — stating the strategies used, the reserved budget,
    and how strong a claim is honestly justified. Returns ``None`` when no
    uniqueness source is used or the profile imposes no uniqueness
    expectation, so an ordinary clean plan stays finding-free.
    """
    if profile.uniqueness is Uniqueness.NONE:
        return None
    uniq = [
        (comp, rep) for comp, rep in selected if comp.provides_uniqueness
    ]
    if not uniq:
        return None

    lo = sum(rep.length_bounds[0] for _, rep in uniq)
    highs = [rep.length_bounds[1] for _, rep in uniq]
    if any(h is None for h in highs):
        reserved = f">= {lo}"
    else:
        hi = sum(h for h in highs if h is not None)
        reserved = f"{lo}" if lo == hi else f"{lo}-{hi}"
    strategies = ", ".join(
        f"{comp.role}={comp.strategy.value}" for comp, _ in uniq
    )

    # A uniqueness *claim* is never exact even when the value is: the library
    # cannot verify the value is actually unique in AWS. Downgrade an
    # otherwise-exact claim to a conservative one; weaker inputs (e.g. an
    # advisory stack id) carry through as warning-level only.
    claim = Certainty.weakest(*(rep.certainty for _, rep in uniq))
    if claim is Certainty.EXACT:
        claim = Certainty.BOUNDED

    if profile.uniqueness is Uniqueness.GLOBAL:
        honesty = (
            "global availability across all AWS accounts and over time is "
            "not verified; treat this as a conservative, warning-level "
            "claim only"
        )
    else:
        honesty = (
            "this is a practical, conservative claim; the library does not "
            "verify availability against AWS"
        )

    return Finding(
        PRACTICAL_UNIQUENESS,
        f"{profile.resource} expects {profile.uniqueness.value} uniqueness; "
        f"reserved {reserved} chars via {strategies}. {honesty}.",
        Severity.WARNING,
        certainty=claim,
    )


def _alternate_suggestions(
    selected: Sequence[tuple[Component, Representation]],
) -> list[Finding]:
    """Surface shorter / more-bounded alternates for caller choice.

    For each component, every representation other than the selected one that
    would *relieve* pressure — a strictly smaller worst-case length, or a
    known bound where the selected form has none — becomes a suggestion. The
    plan is never rewritten; the caller re-runs the planner with an updated
    selection (the visible resolution loop).
    """
    suggestions: list[Finding] = []
    for comp, sel in selected:
        sel_hi = sel.length_bounds[1]
        for rep in comp.representations:
            if rep is sel:
                continue
            rep_hi = rep.length_bounds[1]
            more_bounded = sel_hi is None and rep_hi is not None
            shorter = (
                sel_hi is not None
                and rep_hi is not None
                and rep_hi < sel_hi
            )
            if not (more_bounded or shorter):
                continue
            if more_bounded:
                detail = f"bounds it to <= {rep_hi} chars"
            else:
                detail = f"max length {rep_hi} vs {sel_hi}"
            tradeoff = rep.tradeoff or "none"
            suggestions.append(
                Finding(
                    ALTERNATE_REPRESENTATION,
                    f"component {comp.role!r} can use its "
                    f"{rep.form.value!r} representation ({detail}); "
                    f"tradeoff: {tradeoff}",
                    Severity.SUGGESTION,
                    certainty=rep.certainty,
                    component=comp.role,
                )
            )
    return suggestions
