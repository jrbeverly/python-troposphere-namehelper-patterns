"""The proof-of-concept component families.

HLD "Component Model" lists the first-class families the system must be able
to express: literal semantic labels, stack name, stack id, region,
partitioned stack-UUID fragments, generated uniqueness segments, and explicit
join / delimiter decisions. These constructors build well-formed
:class:`~namehelper.components.component.Component` instances for that set so
later layers compose names from typed inputs instead of ad-hoc strings.

A family encodes only the intrinsic *shape* of an input — its source type,
which representations it can take, and how well each is known. It does not
encode any target-resource rule (that is :mod:`namehelper.profiles`). Where a
family has a conventional length ceiling (e.g. a CloudFormation stack name),
that ceiling is a documented, overridable default, never hidden logic.
"""

from __future__ import annotations

from namehelper.components.component import (
    Component,
    ComponentSource,
    Representation,
    RepresentationForm,
    UniquenessStrategy,
)
from namehelper.diagnostics.certainty import Certainty

__all__ = [
    "literal",
    "derived",
    "generated",
    "stack_name",
    "stack_id",
    "region",
    "uuid_fragment",
    "unique_id",
    "delimiter",
]

# Conventional ceilings for deploy-time context values. They describe the
# component family's own shape (not a target-resource profile rule) and are
# exposed as overridable defaults so the assumption stays explicit.
_STACK_NAME_MAX = 128
_REGION_MAX = 25


def literal(role: str, value: str) -> Component:
    """A known, caller-supplied semantic value.

    Source ``LITERAL``; a single exact full form. This is the common path —
    a value the caller already knows.
    """
    return Component(
        role,
        ComponentSource.LITERAL,
        (Representation(RepresentationForm.FULL, value, Certainty.EXACT),),
    )


def unique_id(role: str, value: str) -> Component:
    """A caller-provided identifier used as a practical uniqueness source.

    Source ``LITERAL``; a single exact full form, like :func:`literal`, but
    marked :attr:`UniquenessStrategy.CALLER_PROVIDED` so the planner reserves
    its budget as uniqueness and diagnostics state the claim is only as strong
    as the caller's own discipline (HLD "Uniqueness Strategy": caller-provided
    exact identifiers). It is never a claim the value is actually unique in
    AWS.
    """
    return Component(
        role,
        ComponentSource.LITERAL,
        (Representation(RepresentationForm.FULL, value, Certainty.EXACT),),
        strategy=UniquenessStrategy.CALLER_PROVIDED,
    )


def derived(
    role: str,
    value: str,
    *,
    certainty: Certainty = Certainty.BOUNDED,
    max_length: int | None = None,
) -> Component:
    """A value derived from deployment / resource context.

    Source ``DERIVED``; a single full form. ``value`` is the concrete value
    when known (pass ``certainty=Certainty.EXACT``) or an illustrative
    placeholder otherwise. ``max_length`` records a known upper bound when one
    exists; omit it to signal an unknown bound. Use this for resource-derived
    contextual segments that do not need a richer family.
    """
    return Component(
        role,
        ComponentSource.DERIVED,
        (
            Representation(
                RepresentationForm.FULL,
                value,
                certainty,
                max_length=max_length,
            ),
        ),
    )


def generated(role: str, *, length: int, role_value: str = "") -> Component:
    """A generated uniqueness segment of fixed length.

    Source ``GENERATED``; a single generated-uniqueness form, marked
    :attr:`UniquenessStrategy.GENERATED`. The concrete value is not known
    until generation, so the form is ``BOUNDED``: its length is fixed (and
    therefore budget-accountable) even though the characters are not yet
    known.
    """
    if length <= 0:
        raise ValueError(f"generated {role!r}: length must be > 0, got {length}")
    return Component(
        role,
        ComponentSource.GENERATED,
        (
            Representation(
                RepresentationForm.GENERATED_UNIQUENESS,
                role_value,
                Certainty.BOUNDED,
                min_length=length,
                max_length=length,
            ),
        ),
        strategy=UniquenessStrategy.GENERATED,
    )


def stack_name(
    value: str | None = None,
    *,
    role: str = "stack",
    max_length: int = _STACK_NAME_MAX,
) -> Component:
    """The deploying stack's name.

    Source ``DERIVED``. When ``value`` is given it is treated as known
    (exact full form). When omitted it is a deploy-time value: a bounded full
    form (placeholder, ``1..max_length``) plus a bounded-fragment alternate
    that keeps only the leading characters — a visible tradeoff a planner can
    fall back to when the full name will not fit.
    """
    if value is not None:
        return Component(
            role,
            ComponentSource.DERIVED,
            (
                Representation(
                    RepresentationForm.FULL, value, Certainty.EXACT
                ),
            ),
        )
    fragment_len = min(8, max_length)
    return Component(
        role,
        ComponentSource.DERIVED,
        (
            Representation(
                RepresentationForm.FULL,
                "<stack-name>",
                Certainty.BOUNDED,
                min_length=1,
                max_length=max_length,
            ),
            Representation(
                RepresentationForm.BOUNDED_FRAGMENT,
                "<stack-name>",
                Certainty.BOUNDED,
                min_length=1,
                max_length=fragment_len,
                tradeoff=(
                    "only the leading fragment of the stack name; risks "
                    "ambiguity across similarly named stacks"
                ),
            ),
        ),
    )


