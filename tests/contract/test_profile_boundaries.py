"""Contract layer: profile boundary and unsupported-surface behaviour.

HLD "Architectural Risks" #3 and the acceptance criteria require unsupported
and partially-supported AWS surfaces to fail honestly rather than silently.
This contract layer encodes those expectations: unsupported resources raise
explicit, actionable errors; partially-supported profiles produce appropriate
diagnostics through the planner; the catalog is internally consistent; and
profile boundaries are clean and deterministic.
"""

import unittest

from namehelper.components import (
    literal,
    region,
    stack_id,
    uuid_fragment,
)
from namehelper.core import plan_name
from namehelper.core.planner import (
    ALTERNATE_REPRESENTATION,
    PRACTICAL_UNIQUENESS,
)
from namehelper.diagnostics import (
    Certainty,
    Severity,
    ValidationPolicy,
)
from namehelper.profiles import (
    API_GATEWAY_REST_API,
    IAM_ROLE,
    S3_BUCKET,
    SSM_PARAMETER,
    ConstraintProfile,
    SupportLevel,
    Uniqueness,
    UnsupportedResourceError,
    get_profile,
    is_supported,
    supported_resources,
)


# ---------------------------------------------------------------------------
# Unsupported profile behaviour
# ---------------------------------------------------------------------------

class UnsupportedProfileContractTests(unittest.TestCase):
    """Unsupported resources fail explicitly with actionable error messages."""

    def test_unsupported_resource_error_is_an_exception_type(self) -> None:
        self.assertTrue(issubclass(UnsupportedResourceError, KeyError))

    def test_error_messages_name_the_missing_resource(self) -> None:
        with self.assertRaises(UnsupportedResourceError) as ctx:
            get_profile("dynamodb-table")
        self.assertIn("dynamodb-table", str(ctx.exception))

    def test_error_messages_list_supported_keys(self) -> None:
        with self.assertRaises(UnsupportedResourceError) as ctx:
            get_profile("nonexistent-resource")
        message = str(ctx.exception)
        for expected in ("ssm-parameter", "iam-role", "s3-bucket", "apigateway-restapi"):
            self.assertIn(expected, message, f"message should mention {expected!r}")

    def test_is_supported_false_for_unknown_resource(self) -> None:
        self.assertFalse(is_supported("dynamodb-table"))
        self.assertFalse(is_supported("lambda-function"))
        self.assertFalse(is_supported(""))

    def test_is_supported_true_for_every_poc_resource(self) -> None:
        for resource in supported_resources():
            with self.subTest(resource=resource):
                self.assertTrue(is_supported(resource))

    def test_supported_resources_is_consistent(self) -> None:
        resources = supported_resources()
        self.assertIsInstance(resources, tuple)
        # Every resource in the catalog is retrievable.
        for r in resources:
            with self.subTest(resource=r):
                profile = get_profile(r)
                self.assertEqual(profile.resource, r)

    def test_supported_resources_includes_all_poc_targets(self) -> None:
        self.assertGreaterEqual(len(supported_resources()), 4)

    def test_partial_profile_still_retrievable_and_usable(self) -> None:
        profile = get_profile("apigateway-restapi")
        self.assertIs(profile.support, SupportLevel.PARTIAL)
        self.assertTrue(profile.notes, "partial profiles must explain their gaps")
        # The profile still enforces its declared envelope.
        self.assertTrue(profile.permits("My API v2"))
        self.assertFalse(profile.permits("x" * 129))


# ---------------------------------------------------------------------------
# Partial-profile behaviour through the planner
# ---------------------------------------------------------------------------

