"""Unit layer: the normalization and rendering layer.

Covers the acceptance scenarios for issue #60: style-sensitive rendering when
the profile permits it, style staying subordinate to resource rules,
deterministic profile-aware separator normalization, profile-restricted
casing sanitization, the guarantee that every self-decided material
transformation is a traceable finding (never hidden), determinism, and
plain-join parity with the planner's default path. Written as
:class:`unittest.TestCase` so the baseline ``make test`` loop stays
zero-dependency.
"""

import unittest

from namehelper.core.rendering import (
    SANITIZED_CHARACTERS,
    SEPARATOR_NORMALIZED,
    STYLE_UNSUPPORTED,
    NamingStyle,
    RenderedName,
    render,
)
from namehelper.diagnostics import Severity
from namehelper.profiles import IAM_ROLE, S3_BUCKET, ConstraintProfile
from namehelper.profiles.profile import Casing

UPPER_PROFILE = ConstraintProfile(
    resource="upper-test",
    max_length=64,
    allowed_pattern=r"[A-Z0-9-]+",
    casing=Casing.UPPER,
    separators=("-",),
)


def _codes(rendered: RenderedName) -> list[str]:
    return [f.code for f in rendered.findings]


def _segs(*values: str) -> list[tuple[str, str]]:
    return [(f"r{i}", v) for i, v in enumerate(values)]


class DefaultParityTests(unittest.TestCase):
    """No style, no sanitize, clean separators -> plain join, no findings."""

    def test_plain_join_matches_separator_join_with_no_findings(self) -> None:
        result = render(
            _segs("payments", "prod"),
            separator="-",
            profile=IAM_ROLE,
        )
        self.assertEqual(result.value, "payments-prod")
        self.assertEqual(result.findings, ())

    def test_single_segment_is_unchanged(self) -> None:
        result = render(_segs("solo"), separator="-", profile=IAM_ROLE)
        self.assertEqual(result.value, "solo")
        self.assertEqual(result.findings, ())


class StyleRenderingTests(unittest.TestCase):
    """Supported styles render when the selected profile permits them."""

    def test_kebab_lowercases_and_joins_with_hyphen(self) -> None:
        result = render(
            _segs("My", "Cool", "Svc"),
            separator="_",
            profile=IAM_ROLE,
            style=NamingStyle.KEBAB,
        )
        self.assertEqual(result.value, "my-cool-svc")

    def test_snake_lowercases_and_joins_with_underscore(self) -> None:
        result = render(
            _segs("My", "Svc"),
            separator="-",
            profile=IAM_ROLE,
            style=NamingStyle.SNAKE,
        )
        self.assertEqual(result.value, "my_svc")

    def test_camel_case_has_lower_head_and_capitalized_tail(self) -> None:
        result = render(
            _segs("MY", "cool", "svc"),
            separator="-",
            profile=IAM_ROLE,
            style=NamingStyle.CAMEL,
        )
        self.assertEqual(result.value, "myCoolSvc")

    def test_pascal_case_capitalizes_every_segment(self) -> None:
        result = render(
            _segs("my", "cool", "svc"),
            separator="-",
            profile=IAM_ROLE,
            style=NamingStyle.PASCAL,
        )
        self.assertEqual(result.value, "MyCoolSvc")

    def test_requested_compatible_style_is_not_a_hidden_transform(
        self,
    ) -> None:
        # An explicitly requested, profile-compatible style is the caller's
        # deliberate choice (like choosing a representation): applying it is
        # not a self-decided transformation, so it emits no finding.
        result = render(
            _segs("My", "Bucket"),
            separator="-",
            profile=S3_BUCKET,
            style=NamingStyle.KEBAB,
        )
        self.assertEqual(result.value, "my-bucket")
        self.assertEqual(result.findings, ())


class StyleSubordinateToResourceRulesTests(unittest.TestCase):
    """A style is declined (never forced) when the profile forbids it."""

    def test_snake_declined_when_profile_lacks_underscore_separator(
        self,
    ) -> None:
        result = render(
            _segs("a", "b"),
            separator="-",
            profile=S3_BUCKET,
            style=NamingStyle.SNAKE,
        )
        self.assertIn(STYLE_UNSUPPORTED, _codes(result))
        self.assertIs(result.findings[0].severity, Severity.WARNING)
        # Falls back to the plain separator join, never an invalid format.
        self.assertEqual(result.value, "a-b")

    def test_camel_declined_under_lowercase_only_profile(self) -> None:
        result = render(
            _segs("My", "Bucket"),
            separator="-",
            profile=S3_BUCKET,
            style=NamingStyle.CAMEL,
        )
        self.assertIn(STYLE_UNSUPPORTED, _codes(result))
        # The layer does not silently "fix" casing either: it declines the
        # style and leaves the plain join for the planner to validate.
        self.assertEqual(result.value, "My-Bucket")

    def test_kebab_declined_under_uppercase_only_profile(self) -> None:
        result = render(
            _segs("AB", "CD"),
            separator="-",
            profile=UPPER_PROFILE,
            style=NamingStyle.KEBAB,
        )
        self.assertIn(STYLE_UNSUPPORTED, _codes(result))
        self.assertEqual(result.value, "AB-CD")


