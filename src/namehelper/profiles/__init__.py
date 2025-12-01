"""Constraint profile catalog.

Responsibility (HLD "Constraint Profile Catalog"): encapsulate
resource-specific AWS naming rules (length ceilings, character restrictions,
casing, separators, formatting restrictions, uniqueness expectations, and
certainty-aware validation capability) as isolated, declarative profiles. The
proof-of-concept target set is SSM Parameters, IAM Roles, S3 Buckets, and API
Gateway resources.

Boundaries: profiles own AWS surface specifics so the core stays generic.
This package depends only on the :mod:`namehelper.diagnostics` vocabulary
(``Certainty``); it must not depend on :mod:`namehelper.core`,
:mod:`namehelper.components`, or :mod:`namehelper.adapters`. New resource
coverage is added by registering profiles, never by rewriting the core.

Unmodelled surfaces are explicit: :func:`get_profile` raises
:class:`UnsupportedResourceError` instead of returning a permissive default,
and partially-modelled surfaces carry ``SupportLevel.PARTIAL``.
"""

from namehelper.profiles.catalog import (
    API_GATEWAY_REST_API,
    IAM_ROLE,
    S3_BUCKET,
    SSM_PARAMETER,
    UnsupportedResourceError,
    get_profile,
    is_supported,
    supported_resources,
)
from namehelper.profiles.profile import (
    Casing,
    ConstraintProfile,
    SupportLevel,
    Uniqueness,
)

__all__ = [
    "ConstraintProfile",
    "Casing",
    "Uniqueness",
    "SupportLevel",
    "UnsupportedResourceError",
    "SSM_PARAMETER",
    "IAM_ROLE",
    "S3_BUCKET",
    "API_GATEWAY_REST_API",
    "get_profile",
    "is_supported",
    "supported_resources",
]
