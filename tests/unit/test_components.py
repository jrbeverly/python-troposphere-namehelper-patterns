"""Unit layer: the component and representation model.

Verifies the three source types are modelled explicitly, that a component can
expose and switch between multiple representations without any AWS logic, that
representation metadata expresses bounds / uncertainty / tradeoff, and that the
proof-of-concept families build the intended shapes. Written as
:class:`unittest.TestCase` so the baseline ``make test`` loop stays
zero-dependency.
"""

import dataclasses
import unittest

from namehelper.components import (
    Component,
    ComponentSource,
    Representation,
    RepresentationForm,
    UniquenessStrategy,
    delimiter,
    derived,
    generated,
    literal,
    region,
    stack_id,
    stack_name,
    unique_id,
    uuid_fragment,
)
from namehelper.diagnostics import Certainty


class ComponentSourceTests(unittest.TestCase):
    def test_three_explicit_source_types(self) -> None:
        members = {
            ComponentSource.LITERAL,
            ComponentSource.DERIVED,
            ComponentSource.GENERATED,
        }
        self.assertEqual(len(members), 3)

    def test_source_is_not_a_plain_string(self) -> None:
        self.assertNotIsInstance(ComponentSource.LITERAL, str)
        self.assertIsInstance(ComponentSource.LITERAL, ComponentSource)


class RepresentationMetadataTests(unittest.TestCase):
    def test_exact_form_bounds_default_to_value_length(self) -> None:
        rep = Representation(RepresentationForm.FULL, "prod")
        self.assertIs(rep.certainty, Certainty.EXACT)
        self.assertEqual(rep.length_bounds, (4, 4))
        self.assertTrue(rep.is_bounded_length)

    def test_bounded_form_uses_explicit_bounds(self) -> None:
        rep = Representation(
            RepresentationForm.BOUNDED_FRAGMENT,
            "<stack-name>",
            Certainty.BOUNDED,
            min_length=1,
            max_length=8,
        )
        self.assertEqual(rep.length_bounds, (1, 8))
        self.assertTrue(rep.is_bounded_length)

    def test_advisory_form_without_bounds_is_unbounded(self) -> None:
        rep = Representation(
            RepresentationForm.FULL,
            "<stack-id-arn>",
            Certainty.ADVISORY,
        )
        self.assertEqual(rep.length_bounds, (0, None))
        self.assertFalse(rep.is_bounded_length)

    def test_tradeoff_is_caller_visible(self) -> None:
        rep = Representation(
            RepresentationForm.SHORTENED,
            "useast1",
            Certainty.EXACT,
            tradeoff="separators removed",
        )
        self.assertEqual(rep.tradeoff, "separators removed")

    def test_representation_is_immutable(self) -> None:
        rep = Representation(RepresentationForm.FULL, "x")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rep.value = "y"  # type: ignore[misc]

    def test_negative_bound_fails_fast(self) -> None:
        with self.assertRaises(ValueError):
            Representation(
                RepresentationForm.FULL, "x", min_length=-1
            )

    def test_max_below_min_fails_fast(self) -> None:
        with self.assertRaises(ValueError):
            Representation(
                RepresentationForm.FULL,
                "x",
                Certainty.BOUNDED,
                min_length=5,
                max_length=2,
            )


class ComponentConstructionTests(unittest.TestCase):
    def test_component_records_source_and_primary(self) -> None:
        comp = Component(
            "env",
            ComponentSource.LITERAL,
            (Representation(RepresentationForm.FULL, "prod"),),
        )
        self.assertIs(comp.source, ComponentSource.LITERAL)
        self.assertEqual(comp.primary.value, "prod")
        self.assertIs(comp.certainty, Certainty.EXACT)

    def test_component_is_immutable(self) -> None:
        comp = literal("env", "prod")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            comp.role = "x"  # type: ignore[misc]

    def test_empty_representations_fail_fast(self) -> None:
        with self.assertRaises(ValueError):
            Component("env", ComponentSource.LITERAL, ())

    def test_duplicate_forms_fail_fast(self) -> None:
        with self.assertRaises(ValueError):
            Component(
                "env",
                ComponentSource.LITERAL,
                (
                    Representation(RepresentationForm.FULL, "a"),
                    Representation(RepresentationForm.FULL, "b"),
                ),
            )

    def test_certainty_tracks_primary_not_alternates(self) -> None:
        comp = Component(
            "stack",
            ComponentSource.DERIVED,
            (
                Representation(
                    RepresentationForm.FULL, "x", Certainty.BOUNDED
                ),
                Representation(
                    RepresentationForm.SHORTENED, "x", Certainty.ADVISORY
                ),
            ),
        )
        self.assertIs(comp.certainty, Certainty.BOUNDED)


class RepresentationSwitchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.comp = Component(
            "stack",
            ComponentSource.DERIVED,
            (
                Representation(RepresentationForm.FULL, "full"),
                Representation(
                    RepresentationForm.SHORTENED,
                    "fl",
                    tradeoff="loses context",
                ),
            ),
        )

    def test_primary_is_first_representation(self) -> None:
        self.assertIs(self.comp.primary, self.comp.representations[0])
        self.assertIs(self.comp.primary.form, RepresentationForm.FULL)

    def test_alternates_exclude_primary(self) -> None:
        forms = tuple(r.form for r in self.comp.alternates)
        self.assertEqual(forms, (RepresentationForm.SHORTENED,))

    def test_forms_lists_all_in_order(self) -> None:
        self.assertEqual(
            self.comp.forms,
            (RepresentationForm.FULL, RepresentationForm.SHORTENED),
        )

    def test_has_form_reports_availability(self) -> None:
        self.assertTrue(self.comp.has_form(RepresentationForm.SHORTENED))
        self.assertFalse(
            self.comp.has_form(RepresentationForm.GENERATED_UNIQUENESS)
        )

    def test_representation_lookup_by_form(self) -> None:
        rep = self.comp.representation(RepresentationForm.SHORTENED)
        self.assertEqual(rep.value, "fl")
        self.assertEqual(rep.tradeoff, "loses context")

    def test_missing_representation_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.comp.representation(RepresentationForm.BOUNDED_FRAGMENT)


class GenericFamilyTests(unittest.TestCase):
    def test_literal_is_exact_full_only(self) -> None:
        comp = literal("env", "prod")
        self.assertIs(comp.source, ComponentSource.LITERAL)
        self.assertEqual(comp.forms, (RepresentationForm.FULL,))
        self.assertIs(comp.certainty, Certainty.EXACT)

    def test_derived_defaults_to_bounded(self) -> None:
        comp = derived("ctx", "<derived>")
        self.assertIs(comp.source, ComponentSource.DERIVED)
        self.assertIs(comp.certainty, Certainty.BOUNDED)

    def test_derived_can_be_exact_with_bound(self) -> None:
        # An exact value may still declare a wider max bound; the explicit
        # bound wins over the value's own length.
        comp = derived(
            "ctx", "value", certainty=Certainty.EXACT, max_length=10
        )
        self.assertIs(comp.certainty, Certainty.EXACT)
        self.assertEqual(comp.primary.length_bounds, (5, 10))

    def test_generated_is_fixed_length_bounded(self) -> None:
        comp = generated("uid", length=6)
        self.assertIs(comp.source, ComponentSource.GENERATED)
        rep = comp.representation(RepresentationForm.GENERATED_UNIQUENESS)
        self.assertIs(rep.certainty, Certainty.BOUNDED)
        self.assertEqual(rep.length_bounds, (6, 6))

    def test_generated_rejects_non_positive_length(self) -> None:
        with self.assertRaises(ValueError):
            generated("uid", length=0)


