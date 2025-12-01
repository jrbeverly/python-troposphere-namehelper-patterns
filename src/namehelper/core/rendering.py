"""The normalization and rendering layer.

HLD "Normalization and Rendering Layer" makes turning a valid plan into its
final output a *dedicated* concern: apply a naming style where the profile
permits it, normalize separators, sanitize characters when the profile's own
rules permit, and produce the final string — without the planner owning those
string-shaping details directly (HLD "Architectural Overview" places this
layer between the planning core and validation). TECHNICAL.md "Naming Style
Support" constrains it: style support stays *subordinate to resource rules*;
the library must never normalize into an invalid format just because a style
was requested.

This is also where hidden behaviour can quietly re-enter the system, so the
layer is conservative and transparent (HLD "Implementation Guidance": any
behaviour that changes the visible structure of a name must be explainable).
Two carve-outs satisfy the trust model (PROBLEM.md "Semantic Loss Through
Naive Shortening"; VISION "Structured Composition Vision"):

- An explicitly requested ``style`` is the caller's deliberate choice (like
  choosing an alternate representation), so applying a *compatible* style is
  not a hidden transformation and needs no finding.
- Every transformation the layer decides on its own — declining an
  incompatible style, collapsing separators, or sanitizing casing — is
  materially visible and therefore emits a traceable :class:`Finding`. The
  layer never silently re-shapes a name.

:func:`render` is pure and deterministic: the same segments, separator,
profile, style, and sanitize flag always produce the same
:class:`RenderedName` and the same findings (HLD "Determinism Builds Trust").
It depends only on :mod:`namehelper.profiles` and :mod:`namehelper.diagnostics`
(one-way dependency direction; never :mod:`namehelper.adapters`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from namehelper.diagnostics.findings import Finding, Severity
from namehelper.profiles.profile import Casing, ConstraintProfile

# Stable machine identifiers for the findings this layer emits. Like the
# planner's codes they are the contract callers and validation policy target
# (HLD "Finding"); keep them stable across changes.
STYLE_UNSUPPORTED = "style_unsupported"
SEPARATOR_NORMALIZED = "separator_normalized"
SANITIZED_CHARACTERS = "sanitized_characters"

__all__ = [
    "NamingStyle",
    "RenderedName",
    "render",
    "STYLE_UNSUPPORTED",
    "SEPARATOR_NORMALIZED",
    "SANITIZED_CHARACTERS",
]


class NamingStyle(Enum):
    """A naming style convention this layer can render.

    Exactly the styles TECHNICAL.md "Naming Style Support" enumerates — no
    more (adding styles purely for completeness is explicitly out of scope).
    Each style implies both a join character and a casing shape:

    - ``KEBAB``: lower-case segments joined by ``-``.
    - ``SNAKE``: lower-case segments joined by ``_``.
    - ``CAMEL``: ``firstSegmentRestCapitalised`` with no separator.
    - ``PASCAL``: ``EverySegmentCapitalised`` with no separator.
    """

    KEBAB = "kebab"
    SNAKE = "snake"
    CAMEL = "camel"
    PASCAL = "pascal"


@dataclass(frozen=True, slots=True)
class RenderedName:
    """The final shaped string and the rendering decisions behind it.

    ``value`` is always a concrete string (rendering shapes whatever segment
    values it is given; whether that string is *exposed* as a compliant result
    is the planner / validation decision, not this layer's). ``findings`` are
    the traceable diagnostics for every transformation this layer chose on its
    own — never an empty silence over a material change.
    """

    value: str
    findings: tuple[Finding, ...] = ()


# Style -> (join separator, requires that separator be profile-recognised).
# CAMEL/PASCAL concatenate (no separator) so impose no separator requirement.
_STYLE_SEPARATOR: dict[NamingStyle, str] = {
    NamingStyle.KEBAB: "-",
    NamingStyle.SNAKE: "_",
    NamingStyle.CAMEL: "",
    NamingStyle.PASCAL: "",
}


def render(
    segments: Sequence[tuple[str, str]],
    *,
    separator: str,
    profile: ConstraintProfile,
    style: NamingStyle | None = None,
    sanitize: bool = False,
) -> RenderedName:
    """Render ordered ``(role, value)`` ``segments`` into a final string.

    ``separator`` is the caller's join string used when no ``style`` is
    requested (or when a requested style is declined). ``profile`` bounds what
    is permitted: a ``style`` whose separator or casing conflicts with the
    profile is *declined* — never forced into an invalid format — and the
    decision is surfaced as a :data:`STYLE_UNSUPPORTED` finding while the
    plain separator join is used instead (style stays subordinate to resource
    rules; TECHNICAL.md "Naming Style Support").

    Separators are then normalized profile-awarely: consecutive runs of the
    active separator (and leading/trailing ones from empty segments) are
    collapsed, but only when that separator is one the profile recognises so
    this never fights the planner's own separator validation. When
    ``sanitize`` is set, the profile's own casing rule is applied as the one
    transformation the profile unambiguously permits. Both are deterministic;
    any that materially changes the string emits a traceable finding
    (:data:`SEPARATOR_NORMALIZED`, :data:`SANITIZED_CHARACTERS`) — lossy
    choices are never hidden (HLD "Normalization and Rendering Layer").
    """
    values = [value for _, value in segments]
    findings: list[Finding] = []

    applied_style = style
    if style is not None and not _style_permitted(style, profile):
        findings.append(
            Finding(
                STYLE_UNSUPPORTED,
                f"naming style {style.value!r} is not compatible with the "
                f"{profile.resource} profile (its separator or required "
                f"casing would produce an invalid name); rendering without "
                f"the requested style instead",
                Severity.WARNING,
            )
        )
        applied_style = None

    if applied_style is None:
        active_separator = separator
        rendered = separator.join(values)
    else:
        active_separator = _STYLE_SEPARATOR[applied_style]
        rendered = _apply_style(values, applied_style)

    if (
        active_separator
        and active_separator in profile.separators
    ):
        collapsed = active_separator.join(
            part
            for part in rendered.split(active_separator)
            if part != ""
        )
        if collapsed != rendered:
            findings.append(
                Finding(
                    SEPARATOR_NORMALIZED,
                    f"separator {active_separator!r} runs were collapsed and "
                    f"trimmed for the {profile.resource} profile "
                    f"({rendered!r} -> {collapsed!r})",
                    Severity.WARNING,
                )
            )
            rendered = collapsed

    if sanitize:
        sanitized = _sanitize_casing(rendered, profile.casing)
        if sanitized != rendered:
            findings.append(
                Finding(
                    SANITIZED_CHARACTERS,
                    f"value was case-sanitized to satisfy the "
                    f"{profile.resource} {profile.casing.value}-casing rule "
                    f"({rendered!r} -> {sanitized!r}); original casing is "
                    f"not recoverable",
                    Severity.WARNING,
                )
            )
            rendered = sanitized

    return RenderedName(value=rendered, findings=tuple(findings))


def _style_permitted(
    style: NamingStyle, profile: ConstraintProfile
) -> bool:
    """Whether ``style`` can render a value the profile could accept.

    Subordinate to resource rules: a style is permitted only when its join
    separator is one the profile recognises (or it uses none) *and* its
    casing shape does not contradict the profile's required casing. This is a
    necessary compatibility gate, not full validation — the planner still
    validates the concrete composed value.
    """
    separator = _STYLE_SEPARATOR[style]
    if separator and separator not in profile.separators:
        return False
    lowercase_style = style in (NamingStyle.KEBAB, NamingStyle.SNAKE)
    if lowercase_style and profile.casing is Casing.UPPER:
        return False
    mixed_case_style = style in (NamingStyle.CAMEL, NamingStyle.PASCAL)
    if mixed_case_style and profile.casing in (
        Casing.LOWER,
        Casing.UPPER,
    ):
        return False
    return True


def _apply_style(values: Sequence[str], style: NamingStyle) -> str:
    """Deterministically shape ``values`` into ``style``.

    The transform is total and order-preserving so the same inputs always
    yield the same output (HLD "Determinism Builds Trust").
    """
    if style is NamingStyle.KEBAB:
        return "-".join(v.lower() for v in values)
    if style is NamingStyle.SNAKE:
        return "_".join(v.lower() for v in values)
    if style is NamingStyle.CAMEL:
        if not values:
            return ""
        head = values[0].lower()
        tail = "".join(_capitalize(v) for v in values[1:])
        return head + tail
    return "".join(_capitalize(v) for v in values)  # PASCAL


def _capitalize(value: str) -> str:
    """Upper-case the first character, lower-case the remainder.

    Used for camel/pascal word boundaries; deterministic and independent of
    the input's original casing.
    """
    if not value:
        return value
    return value[:1].upper() + value[1:].lower()


def _sanitize_casing(value: str, casing: Casing) -> str:
    """Apply the profile's casing rule — the one permitted sanitization.

    Only casing is sanitized: it is a rule the profile itself declares, so the
    transform is predictable. Stripping or substituting other disallowed
    characters would be guesswork and is deliberately not done (it would hide
    semantic loss; PROBLEM.md "Semantic Loss Through Naive Shortening").
    """
    if casing is Casing.LOWER:
        return value.lower()
    if casing is Casing.UPPER:
        return value.upper()
    return value
