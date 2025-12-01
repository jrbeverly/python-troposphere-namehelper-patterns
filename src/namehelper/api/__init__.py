"""Public API layer.

Responsibility (HLD "Public API Layer"): provide the small, ergonomic
entrypoint used by application code, and coordinate planning, validation, and
rendering. It must *not* own AWS-specific rule logic (that belongs to
:mod:`namehelper.profiles`) and must *not* hide important tradeoffs.

Skeleton (issue #10): :class:`NameHelper` exists to anchor the public surface
and prove the module boundary. Naming behavior is deferred to later issues.
"""

from namehelper.api.namehelper import NameHelper

__all__ = ["NameHelper"]
