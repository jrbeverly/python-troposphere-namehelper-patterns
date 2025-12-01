"""Unit layer: the planning and visible constraint-resolution engine.

Covers the acceptance scenarios for issue #50: exact fit, over-budget
(deterministic and bounded-risk), impossible plans, length-floor breaches,
invalid characters, unsupported separators, unbounded/advisory inputs,
explicit alternate-representation surfacing (never auto-applied), the visible
re-plan loop, determinism, and policy integration. Written as
:class:`unittest.TestCase` so the baseline ``make test`` loop stays
zero-dependency.
"""

import unittest

from namehelper.components import (
    RepresentationForm,
    derived,
    generated,
    literal,
    region,
    stack_id,
    unique_id,
    uuid_fragment,
)
from namehelper.core import plan_name
from namehelper.core.planner import (
    ALTERNATE_REPRESENTATION,
    BELOW_MIN_LENGTH,
    IMPOSSIBLE_OVER_BUDGET,
    INVALID_CHARACTERS,
    OVER_BUDGET,
    PRACTICAL_UNIQUENESS,
    SEPARATOR_UNSUPPORTED,
    UNBOUNDED_LENGTH,
    VALIDATION_CONSERVATIVE,
)
from namehelper.diagnostics import (
    Certainty,
    Severity,
    ValidationKind,
    ValidationPolicy,
)
from namehelper.profiles import (
    API_GATEWAY_REST_API,
    IAM_ROLE,
    S3_BUCKET,
    SSM_PARAMETER,
)


def _codes(result):
    return [f.code for f in result.findings]


class ExactFitTests(unittest.TestCase):
    def test_valid_exact_plan_renders_with_no_findings(self) -> None:
        result = plan_name(
            [literal("svc", "payments"), literal("env", "prod")],
            IAM_ROLE,
        )
        self.assertEqual(result.rendered, "payments-prod")
        self.assertFalse(result.has_findings)
        self.assertIs(result.certainty, Certainty.EXACT)
        self.assertEqual(result.plan.roles, ("svc", "env"))
        self.assertEqual(result.plan.separator, "-")

    def test_no_alternate_suggestions_when_plan_is_clean(self) -> None:
        result = plan_name([literal("svc", "payments")], IAM_ROLE)
        self.assertEqual(result.findings, ())


class BudgetTests(unittest.TestCase):
    def test_exact_overflow_is_impossible_violation(self) -> None:
        result = plan_name([literal("svc", "x" * 70)], IAM_ROLE)
        self.assertEqual(_codes(result), [IMPOSSIBLE_OVER_BUDGET])
        finding = result.findings[0]
        self.assertIs(finding.severity, Severity.VIOLATION)
        self.assertEqual(finding.component, "svc")
        self.assertIsNone(result.rendered)

    def test_min_overflow_is_impossible_even_when_bounded(self) -> None:
        # The minimum already overflows: no deploy-time value can help, so the
        # verdict is deterministic despite the generated value being bounded.
        result = plan_name([generated("uid", length=80)], IAM_ROLE)
        finding = result.findings[0]
        self.assertEqual(finding.code, IMPOSSIBLE_OVER_BUDGET)
        self.assertIs(finding.severity, Severity.VIOLATION)
        self.assertEqual(finding.component, "uid")

    def test_bounded_worst_case_overflow_is_a_warning(self) -> None:
        result = plan_name(
            [
                literal("env", "prod"),
                derived("ctx", "<x>", max_length=70),
            ],
            IAM_ROLE,
        )
        over = next(f for f in result.findings if f.code == OVER_BUDGET)
        self.assertIs(over.severity, Severity.WARNING)
        self.assertIs(over.certainty, Certainty.BOUNDED)
        self.assertEqual(over.component, "ctx")
        self.assertIsNone(result.rendered)
        self.assertIs(result.certainty, Certainty.BOUNDED)

    def test_below_minimum_is_a_deterministic_violation(self) -> None:
        result = plan_name([literal("n", "ab")], S3_BUCKET)
        finding = result.findings[0]
        self.assertEqual(finding.code, BELOW_MIN_LENGTH)
        self.assertIs(finding.severity, Severity.VIOLATION)
        self.assertIsNone(result.rendered)

    def test_unbounded_input_is_an_advisory_warning(self) -> None:
        result = plan_name(
            [literal("svc", "app"), stack_id()], IAM_ROLE
        )
        unbounded = next(
            f for f in result.findings if f.code == UNBOUNDED_LENGTH
        )
        self.assertIs(unbounded.severity, Severity.WARNING)
        self.assertIs(unbounded.certainty, Certainty.ADVISORY)
        self.assertEqual(unbounded.component, "stackid")
        self.assertIs(result.certainty, Certainty.ADVISORY)
        self.assertIsNone(result.rendered)


