"""Unit layer: finding type semantics and immutability."""

import dataclasses
import unittest

from namehelper.diagnostics import Certainty, Finding, Severity


class FindingTests(unittest.TestCase):
    def test_severity_levels_are_distinct(self) -> None:
        members = {Severity.VIOLATION, Severity.WARNING, Severity.SUGGESTION}
        self.assertEqual(len(members), 3)

    def test_finding_carries_code_message_and_severity(self) -> None:
        f = Finding(
            code="over_budget",
            message="name exceeds the profile length ceiling",
            severity=Severity.VIOLATION,
        )
        self.assertEqual(f.code, "over_budget")
        self.assertEqual(f.message, "name exceeds the profile length ceiling")
        self.assertIs(f.severity, Severity.VIOLATION)

    def test_optional_context_defaults_to_none(self) -> None:
        f = Finding(code="c", message="m", severity=Severity.WARNING)
        self.assertIsNone(f.certainty)
        self.assertIsNone(f.component)

    def test_finding_can_record_certainty_and_component(self) -> None:
        f = Finding(
            code="bounded_risk",
            message="value may not fit under its declared bound",
            severity=Severity.WARNING,
            certainty=Certainty.BOUNDED,
            component="uniqueness",
        )
        self.assertIs(f.certainty, Certainty.BOUNDED)
        self.assertEqual(f.component, "uniqueness")

    def test_finding_is_immutable(self) -> None:
        f = Finding(code="c", message="m", severity=Severity.SUGGESTION)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            f.code = "other"  # type: ignore[misc]

    def test_findings_with_same_fields_are_equal(self) -> None:
        a = Finding(code="c", message="m", severity=Severity.VIOLATION)
        b = Finding(code="c", message="m", severity=Severity.VIOLATION)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