class ProofOfConceptFamilyTests(unittest.TestCase):
    def test_stack_name_known_is_exact(self) -> None:
        comp = stack_name("my-stack")
        self.assertIs(comp.source, ComponentSource.DERIVED)
        self.assertIs(comp.certainty, Certainty.EXACT)
        self.assertEqual(comp.forms, (RepresentationForm.FULL,))

    def test_stack_name_unknown_offers_bounded_fragment(self) -> None:
        comp = stack_name(max_length=64)
        self.assertIs(comp.certainty, Certainty.BOUNDED)
        self.assertEqual(comp.primary.length_bounds, (1, 64))
        frag = comp.representation(RepresentationForm.BOUNDED_FRAGMENT)
        self.assertEqual(frag.length_bounds, (1, 8))
        self.assertTrue(frag.tradeoff)

    def test_stack_id_full_is_advisory_unbounded(self) -> None:
        comp = stack_id()
        self.assertIs(comp.certainty, Certainty.ADVISORY)
        self.assertFalse(comp.primary.is_bounded_length)
        frag = comp.representation(RepresentationForm.BOUNDED_FRAGMENT)
        self.assertIs(frag.certainty, Certainty.BOUNDED)
        self.assertEqual(frag.length_bounds, (12, 12))

    def test_stack_id_known_value_is_exact(self) -> None:
        comp = stack_id("arn:aws:cloudformation:...:stack/s/uuid")
        self.assertIs(comp.primary.certainty, Certainty.EXACT)

    def test_region_known_shortened_stays_exact(self) -> None:
        comp = region("us-east-1")
        self.assertEqual(
            comp.forms,
            (RepresentationForm.FULL, RepresentationForm.SHORTENED),
        )
        short = comp.representation(RepresentationForm.SHORTENED)
        self.assertEqual(short.value, "useast1")
        self.assertIs(short.certainty, Certainty.EXACT)
        self.assertTrue(short.tradeoff)

    def test_region_unknown_is_single_bounded_form(self) -> None:
        comp = region(max_length=20)
        self.assertEqual(comp.forms, (RepresentationForm.FULL,))
        self.assertEqual(comp.primary.length_bounds, (1, 20))
        self.assertIs(comp.certainty, Certainty.BOUNDED)

    def test_uuid_fragment_is_generated_bounded(self) -> None:
        comp = uuid_fragment(length=10)
        self.assertIs(comp.source, ComponentSource.GENERATED)
        rep = comp.primary
        self.assertIs(rep.form, RepresentationForm.GENERATED_UNIQUENESS)
        self.assertIs(rep.certainty, Certainty.BOUNDED)
        self.assertEqual(rep.length_bounds, (10, 10))

    def test_uuid_fragment_rejects_non_positive_length(self) -> None:
        with self.assertRaises(ValueError):
            uuid_fragment(length=-1)

    def test_delimiter_is_literal_exact(self) -> None:
        comp = delimiter("_")
        self.assertIs(comp.source, ComponentSource.LITERAL)
        self.assertIs(comp.certainty, Certainty.EXACT)
        self.assertEqual(comp.primary.value, "_")
        self.assertEqual(comp.primary.length_bounds, (1, 1))


class UniquenessStrategyTests(unittest.TestCase):
    """Issue #80: practical uniqueness sources are modelled explicitly."""

    def test_five_explicit_strategies(self) -> None:
        members = {
            UniquenessStrategy.NONE,
            UniquenessStrategy.CALLER_PROVIDED,
            UniquenessStrategy.STACK_DERIVED,
            UniquenessStrategy.UUID_FRAGMENT,
            UniquenessStrategy.GENERATED,
        }
        self.assertEqual(len(members), 5)
        self.assertNotIsInstance(UniquenessStrategy.NONE, str)

    def test_ordinary_components_are_not_uniqueness_sources(self) -> None:
        for comp in (
            literal("env", "prod"),
            derived("ctx", "<ctx>"),
            stack_name("s"),
            region("us-east-1"),
            delimiter("-"),
        ):
            with self.subTest(role=comp.role):
                self.assertIs(comp.strategy, UniquenessStrategy.NONE)
                self.assertFalse(comp.provides_uniqueness)

    def test_caller_provided_identifier_is_exact_but_marked(self) -> None:
        comp = unique_id("name", "my-unique-id")
        self.assertIs(comp.source, ComponentSource.LITERAL)
        self.assertIs(comp.certainty, Certainty.EXACT)
        self.assertEqual(comp.forms, (RepresentationForm.FULL,))
        self.assertIs(comp.strategy, UniquenessStrategy.CALLER_PROVIDED)
        self.assertTrue(comp.provides_uniqueness)

    def test_generated_suffix_is_a_generated_strategy(self) -> None:
        comp = generated("uid", length=6)
        self.assertIs(comp.strategy, UniquenessStrategy.GENERATED)
        self.assertTrue(comp.provides_uniqueness)

    def test_uuid_fragment_is_a_uuid_strategy(self) -> None:
        comp = uuid_fragment(length=8)
        self.assertIs(comp.strategy, UniquenessStrategy.UUID_FRAGMENT)
        self.assertTrue(comp.provides_uniqueness)

    def test_stack_id_is_a_stack_derived_strategy(self) -> None:
        # Both the deploy-time (advisory) and the known (exact) forms keep
        # the strategy: it is a property of the component, not the form.
        self.assertIs(
            stack_id().strategy, UniquenessStrategy.STACK_DERIVED
        )
        self.assertIs(
            stack_id("arn:...:stack/s/uuid").strategy,
            UniquenessStrategy.STACK_DERIVED,
        )

    def test_strategy_defaults_to_none(self) -> None:
        comp = Component(
            "x",
            ComponentSource.LITERAL,
            (Representation(RepresentationForm.FULL, "v"),),
        )
        self.assertIs(comp.strategy, UniquenessStrategy.NONE)
        self.assertFalse(comp.provides_uniqueness)


if __name__ == "__main__":
    unittest.main()