class CharacterValidityTests(unittest.TestCase):
    def test_casing_violation_is_attributed_to_a_segment(self) -> None:
        result = plan_name(
            [literal("a", "my"), literal("b", "Bucket")], S3_BUCKET
        )
        finding = next(
            f for f in result.findings if f.code == INVALID_CHARACTERS
        )
        self.assertIs(finding.severity, Severity.VIOLATION)
        self.assertEqual(finding.component, "b")
        self.assertIsNone(result.rendered)

    def test_pattern_violation_stays_a_whole_name_finding(self) -> None:
        result = plan_name(
            [literal("x", "good"), literal("y", "b ad")], IAM_ROLE
        )
        finding = next(
            f for f in result.findings if f.code == INVALID_CHARACTERS
        )
        self.assertIs(finding.severity, Severity.VIOLATION)
        self.assertIsNone(finding.component)


class SeparatorTests(unittest.TestCase):
    def test_unsupported_separator_is_a_violation(self) -> None:
        result = plan_name(
            [literal("a", "x"), literal("b", "y")],
            IAM_ROLE,
            separator=".",
        )
        self.assertIn(SEPARATOR_UNSUPPORTED, _codes(result))
        finding = result.findings[0]
        self.assertIs(finding.severity, Severity.VIOLATION)
        self.assertIsNone(result.rendered)


class AlternateRepresentationTests(unittest.TestCase):
    def test_alternates_are_surfaced_not_applied(self) -> None:
        comps = [literal("base", "a" * 55), region("us-east-1")]
        result = plan_name(comps, S3_BUCKET)

        # Over budget reported, and a shorter region form is *offered*.
        self.assertIn(IMPOSSIBLE_OVER_BUDGET, _codes(result))
        suggestion = next(
            f
            for f in result.findings
            if f.code == ALTERNATE_REPRESENTATION
        )
        self.assertIs(suggestion.severity, Severity.SUGGESTION)
        self.assertEqual(suggestion.component, "region")
        # The plan still carries the originally selected (full) form: the
        # engine never silently compresses.
        region_segment = result.plan.segments[1]
        self.assertEqual(region_segment.value, "us-east-1")
        self.assertIsNone(result.rendered)

    def test_visible_replan_loop_resolves_with_caller_choice(self) -> None:
        comps = [literal("base", "a" * 55), region("us-east-1")]
        first = plan_name(comps, S3_BUCKET)
        self.assertIsNone(first.rendered)

        resolved = plan_name(
            comps,
            S3_BUCKET,
            selections={"region": RepresentationForm.SHORTENED},
        )
        self.assertEqual(resolved.rendered, "a" * 55 + "-useast1")
        self.assertEqual(len(resolved.rendered), 63)
        self.assertFalse(resolved.has_findings)


class CertaintyHonestyTests(unittest.TestCase):
    def test_fitting_but_inexact_plan_is_flagged_conservative(self) -> None:
        result = plan_name(
            [literal("svc", "api"), derived("ctx", "<ctx>", max_length=10)],
            API_GATEWAY_REST_API,
        )
        self.assertEqual(_codes(result), [VALIDATION_CONSERVATIVE])
        finding = result.findings[0]
        self.assertIs(finding.severity, Severity.WARNING)
        self.assertIs(finding.certainty, Certainty.BOUNDED)
        self.assertIsNone(result.rendered)


