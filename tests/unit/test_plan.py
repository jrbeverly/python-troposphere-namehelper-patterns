"""Unit layer: structured plan composition and certainty derivation."""

import dataclasses
import unittest

from namehelper.core import NamePlan, PlanSegment
from namehelper.diagnostics import Certainty


class PlanSegmentTests(unittest.TestCase):
    def test_segment_defaults_to_exact(self) -> None:
        seg = PlanSegment(role="env", value="prod")
        self.assertIs(seg.certainty, Certainty.EXACT)

    def test_segment_is_immutable(self) -> None:
        seg = PlanSegment(role="env", value="prod")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            seg.value = "dev"  # type: ignore[misc]


class NamePlanTests(unittest.TestCase):
    def test_empty_plan_is_exact(self) -> None:
        self.assertIs(NamePlan().certainty, Certainty.EXACT)

    def test_roles_preserve_composition_order(self) -> None:
        plan = NamePlan(
            segments=(
                PlanSegment("env", "prod"),
                PlanSegment("service", "api"),
                PlanSegment("uid", "ab12"),
            )
        )
        self.assertEqual(plan.roles, ("env", "service", "uid"))

    def test_plan_certainty_is_weakest_segment(self) -> None:
        plan = NamePlan(
            segments=(
                PlanSegment("env", "prod", Certainty.EXACT),
                PlanSegment("stack", "x", Certainty.BOUNDED),
                PlanSegment("uid", "y", Certainty.ADVISORY),
            )
        )
        self.assertIs(plan.certainty, Certainty.ADVISORY)

    def test_all_exact_segments_keep_plan_exact(self) -> None:
        plan = NamePlan(
            segments=(
                PlanSegment("env", "prod"),
                PlanSegment("service", "api"),
            )
        )
        self.assertIs(plan.certainty, Certainty.EXACT)

    def test_plan_is_immutable(self) -> None:
        plan = NamePlan()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            plan.separator = "_"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
