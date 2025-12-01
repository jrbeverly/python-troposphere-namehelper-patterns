"""Integration layer: adapter behaviour and template-generation gates.

Proves the acceptance criteria for issue #100: TemplateHelper delegates to the
public API, the generate-or-block gate respects policy modes, from_context
preserves bounded/advisory uncertainty, and a realistic derived-value scenario
from CloudFormation stack context renders against the IAM profile.  Written as
:class:`unittest.TestCase` so the baseline ``make e2e`` loop stays
zero-dependency.
"""

import unittest

from namehelper.adapters import TemplateHelper, from_context
from namehelper.components import (
    RepresentationForm,
    literal,
    region,
    stack_id,
    unique_id,
)
from namehelper.diagnostics import PolicyOutcome, ValidationKind, ValidationPolicy
from namehelper.profiles import IAM_ROLE, S3_BUCKET
from namehelper.profiles.catalog import UnsupportedResourceError


class TemplateHelperDelegationTests(unittest.TestCase):
    """TemplateHelper delegates correctly to the core naming flow."""

    def test_exact_plan_renders_through_adapter(self) -> None:
        helper = TemplateHelper()
        result = helper.name(
            literal("svc", "payments"),
            literal("env", "prod"),
            resource="iam-role",
        )
        self.assertEqual(result.rendered, "payments-prod")
        self.assertFalse(result.has_findings)

    def test_over_budget_is_fatal_under_default_policy(self) -> None:
        helper = TemplateHelper()
        result = helper.name(literal("base", "x" * 70), resource="iam-role")
        self.assertIsNone(helper.generate_or_block(result))
        self.assertTrue(result.has_findings)

    def test_errors_propagate_through_adapter(self) -> None:
        helper = TemplateHelper()
        with self.assertRaises(UnsupportedResourceError):
            helper.name(literal("a", "x"), resource="nonexistent")

    def test_empty_components_fails_fast(self) -> None:
        helper = TemplateHelper()
        with self.assertRaises(ValueError):
            helper.name(resource="iam-role")


class GenerateOrBlockTests(unittest.TestCase):
    """The generate-or-block gate respects policy modes."""

    def test_fatal_violation_blocks_generation(self) -> None:
        helper = TemplateHelper()
        result = helper.name(literal("base", "x" * 70), resource="iam-role")
        self.assertIsNone(helper.generate_or_block(result))
        self.assertTrue(helper.helper.policy.is_blocking(result.findings))

    def test_warning_does_not_block_in_permissive_mode(self) -> None:
        # An exact plan with a PRACTICAL_UNIQUENESS warning renders and
        # generation continues under the default permissive policy.
        helper = TemplateHelper()
        result = helper.name(
            unique_id("name", "my-bucket"), resource="s3-bucket"
        )
        emitted = helper.generate_or_block(result)
        self.assertEqual(emitted, "my-bucket")
        self.assertTrue(result.has_findings)

    def test_warning_blocks_when_escalated_to_fatal(self) -> None:
        helper = TemplateHelper(treat_warnings_as_fatal=True)
        result = helper.name(
            unique_id("name", "my-bucket"), resource="s3-bucket"
        )
        self.assertIsNone(helper.generate_or_block(result))
        evaluation = helper.evaluate(result.findings)
        self.assertTrue(evaluation.fatal)

    def test_ignored_code_unblocks_a_fatal_violation(self) -> None:
        # The caller explicitly accepts the over-budget risk.
        code = "impossible_over_budget"
        helper = TemplateHelper(ignored_codes=[code])
        result = helper.name(literal("base", "x" * 70), resource="iam-role")
        # Not blocked, but rendered is still None (the plan wasn't exact).
        emitted = helper.generate_or_block(result)
        self.assertIsNone(emitted)
        evaluation = helper.evaluate(result.findings)
        self.assertFalse(evaluation.blocked)
        self.assertTrue(evaluation.bypassed)

    def test_clean_plan_has_no_block_and_renders(self) -> None:
        helper = TemplateHelper()
        result = helper.name(
            literal("svc", "api"), literal("env", "dev"), resource="iam-role"
        )
        self.assertEqual(helper.generate_or_block(result), "api-dev")


class FromContextTests(unittest.TestCase):
    """from_context translates stack context while preserving uncertainty."""

    def test_known_values_produce_exact_components(self) -> None:
        context = from_context(
            region_code="us-east-1",
            stack="orders-prod-stack",
        )
        region_comp = context["region"]
        self.assertEqual(region_comp.primary.value, "us-east-1")
        self.assertEqual(region_comp.certainty.value, "exact")
        stack_comp = context["stack"]
        self.assertEqual(stack_comp.primary.value, "orders-prod-stack")
        self.assertEqual(stack_comp.certainty.value, "exact")

    def test_omitted_values_preserve_bounded_uncertainty(self) -> None:
        context = from_context()  # nothing known
        self.assertEqual(context["region"].certainty.value, "bounded")
        self.assertEqual(context["stack"].certainty.value, "bounded")

    def test_context_values_are_unpackable_into_helper_name(self) -> None:
        helper = TemplateHelper()
        context = from_context(
            region_code="us-east-1", stack="orders-prod-stack"
        )
        result = helper.name(
            *context.values(),
            literal("svc", "payments"),
            resource="iam-role",
        )
        self.assertEqual(result.rendered, "us-east-1-orders-prod-stack-payments")
        self.assertFalse(result.has_findings)

    def test_deploy_time_context_never_flattened_to_exact(self) -> None:
        # When region is unknown, from_context never silently fills it
        # with a guess or promotes a bounded value to exact.
        context = from_context()
        self.assertEqual(context["region"].certainty.value, "bounded")
        self.assertEqual(context["stack"].certainty.value, "bounded")
        # Verify the underlying component is the region family's unknown
        # (bounded) form, not the known (exact) form.
        self.assertEqual(context["region"].primary.value, "<region>")
        self.assertEqual(context["stack"].primary.value, "<stack-name>")