class DeterminismTests(unittest.TestCase):
    def test_same_inputs_produce_identical_result_and_findings(self) -> None:
        comps = [literal("base", "a" * 55), region("us-east-1")]
        first = plan_name(comps, S3_BUCKET)
        second = plan_name(comps, S3_BUCKET)
        self.assertEqual(first, second)
        self.assertEqual(first.findings, second.findings)


class PolicyIntegrationTests(unittest.TestCase):
    def test_violation_blocks_under_default_policy(self) -> None:
        result = plan_name([literal("svc", "x" * 70)], IAM_ROLE)
        self.assertTrue(ValidationPolicy().is_blocking(result.findings))

    def test_warning_does_not_block_unless_escalated(self) -> None:
        result = plan_name(
            [literal("env", "prod"), derived("ctx", "<x>", max_length=70)],
            IAM_ROLE,
        )
        self.assertFalse(ValidationPolicy().is_blocking(result.findings))
        strict = ValidationPolicy(treat_warnings_as_fatal=True)
        self.assertTrue(strict.is_blocking(result.findings))

    def test_ignored_code_unblocks_an_accepted_risk(self) -> None:
        result = plan_name([literal("svc", "x" * 70)], IAM_ROLE)
        policy = ValidationPolicy(
            ignored_codes=frozenset({IMPOSSIBLE_OVER_BUDGET})
        )
        self.assertFalse(policy.is_blocking(result.findings))


class InputValidationTests(unittest.TestCase):
    def test_empty_composition_fails_fast(self) -> None:
        with self.assertRaises(ValueError):
            plan_name([], IAM_ROLE)

    def test_duplicate_roles_fail_fast(self) -> None:
        with self.assertRaises(ValueError):
            plan_name(
                [literal("env", "a"), literal("env", "b")], IAM_ROLE
            )

    def test_selecting_an_unavailable_form_fails_fast(self) -> None:
        with self.assertRaises(KeyError):
            plan_name(
                [literal("a", "x")],
                IAM_ROLE,
                selections={"a": RepresentationForm.SHORTENED},
            )


