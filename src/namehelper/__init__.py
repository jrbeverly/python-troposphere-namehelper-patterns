"""namehelper — structured, constraint-aware AWS resource naming for Python.

This package is the public import root. The caller-facing surface lives in
:mod:`namehelper.api`; the internal architectural seams defined by ``HLD.md``
("Repository and Module Shape") are:

- :mod:`namehelper.api`          public, ergonomic entrypoint (``NameHelper``)
- :mod:`namehelper.core`         composition, planning, budget evaluation
- :mod:`namehelper.components`   literal / derived / generated components
- :mod:`namehelper.profiles`     AWS resource-specific constraint profiles
- :mod:`namehelper.adapters`     Troposphere/CloudFormation integrations
- :mod:`namehelper.diagnostics`  findings, validation policy, explainability

Dependency direction is one-way (HLD core principle "Dependency Direction"):
``api`` -> ``core`` -> ``components`` / ``profiles`` / ``diagnostics``.
``adapters`` may depend on the core, but the core must never depend on
``adapters`` — this keeps the library usable outside any single integration.

This is a skeleton (issue #10): the module boundaries exist and import
cleanly, but composition, validation, and rendering behavior is intentionally
deferred to later issues.
"""

from namehelper._version import __version__
from namehelper.api import NameHelper

__all__ = ["NameHelper", "__version__"]