class RealisticDerivedValueScenarioTests(unittest.TestCase):
    """Issue #100: at least one realistic derived-value integration scenario."""

    def test_known_region_and_stack_fit_iam_role_with_literal_service(
        self,
    ) -> None:
        """Region + stack name (known at deploy time) + service literal.

        This is the common CloudFormation pattern: the region and stack
        name are available from the template context, and the caller adds a
        service identifier.  Against the IAM role profile (max 64 chars) the
        composition fits and renders cleanly.
        """
        helper = TemplateHelper()
        context = from_context(
            region_code="us-east-1", stack="orders-prod-stack"
        )
        result = helper.name(
            *context.values(),
            literal("svc", "payments"),
            resource="iam-role",
        )
        self.assertEqual(
            result.rendered, "us-east-1-orders-prod-stack-payments"
        )
        self.assertFalse(result.has_findings)
        self.assertIsNotNone(helper.generate_or_block(result))

    def test_unknown_region_surfaces_bounded_uncertainty_in_plan(self) -> None:
        """When region is unknown, the plan segment records BOUNDED certainty.

        This proves the adapter does not flatten deploy-time uncertainty
        into false exactness (HLD acceptance criterion).
        """
        helper = TemplateHelper()
        context = from_context()  # neither region nor stack known
        result = helper.name(
            *context.values(),
            literal("svc", "api"),
            resource="iam-role",
        )
        region_seg = result.plan.segments[0]
        self.assertEqual(region_seg.certainty.value, "bounded")
        stack_seg = result.plan.segments[1]
        self.assertEqual(stack_seg.certainty.value, "bounded")
        # Rendered is None because not all segments are exact.
        self.assertIsNone(result.rendered)

    def test_region_with_alternate_representation_via_selection(self) -> None:
        """Caller selects a shortened region form through the public API.

        This is the visible re-plan loop exercised through the adapter:
        the caller uses region (exact, full form), sees a suggestion, and
        re-plans with the shortened form via ``selections`` — all through
        the public TemplateHelper surface, never re-implementing rules.
        """
        helper = TemplateHelper()
        result = helper.name(
            region("us-east-1"),
            literal("base", "a" * 55),
            resource="s3-bucket",
            selections={"region": RepresentationForm.SHORTENED},
        )
        self.assertEqual(result.rendered, "useast1-" + "a" * 55)
        self.assertFalse(result.has_findings)


class AdapterIntegrationWithPolicyTests(unittest.TestCase):
    """TemplateHelper integrates with the public ValidationPolicy framework."""

    def test_evaluate_returns_stable_policy_evaluation(self) -> None:
        helper = TemplateHelper()
        result = helper.name(
            unique_id("name", "my-bucket"), resource="s3-bucket"
        )
        evaluation = helper.evaluate(result.findings)
        self.assertTrue(evaluation.confidence)
        self.assertFalse(evaluation.blocked)

    def test_strict_policy_blocks_on_uniqueness_warning(self) -> None:
        helper = TemplateHelper(treat_warnings_as_fatal=True)
        result = helper.name(
            unique_id("name", "my-bucket"), resource="s3-bucket"
        )
        self.assertIsNone(helper.generate_or_block(result))
        evaluation = helper.evaluate(result.findings)
        self.assertTrue(evaluation.blocked)
        self.assertTrue(evaluation.fatal)

    def test_bypassed_condition_remains_visible(self) -> None:
        """Explicitly ignored codes appear in the bypassed channel (HLD)."""
        helper = TemplateHelper(ignored_codes=["unbounded_length"])
        result = helper.name(
            literal("svc", "api"), stack_id(), resource="iam-role"
        )
        evaluation = helper.evaluate(result.findings)
        bypassed_codes = [e.finding.code for e in evaluation.bypassed]
        self.assertIn("unbounded_length", bypassed_codes)
        # The unbounded_length code appears in bypassed, not in fatal or
        # warnings (it was explicitly suppressed).
        self.assertNotIn(
            "unbounded_length",
            [e.finding.code for e in evaluation.fatal],
        )
        self.assertNotIn(
            "unbounded_length",
            [e.finding.code for e in evaluation.warnings],
        )


if __name__ == "__main__":
    unittest.main()
