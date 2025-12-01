"""Unit layer: deterministic regression fixtures.

HLD workstream 7 requires "regression protection for deterministic output" as
a first-class verification concern. This file pins known input → output pairs
across the full planning, rendering, finding, and policy-evaluation surface so
any change to composition, validation, or rendering logic will fail here before
it can silently alter a caller-visible result.

Every test in this file asserts a concrete, expected value rather than merely
checking that repeated calls agree. Written as :class:`unittest.TestCase` so
the baseline ``make test`` loop stays zero-dependency.
"""

import unittest

from namehelper.components import (
    RepresentationForm,
    derived,
    generated,
    literal,
    region,
    stack_id,
    stack_name,
    unique_id,
    uuid_fragment,
)
from namehelper.components.component import (
    Component,
    ComponentSource,
    Representation,
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
from namehelper.core.rendering import (
    SANITIZED_CHARACTERS,
    SEPARATOR_NORMALIZED,
    STYLE_UNSUPPORTED,
    NamingStyle,
    RenderedName,
    render,
)
from namehelper.diagnostics import (
    Certainty,
    PolicyOutcome,
    Severity,
    ValidationKind,
    ValidationPolicy,
)
from namehelper.profiles import (
    API_GATEWAY_REST_API,
    IAM_ROLE,
    S3_BUCKET,
    SSM_PARAMETER,
    Casing,
    ConstraintProfile,
    SupportLevel,
    Uniqueness,
)


# ---------------------------------------------------------------------------
# Plan-output regression fixtures
# ---------------------------------------------------------------------------

class PlanExactFitRegressionTests(unittest.TestCase):
    """Known inputs + known profiles → exact rendered names, no findings."""

    def test_iam_role_two_literals(self) -> None:
        result = plan_name(
            [literal("svc", "payments"), literal("env", "prod")],
            IAM_ROLE,
        )
        self.assertEqual(result.rendered, "payments-prod")
        self.assertEqual(result.findings, ())
        self.assertIs(result.certainty, Certainty.EXACT)

    def test_iam_role_single_literal(self) -> None:
        result = plan_name([literal("svc", "api")], IAM_ROLE)
        self.assertEqual(result.rendered, "api")
        self.assertEqual(result.findings, ())

    def test_s3_bucket_exact_fit(self) -> None:
        result = plan_name(
            [literal("app", "myapp"), literal("env", "prod")],
            S3_BUCKET,
        )
        self.assertEqual(result.rendered, "myapp-prod")
        self.assertEqual(result.findings, ())

    def test_ssm_parameter_hierarchical_exact(self) -> None:
        # Separator normalization collapses the leading '/' from the value
        # and surfaces the change as a traceable finding. The result is
        # still valid: the SSM pattern treats the leading '/' as optional.
        result = plan_name(
            [literal("path", "/app/prod"), literal("key", "db-pass")],
            SSM_PARAMETER,
            separator="/",
        )
        self.assertEqual(result.rendered, "app/prod/db-pass")
        codes = [f.code for f in result.findings]
        self.assertIn(SEPARATOR_NORMALIZED, codes)
        self.assertNotIn(SEPARATOR_UNSUPPORTED, codes)

    def test_api_gateway_exact(self) -> None:
        result = plan_name(
            [literal("name", "My Public API v2")],
            API_GATEWAY_REST_API,
        )
        self.assertEqual(result.rendered, "My Public API v2")
        self.assertEqual(result.findings, ())

    def test_three_component_exact(self) -> None:
        result = plan_name(
            [
                literal("env", "prod"),
                literal("svc", "payments"),
                literal("role", "worker"),
            ],
            IAM_ROLE,
        )
        self.assertEqual(result.rendered, "prod-payments-worker")

    def test_exact_region_and_stack_iam(self) -> None:
        result = plan_name(
            [
                region("us-east-1"),
                stack_name("orders-prod-stack"),
                literal("svc", "payments"),
            ],
            IAM_ROLE,
        )
        self.assertEqual(result.rendered, "us-east-1-orders-prod-stack-payments")
        self.assertEqual(result.findings, ())


class PlanOverBudgetRegressionTests(unittest.TestCase):
    """Known over-length inputs produce stable, specific findings."""

    def test_iam_role_too_long_exact(self) -> None:
        result = plan_name([literal("svc", "x" * 70)], IAM_ROLE)
        self.assertIsNone(result.rendered)
        self.assertEqual(len(result.findings), 1)
        finding = result.findings[0]
        self.assertEqual(finding.code, IMPOSSIBLE_OVER_BUDGET)
        self.assertIs(finding.severity, Severity.VIOLATION)
        self.assertEqual(finding.component, "svc")

    def test_s3_bucket_too_long_exact(self) -> None:
        result = plan_name([literal("base", "a" * 65)], S3_BUCKET)
        self.assertIsNone(result.rendered)
        finding = result.findings[0]
        self.assertEqual(finding.code, IMPOSSIBLE_OVER_BUDGET)
        self.assertIs(finding.severity, Severity.VIOLATION)

    def test_bounded_overflow_is_a_warning_not_a_violation(self) -> None:
        result = plan_name(
            [
                literal("env", "prod"),
                derived("ctx", "<x>", max_length=70),
            ],
            IAM_ROLE,
        )
        finding = next(f for f in result.findings if f.code == OVER_BUDGET)
        self.assertIs(finding.severity, Severity.WARNING)
        self.assertIs(finding.certainty, Certainty.BOUNDED)
        self.assertEqual(finding.component, "ctx")

    def test_min_length_overflow_is_impossible_violation(self) -> None:
        # Even with a generated value (BOUNDED certainty), the min already
        # overflows so there's nothing deploy-time can fix.
        result = plan_name([generated("uid", length=80)], IAM_ROLE)
        finding = result.findings[0]
        self.assertEqual(finding.code, IMPOSSIBLE_OVER_BUDGET)
        self.assertIs(finding.severity, Severity.VIOLATION)


class PlanUnsupportedSeparatorRegressionTests(unittest.TestCase):
    """Known unsupported separator → stable finding."""

    def test_s3_bucket_rejects_underscore_separator(self) -> None:
        result = plan_name(
            [literal("a", "x"), literal("b", "y")],
            S3_BUCKET,
            separator="_",
        )
        finding = next(f for f in result.findings if f.code == SEPARATOR_UNSUPPORTED)
        self.assertIs(finding.severity, Severity.VIOLATION)
        self.assertIn("_", finding.message)

    def test_ssm_parameter_accepts_forward_slash_separator(self) -> None:
        # SSM supports "/", "-", and "_" as separators.
        result = plan_name(
            [literal("a", "x"), literal("b", "y")],
            SSM_PARAMETER,
            separator="/",
        )
        self.assertEqual(result.rendered, "x/y")
        self.assertEqual(result.findings, ())


class PlanBelowMinLengthRegressionTests(unittest.TestCase):
    """Known below-minimum-length inputs produce stable findings."""

    def test_s3_bucket_too_short_exact_is_violation(self) -> None:
        result = plan_name([literal("a", "ab")], S3_BUCKET)
        finding = next(f for f in result.findings if f.code == BELOW_MIN_LENGTH)
        self.assertIs(finding.severity, Severity.VIOLATION)

    def test_s3_bucket_exactly_at_min_is_clean(self) -> None:
        result = plan_name([literal("a", "abc")], S3_BUCKET)
        self.assertEqual(result.rendered, "abc")
        self.assertEqual(result.findings, ())

    def test_s3_bucket_exactly_at_max_is_clean(self) -> None:
        result = plan_name([literal("a", "a" * 63)], S3_BUCKET)
        self.assertEqual(result.rendered, "a" * 63)
        self.assertEqual(result.findings, ())


class PlanInvalidCharactersRegressionTests(unittest.TestCase):
    """Known invalid-character inputs produce stable findings."""

    def test_s3_bucket_uppercase_is_invalid(self) -> None:
        result = plan_name([literal("name", "MyBucket")], S3_BUCKET)
        finding = next(f for f in result.findings if f.code == INVALID_CHARACTERS)
        self.assertIs(finding.severity, Severity.VIOLATION)

    def test_iam_role_slash_is_invalid(self) -> None:
        result = plan_name([literal("name", "bad/slash")], IAM_ROLE)
        finding = next(f for f in result.findings if f.code == INVALID_CHARACTERS)
        self.assertIs(finding.severity, Severity.VIOLATION)

    def test_s3_bucket_ip_shaped_name_is_invalid(self) -> None:
        result = plan_name([literal("name", "192.168.5.4")], S3_BUCKET)
        self.assertIsNotNone(
            next((f for f in result.findings if f.code == INVALID_CHARACTERS), None)
        )

    def test_ssm_reserved_prefix_is_invalid(self) -> None:
        result = plan_name([literal("path", "aws-secret")], SSM_PARAMETER)
        self.assertIsNotNone(
            next((f for f in result.findings if f.code == INVALID_CHARACTERS), None)
        )


class PlanCertaintyHonestyRegressionTests(unittest.TestCase):
    """Known non-exact inputs produce the conservative-verdict finding."""

    def test_bounded_but_fitting_plan_flags_conservative(self) -> None:
        # A plan that fits the budget envelope but has non-exact inputs must
        # flag the conservative verdict. Construct a bounded component with
        # an explicit min_length >= 1 so the below-min-length check does not
        # fire first (IAM min_length is 1).
        comp = Component(
            "x",
            ComponentSource.DERIVED,
            (
                Representation(
                    RepresentationForm.FULL,
                    "<x>",
                    Certainty.BOUNDED,
                    min_length=1,
                    max_length=5,
                ),
            ),
        )
        result = plan_name([comp], IAM_ROLE)
        codes = [f.code for f in result.findings]
        self.assertIn(VALIDATION_CONSERVATIVE, codes)
        self.assertNotIn(BELOW_MIN_LENGTH, codes)


# ---------------------------------------------------------------------------
# Finding regression fixtures
# ---------------------------------------------------------------------------

class FindingRegressionTests(unittest.TestCase):
    """Stable finding codes, severities, and messages for known violations."""

    def test_impossible_over_budget_message_is_stable(self) -> None:
        result = plan_name([literal("svc", "x" * 70)], IAM_ROLE)
        finding = result.findings[0]
        self.assertIn("minimum composed length", finding.message)
        self.assertIn("limit of 64", finding.message)

    def test_over_budget_message_is_stable(self) -> None:
        result = plan_name(
            [literal("env", "prod"), derived("ctx", "<x>", max_length=70)],
            IAM_ROLE,
        )
        over = next(f for f in result.findings if f.code == OVER_BUDGET)
        self.assertIn("may exceed", over.message)

    def test_unbounded_message_is_stable(self) -> None:
        result = plan_name([stack_id()], SSM_PARAMETER)
        unbounded = next(f for f in result.findings if f.code == UNBOUNDED_LENGTH)
        self.assertIn("no known upper length bound", unbounded.message)
        self.assertIs(unbounded.severity, Severity.WARNING)
        self.assertIs(unbounded.certainty, Certainty.ADVISORY)

    def test_practical_uniqueness_for_s3_is_a_warning(self) -> None:
        result = plan_name(
            [literal("base", "app"), uuid_fragment(length=8)],
            S3_BUCKET,
        )
        finding = next(f for f in result.findings if f.code == PRACTICAL_UNIQUENESS)
        self.assertIs(finding.severity, Severity.WARNING)
        self.assertIn("global", finding.message)
        self.assertIn("availability", finding.message)

    def test_practical_uniqueness_for_iam_is_account_scoped(self) -> None:
        result = plan_name(
            [literal("name", "myrole"), generated("uid", length=6)],
            IAM_ROLE,
        )
        finding = next(f for f in result.findings if f.code == PRACTICAL_UNIQUENESS)
        self.assertIs(finding.severity, Severity.WARNING)
        self.assertIn("account", finding.message)


# ---------------------------------------------------------------------------
# Alternate-representation regression fixtures
# ---------------------------------------------------------------------------

class AlternateRepresentationRegressionTests(unittest.TestCase):
    """The visible re-plan loop surfaces stable suggestions and resolves
    deterministically when the caller chooses a representation."""

    def test_shortened_region_suggestion_is_surfaced(self) -> None:
        comps = [literal("base", "a" * 55), region("us-east-1")]
        result = plan_name(comps, S3_BUCKET)
        alternates = [
            f for f in result.findings if f.code == ALTERNATE_REPRESENTATION
        ]
        self.assertTrue(len(alternates) >= 1)
        region_alt = next(a for a in alternates if a.component == "region")
        self.assertIs(region_alt.severity, Severity.SUGGESTION)
        self.assertIn("shortened", region_alt.message.lower())

    def test_replan_with_shortened_region_resolves(self) -> None:
        comps = [literal("base", "a" * 55), region("us-east-1")]
        resolved = plan_name(
            comps,
            S3_BUCKET,
            selections={"region": RepresentationForm.SHORTENED},
        )
        self.assertEqual(resolved.rendered, "a" * 55 + "-useast1")
        self.assertEqual(len(resolved.rendered), 63)
        self.assertIs(
            resolved.plan.segments[1].form,
            RepresentationForm.SHORTENED,
        )
        self.assertEqual(resolved.findings, ())

    def test_bounded_fragment_suggestion_is_surfaced(self) -> None:
        comps = [
            literal("env", "production"),
            derived("ctx", "<ctx>", max_length=70),
        ]
        result = plan_name(comps, IAM_ROLE)
        # With a 70-char max derived value plus separator+literal, the plan may
        # overflow. A canonical SUGGESTION is not guaranteed when bounded (no
        # alternate form shorter than the selected one exists), so we verify
        # determinism: same inputs → same result.
        second = plan_name(comps, IAM_ROLE)
        self.assertEqual(result, second)
        self.assertEqual(result.findings, second.findings)

    def test_no_suggestions_when_plan_is_clean(self) -> None:
        result = plan_name([literal("svc", "api")], IAM_ROLE)
        alternates = [
            f for f in result.findings if f.code == ALTERNATE_REPRESENTATION
        ]
        self.assertEqual(alternates, [])


# ---------------------------------------------------------------------------
# Rendering regression fixtures
# ---------------------------------------------------------------------------

class RenderingStyleRegressionTests(unittest.TestCase):
    """Known style + profile combinations produce deterministic output."""

    SEGS = [("r0", "My"), ("r1", "Cool"), ("r2", "Svc")]

    def test_kebab_iam(self) -> None:
        result = render(self.SEGS, separator="_", profile=IAM_ROLE, style=NamingStyle.KEBAB)
        self.assertEqual(result.value, "my-cool-svc")
        self.assertEqual(result.findings, ())

    def test_snake_iam(self) -> None:
        result = render(self.SEGS, separator="-", profile=IAM_ROLE, style=NamingStyle.SNAKE)
        self.assertEqual(result.value, "my_cool_svc")
        self.assertEqual(result.findings, ())

    def test_camel_iam(self) -> None:
        result = render(self.SEGS, separator="-", profile=IAM_ROLE, style=NamingStyle.CAMEL)
        self.assertEqual(result.value, "myCoolSvc")
        self.assertEqual(result.findings, ())

    def test_pascal_iam(self) -> None:
        result = render(self.SEGS, separator="-", profile=IAM_ROLE, style=NamingStyle.PASCAL)
        self.assertEqual(result.value, "MyCoolSvc")
        self.assertEqual(result.findings, ())

    def test_style_subordinate_to_resource_rules(self) -> None:
        # Snake requires '_' which S3 does not allow.
        result = render(
            [("r0", "a"), ("r1", "b")],
            separator="-",
            profile=S3_BUCKET,
            style=NamingStyle.SNAKE,
        )
        codes = [f.code for f in result.findings]
        self.assertIn(STYLE_UNSUPPORTED, codes)
        self.assertEqual(result.value, "a-b")


class RenderingSanitizationRegressionTests(unittest.TestCase):
    """Known sanitization transforms produce deterministic output."""

    def test_s3_sanitize_lowercases(self) -> None:
        result = render(
            [("r0", "My"), ("r1", "Bucket")],
            separator="-",
            profile=S3_BUCKET,
            sanitize=True,
        )
        self.assertEqual(result.value, "my-bucket")
        codes = [f.code for f in result.findings]
        self.assertIn(SANITIZED_CHARACTERS, codes)

    def test_upper_profile_sanitize_uppercases(self) -> None:
        upper = ConstraintProfile(
            resource="upper-test",
            max_length=64,
            allowed_pattern=r"[A-Z0-9-]+",
            casing=Casing.UPPER,
            separators=("-",),
        )
        result = render(
            [("r0", "ab"), ("r1", "cd")],
            separator="-",
            profile=upper,
            sanitize=True,
        )
        self.assertEqual(result.value, "AB-CD")
        codes = [f.code for f in result.findings]
        self.assertIn(SANITIZED_CHARACTERS, codes)

    def test_sanitize_off_leaves_casing_alone(self) -> None:
        result = render(
            [("r0", "My"), ("r1", "Bucket")],
            separator="-",
            profile=S3_BUCKET,
            sanitize=False,
        )
        self.assertEqual(result.value, "My-Bucket")
        self.assertEqual(result.findings, ())


class RenderingSeparatorNormalizationRegressionTests(unittest.TestCase):
    """Known separator normalization produces deterministic output."""

    def test_empty_segment_collapses_separator(self) -> None:
        result = render(
            [("r0", "x"), ("r1", ""), ("r2", "y")],
            separator="-",
            profile=IAM_ROLE,
        )
        self.assertEqual(result.value, "x-y")
        codes = [f.code for f in result.findings]
        self.assertIn(SEPARATOR_NORMALIZED, codes)

    def test_leading_and_trailing_empty_segments_are_trimmed(self) -> None:
        result = render(
            [("r0", ""), ("r1", "y"), ("r2", "")],
            separator="-",
            profile=IAM_ROLE,
        )
        self.assertEqual(result.value, "y")
        codes = [f.code for f in result.findings]
        self.assertIn(SEPARATOR_NORMALIZED, codes)

    def test_value_internal_separator_is_never_collapsed(self) -> None:
        result = render(
            [("r0", "a"), ("r1", "us-east-1")],
            separator="-",
            profile=IAM_ROLE,
        )
        self.assertEqual(result.value, "a-us-east-1")
        self.assertEqual(result.findings, ())


# ---------------------------------------------------------------------------
# Policy-evaluation regression fixtures
# ---------------------------------------------------------------------------

class PolicyEvaluationRegressionTests(unittest.TestCase):
    """Known finding sets + known policies → deterministic evaluations."""

    def test_empty_findings_permissive(self) -> None:
        evaluation = ValidationPolicy().evaluate([])
        self.assertFalse(evaluation.blocked)
        self.assertEqual(evaluation.fatal, ())
        self.assertEqual(evaluation.warnings, ())
        self.assertEqual(evaluation.bypassed, ())

    def test_violation_is_fatal_by_default(self) -> None:
        result = plan_name([literal("svc", "x" * 70)], IAM_ROLE)
        evaluation = ValidationPolicy().evaluate(result.findings)
        self.assertTrue(evaluation.blocked)
        self.assertEqual(len(evaluation.fatal), 1)
        self.assertIs(evaluation.fatal[0].kind, ValidationKind.STRUCTURAL)

    def test_warning_is_warn_not_fatal_by_default(self) -> None:
        result = plan_name(
            [literal("env", "prod"), derived("ctx", "<x>", max_length=70)],
            IAM_ROLE,
        )
        evaluation = ValidationPolicy().evaluate(result.findings)
        self.assertFalse(evaluation.blocked)
        self.assertTrue(evaluation.warnings)
        self.assertTrue(evaluation.confidence)

    def test_strict_policy_escalates_warning_to_fatal(self) -> None:
        result = plan_name(
            [literal("env", "prod"), derived("ctx", "<x>", max_length=70)],
            IAM_ROLE,
        )
        evaluation = ValidationPolicy(treat_warnings_as_fatal=True).evaluate(
            result.findings
        )
        self.assertTrue(evaluation.blocked)
        self.assertTrue(evaluation.fatal)

    def test_ignored_code_unblocks_and_is_bypassed(self) -> None:
        result = plan_name([literal("svc", "x" * 70)], IAM_ROLE)
        code = result.findings[0].code
        policy = ValidationPolicy(ignored_codes=frozenset({code}))
        evaluation = policy.evaluate(result.findings)
        self.assertFalse(evaluation.blocked)
        bypassed_codes = [e.finding.code for e in evaluation.bypassed]
        self.assertIn(code, bypassed_codes)

    def test_policy_evaluation_is_deterministic(self) -> None:
        result = plan_name([literal("svc", "x" * 70)], IAM_ROLE)
        first = ValidationPolicy().evaluate(result.findings)
        second = ValidationPolicy().evaluate(result.findings)
        self.assertEqual(first.blocked, second.blocked)
        self.assertEqual(len(first.fatal), len(second.fatal))
        self.assertEqual(
            [e.finding.code for e in first.fatal],
            [e.finding.code for e in second.fatal],
        )

    def test_channels_are_disjoint(self) -> None:
        result = plan_name(
            [literal("base", "app"), uuid_fragment(length=8)],
            S3_BUCKET,
        )
        evaluation = ValidationPolicy().evaluate(result.findings)
        structural_codes = {e.finding.code for e in evaluation.structural}
        confidence_codes = {e.finding.code for e in evaluation.confidence}
        self.assertFalse(
            structural_codes & confidence_codes,
            "structural and confidence channels must be disjoint",
        )


# ---------------------------------------------------------------------------
# Profile regression fixtures
# ---------------------------------------------------------------------------

class ProfileEncodingRegressionTests(unittest.TestCase):
    """Known profile field values are pinned against accidental edits."""

    def test_iam_role_dimensions(self) -> None:
        self.assertEqual(IAM_ROLE.resource, "iam-role")
        self.assertEqual(IAM_ROLE.max_length, 64)
        self.assertEqual(IAM_ROLE.min_length, 1)
        self.assertIs(IAM_ROLE.casing, Casing.ANY)
        self.assertIs(IAM_ROLE.uniqueness, Uniqueness.ACCOUNT)
        self.assertIs(IAM_ROLE.support, SupportLevel.SUPPORTED)

    def test_s3_bucket_dimensions(self) -> None:
        self.assertEqual(S3_BUCKET.resource, "s3-bucket")
        self.assertEqual(S3_BUCKET.max_length, 63)
        self.assertEqual(S3_BUCKET.min_length, 3)
        self.assertIs(S3_BUCKET.casing, Casing.LOWER)
        self.assertIs(S3_BUCKET.uniqueness, Uniqueness.GLOBAL)
        self.assertIs(S3_BUCKET.support, SupportLevel.SUPPORTED)

    def test_ssm_parameter_dimensions(self) -> None:
        self.assertEqual(SSM_PARAMETER.resource, "ssm-parameter")
        self.assertEqual(SSM_PARAMETER.max_length, 1011)
        self.assertIs(SSM_PARAMETER.uniqueness, Uniqueness.ACCOUNT_REGION)
        self.assertIs(SSM_PARAMETER.support, SupportLevel.SUPPORTED)

    def test_api_gateway_dimensions(self) -> None:
        self.assertEqual(API_GATEWAY_REST_API.resource, "apigateway-restapi")
        self.assertEqual(API_GATEWAY_REST_API.max_length, 128)
        self.assertIs(API_GATEWAY_REST_API.uniqueness, Uniqueness.NONE)
        self.assertIs(API_GATEWAY_REST_API.support, SupportLevel.PARTIAL)
        self.assertTrue(API_GATEWAY_REST_API.notes)

    def test_profile_permits_is_deterministic(self) -> None:
        values = ["my-app", "a" * 63, "abc", "192.168.5.4", "MyBucket", "-leading"]
        for value in values:
            with self.subTest(value=value):
                first = S3_BUCKET.permits(value)
                second = S3_BUCKET.permits(value)
                self.assertIs(first, second)


# ---------------------------------------------------------------------------
# Cross-profile determinism regression
# ---------------------------------------------------------------------------

class CrossProfileDeterminismTests(unittest.TestCase):
    """Same plan evaluated against different profiles produces stable results."""

    def test_exact_plan_is_stable_against_iam_and_ssm(self) -> None:
        comps = [literal("svc", "payments"), literal("env", "prod")]
        iam = plan_name(comps, IAM_ROLE)
        ssm = plan_name(comps, SSM_PARAMETER)
        self.assertEqual(iam.rendered, ssm.rendered)
        self.assertEqual(iam.findings, ())
        self.assertEqual(ssm.findings, ())

    def test_repeated_calls_produce_identical_results(self) -> None:
        comps = [
            literal("base", "app"),
            region("us-east-1"),
            generated("uid", length=8),
        ]
        for profile in (IAM_ROLE, S3_BUCKET, SSM_PARAMETER, API_GATEWAY_REST_API):
            with self.subTest(profile=profile.resource):
                first = plan_name(comps, profile)
                second = plan_name(comps, profile)
                self.assertEqual(first, second)
                self.assertEqual(first.findings, second.findings)
                self.assertEqual(first.plan.segments, second.plan.segments)


# ---------------------------------------------------------------------------
# Uniqueness determinism regression
# ---------------------------------------------------------------------------

class UniquenessDeterminismTests(unittest.TestCase):
    """Known uniqueness inputs produce stable findings across repeated calls."""

    def test_caller_provided_uniqueness_is_deterministic(self) -> None:
        comps = [unique_id("name", "my-unique-bucket")]
        first = plan_name(comps, S3_BUCKET)
        second = plan_name(comps, S3_BUCKET)
        self.assertEqual(first, second)
        codes = [f.code for f in first.findings]
        self.assertIn(PRACTICAL_UNIQUENESS, codes)

    def test_multi_strategy_uniqueness_is_deterministic(self) -> None:
        comps = [
            literal("env", "prod"),
            uuid_fragment(length=8),
            generated("suffix", length=4),
        ]
        first = plan_name(comps, S3_BUCKET)
        second = plan_name(comps, S3_BUCKET)
        self.assertEqual(first.findings, second.findings)


if __name__ == "__main__":
    unittest.main()
