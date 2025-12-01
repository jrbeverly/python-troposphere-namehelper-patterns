"""Integration layer: planning + policy execution wired end to end.

Proves the issue #70 flows across real seams (components -> core planner ->
diagnostics policy) without any adapter coupling: a strict gate stops
generation on a deterministic violation, the same findings only warn under a
permissive policy, an explicitly ignored finding is bypassed yet still
visible, and the visible re-plan loop preserves which representation each
segment used. Real profiles/components are used so this exercises the
genuine cross-module path, not stubs.
"""

import unittest

from namehelper.components import (
    RepresentationForm,
    derived,
    generated,
    literal,
    region,
    uuid_fragment,
)
from namehelper.core import plan_name
from namehelper.core.planner import PRACTICAL_UNIQUENESS
from namehelper.diagnostics import ValidationKind, ValidationPolicy
from namehelper.profiles import IAM_ROLE, S3_BUCKET, SSM_PARAMETER


class ExactCleanFlowTests(unittest.TestCase):
    def test_clean_plan_evaluates_unblocked_and_traceable(self) -> None:
        result = plan_name(
            [literal("svc", "payments"), literal("env", "prod")],
            IAM_ROLE,
        )
        self.assertEqual(result.rendered, "payments-prod")

        evaluation = ValidationPolicy().evaluate(result.findings)
        self.assertFalse(evaluation.blocked)
        self.assertEqual(evaluation.evaluated, ())
        # Which representation each segment used is recoverable.
        self.assertEqual(
            [s.form for s in result.plan.segments],
            [RepresentationForm.FULL, RepresentationForm.FULL],
        )


class TemplateGenerationGateTests(unittest.TestCase):
    def test_deterministic_violation_blocks_generation(self) -> None:
        result = plan_name([literal("svc", "x" * 70)], IAM_ROLE)
        self.assertIsNone(result.rendered)

        evaluation = ValidationPolicy().evaluate(result.findings)
        self.assertTrue(evaluation.blocked)
        self.assertTrue(evaluation.structural)
        self.assertEqual(evaluation.confidence, ())

    def test_bounded_risk_warns_permissively_but_blocks_when_strict(
        self,
    ) -> None:
        result = plan_name(
            [literal("env", "prod"), derived("ctx", "<x>", max_length=70)],
            IAM_ROLE,
        )

        permissive = ValidationPolicy().evaluate(result.findings)
        self.assertFalse(permissive.blocked)
        self.assertTrue(permissive.confidence)

        strict = ValidationPolicy(treat_warnings_as_fatal=True).evaluate(
            result.findings
        )
        self.assertTrue(strict.blocked)

    def test_selectively_ignored_violation_is_bypassed_but_visible(
        self,
    ) -> None:
        result = plan_name([literal("svc", "x" * 70)], IAM_ROLE)
        code = result.findings[0].code

        policy = ValidationPolicy(ignored_codes=frozenset({code}))
        evaluation = policy.evaluate(result.findings)
        self.assertFalse(evaluation.blocked)
        self.assertEqual(
            [e.finding.code for e in evaluation.bypassed], [code]
        )
        self.assertIs(
            evaluation.bypassed[0].kind, ValidationKind.STRUCTURAL
        )


class VisibleReplanLoopTests(unittest.TestCase):
    def test_replan_resolves_and_preserves_chosen_representation(
        self,
    ) -> None:
        comps = [literal("base", "a" * 55), region("us-east-1")]

        first = plan_name(comps, S3_BUCKET)
        self.assertTrue(
            ValidationPolicy().evaluate(first.findings).blocked
        )
        self.assertIs(
            first.plan.segments[1].form, RepresentationForm.FULL
        )

        resolved = plan_name(
            comps,
            S3_BUCKET,
            selections={"region": RepresentationForm.SHORTENED},
        )
        self.assertEqual(resolved.rendered, "a" * 55 + "-useast1")
        self.assertFalse(
            ValidationPolicy().evaluate(resolved.findings).blocked
        )
        # The result records that the shortened form was the one used.
        self.assertIs(
            resolved.plan.segments[1].form,
            RepresentationForm.SHORTENED,
        )


class PracticalUniquenessGateTests(unittest.TestCase):
    """Issue #80 flow: practical uniqueness across the real planner+policy
    seam, on a strict (global) and a permissive (account-region) profile.
    """

    def test_global_uniqueness_warns_but_strict_gate_escalates(
        self,
    ) -> None:
        result = plan_name(
            [literal("base", "app"), uuid_fragment(length=8)],
            S3_BUCKET,
        )

        permissive = ValidationPolicy().evaluate(result.findings)
        self.assertFalse(permissive.blocked)
        self.assertIn(
            PRACTICAL_UNIQUENESS,
            [e.finding.code for e in permissive.confidence],
        )
        # Never collapsed into the structural/syntactic channel.
        self.assertNotIn(
            PRACTICAL_UNIQUENESS,
            [e.finding.code for e in permissive.structural],
        )
        self.assertIs(
            next(
                e
                for e in permissive.evaluated
                if e.finding.code == PRACTICAL_UNIQUENESS
            ).kind,
            ValidationKind.CONFIDENCE,
        )

        strict = ValidationPolicy(treat_warnings_as_fatal=True).evaluate(
            result.findings
        )
        self.assertTrue(strict.blocked)

    def test_permissive_profile_bypass_keeps_uniqueness_traceable(
        self,
    ) -> None:
        result = plan_name(
            [literal("svc", "payments"), generated("uid", length=8)],
            SSM_PARAMETER,
        )
        policy = ValidationPolicy(
            ignored_codes=frozenset({PRACTICAL_UNIQUENESS})
        )
        evaluation = policy.evaluate(result.findings)
        self.assertFalse(evaluation.blocked)
        self.assertIn(
            PRACTICAL_UNIQUENESS,
            [e.finding.code for e in evaluation.bypassed],
        )


if __name__ == "__main__":
    unittest.main()
