"""Unit layer: result object carries output, plan, and findings."""

import dataclasses
import unittest

from namehelper.core import NamePlan, NameResult, PlanSegment
from namehelper.diagnostics import Certainty, Finding, Severity


class NameResultTests(unittest.TestCase):
    def test_result_carries_rendered_plan_and_findings(self) -> None:
        plan = NamePlan(segments=(PlanSegment("env", "prod"),))
        finding = Finding(
            code="suggest_short",
            message="a shorter representation is available",
            severity=Severity.SUGGESTION,
        )
        result = NameResult(
            plan=plan,
            rendered="prod",
            findings=(finding,),
        )
        self.assertEqual(result.rendered, "prod")
        self.assertIs(result.plan, plan)
        self.assertEqual(result.findings, (finding,))
        self.assertTrue(result.has_findings)

    def test_rendered_defaults_to_none_for_unresolved(self) -> None:
        result = NameResult(plan=NamePlan())
        self.assertIsNone(result.rendered)
        self.assertFalse(result.has_findings)

    def test_certainty_is_derived_from_plan(self) -> None:
        plan = NamePlan(
            segments=(
                PlanSegment("env", "prod", Certainty.EXACT),
                PlanSegment("uid", "x", Certainty.BOUNDED),
            )
        )
        result = NameResult(plan=plan, rendered="prod-x")
        self.assertIs(result.certainty, Certainty.BOUNDED)

    def test_result_is_immutable(self) -> None:
        result = NameResult(plan=NamePlan())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.rendered = "x"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
