"""Unit layer: validation-kind classification and policy execution.

Covers the acceptance scenarios for issue #70: structured diagnostics for
deterministic violations, bounded-risk, advisory uncertainty, and
policy-bypassed conditions; the structural-vs-confidence distinction kept as
separate channels; deterministic conversion of findings into fatal / warning /
ignored outcomes; and strict, permissive, and selectively ignored policy
scenarios. Written as :class:`unittest.TestCase` so the baseline ``make test``
loop stays zero-dependency.
"""

import unittest

from namehelper.diagnostics import (
    Certainty,
    EvaluatedFinding,
    Finding,
    PolicyEvaluation,
    PolicyOutcome,
    Severity,
    ValidationKind,
    ValidationPolicy,
    classify_kind,
)


def _violation(code: str = "v") -> Finding:
    return Finding(code=code, message=code, severity=Severity.VIOLATION)


def _bounded_warning(code: str = "w") -> Finding:
    return Finding(
        code=code,
        message=code,
        severity=Severity.WARNING,
        certainty=Certainty.BOUNDED,
    )


def _advisory_warning(code: str = "a") -> Finding:
    return Finding(
        code=code,
        message=code,
        severity=Severity.WARNING,
        certainty=Certainty.ADVISORY,
    )


def _structural_warning(code: str = "n") -> Finding:
    # A warning with no certainty: a visible structural transformation
    # (e.g. separator normalization), not a knowledge limitation.
    return Finding(code=code, message=code, severity=Severity.WARNING)


def _suggestion(code: str = "s") -> Finding:
    return Finding(code=code, message=code, severity=Severity.SUGGESTION)


class ClassifyKindTests(unittest.TestCase):
    def test_violation_is_structural(self) -> None:
        self.assertIs(
            classify_kind(_violation()), ValidationKind.STRUCTURAL
        )

    def test_bounded_warning_is_confidence(self) -> None:
        self.assertIs(
            classify_kind(_bounded_warning()), ValidationKind.CONFIDENCE
        )

    def test_advisory_warning_is_confidence(self) -> None:
        self.assertIs(
            classify_kind(_advisory_warning()), ValidationKind.CONFIDENCE
        )

    def test_warning_without_certainty_is_structural(self) -> None:
        self.assertIs(
            classify_kind(_structural_warning()), ValidationKind.STRUCTURAL
        )

    def test_suggestion_is_unclassified(self) -> None:
        self.assertIsNone(classify_kind(_suggestion()))

    def test_classification_is_deterministic(self) -> None:
        f = _bounded_warning()
        self.assertIs(classify_kind(f), classify_kind(f))


class StructuralVsConfidenceChannelTests(unittest.TestCase):
    def test_channels_are_not_collapsed(self) -> None:
        findings = [
            _violation("over_budget"),
            _bounded_warning("conservative"),
            _advisory_warning("unbounded"),
            _suggestion("alternate"),
        ]
        evaluation = ValidationPolicy().evaluate(findings)

        structural = [e.finding.code for e in evaluation.structural]
        confidence = [e.finding.code for e in evaluation.confidence]
        self.assertEqual(structural, ["over_budget"])
        self.assertEqual(confidence, ["conservative", "unbounded"])
        # The suggestion is neither a structural nor a confidence problem.
        self.assertNotIn("alternate", structural + confidence)


class PermissivePolicyTests(unittest.TestCase):
    def test_violation_is_fatal_and_blocks(self) -> None:
        evaluation = ValidationPolicy().evaluate([_violation("x")])
        self.assertTrue(evaluation.blocked)
        self.assertEqual(
            [e.finding.code for e in evaluation.fatal], ["x"]
        )
        self.assertEqual(evaluation.warnings, ())
        self.assertEqual(evaluation.bypassed, ())

    def test_warning_surfaces_but_does_not_block(self) -> None:
        evaluation = ValidationPolicy().evaluate([_bounded_warning("w")])
        self.assertFalse(evaluation.blocked)
        self.assertEqual(
            [e.finding.code for e in evaluation.warnings], ["w"]
        )
        self.assertEqual(evaluation.fatal, ())

    def test_each_finding_records_its_policy_decision(self) -> None:
        evaluation = ValidationPolicy().evaluate(
            [_violation("v"), _bounded_warning("w")]
        )
        decisions = {
            e.finding.code: e.outcome for e in evaluation.evaluated
        }
        self.assertEqual(
            decisions,
            {"v": PolicyOutcome.FATAL, "w": PolicyOutcome.WARN},
        )


