"""Validation, diagnostics, and policy.

Responsibility (HLD "Validation and Diagnostics Layer"): explain whether a
proposed name is safe, unsafe, exact, bounded, or advisory; produce findings;
and interpret the caller-controlled validation policy (fatal / warning /
ignored).

Boundaries: diagnostics describe and classify outcomes; they do not mutate
the plan or select representations (that is :mod:`namehelper.core`). This
layer contains no AWS-specific rules and no adapter-specific types.
"""

from namehelper.diagnostics.certainty import Certainty
from namehelper.diagnostics.findings import Finding, Severity
from namehelper.diagnostics.policy import (
    EvaluatedFinding,
    PolicyEvaluation,
    PolicyOutcome,
    ValidationKind,
    ValidationPolicy,
    classify_kind,
)

__all__ = [
    "Certainty",
    "Severity",
    "Finding",
    "PolicyOutcome",
    "ValidationKind",
    "classify_kind",
    "ValidationPolicy",
    "EvaluatedFinding",
    "PolicyEvaluation",
]