class SeparatorNormalizationTests(unittest.TestCase):
    """Profile-aware, deterministic separator collapsing/trimming."""

    def test_interior_run_is_collapsed_with_a_finding(self) -> None:
        result = render(
            _segs("x", "", "y"),
            separator="-",
            profile=IAM_ROLE,
        )
        self.assertEqual(result.value, "x-y")
        self.assertEqual(_codes(result), [SEPARATOR_NORMALIZED])
        self.assertIs(result.findings[0].severity, Severity.WARNING)

    def test_leading_and_trailing_separators_are_trimmed(self) -> None:
        result = render(
            _segs("", "y", ""),
            separator="-",
            profile=IAM_ROLE,
        )
        self.assertEqual(result.value, "y")
        self.assertEqual(_codes(result), [SEPARATOR_NORMALIZED])

    def test_clean_join_is_not_normalized(self) -> None:
        result = render(
            _segs("x", "y"),
            separator="-",
            profile=IAM_ROLE,
        )
        self.assertEqual(result.value, "x-y")
        self.assertEqual(result.findings, ())

    def test_value_internal_separator_is_preserved(self) -> None:
        # A single separator that lives *inside* a segment value is not a run
        # and must survive normalization unchanged.
        result = render(
            _segs("a", "us-east-1"),
            separator="-",
            profile=IAM_ROLE,
        )
        self.assertEqual(result.value, "a-us-east-1")
        self.assertEqual(result.findings, ())

    def test_unrecognized_separator_is_left_to_the_planner(self) -> None:
        # '.' is not an IAM separator: normalization stays out of the way so
        # it never competes with the planner's separator validation.
        result = render(
            _segs("x", "", "y"),
            separator=".",
            profile=IAM_ROLE,
        )
        self.assertEqual(result.value, "x..y")
        self.assertEqual(result.findings, ())


class SanitizationTests(unittest.TestCase):
    """Casing sanitization only, gated on the profile's own rule."""

    def test_lowercase_profile_sanitizes_with_a_traceable_finding(
        self,
    ) -> None:
        result = render(
            _segs("My", "Bucket"),
            separator="-",
            profile=S3_BUCKET,
            sanitize=True,
        )
        self.assertEqual(result.value, "my-bucket")
        self.assertEqual(_codes(result), [SANITIZED_CHARACTERS])
        self.assertIs(result.findings[0].severity, Severity.WARNING)

    def test_uppercase_profile_sanitizes_upward(self) -> None:
        result = render(
            _segs("ab", "cd"),
            separator="-",
            profile=UPPER_PROFILE,
            sanitize=True,
        )
        self.assertEqual(result.value, "AB-CD")
        self.assertEqual(_codes(result), [SANITIZED_CHARACTERS])

    def test_no_finding_when_casing_already_satisfies_the_rule(self) -> None:
        result = render(
            _segs("my", "bucket"),
            separator="-",
            profile=S3_BUCKET,
            sanitize=True,
        )
        self.assertEqual(result.value, "my-bucket")
        self.assertEqual(result.findings, ())

    def test_any_casing_profile_is_never_sanitized(self) -> None:
        result = render(
            _segs("My", "Svc"),
            separator="-",
            profile=IAM_ROLE,
            sanitize=True,
        )
        self.assertEqual(result.value, "My-Svc")
        self.assertEqual(result.findings, ())

    def test_sanitize_off_never_changes_casing(self) -> None:
        result = render(
            _segs("My", "Bucket"),
            separator="-",
            profile=S3_BUCKET,
        )
        self.assertEqual(result.value, "My-Bucket")
        self.assertEqual(result.findings, ())


class LossyTransformsAreNeverHiddenTests(unittest.TestCase):
    """Every self-decided material change is reported, in stable order."""

    def test_normalization_then_sanitization_both_surface(self) -> None:
        result = render(
            _segs("My", ""),
            separator="-",
            profile=S3_BUCKET,
            sanitize=True,
        )
        self.assertEqual(result.value, "my")
        self.assertEqual(
            _codes(result),
            [SEPARATOR_NORMALIZED, SANITIZED_CHARACTERS],
        )

    def test_every_self_decided_decision_is_traceable(self) -> None:
        # Each case is a decision the layer made on its own (normalize a
        # separator run, sanitize casing, decline an incompatible style); all
        # three must surface a finding rather than change behaviour silently.
        cases = {
            SEPARATOR_NORMALIZED: render(
                _segs("x", "", "y"), separator="-", profile=IAM_ROLE
            ),
            SANITIZED_CHARACTERS: render(
                _segs("My", "B"),
                separator="-",
                profile=S3_BUCKET,
                sanitize=True,
            ),
            STYLE_UNSUPPORTED: render(
                _segs("a", "b"),
                separator="-",
                profile=S3_BUCKET,
                style=NamingStyle.SNAKE,
            ),
        }
        for code, shaped in cases.items():
            with self.subTest(code=code):
                self.assertTrue(
                    shaped.findings,
                    "a self-decided rendering change must be traceable",
                )
                self.assertIn(code, _codes(shaped))


class DeterminismTests(unittest.TestCase):
    def test_same_inputs_produce_identical_rendered_name(self) -> None:
        args = dict(
            separator="-",
            profile=S3_BUCKET,
            style=NamingStyle.SNAKE,
            sanitize=True,
        )
        first = render(_segs("My", "", "Bucket"), **args)
        second = render(_segs("My", "", "Bucket"), **args)
        self.assertEqual(first, second)
        self.assertEqual(first.findings, second.findings)


if __name__ == "__main__":
    unittest.main()
