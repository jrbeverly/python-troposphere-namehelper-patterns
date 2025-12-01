"""Integration layer: public NameHelper API orchestration.

Proves the acceptance criteria for issue #90: exact, bounded, and
warning-oriented flows through the public entrypoint, explicit representation
choice, policy integration, and error propagation. Uses the real
orchestration path (NameHelper -> profile catalog -> planner -> result).

Written as :class:`unittest.TestCase` so the baseline ``make e2e`` loop
stays zero-dependency.
"""

import unittest

from namehelper import NameHelper, __version__
from namehelper.components import (
    RepresentationForm,
    derived,
    literal,
    region,
)
from namehelper.diagnostics import PolicyOutcome, ValidationPolicy
from namehelper.profiles import IAM_ROLE, S3_BUCKET
from namehelper.profiles.catalog import UnsupportedResourceError


class ExactFlowTests(unittest.TestCase):
    """An exact, fully-known plan renders with no findings."""

    def test_valid_exact_plan_renders_and_has_no_findings(self) -> None:
        helper = NameHelper()
        result = helper.name(
            literal("svc", "payments"),
            literal("env", "prod"),
            resource="iam-role",
        )
        self.assertEqual(result.rendered, "payments-prod")
        self.assertFalse(result.has_findings)
        self.assertFalse(helper.policy.is_blocking(result.findings))

    def test_evaluate_empty_findings_is_not_blocked(self) -> None:
        helper = NameHelper()
        result = helper.name(
            literal("svc", "api"), resource="iam-role"
        )
        evaluation = helper.evaluate(result.findings)
        self.assertFalse(evaluation.blocked)
        self.assertEqual(evaluation.evaluated, ())


class BoundedRiskTests(unittest.TestCase):
    """A plan with bounded risk warns but does not block by default."""

    def test_bounded_overflow_is_a_warning_not_fatal(self) -> None:
        helper = NameHelper()
        result = helper.name(
            literal("env", "prod"),
            derived("ctx", "<unknown>", max_length=70),
            resource="iam-role",
        )
        self.assertIsNone(result.rendered)
        self.assertTrue(result.has_findings)
        self.assertFalse(helper.policy.is_blocking(result.findings))

    def test_strict_policy_escalates_warning_to_blocking(self) -> None:
        helper = NameHelper(treat_warnings_as_fatal=True)
        result = helper.name(
            literal("env", "prod"),
            derived("ctx", "<unknown>", max_length=70),
            resource="iam-role",
        )
        evaluation = helper.evaluate(result.findings)
        self.assertTrue(evaluation.blocked)
        self.assertTrue(evaluation.confidence)

    def test_explicitly_ignored_code_unblocks(self) -> None:
        helper = NameHelper()
        # First find the code that would block.
        result = helper.name(
            literal("svc", "x" * 70), resource="iam-role"
        )
        code = result.findings[0].code

        permissive = NameHelper(ignored_codes=[code])
        result2 = permissive.name(
            literal("svc", "x" * 70), resource="iam-role"
        )
        self.assertFalse(permissive.policy.is_blocking(result2.findings))
        evaluation = permissive.evaluate(result2.findings)
        self.assertTrue(evaluation.bypassed)


class RepresentationSelectionTests(unittest.TestCase):
    """Explicit representation choice through the public surface."""

    def test_visible_replan_loop_via_helper(self) -> None:
        helper = NameHelper()
        comps = [literal("base", "a" * 55), region("us-east-1")]

        first = helper.name(*comps, resource="s3-bucket")
        self.assertIsNone(first.rendered)
        self.assertTrue(
            ValidationPolicy().is_blocking(first.findings)
        )

        resolved = helper.name(
            *comps,
            resource="s3-bucket",
            selections={"region": RepresentationForm.SHORTENED},
        )
        self.assertEqual(resolved.rendered, "a" * 55 + "-useast1")
        self.assertEqual(len(resolved.rendered), 63)
        self.assertFalse(resolved.has_findings)
        self.assertIs(
            resolved.plan.segments[1].form,
            RepresentationForm.SHORTENED,
        )


class ErrorPropagationTests(unittest.TestCase):
    """Errors from lower layers propagate cleanly through the helper."""

    def test_unsupported_resource_raises_explicit_error(self) -> None:
        helper = NameHelper()
        with self.assertRaises(UnsupportedResourceError):
            helper.name(literal("a", "x"), resource="nonexistent")

    def test_empty_components_fails_fast(self) -> None:
        helper = NameHelper()
        with self.assertRaises(ValueError):
            helper.name(resource="iam-role")

    def test_duplicate_roles_fail_fast(self) -> None:
        helper = NameHelper()
        with self.assertRaises(ValueError):
            helper.name(
                literal("env", "a"), literal("env", "b"),
                resource="iam-role",
            )

    def test_unavailable_form_selection_fails_fast(self) -> None:
        helper = NameHelper()
        with self.assertRaises(KeyError):
            helper.name(
                literal("a", "x"),
                resource="iam-role",
                selections={"a": RepresentationForm.SHORTENED},
            )


class VersionAndReprTests(unittest.TestCase):
    """The skeleton's baseline behavior is preserved."""

    def test_version_matches_package(self) -> None:
        self.assertEqual(NameHelper.version(), __version__)

    def test_repr_is_stable(self) -> None:
        self.assertEqual(repr(NameHelper()), "NameHelper()")


class DeterminismTests(unittest.TestCase):
    """The helper is deterministic (same inputs -> same outputs)."""

    def test_same_inputs_produce_same_result(self) -> None:
        helper = NameHelper()
        first = helper.name(
            literal("a", "x"), literal("b", "y"), resource="iam-role"
        )
        second = helper.name(
            literal("a", "x"), literal("b", "y"), resource="iam-role"
        )
        self.assertEqual(first, second)
        self.assertEqual(first.findings, second.findings)


class PolicyConfigurationTests(unittest.TestCase):
    """The stored policy is correctly configured and inspectable."""

    def test_default_policy_is_permissive(self) -> None:
        helper = NameHelper()
        self.assertFalse(helper.policy.treat_warnings_as_fatal)
        self.assertEqual(helper.policy.ignored_codes, frozenset())

    def test_strict_policy_escalates_warnings(self) -> None:
        helper = NameHelper(treat_warnings_as_fatal=True)
        self.assertTrue(helper.policy.treat_warnings_as_fatal)


if __name__ == "__main__":
    unittest.main()
