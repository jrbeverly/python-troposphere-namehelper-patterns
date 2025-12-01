"""Unit layer: validation policy outcome mapping and gating."""

import unittest

from namehelper.diagnostics import (
    Finding,
    PolicyOutcome,
    Severity,
    ValidationPolicy,
)


def _finding(code: str, severity: Severity) -> Finding:
    return Finding(code=code, message=code, severity=severity)


class ValidationPolicyTests(unittest.TestCase):
    def test_default_violation_is_fatal(self) -> None:
        policy = ValidationPolicy()
        outcome = policy.outcome_for(_finding("v", Severity.VIOLATION))
        self.assertIs(outcome, PolicyOutcome.FATAL)

    def test_default_warning_warns(self) -> None:
        policy = ValidationPolicy()
        outcome = policy.outcome_for(_finding("w", Severity.WARNING))
        self.assertIs(outcome, PolicyOutcome.WARN)

    def test_suggestion_is_non_blocking(self) -> None:
        policy = ValidationPolicy()
        outcome = policy.outcome_for(_finding("s", Severity.SUGGESTION))
        self.assertIs(outcome, PolicyOutcome.WARN)

    def test_ignored_code_is_suppressed_even_for_violation(self) -> None:
        policy = ValidationPolicy(ignored_codes=frozenset({"accepted"}))
        outcome = policy.outcome_for(
            _finding("accepted", Severity.VIOLATION)
        )
        self.assertIs(outcome, PolicyOutcome.IGNORED)

    def test_treat_warnings_as_fatal_escalates_only_warnings(self) -> None:
        policy = ValidationPolicy(treat_warnings_as_fatal=True)
        self.assertIs(
            policy.outcome_for(_finding("w", Severity.WARNING)),
            PolicyOutcome.FATAL,
        )
        self.assertIs(
            policy.outcome_for(_finding("s", Severity.SUGGESTION)),
            PolicyOutcome.WARN,
        )

    def test_ignored_wins_over_warning_escalation(self) -> None:
        policy = ValidationPolicy(
            ignored_codes=frozenset({"w"}),
            treat_warnings_as_fatal=True,
        )
        self.assertIs(
            policy.outcome_for(_finding("w", Severity.WARNING)),
            PolicyOutcome.IGNORED,
        )

    def test_is_blocking_true_when_any_finding_is_fatal(self) -> None:
        policy = ValidationPolicy()
        findings = [
            _finding("w", Severity.WARNING),
            _finding("v", Severity.VIOLATION),
        ]
        self.assertTrue(policy.is_blocking(findings))

    def test_is_blocking_false_when_no_fatal(self) -> None:
        policy = ValidationPolicy(ignored_codes=frozenset({"v"}))
        findings = [
            _finding("w", Severity.WARNING),
            _finding("v", Severity.VIOLATION),
        ]
        self.assertFalse(policy.is_blocking(findings))

    def test_is_blocking_empty_is_false(self) -> None:
        self.assertFalse(ValidationPolicy().is_blocking([]))


if __name__ == "__main__":
    unittest.main()
