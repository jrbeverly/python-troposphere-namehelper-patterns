"""Caller-controlled validation policy and its execution.

HLD "Validation Policy" requires the same finding to be treatable as a hard
failure, a warning, or an explicitly ignored condition depending on the
caller's context (strict CI gate vs. local exploration vs. template
generation). The policy is the single place that maps a :class:`Finding` to
one of those outcomes so every downstream layer evaluates findings
consistently rather than re-implementing severity logic.

Executing a policy over a set of findings is also done here. HLD "Validation
Model" separates *structural* validation (can the composition fit / is it a
deterministic rule break) from *confidence* validation (is there enough
certainty to claim safety); :func:`classify_kind` derives that level from a
finding's intrinsic shape and :class:`ValidationPolicy.evaluate` returns a
deterministic :class:`PolicyEvaluation` that keeps the two channels distinct
and records, per finding, exactly which policy decision was made — including
explicitly bypassed conditions. This is the gating primitive template
generation consumes (HLD "Flow 5"); it stays free of any adapter coupling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from namehelper.diagnostics.findings import Finding, Severity

__all__ = [
    "PolicyOutcome",
    "ValidationKind",
    "classify_kind",
    "ValidationPolicy",
    "EvaluatedFinding",
    "PolicyEvaluation",
]


class PolicyOutcome(Enum):
    """How the active policy treats a finding.

    - ``FATAL``: stop generation.
    - ``WARN``: surface the finding but allow continuation.
    - ``IGNORED``: explicitly suppressed; recorded but non-blocking.
    """

    FATAL = "fatal"
    WARN = "warn"
    IGNORED = "ignored"


class ValidationKind(Enum):
    """Which of the HLD's two validation levels a finding belongs to.

    HLD "Validation Model" separates *structural* validation (can the
    composition fit the profile / is it a deterministic rule break) from
    *confidence* validation (does the system have enough certainty to claim
    safety). Keeping these as distinct channels is required so the two are
    never collapsed into one generic error stream.

    - ``STRUCTURAL``: a deterministic problem or a visible structural
      transformation (over-length, invalid characters, unsupported or
      normalized separators, declined style, casing sanitization).
    - ``CONFIDENCE``: a knowledge-limited problem — the value is bounded or
      advisory, so safety can only be asserted conservatively.
    """

    STRUCTURAL = "structural"
    CONFIDENCE = "confidence"


def classify_kind(finding: Finding) -> ValidationKind | None:
    """Classify ``finding`` into the HLD two-level validation model.

    Derived only from the finding's intrinsic ``severity`` / ``certainty`` so
    no finding producer has to be coupled to this taxonomy, and deterministic
    so the same finding always classifies the same way:

    - a :attr:`Severity.SUGGESTION` is an available alternate, not a
      validation problem -> ``None``;
    - a :attr:`Severity.VIOLATION` is a deterministic rule break ->
      ``STRUCTURAL``;
    - a :attr:`Severity.WARNING` that records a weaker ``certainty`` is a
      knowledge limitation -> ``CONFIDENCE``;
    - any other warning is a visible structural transformation or risk that is
      not certainty-limited -> ``STRUCTURAL``.
    """
    if finding.severity is Severity.SUGGESTION:
        return None
    if finding.severity is Severity.VIOLATION:
        return ValidationKind.STRUCTURAL
    if finding.certainty is not None:
        return ValidationKind.CONFIDENCE
    return ValidationKind.STRUCTURAL


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    """Maps findings to outcomes for a given calling context.

    Defaults model the common case: deterministic violations fail hard,
    warnings surface but continue, and suggestions are informational.
    ``ignored_codes`` lets a caller explicitly bypass accepted risk by finding
    code; ``treat_warnings_as_fatal`` escalates non-deterministic warnings for
    strict contexts (e.g. a CI gate). An explicitly ignored code always wins,
    so accepted risk is never re-escalated.
    """

    ignored_codes: frozenset[str] = field(default_factory=frozenset)
    treat_warnings_as_fatal: bool = False

    def outcome_for(self, finding: Finding) -> PolicyOutcome:
        """Resolve a single finding to its policy outcome."""
        if finding.code in self.ignored_codes:
            return PolicyOutcome.IGNORED
        if finding.severity is Severity.VIOLATION:
            return PolicyOutcome.FATAL
        if finding.severity is Severity.WARNING:
            return (
                PolicyOutcome.FATAL
                if self.treat_warnings_as_fatal
                else PolicyOutcome.WARN
            )
        return PolicyOutcome.WARN

    def is_blocking(self, findings: Iterable[Finding]) -> bool:
        """True if any finding resolves to ``FATAL`` under this policy.

        This is the gate downstream template-generation flows use to decide
        whether generation must stop (HLD "Flow 5: Template Generation Gate").
        """
        return any(
            self.outcome_for(f) is PolicyOutcome.FATAL for f in findings
        )

    def evaluate(
        self, findings: Iterable[Finding]
    ) -> "PolicyEvaluation":
        """Execute this policy over ``findings`` into a structured report.

        Pure and deterministic: each finding is classified into its
        :class:`ValidationKind` and resolved to its :class:`PolicyOutcome` in
        input order. The returned :class:`PolicyEvaluation` keeps the
        structural and confidence channels distinct, records every policy
        decision (including explicitly bypassed conditions), and exposes a
        single ``blocked`` gate for template generation — all without any
        adapter-specific coupling (HLD "Flow 5: Template Generation Gate").
        """
        return PolicyEvaluation(
            policy=self,
            evaluated=tuple(
                EvaluatedFinding(
                    finding=f,
                    outcome=self.outcome_for(f),
                    kind=classify_kind(f),
                )
                for f in findings
            ),
        )


@dataclass(frozen=True, slots=True)
class EvaluatedFinding:
    """A finding paired with the decisions made about it.

    Preserves, for one finding, both *what kind* of validation it represents
    (:attr:`kind`) and *how the active policy treated it* (:attr:`outcome`),
    so an evaluation stays fully traceable: which certainty assumption the
    finding was reasoned under (on the finding itself) and which policy
    decision was applied are both recoverable.
    """

    finding: Finding
    outcome: PolicyOutcome
    kind: ValidationKind | None


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    """The deterministic outcome of executing a policy over findings.

    ``evaluated`` preserves every finding in input order with its
    classification and resolved outcome (so the exact representations,
    certainty assumptions, and policy decisions used remain inspectable). The
    grouped views are the actionable channels callers and template-generation
    gates consume; structural and confidence problems are never collapsed into
    one stream, and explicitly bypassed conditions remain visible rather than
    silently dropped.
    """

    policy: ValidationPolicy
    evaluated: tuple[EvaluatedFinding, ...] = ()

    @property
    def blocked(self) -> bool:
        """True if any finding resolved to ``FATAL`` (the generation gate)."""
        return any(
            e.outcome is PolicyOutcome.FATAL for e in self.evaluated
        )

    @property
    def fatal(self) -> tuple[EvaluatedFinding, ...]:
        """Findings the policy resolved to a hard failure."""
        return tuple(
            e for e in self.evaluated if e.outcome is PolicyOutcome.FATAL
        )

    @property
    def warnings(self) -> tuple[EvaluatedFinding, ...]:
        """Findings that surface but allow continuation."""
        return tuple(
            e for e in self.evaluated if e.outcome is PolicyOutcome.WARN
        )

    @property
    def bypassed(self) -> tuple[EvaluatedFinding, ...]:
        """Conditions the caller explicitly accepted (policy-bypassed).

        Surfaced as a first-class channel so accepted risk stays traceable
        instead of vanishing (HLD "Validation Policy": explicit ignore must
        preserve diagnostics).
        """
        return tuple(
            e for e in self.evaluated if e.outcome is PolicyOutcome.IGNORED
        )

    @property
    def structural(self) -> tuple[EvaluatedFinding, ...]:
        """Structural-validation findings (HLD "Structural Validation")."""
        return tuple(
            e
            for e in self.evaluated
            if e.kind is ValidationKind.STRUCTURAL
        )

    @property
    def confidence(self) -> tuple[EvaluatedFinding, ...]:
        """Confidence-validation findings (HLD "Confidence Validation")."""
        return tuple(
            e
            for e in self.evaluated
            if e.kind is ValidationKind.CONFIDENCE
        )
