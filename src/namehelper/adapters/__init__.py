"""Integration adapters.

Responsibility (HLD "Adapters"): connect the core library to
Troposphere/CloudFormation and similar environments by translating
integration-specific inputs into core concepts and carrying through
deploy-time uncertainty.

Boundaries: adapters are translation layers only. They must *not* redefine
naming rules and the core must never depend on this package — keeping the
core usable outside any single integration (PROBLEM.md "Architectural
Constraints").
"""

from namehelper.adapters.template import TemplateHelper, from_context

__all__ = ["TemplateHelper", "from_context"]
