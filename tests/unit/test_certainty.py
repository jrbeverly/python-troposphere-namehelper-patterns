"""Unit layer: certainty model semantics and invariants.

Verifies the knowledge model stays a closed three-valued enum (not a boolean
or free-form string) and that ``weakest`` combines compositions correctly.
"""

import unittest

from namehelper.diagnostics import Certainty


class CertaintyTests(unittest.TestCase):
    def test_three_distinct_levels(self) -> None:
        members = {Certainty.EXACT, Certainty.BOUNDED, Certainty.ADVISORY}
        self.assertEqual(len(members), 3)

    def test_levels_are_not_booleans_or_plain_strings(self) -> None:
        self.assertNotIsInstance(Certainty.EXACT, bool)
        self.assertNotIsInstance(Certainty.EXACT, str)
        self.assertIsInstance(Certainty.EXACT, Certainty)

    def test_weakest_of_empty_is_exact(self) -> None:
        self.assertIs(Certainty.weakest(), Certainty.EXACT)

    def test_weakest_all_exact_stays_exact(self) -> None:
        self.assertIs(
            Certainty.weakest(Certainty.EXACT, Certainty.EXACT),
            Certainty.EXACT,
        )

    def test_any_bounded_makes_composition_bounded(self) -> None:
        self.assertIs(
            Certainty.weakest(Certainty.EXACT, Certainty.BOUNDED),
            Certainty.BOUNDED,
        )

    def test_any_advisory_dominates(self) -> None:
        self.assertIs(
            Certainty.weakest(
                Certainty.EXACT, Certainty.BOUNDED, Certainty.ADVISORY
            ),
            Certainty.ADVISORY,
        )

    def test_weakest_is_order_independent(self) -> None:
        self.assertIs(
            Certainty.weakest(Certainty.ADVISORY, Certainty.EXACT),
            Certainty.weakest(Certainty.EXACT, Certainty.ADVISORY),
        )


if __name__ == "__main__":
    unittest.main()