def stack_id(
    value: str | None = None,
    *,
    role: str = "stackid",
    fragment_length: int = 12,
) -> Component:
    """The deploying stack's id (an ARN containing a stack UUID).

    Source ``DERIVED``, marked :attr:`UniquenessStrategy.STACK_DERIVED` — a
    practical uniqueness source scoped to the deploying stack. The full id is
    only knowable at deploy time and has no tight length bound, so the full
    form is ``ADVISORY`` and unbounded. The bounded-fragment alternate keeps
    just a fixed-length slice of the stack UUID — a length-accountable form
    whose tradeoff is the loss of the account / region / stack-name context
    the ARN carried.
    """
    if fragment_length <= 0:
        raise ValueError(
            f"stack_id {role!r}: fragment_length must be > 0, "
            f"got {fragment_length}"
        )
    full = Representation(
        RepresentationForm.FULL,
        value if value is not None else "<stack-id-arn>",
        Certainty.EXACT if value is not None else Certainty.ADVISORY,
    )
    fragment = Representation(
        RepresentationForm.BOUNDED_FRAGMENT,
        "<stack-uuid>",
        Certainty.BOUNDED,
        min_length=fragment_length,
        max_length=fragment_length,
        tradeoff=(
            "uses only a fixed slice of the stack UUID; drops the "
            "account, region, and stack-name context of the full id"
        ),
    )
    return Component(
        role,
        ComponentSource.DERIVED,
        (full, fragment),
        strategy=UniquenessStrategy.STACK_DERIVED,
    )


def region(
    value: str | None = None,
    *,
    role: str = "region",
    max_length: int = _REGION_MAX,
) -> Component:
    """The deployment region (e.g. ``us-east-1``).

    Source ``DERIVED``. When ``value`` is known it offers a full form and a
    shortened symbolic form with the separators removed (``us-east-1`` ->
    ``useast1``) — a deterministic transform, so the shortened form stays
    ``EXACT``; only human scan-ability is traded. When omitted it is a single
    bounded full form (regions are short but the exact code is unknown).
    """
    if value is None:
        return Component(
            role,
            ComponentSource.DERIVED,
            (
                Representation(
                    RepresentationForm.FULL,
                    "<region>",
                    Certainty.BOUNDED,
                    min_length=1,
                    max_length=max_length,
                ),
            ),
        )
    return Component(
        role,
        ComponentSource.DERIVED,
        (
            Representation(
                RepresentationForm.FULL, value, Certainty.EXACT
            ),
            Representation(
                RepresentationForm.SHORTENED,
                value.replace("-", "").replace("_", ""),
                Certainty.EXACT,
                tradeoff="separators removed; less human-scannable",
            ),
        ),
    )


def uuid_fragment(*, length: int = 8, role: str = "uid") -> Component:
    """A generated UUID-like uniqueness fragment.

    Source ``GENERATED``; a fixed-length generated-uniqueness form, marked
    :attr:`UniquenessStrategy.UUID_FRAGMENT`. Length is known (so it is
    budget-accountable) but the value is not until generation — the form is
    ``BOUNDED``. The uniqueness it provides is practical, not absolute
    (PROBLEM.md "Uniqueness Is Practical, Not Absolute").
    """
    if length <= 0:
        raise ValueError(
            f"uuid_fragment {role!r}: length must be > 0, got {length}"
        )
    return Component(
        role,
        ComponentSource.GENERATED,
        (
            Representation(
                RepresentationForm.GENERATED_UNIQUENESS,
                "<uuid>",
                Certainty.BOUNDED,
                min_length=length,
                max_length=length,
            ),
        ),
        strategy=UniquenessStrategy.UUID_FRAGMENT,
    )


def delimiter(value: str = "-", *, role: str = "delimiter") -> Component:
    """An explicit join / delimiter decision.

    Source ``LITERAL``; a single exact full form. Modelling the delimiter as
    a first-class component lets a later planner account for separator length
    explicitly instead of inferring it, and keeps join behaviour an explicit
    caller decision rather than a hidden formatting assumption (PROBLEM.md
    "Inconsistent Join and Delimiter Logic").
    """
    return Component(
        role,
        ComponentSource.LITERAL,
        (Representation(RepresentationForm.FULL, value, Certainty.EXACT),),
    )
