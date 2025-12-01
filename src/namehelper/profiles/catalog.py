"""The curated proof-of-concept profile catalog.

HLD "Constraint Profile Catalog" and TECHNICAL.md "Resource Coverage
Strategy" name the initial target surfaces: SSM Parameters, IAM Roles, S3
Buckets, and API Gateway resources. This set is deliberately varied (a strict
global-unique envelope, a different account-scoped envelope, a hierarchical
parameter convention, and a loosely-specified display name) so the
abstraction is proven on variety rather than exhaustiveness (HLD Risk 3).

Lookups for an unmodelled surface raise :class:`UnsupportedResourceError`
rather than returning a permissive generic profile — unsupported coverage is
represented explicitly, never silently tolerated (acceptance criteria;
HLD "treat unsupported profiles explicitly"). Coverage grows by adding
profiles here, not by changing the core.

Rule sources are AWS public naming documentation as of the proof of concept;
each profile records curation choices and known gaps in ``notes`` and via
:class:`SupportLevel`.
"""

from __future__ import annotations

from namehelper.diagnostics.certainty import Certainty
from namehelper.profiles.profile import (
    Casing,
    ConstraintProfile,
    SupportLevel,
    Uniqueness,
)

__all__ = [
    "UnsupportedResourceError",
    "SSM_PARAMETER",
    "IAM_ROLE",
    "S3_BUCKET",
    "API_GATEWAY_REST_API",
    "get_profile",
    "is_supported",
    "supported_resources",
]


class UnsupportedResourceError(KeyError):
    """Raised when a profile is requested for an unmodelled resource.

    Subclasses :class:`KeyError` (a missing catalog key) while giving callers
    a distinct, explicit type to catch instead of guessing from a permissive
    fallback that does not exist.
    """


SSM_PARAMETER = ConstraintProfile(
    resource="ssm-parameter",
    max_length=1011,
    # Hierarchical: optional leading '/', segments of word/.-, no empty
    # segments (so '//' and a trailing '/' are rejected).
    allowed_pattern=r"/?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*",
    # 'aws' and 'ssm' (any case) are reserved name prefixes.
    forbidden_pattern=r"(?i)\A/?(?:aws|ssm)",
    casing=Casing.ANY,
    separators=("/", "-", "_"),
    uniqueness=Uniqueness.ACCOUNT_REGION,
    support=SupportLevel.SUPPORTED,
    notes=(
        "Fully-qualified name including path, max 1011 chars. Reserved "
        "prefixes 'aws'/'ssm' are rejected. Tag/length interactions and "
        "advanced-tier nuances are out of PoC scope."
    ),
)

IAM_ROLE = ConstraintProfile(
    resource="iam-role",
    max_length=64,
    min_length=1,
    # AWS role-name pattern: [\w+=,.@-]+  (\w == [A-Za-z0-9_]).
    allowed_pattern=r"[A-Za-z0-9_+=,.@-]+",
    casing=Casing.ANY,
    separators=("-", "_"),
    uniqueness=Uniqueness.ACCOUNT,
    support=SupportLevel.SUPPORTED,
    notes=(
        "Role name only (not the path). Case-preserving but unique within "
        "the account; service-linked-role naming reservations are out of "
        "PoC scope."
    ),
)

S3_BUCKET = ConstraintProfile(
    resource="s3-bucket",
    max_length=63,
    min_length=3,
    # Begin and end alphanumeric; interior may add '.' and '-'.
    allowed_pattern=r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]",
    # A name formatted as an IPv4 address is not allowed.
    forbidden_pattern=r"\A(?:[0-9]{1,3}\.){3}[0-9]{1,3}\Z",
    casing=Casing.LOWER,
    separators=("-", "."),
    uniqueness=Uniqueness.GLOBAL,
    support=SupportLevel.SUPPORTED,
    notes=(
        "General-purpose bucket envelope (3-63, lower-case, no IP shape). "
        "Newer reservations (xn--/sthree- prefixes, -s3alias/--ol-s3 "
        "suffixes) and adjacent-dot/-hyphen rules are not modelled."
    ),
)

API_GATEWAY_REST_API = ConstraintProfile(
    resource="apigateway-restapi",
    max_length=128,
    min_length=1,
    # AWS does not publish a strict character grammar for the REST API
    # display name; modelled conservatively as printable ASCII.
    allowed_pattern=r"[ -~]+",
    casing=Casing.ANY,
    separators=("-", "_"),
    # REST API names are not unique; the API id provides identity.
    uniqueness=Uniqueness.NONE,
    support=SupportLevel.PARTIAL,
    notes=(
        "Partial: the REST API name has no published strict grammar, so a "
        "conservative 1-128 printable-ASCII envelope is modelled. Verdicts "
        "are indicative, not authoritative."
    ),
)


_CATALOG: dict[str, ConstraintProfile] = {
    profile.resource: profile
    for profile in (
        SSM_PARAMETER,
        IAM_ROLE,
        S3_BUCKET,
        API_GATEWAY_REST_API,
    )
}


def get_profile(resource: str) -> ConstraintProfile:
    """Return the profile for ``resource``.

    Raises :class:`UnsupportedResourceError` for any unmodelled resource —
    the catalog never falls through to a permissive generic profile.
    """
    try:
        return _CATALOG[resource]
    except KeyError:
        raise UnsupportedResourceError(
            f"No constraint profile for resource {resource!r}. "
            f"Supported: {', '.join(supported_resources())}."
        ) from None


def is_supported(resource: str) -> bool:
    """Whether the catalog models ``resource`` at all."""
    return resource in _CATALOG


def supported_resources() -> tuple[str, ...]:
    """The modelled resource identifiers, in catalog order."""
    return tuple(_CATALOG)
