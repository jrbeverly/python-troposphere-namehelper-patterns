"""Integration layer: verify the public path wires together end to end.

A placeholder smoke test proving a caller can construct ``NameHelper`` and
reach the package version through the public surface. Real cross-module
behavior tests land here in later issues.
"""

import unittest


class PublicPathSmokeTests(unittest.TestCase):
    def test_namehelper_constructs_and_reports_version(self) -> None:
        from namehelper import NameHelper, __version__

        helper = NameHelper()
        self.assertEqual(helper.version(), __version__)
        self.assertEqual(repr(helper), "NameHelper()")


if __name__ == "__main__":
    unittest.main()
