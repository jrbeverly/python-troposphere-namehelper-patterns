"""The :class:`NameHelper` public entrypoint.

``NameHelper`` is the single ergonomic surface callers import. It orchestrates
the full naming flow --- profile resolution, planning, and validation --- so
callers do not need direct knowledge of every internal subsystem.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from namehelper._version import __version__
from namehelper.components.component import Component, RepresentationForm
from namehelper.core.planner import plan_name
from namehelper.core.result import NameResult
from namehelper.diagnostics.findings import Finding
from namehelper.diagnostics.policy import PolicyEvaluation, ValidationPolicy
from namehelper.profiles.catalog import get_profile

__all__ = ["NameHelper"]


class NameHelper:
    """Caller-facing entrypoint for structured AWS resource naming.

    Holds a :class:`~namehelper.diagnostics.policy.ValidationPolicy` so
    different calling contexts (strict CI vs. permissive local) can be
    configured once and reused across naming operations.

    The :meth:`name` method is the primary orchestration path: it resolves a
    resource profile, plans the component composition against it, and returns a
    :class:`~namehelper.core.result.NameResult` with the rendered name and
    diagnostic findings.
    """

    __slots__ = ("_policy",)

    def __init__(
        self,
        *,
        ignored_codes: Iterable[str] = (),
        treat_warnings_as_fatal: bool = False,
    ) -> None:
        self._policy = ValidationPolicy(
            ignored_codes=frozenset(ignored_codes),
            treat_warnings_as_fatal=treat_warnings_as_fatal,
        )

    @staticmethod
    def version() -> str:
        """Return the installed library version."""
        return __version__

    @property
    def policy(self) -> ValidationPolicy:
        """The :class:`~namehelper.diagnostics.policy.ValidationPolicy` this
        helper applies.
        """
        return self._policy

    # --- orchestration --------------------------------------------------

    def name(
        self,
        *components: Component,
        resource: str,
        separator: str = "-",
        selections: Mapping[str, RepresentationForm] | None = None,
    ) -> NameResult:
        """Plan and validate a name from ``components`` for ``resource``.

        ``resource`` is a catalog key (e.g. ``"iam-role"``, ``"s3-bucket"``).
        ``separator`` is the join string between segments.  ``selections``
        chooses which :class:`~namehelper.components.component.RepresentationForm`
        each component contributes; a role omitted from the mapping uses its
        primary (default) form.

        Returns a :class:`~namehelper.core.result.NameResult` with the
        rendered name (when compliant), the structured plan, and diagnostic
        findings.
        """
        profile = get_profile(resource)
        return plan_name(
            components,
            profile,
            separator=separator,
            selections=selections,
        )

    def evaluate(
        self, findings: Iterable[Finding]
    ) -> PolicyEvaluation:
        """Evaluate ``findings`` against this helper's configured policy.

        Convenience wrapper for ``self.policy.evaluate(findings)``.
        """
        return self._policy.evaluate(findings)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"{type(self).__name__}()"