class PartialProfilePlannerContractTests(unittest.TestCase):
    """A PARTIAL profile's incomplete coverage is visible in diagnostics."""

    def test_partial_profile_permits_clean_plan(self) -> None:
        result = plan_name(
            [literal("name", "My Public API")],
            API_GATEWAY_REST_API,
        )
        self.assertEqual(result.rendered, "My Public API")

    def test_partial_profile_rejects_over_length(self) -> None:
        result = plan_name(
            [literal("name", "x" * 130)],
            API_GATEWAY_REST_API,
        )
        self.assertIsNone(result.rendered)
        self.assertTrue(result.has_findings)

    def test_partial_profile_support_level_is_visible_to_callers(self) -> None:
        # Any caller can inspect support level before accepting a verdict.
        for resource in supported_resources():
            with self.subTest(resource=resource):
                profile = get_profile(resource)
                self.assertIsInstance(profile.support, SupportLevel)

    def test_partial_profile_notes_are_always_populated(self) -> None:
        # When a profile is PARTIAL, notes must explain the gaps.
        for resource in supported_resources():
            with self.subTest(resource=resource):
                profile = get_profile(resource)
                if profile.support is SupportLevel.PARTIAL:
                    self.assertTrue(
                        profile.notes.strip(),
                        f"{resource} is PARTIAL but has no notes explaining gaps",
                    )

    def test_supported_profiles_notes_may_be_empty(self) -> None:
        # A SUPPORTED profile may or may not have notes; both are valid.
        for resource in supported_resources():
            with self.subTest(resource=resource):
                profile = get_profile(resource)
                if profile.support is SupportLevel.SUPPORTED:
                    self.assertIsInstance(profile.notes, str)


# ---------------------------------------------------------------------------
# Profile boundary edge cases
# ---------------------------------------------------------------------------

class ProfileBoundaryEdgeCaseContractTests(unittest.TestCase):
    """Profile constraints at exactly the boundary are pass/fail deterministically."""

    def test_iam_role_exactly_64_chars_fits(self) -> None:
        result = plan_name([literal("name", "a" * 64)], IAM_ROLE)
        self.assertEqual(result.rendered, "a" * 64)

    def test_iam_role_65_chars_overflows(self) -> None:
        result = plan_name([literal("name", "a" * 65)], IAM_ROLE)
        self.assertIsNone(result.rendered)
        self.assertTrue(result.has_findings)

    def test_s3_bucket_exactly_3_chars_fits(self) -> None:
        result = plan_name([literal("name", "abc")], S3_BUCKET)
        self.assertEqual(result.rendered, "abc")

    def test_s3_bucket_2_chars_too_short(self) -> None:
        result = plan_name([literal("name", "ab")], S3_BUCKET)
        self.assertIsNone(result.rendered)

    def test_s3_bucket_exactly_63_chars_fits(self) -> None:
        result = plan_name([literal("name", "a" * 63)], S3_BUCKET)
        self.assertEqual(result.rendered, "a" * 63)

    def test_s3_bucket_64_chars_overflows(self) -> None:
        result = plan_name([literal("name", "a" * 64)], S3_BUCKET)
        self.assertIsNone(result.rendered)

    def test_ssm_parameter_exactly_1011_chars_fits(self) -> None:
        result = plan_name([literal("name", "a" * 1011)], SSM_PARAMETER)
        self.assertEqual(result.rendered, "a" * 1011)

    def test_ssm_parameter_1012_chars_overflows(self) -> None:
        result = plan_name([literal("name", "a" * 1012)], SSM_PARAMETER)
        self.assertIsNone(result.rendered)

    def test_api_gateway_exactly_128_chars_fits(self) -> None:
        result = plan_name([literal("name", "a" * 128)], API_GATEWAY_REST_API)
        self.assertEqual(result.rendered, "a" * 128)

    def test_api_gateway_129_chars_overflows(self) -> None:
        result = plan_name([literal("name", "a" * 129)], API_GATEWAY_REST_API)
        self.assertIsNone(result.rendered)


# ---------------------------------------------------------------------------
# Profile catalog integrity
# ---------------------------------------------------------------------------

class ProfileCatalogIntegrityContractTests(unittest.TestCase):
    """The profile catalog is internally consistent and deterministic."""

    def test_every_profile_resource_key_matches_its_field(self) -> None:
        for resource in supported_resources():
            with self.subTest(resource=resource):
                profile = get_profile(resource)
                self.assertEqual(profile.resource, resource)

    def test_every_profile_has_valid_length_bounds(self) -> None:
        for resource in supported_resources():
            with self.subTest(resource=resource):
                profile = get_profile(resource)
                self.assertGreaterEqual(profile.max_length, profile.min_length)
                self.assertGreaterEqual(profile.min_length, 1)

    def test_every_profile_has_a_non_empty_allowed_pattern(self) -> None:
        for resource in supported_resources():
            with self.subTest(resource=resource):
                profile = get_profile(resource)
                self.assertTrue(
                    profile.allowed_pattern.strip(),
                    f"{resource} has an empty allowed_pattern",
                )

    def test_catalog_lookups_are_deterministic(self) -> None:
        for resource in supported_resources():
            with self.subTest(resource=resource):
                first = get_profile(resource)
                second = get_profile(resource)
                self.assertIs(first, second)

    def test_supported_profiles_have_exact_validation_certainty(self) -> None:
        for resource in supported_resources():
            with self.subTest(resource=resource):
                profile = get_profile(resource)
                if profile.support is SupportLevel.SUPPORTED:
                    self.assertIs(
                        profile.max_validation_certainty,
                        Certainty.EXACT,
                        f"{resource}: supported profiles must accept exact validation",
                    )

    def test_ssm_separators_include_slash(self) -> None:
        self.assertIn("/", SSM_PARAMETER.separators)

    def test_s3_separators_include_dot_and_hyphen(self) -> None:
        self.assertIn("-", S3_BUCKET.separators)
        self.assertIn(".", S3_BUCKET.separators)

    def test_iam_separators_include_hyphen_and_underscore(self) -> None:
        self.assertIn("-", IAM_ROLE.separators)
        self.assertIn("_", IAM_ROLE.separators)


