"""Template-generation adapter for Troposphere / CloudFormation environments.

HLD "Adapters" requires this layer to translate integration-specific inputs into
core concepts while preserving deploy-time uncertainty and supporting
template-generation failure behaviour — without coupling the core to any single
integration (PROBLEM.md "Architectural Constraints").

:class:`TemplateHelper` wraps :class:`~namehelper.api.NameHelper` with the
generate-or-block gate that template code needs at generation time (HLD "Flow 5:
Template Generation Gate"). :func:`from_context` translates CloudFormation stack
context (region, stack name) into :class:`~namehelper.components.Component`
objects while preserving bounded certainty so deploy-time values are never
flattened into false exactness.

Neither the helper nor the context factory redefines naming rules: they delegate
to the core planner and profile framework exclusively (HLD "Adapters": adapters
must not redefine naming rules).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Optional

from namehelper.api import NameHelper
from namehelper.components.component import Component, RepresentationForm
from namehelper.components.families import region, stack_name
from namehelper.core.result import NameResult
from namehelper.diagnostics.findings import Finding
from namehelper.diagnostics.policy import PolicyEvaluation

__all__ = ["TemplateHelper", "from_context"]


class TemplateHelper:
    """Adapts :class:`NameHelper` for template-generation environments.

    Wraps the core naming flow and adds the ``generate_or_block`` gate that
    template code calls at generation time: it returns the rendered name when the
    plan fits the resource and is not blocked by policy, or ``None`` when
    generation must stop so the template can surface findings instead of emitting
    an invalid name.

    The underlying :class:`NameHelper` policy is configured once at construction
    so the same instance can be reused across many naming operations.
    """

    __slots__ = ("_helper",)

    def __init__(
        self,
        *,
        ignored_codes: Sequence[str] = (),
        treat_warnings_as_fatal: bool = False,
    ) -> None:
        self._helper = NameHelper(
            ignored_codes=ignored_codes,
            treat_warnings_as_fatal=treat_warnings_as_fatal,
        )

    @property
    def helper(self) -> NameHelper:
        """The underlying :class:`NameHelper` this adapter delegates to."""
        return self._helper

    # --- core delegation -------------------------------------------------

    def name(
        self,
        *components: Component,
        resource: str,
        separator: str = "-",
        selections: Mapping[str, RepresentationForm] | None = None,
    ) -> NameResult:
        """Plan and validate a name, delegating to the core naming flow.

        All arguments are passed through to :meth:`NameHelper.name`.
        """
        return self._helper.name(
            *components,
            resource=resource,
            separator=separator,
            selections=selections,
        )

    # --- template-generation gate ----------------------------------------

    def generate_or_block(self, result: NameResult) -> str | None:
        """Template-generation gate.

        Returns ``result.rendered`` when the active policy does not block
        generation, or ``None`` when generation must stop (HLD "Flow 5:
        Template Generation Gate"). The caller is expected to surface findings
        when a block occurs so the reason is visible.
        """
        if self._helper.policy.is_blocking(result.findings):
            return None
        return result.rendered

    def evaluate(self, findings: Sequence[Finding]) -> PolicyEvaluation:
        """Evaluate findings against this helper's configured policy."""
        return self._helper.evaluate(findings)

    def __repr__(self) -> str:  # pragma: no cover — trivial
        return f"{type(self).__name__}()"


def from_context(
    *,
    region_code: str | None = None,
    stack: str | None = None,
) -> dict[str, Component]:
    """Translate CloudFormation stack context into core components.

    ``region_code`` and ``stack`` are the deploy-time values when known; each
    omitted value produces a component whose certainty is :class:`Certainty.BOUNDED`
    (the shape is known from AWS conventions, but the concrete value is not)
    rather than :class:`Certainty.EXACT`, preserving deploy-time uncertainty
    (HLD "Adapters": carry through deploy-time uncertainty).

    Returns a ``{role: Component}`` dict suitable for unpacking into
    :meth:`TemplateHelper.name`.
    """
    components: dict[str, Component] = {}
    if region_code is not None:
        components["region"] = region(region_code)
    else:
        components["region"] = region()
    if stack is not None:
        components["stack"] = stack_name(stack)
    else:
        components["stack"] = stack_name()
    return components
