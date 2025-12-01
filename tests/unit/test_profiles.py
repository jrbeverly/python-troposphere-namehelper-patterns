"""Unit layer: constraint profile abstraction and the encoded PoC rules.

Verifies the profile abstraction can express every required dimension, that
its ``permits`` predicate enforces the encoded envelope deterministically, and
that each curated proof-of-concept profile encodes the intended AWS rules.
"""

import unittest

from namehelper.diagnostics import Certainty
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


class ProfileAbstractionTests(unittest.TestCase):
    def test_expresses_all_required_dimensions(self) -> None:
        p = ConstraintProfile(
            resource="example",
            max_length=10,
            allowed_pattern=r"[a-z]+",
        )
        self.assertEqual(p.max_length, 10)
        self.assertEqual(p.min_length, 1)
        self.assertEqual(p.allowed_pattern, r"[a-z]+")
        self.assertIsNone(p.forbidden_pattern)
        self.assertIs(p.casing, Casing.ANY)
        self.assertEqual(p.separators, ("-",))
        self.assertIs(p.uniqueness, Uniqueness.NONE)
        self.assertIs(p.max_validation_certainty, Certainty.EXACT)
        self.assertIs(p.support, SupportLevel.SUPPORTED)

    def test_profile_is_immutable(self) -> None:
        p = ConstraintProfile(
            resource="example", max_length=5, allowed_pattern=r"[a-z]+"
        )
        with self.assertRaises(Exception):
            p.max_length = 6  # type: ignore[misc]

    def test_invalid_length_bounds_fail_fast(self) -> None:
        with self.assertRaises(ValueError):
            ConstraintProfile(
                resource="bad",
                max_length=2,
                min_length=5,
                allowed_pattern=r"[a-z]+",
            )

    def test_bad_pattern_fails_fast(self) -> None:
        with self.assertRaises(Exception):
            ConstraintProfile(
                resource="bad", max_length=5, allowed_pattern=r"[a-z"
            )

    def test_permits_enforces_length(self) -> None:
        p = ConstraintProfile(
            resource="ex",
            max_length=4,
            min_length=2,
            allowed_pattern=r"[a-z]+",
        )
        self.assertFalse(p.permits("a"))
        self.assertTrue(p.permits("ab"))
        self.assertTrue(p.permits("abcd"))
        self.assertFalse(p.permits("abcde"))

    def test_permits_enforces_allowed_pattern(self) -> None:
        p = ConstraintProfile(
            resource="ex", max_length=10, allowed_pattern=r"[a-z]+"
        )
        self.assertTrue(p.permits("abc"))
        self.assertFalse(p.permits("abc1"))

    def test_permits_enforces_forbidden_pattern(self) -> None:
        p = ConstraintProfile(
            resource="ex",
            max_length=10,
            allowed_pattern=r"[a-z]+",
            forbidden_pattern=r"\Axyz",
        )
        self.assertFalse(p.permits("xyzabc"))
        self.assertTrue(p.permits("abcxyz"))

    def test_permits_enforces_casing(self) -> None:
        lower = ConstraintProfile(
            resource="ex",
            max_length=10,
            allowed_pattern=r"[A-Za-z]+",
            casing=Casing.LOWER,
        )
        self.assertTrue(lower.permits("abc"))
        self.assertFalse(lower.permits("Abc"))


class SsmParameterProfileTests(unittest.TestCase):
    def test_encoded_rules(self) -> None:
        self.assertEqual(SSM_PARAMETER.resource, "ssm-parameter")
        self.assertEqual(SSM_PARAMETER.max_length, 1011)
        self.assertIs(SSM_PARAMETER.uniqueness, Uniqueness.ACCOUNT_REGION)
        self.assertIs(SSM_PARAMETER.support, SupportLevel.SUPPORTED)

    def test_accepts_hierarchical_name(self) -> None:
        self.assertTrue(SSM_PARAMETER.permits("/app/prod/db-password"))
        self.assertTrue(SSM_PARAMETER.permits("simple_name"))

    def test_rejects_empty_path_segments(self) -> None:
        self.assertFalse(SSM_PARAMETER.permits("/app//db"))
        self.assertFalse(SSM_PARAMETER.permits("/app/"))

    def test_rejects_reserved_prefixes(self) -> None:
        self.assertFalse(SSM_PARAMETER.permits("aws-secret"))
        self.assertFalse(SSM_PARAMETER.permits("/SSM/thing"))


class IamRoleProfileTests(unittest.TestCase):
    def test_encoded_rules(self) -> None:
        self.assertEqual(IAM_ROLE.resource, "iam-role")
        self.assertEqual(IAM_ROLE.max_length, 64)
        self.assertIs(IAM_ROLE.uniqueness, Uniqueness.ACCOUNT)
        self.assertIs(IAM_ROLE.casing, Casing.ANY)

    def test_accepts_typical_role_names(self) -> None:
        self.assertTrue(IAM_ROLE.permits("MyApp-prod_Role+test=1,2.3@x"))
        self.assertTrue(IAM_ROLE.permits("Service"))

    def test_rejects_too_long_and_bad_chars(self) -> None:
        self.assertFalse(IAM_ROLE.permits("a" * 65))
        self.assertFalse(IAM_ROLE.permits("bad/slash"))


class S3BucketProfileTests(unittest.TestCase):
    def test_encoded_rules(self) -> None:
        self.assertEqual(S3_BUCKET.resource, "s3-bucket")
        self.assertEqual(S3_BUCKET.max_length, 63)
        self.assertEqual(S3_BUCKET.min_length, 3)
        self.assertIs(S3_BUCKET.casing, Casing.LOWER)
        self.assertIs(S3_BUCKET.uniqueness, Uniqueness.GLOBAL)

    def test_accepts_valid_bucket(self) -> None:
        self.assertTrue(S3_BUCKET.permits("my-app-prod-bucket"))
        self.assertTrue(S3_BUCKET.permits("a1b"))

    def test_rejects_uppercase_and_edges(self) -> None:
        self.assertFalse(S3_BUCKET.permits("My-Bucket"))
        self.assertFalse(S3_BUCKET.permits("-leading"))
        self.assertFalse(S3_BUCKET.permits("trailing-"))
        self.assertFalse(S3_BUCKET.permits("ab"))

    def test_rejects_ip_shaped_name(self) -> None:
        self.assertFalse(S3_BUCKET.permits("192.168.5.4"))


class ApiGatewayProfileTests(unittest.TestCase):
    def test_partial_support_is_explicit(self) -> None:
        self.assertEqual(API_GATEWAY_REST_API.resource, "apigateway-restapi")
        self.assertEqual(API_GATEWAY_REST_API.max_length, 128)
        self.assertIs(API_GATEWAY_REST_API.support, SupportLevel.PARTIAL)
        self.assertIs(API_GATEWAY_REST_API.uniqueness, Uniqueness.NONE)
        self.assertTrue(API_GATEWAY_REST_API.notes)

    def test_accepts_display_name(self) -> None:
        self.assertTrue(API_GATEWAY_REST_API.permits("My Public API v2"))

    def test_rejects_over_length_and_control_chars(self) -> None:
        self.assertFalse(API_GATEWAY_REST_API.permits("x" * 129))
        self.assertFalse(API_GATEWAY_REST_API.permits("bad\tname"))


if __name__ == "__main__":
    unittest.main()
