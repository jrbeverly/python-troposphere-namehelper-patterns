"""Contract layer: profile catalog coverage and isolation boundary.

Encodes the contract downstream issues must preserve:

- the curated proof-of-concept resource set (HLD "Constraint Profile
  Catalog") stays available and retrievable;
- an unmodelled resource fails *explicitly* instead of falling through to a
  permissive generic profile (acceptance criteria);
- the profiles package stays isolated from the planning/component/adapter
  layers so coverage grows by profile addition, not core rewrites
  (CODEMAP "Dependency direction").
"""

import ast
import pathlib
import unittest

import namehelper.profiles as profiles_pkg
from namehelper.profiles import (
    SupportLevel,
    UnsupportedResourceError,
    get_profile,
    is_supported,
    supported_resources,
)

POC_RESOURCES = {
    "ssm-parameter",
    "iam-role",
    "s3-bucket",
    "apigateway-restapi",
}

# The profiles package may only use the diagnostics vocabulary; depending on
# these layers would invert the one-way dependency direction.
FORBIDDEN_DEPENDENCIES = (
    "namehelper.core",
    "namehelper.components",
    "namehelper.adapters",
)


class ProfileCatalogContractTests(unittest.TestCase):
    def test_poc_resources_present_and_retrievable(self) -> None:
        available = set(supported_resources())
        self.assertTrue(POC_RESOURCES.issubset(available))
        for resource in POC_RESOURCES:
            with self.subTest(resource=resource):
                profile = get_profile(resource)
                self.assertEqual(profile.resource, resource)
                self.assertTrue(is_supported(resource))

    def test_support_level_is_explicit_for_every_profile(self) -> None:
        for resource in supported_resources():
            with self.subTest(resource=resource):
                self.assertIsInstance(
                    get_profile(resource).support, SupportLevel
                )

    def test_unknown_resource_fails_explicitly(self) -> None:
        self.assertFalse(is_supported("dynamodb-table"))
        with self.assertRaises(UnsupportedResourceError):
            get_profile("dynamodb-table")

    def test_unsupported_error_is_a_key_error(self) -> None:
        # Callers may catch the broad KeyError or the specific type.
        with self.assertRaises(KeyError):
            get_profile("not-a-resource")

    def test_profiles_package_isolated_from_core_layers(self) -> None:
        package_dir = pathlib.Path(profiles_pkg.__file__).parent
        for source in package_dir.glob("*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
            for module in imported:
                for forbidden in FORBIDDEN_DEPENDENCIES:
                    with self.subTest(file=source.name, imported=module):
                        self.assertFalse(
                            module == forbidden
                            or module.startswith(forbidden + "."),
                            f"{source.name} imports {module}",
                        )


if __name__ == "__main__":
    unittest.main()