class StrictPolicyTests(unittest.TestCase):
    def test_warnings_escalate_to_fatal_and_block(self) -> None:
        strict = ValidationPolicy(treat_warnings_as_fatal=True)
        evaluation = strict.evaluate([_advisory_warning("risk")])
        self.assertTrue(evaluation.blocked)
        self.assertEqual(
            [e.finding.code for e in evaluation.fatal], ["risk"]
        )
        # Escalation changes the outcome, never the structural/confidence
        # classification: an advisory warning is still a confidence problem.
        self.assertEqual(
            [e.finding.code for e in evaluation.confidence], ["risk"]
        )


class SelectivelyIgnoredPolicyTests(unittest.TestCase):
    def test_ignored_violation_is_bypassed_not_fatal(self) -> None:
        policy = ValidationPolicy(ignored_codes=frozenset({"accepted"}))
        evaluation = policy.evaluate(
            [_violation("accepted"), _violation("blocking")]
        )
        self.assertTrue(evaluation.blocked)  # the other violation still blocks
        self.assertEqual(
            [e.finding.code for e in evaluation.bypassed], ["accepted"]
        )
        self.assertEqual(
            [e.finding.code for e in evaluation.fatal], ["blocking"]
        )

    def test_bypass_unblocks_when_it_is_the_only_violation(self) -> None:
        policy = ValidationPolicy(ignored_codes=frozenset({"accepted"}))
        evaluation = policy.evaluate([_violation("accepted")])
        self.assertFalse(evaluation.blocked)
        self.assertEqual(len(evaluation.bypassed), 1)

    def test_bypassed_condition_remains_a_structured_diagnostic(self) -> None:
        # Accepted risk must stay visible and classifiable, not silently
        # dropped (HLD "Validation Policy").
        policy = ValidationPolicy(ignored_codes=frozenset({"accepted"}))
        evaluation = policy.evaluate([_violation("accepted")])
        bypassed = evaluation.bypassed[0]
        self.assertIsInstance(bypassed, EvaluatedFinding)
        self.assertIs(bypassed.outcome, PolicyOutcome.IGNORED)
        self.assertIs(bypassed.kind, ValidationKind.STRUCTURAL)


class EvaluationShapeTests(unittest.TestCase):
    def test_empty_findings_produce_an_empty_unblocked_evaluation(
        self,
    ) -> None:
        evaluation = ValidationPolicy().evaluate([])
        self.assertIsInstance(evaluation, PolicyEvaluation)
        self.assertEqual(evaluation.evaluated, ())
        self.assertFalse(evaluation.blocked)

    def test_evaluation_preserves_input_order(self) -> None:
        findings = [_violation("a"), _bounded_warning("b"), _suggestion("c")]
        evaluation = ValidationPolicy().evaluate(findings)
        self.assertEqual(
            [e.finding.code for e in evaluation.evaluated],
            ["a", "b", "c"],
        )

    def test_evaluation_records_the_policy_used(self) -> None:
        policy = ValidationPolicy(treat_warnings_as_fatal=True)
        self.assertIs(policy.evaluate([]).policy, policy)

    def test_evaluation_is_deterministic(self) -> None:
        findings = [_violation("a"), _advisory_warning("b")]
        policy = ValidationPolicy()
        self.assertEqual(
            policy.evaluate(findings), policy.evaluate(findings)
        )


if __name__ == "__main__":
    unittest.main()
