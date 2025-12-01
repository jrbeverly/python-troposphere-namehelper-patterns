"""Component and representation model.

Responsibility (HLD "Component Model"): represent the kinds of naming inputs
(``literal``, ``derived``, ``generated``) and the alternate representations a
component can take (full, shortened, bounded-fragment, generated-uniqueness),
including exact/bounded/advisory certainty metadata, known length bounds, and
the caller-visible tradeoff of each form.

Boundaries: components describe inputs and their forms; they do not select a
representation, account for a whole-name budget, or embed any resource-specific
(AWS) rule — that planning behaviour is :mod:`namehelper.core` and the rules
are :mod:`namehelper.profiles`. This package depends only on the
:mod:`namehelper.diagnostics` certainty vocabulary (one-way dependency
direction; never the reverse).

The model lives in :mod:`namehelper.components.component`; the curated
proof-of-concept families (stack name, stack id, region, UUID fragments,
explicit delimiter/join, plus generic literal/derived/generated builders) live
in :mod:`namehelper.components.families`.
"""

from namehelper.components.component import (
    Component,
    ComponentSource,
    Representation,
    RepresentationForm,
    UniquenessStrategy,
)
from namehelper.components.families import (
    delimiter,
    derived,
    generated,
    literal,
    region,
    stack_id,
    stack_name,
    unique_id,
    uuid_fragment,
)

__all__ = [
    "ComponentSource",
    "RepresentationForm",
    "UniquenessStrategy",
    "Representation",
    "Component",
    "literal",
    "derived",
    "generated",
    "stack_name",
    "stack_id",
    "region",
    "uuid_fragment",
    "unique_id",
    "delimiter",
]
