"""Unit layer: verify the package skeleton and module boundaries exist.

These tests exist so later issues land into a stable structure. They assert
the architectural seams from HLD "Repository and Module Shape" are importable
and that the public entrypoint is reachable.

Written as :class:`unittest.TestCase` so the baseline `make test` loop runs
with zero third-party dependencies; they are also collected by pytest.
"""

import importlib
import unittest

# The architectural seams defined by HLD "Repository and Module Shape".
SEAM_MODULES = (
    "namehelper.api",
    "namehelper.core",
    "namehelper.components",
    "namehelper.profiles",
    "namehelper.adapters",
    "namehelper.diagnostics",
)


class PackageSkeletonTests(unittest.TestCase):
    def test_all_seam_modules_import(self) -> None:
        for name in SEAM_MODULES:
            with self.subTest(module=name):
                module = importlib.import_module(name)
                self.assertTrue(hasattr(module, "__all__"))

    def test_namehelper_importable_from_root(self) -> None:
        import namehelper

        self.assertTrue(hasattr(namehelper, "NameHelper"))

    def test_namehelper_importable_from_api_layer(self) -> None:
        from namehelper.api import NameHelper

        self.assertIsNotNone(NameHelper)

    def test_version_is_non_empty_string(self) -> None:
        import namehelper

        self.assertIsInstance(namehelper.__version__, str)
        self.assertTrue(namehelper.__version__)


if __name__ == "__main__":
    unittest.main()
