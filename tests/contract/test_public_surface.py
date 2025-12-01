"""Contract layer: pin the public surface and architectural boundaries.

This encodes the contract downstream issues must preserve: the public import
root exposes exactly the documented names, and every architectural seam from
HLD "Repository and Module Shape" remains importable. Breaking a boundary
should fail here rather than be discovered later.
"""

import importlib
import unittest

EXPECTED_PUBLIC_SURFACE = {"NameHelper", "__version__"}

SEAM_MODULES = (
    "namehelper.api",
    "namehelper.core",
    "namehelper.components",
    "namehelper.profiles",
    "namehelper.adapters",
    "namehelper.diagnostics",
)


class PublicSurfaceContractTests(unittest.TestCase):
    def test_root_all_matches_documented_surface(self) -> None:
        import namehelper

        self.assertEqual(set(namehelper.__all__), EXPECTED_PUBLIC_SURFACE)

    def test_all_architectural_seams_present(self) -> None:
        for name in SEAM_MODULES:
            with self.subTest(module=name):
                self.assertIsNotNone(importlib.import_module(name))


if __name__ == "__main__":
    unittest.main()