class PracticalUniquenessTests(unittest.TestCase):
    """Issue #80: explicit uniqueness budget + honest, conservative claims.

    Covered across a permissive profile (``SSM_PARAMETER``,
    ``account-region`` scope) and a strict one (``S3_BUCKET``, ``global``
    scope), including bounded and advisory deploy-time sources.
    """

    def test_generated_suffix_reserves_budget_and_is_conservative(
        self,
    ) -> None:
        # Permissive profile, bounded generated uniqueness source.
        result = plan_name(
            [literal("svc", "payments"), generated("uid", length=8)],
            SSM_PARAMETER,
        )
        finding = next(
            f for f in result.findings if f.code == PRACTICAL_UNIQUENESS
        )
        self.assertIs(finding.severity, Severity.WARNING)
        # A bounded source yields a conservative (non-exact) claim.
        self.assertIs(finding.certainty, Certainty.BOUNDED)
        self.assertIn("reserved 8 chars", finding.message)
        self.assertIn("uid=generated", finding.message)
        self.assertIn("account-region", finding.message)
        self.assertIn("conservative", finding.message)

        evaluation = ValidationPolicy().evaluate(result.findings)
        self.assertFalse(evaluation.blocked)
        # Practical uniqueness is a confidence concern, never collapsed into
        # structural/syntactic validity.
        self.assertIn(
            PRACTICAL_UNIQUENESS,
            [e.finding.code for e in evaluation.confidence],
        )
        self.assertNotIn(
            PRACTICAL_UNIQUENESS,
            [e.finding.code for e in evaluation.structural],
        )

    def test_global_scope_is_only_a_warning_level_claim(self) -> None:
        # Strict profile: even a strong generated fragment cannot promise
        # global availability across accounts/time (explicitly out of scope).
        result = plan_name(
            [literal("base", "app"), uuid_fragment(length=8)],
            S3_BUCKET,
        )
        finding = next(
            f for f in result.findings if f.code == PRACTICAL_UNIQUENESS
        )
        self.assertIs(finding.severity, Severity.WARNING)
        self.assertIs(finding.certainty, Certainty.BOUNDED)
        self.assertIn("uid=uuid-fragment", finding.message)
        self.assertIn("global", finding.message)
        self.assertIn("warning-level", finding.message)

        self.assertFalse(
            ValidationPolicy().evaluate(result.findings).blocked
        )
        strict = ValidationPolicy(treat_warnings_as_fatal=True)
        self.assertTrue(strict.evaluate(result.findings).blocked)

    def test_caller_provided_value_is_exact_but_claim_is_not(self) -> None:
        # The value is exactly known and renders; the *uniqueness claim* is
        # still conservative because the library cannot verify it in AWS.
        result = plan_name(
            [unique_id("name", "my-unique-bucket")], S3_BUCKET
        )
        self.assertEqual(result.rendered, "my-unique-bucket")
        finding = next(
            f for f in result.findings if f.code == PRACTICAL_UNIQUENESS
        )
        self.assertIs(finding.certainty, Certainty.BOUNDED)
        self.assertIs(
            ValidationPolicy().evaluate(result.findings).evaluated[0].kind,
            ValidationKind.CONFIDENCE,
        )

    def test_stack_derived_source_is_advisory_not_exact(self) -> None:
        # Advisory deploy-time value: surfaced as advisory, not pretended
        # exact (PROBLEM.md ambiguity model / AC3).
        result = plan_name(
            [literal("svc", "app"), stack_id()], SSM_PARAMETER
        )
        finding = next(
            f for f in result.findings if f.code == PRACTICAL_UNIQUENESS
        )
        self.assertIs(finding.severity, Severity.WARNING)
        self.assertIs(finding.certainty, Certainty.ADVISORY)
        self.assertIn("stackid=stack-derived", finding.message)
        self.assertIs(result.certainty, Certainty.ADVISORY)
        self.assertIsNone(result.rendered)

    def test_multiple_strategies_reserve_a_combined_budget(self) -> None:
        result = plan_name(
            [
                literal("base", "app"),
                uuid_fragment(length=6),
                generated("g", length=4),
            ],
            S3_BUCKET,
        )
        finding = next(
            f for f in result.findings if f.code == PRACTICAL_UNIQUENESS
        )
        self.assertIn("reserved 10 chars", finding.message)
        self.assertIn("uid=uuid-fragment", finding.message)
        self.assertIn("g=generated", finding.message)
        self.assertIs(finding.certainty, Certainty.BOUNDED)

    def test_no_finding_when_profile_expects_no_uniqueness(self) -> None:
        result = plan_name(
            [literal("svc", "api"), generated("uid", length=6)],
            API_GATEWAY_REST_API,
        )
        self.assertNotIn(PRACTICAL_UNIQUENESS, _codes(result))

    def test_clean_plan_without_a_uniqueness_source_stays_silent(
        self,
    ) -> None:
        # Regression guard: a profile expecting uniqueness must not nag a
        # plan that simply did not opt into a uniqueness strategy.
        result = plan_name(
            [literal("svc", "payments"), literal("env", "prod")],
            IAM_ROLE,
        )
        self.assertEqual(result.findings, ())
        self.assertEqual(result.rendered, "payments-prod")

    def test_uniqueness_finding_is_deterministic(self) -> None:
        comps = [literal("base", "app"), uuid_fragment(length=8)]
        self.assertEqual(
            plan_name(comps, S3_BUCKET), plan_name(comps, S3_BUCKET)
        )


if __name__ == "__main__":
    unittest.main()
