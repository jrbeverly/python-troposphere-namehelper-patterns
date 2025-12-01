"""Integration tests for the runnable example templates."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
LOCAL_PACKAGES = ROOT / ".python_packages"
SRC = ROOT / "src"


if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))


def _troposphere_available() -> bool:
    return importlib.util.find_spec("troposphere") is not None


def _load_example_module(name: str):
    module_name = f"test_examples_{name.replace('.', '_')}"
    path = EXAMPLES / name
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load example module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_example(name: str) -> dict[str, object]:
    env = os.environ.copy()
    current = env.get("PYTHONPATH")
    parts = [str(SRC)]
    if LOCAL_PACKAGES.exists():
        parts.append(str(LOCAL_PACKAGES))
    if current:
        parts.append(current)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    completed = subprocess.run(
        [sys.executable, str(EXAMPLES / name)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        check=True,
        text=True,
    )
    return json.loads(completed.stdout)


@unittest.skipUnless(
    _troposphere_available(), "troposphere is not installed"
)
class RunnableExamplesTests(unittest.TestCase):
    """The examples emit parseable CloudFormation templates."""

    def test_build_template_returns_troposphere_template(self) -> None:
        from troposphere import Template

        minimal = _load_example_module("minimal.py")
        adapter = _load_example_module("template_generation.py")

        self.assertIsInstance(minimal.build_template(), Template)
        self.assertIsInstance(adapter.build_template(), Template)

    def test_minimal_example_emits_template(self) -> None:
        template = _run_example("minimal.py")

        self.assertEqual(template["AWSTemplateFormatVersion"], "2010-09-09")
        resources = template["Resources"]
        self.assertEqual(
            resources["AppBucket"]["Properties"]["BucketName"],
            "payments-prod-assets",
        )
        self.assertEqual(
            resources["AppRole"]["Properties"]["RoleName"],
            "payments-prod-app",
        )
        self.assertEqual(
            resources["ConfigParameter"]["Properties"]["Name"],
            "/payments/prod/app/config",
        )
        self.assertEqual(
            resources["ServiceApi"]["Properties"]["Name"],
            "payments-prod-api",
        )
        self.assertFalse(
            template["Metadata"]["NameHelperResults"]["AppBucket"]["findings"]
        )

    def test_template_generation_example_emits_template(self) -> None:
        template = _run_example("template_generation.py")

        self.assertEqual(template["AWSTemplateFormatVersion"], "2010-09-09")
        resources = template["Resources"]
        self.assertEqual(
            resources["ArtifactsBucket"]["Properties"]["BucketName"],
            "payments-prod-artifacts01",
        )
        self.assertEqual(
            resources["ExecutionRole"]["Properties"]["RoleName"],
            "us-east-1-orders-prod-payments",
        )
        self.assertEqual(
            resources["ServiceApi"]["Properties"]["Name"],
            "payments-prod-api",
        )
        bucket_metadata = template["Metadata"]["NameHelperResults"][
            "ArtifactsBucket"
        ]
        self.assertEqual(
            bucket_metadata["confidence_codes"], ["practical_uniqueness"]
        )
        self.assertIn("practical_uniqueness", bucket_metadata["warning_codes"])


if __name__ == "__main__":
    unittest.main()