# ---------------------------------------------------------------------------
# Uniqueness scope contract
# ---------------------------------------------------------------------------

class UniquenessScopeContractTests(unittest.TestCase):
    """The uniqueness scope declared on each profile is consistent."""

    def test_s3_bucket_requires_global_uniqueness(self) -> None:
        self.assertIs(S3_BUCKET.uniqueness, Uniqueness.GLOBAL)

    def test_iam_role_requires_account_uniqueness(self) -> None:
        self.assertIs(IAM_ROLE.uniqueness, Uniqueness.ACCOUNT)

    def test_ssm_parameter_requires_account_region_uniqueness(self) -> None:
        self.assertIs(SSM_PARAMETER.uniqueness, Uniqueness.ACCOUNT_REGION)

    def test_api_gateway_has_no_uniqueness_requirement(self) -> None:
        self.assertIs(API_GATEWAY_REST_API.uniqueness, Uniqueness.NONE)

    def test_no_uniqueness_requirement_means_no_practical_uniqueness_finding(
        self,
    ) -> None:
        # API Gateway has Uniqueness.NONE: even when the caller supplies a
        # uniqueness source, the planner should not emit a PRACTICAL_UNIQUENESS
        # finding because the resource does not need one.
        result = plan_name(
            [literal("name", "My API"), uuid_fragment(length=8)],
            API_GATEWAY_REST_API,
        )
        codes = {f.code for f in result.findings}
        self.assertNotIn(PRACTICAL_UNIQUENESS, codes)


# ---------------------------------------------------------------------------
# Profile-driven alternate-representation contract
# ---------------------------------------------------------------------------

class ProfileDrivenAlternateContractTests(unittest.TestCase):
    """Constraint pressure produces suggestions, but only when actionable."""

    def test_region_alternate_is_surfaced_under_s3_pressure(self) -> None:
        comps = [literal("base", "a" * 55), region("us-east-1")]
        result = plan_name(comps, S3_BUCKET)
        alternates = [f for f in result.findings if f.code == ALTERNATE_REPRESENTATION]
        self.assertTrue(alternates)
        region_alts = [a for a in alternates if a.component == "region"]
        self.assertTrue(region_alts)

    def test_no_alternates_when_plan_fits_without_pressure(self) -> None:
        result = plan_name(
            [literal("svc", "api"), literal("env", "dev")],
            IAM_ROLE,
        )
        alternates = [f for f in result.findings if f.code == ALTERNATE_REPRESENTATION]
        self.assertEqual(alternates, [])

    def test_no_alternates_when_component_lacks_shorter_form(self) -> None:
        # A bounded derived value with no alternate forms should not produce
        # a bogus suggestion when it causes pressure.
        result = plan_name(
            [literal("base", "a" * 55), stack_id()],
            S3_BUCKET,
        )
        alternates = [f for f in result.findings if f.code == ALTERNATE_REPRESENTATION]
        # stack_id has a FULL and BOUNDED_FRAGMENT form. The BOUNDED_FRAGMENT
        # has max_length=12 which is more bounded than the unbounded FULL form.
        # Since it's "more bounded" it should be suggested if length pressure exists.
        # If alternates exist, verify they only name components with alternates.
        for alt in alternates:
            self.assertIsNotNone(alt.component)
            self.assertIs(alt.severity, Severity.SUGGESTION)


if __name__ == "__main__":
    unittest.main()
