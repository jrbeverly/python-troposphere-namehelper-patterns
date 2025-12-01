# Technical

## Role of This Document

This document captures the technical direction that the implementation should follow.

`HLD.md` is the canonical design reference. This file exists to reinforce the technical posture, terminology, and boundaries that the implementation should observe.

## Core Technical Position

The system should be implemented as a lightweight Python library with a small public helper surface, likely centered around `NameHelper`.

The library is not merely a formatter. It is a structured naming composition and validation system that must:

- compose names from meaningful components
- model resource-specific AWS naming rules
- reason about exact, bounded, and advisory inputs
- surface findings about validity and risk
- support explicit caller choice when constraint pressure requires alternate representations

The technical direction should remain implementation-aware without turning into a large framework or control plane.

## Technical Scope

The first implementation should support:

- static known values
- bounded deploy-time values
- unbounded or only approximately predictable values
- practical uniqueness derivation
- resource-aware validation
- policy-controlled failure, warning, and ignore behavior

The first implementation should not assume:

- exhaustive AWS coverage
- perfect deploy-time predictability
- automatic hidden compression
- universal uniqueness guarantees

## Primary Technical Abstractions

### Structured Components

Names should be assembled from ordered components rather than flat strings.

Relevant component families include:

- literal semantic labels
- stack name
- stack ID
- region
- partitioned stack-UUID fragments
- join and delimiter decisions
- resource-derived contextual segments
- generated uniqueness segments

### Knowledge Levels

Each input should be treated according to how well it is known:

- `exact`
- `bounded`
- `advisory`

This distinction is central to the implementation because it drives:

- how safely a name can be validated
- how conservative the budget model must be
- whether a result should fail, warn, or proceed only under explicit override

### Representations

A component may expose multiple usable representations with different tradeoffs.

Examples include:

- full semantic form
- shortened symbolic form
- bounded fragment form
- generated uniqueness form

The system should recommend alternate representations when necessary, but it should not silently choose them as its primary behavior.

### Constraint Profiles

AWS-specific naming rules should be modeled as resource-aware profiles.

A profile may encode:

- length limits
- character restrictions
- separator rules
- casing expectations
- formatting rules
- uniqueness expectations
- whether exact, bounded, or advisory validation is possible for a given case

### Findings and Validation Policy

The system should produce findings during planning and validation.

A caller-controlled policy should determine whether each finding behaves as:

- a hard failure
- a warning
- an ignored or bypassed condition

This policy model is required because the same library may be used in:

- strict CI gates
- local exploration
- template generation
- partial or ambiguous deploy-time scenarios

## System Shape

The technical design should follow the component boundaries defined in `HLD.md`:

- public API layer
- composition and planning core
- component and representation model
- constraint profile catalog
- normalization and rendering layer
- validation and diagnostics layer
- optional adapters for Troposphere/CloudFormation and adjacent workflows

These boundaries are important because they prevent:

- AWS rule logic from leaking everywhere
- integration-specific concerns from defining the core
- validation behavior from becoming ad hoc

## Composition and Planning Behavior

The system should treat naming as a planning problem.

That means the implementation should:

- evaluate names as ordered compositions
- account for delimiter and suffix budget
- reason about reserved uniqueness space
- identify over-budget or invalid conditions
- return actionable findings rather than only raw strings

This is a key philosophical correction from the earlier drafts: the library should not feel like "smart string concatenation." It should feel like a predictable planner with an ergonomic surface.

## Constraint Resolution Behavior

Constraint resolution must be visible and caller-directed.

Expected behavior:

- a caller proposes a name structure
- the system evaluates that structure under a selected profile
- the system reports exact violations, bounded risks, or advisory uncertainty
- if the composition is unsafe or too long, the system suggests alternate representations
- the caller chooses whether to revise the plan, accept a shorter representation, or override selected warnings

The implementation should not rely on hidden heuristics or silent compression.

## Validation Behavior

Validation is a core technical responsibility.

The implementation should support:

- deterministic validation for exact values
- conservative validation for bounded values
- warning-oriented reporting for advisory values
- hard-failure behavior for strict execution contexts
- override or suppression behavior when callers accept known risk

The implementation should be honest about what it can and cannot guarantee.

In particular:

- exact inputs may allow strong compliance claims
- bounded inputs may allow conservative safety claims
- advisory inputs should not be represented as fully guaranteed

## Uniqueness Strategy

The technical design should treat uniqueness as a practical, explicit strategy rather than a universal guarantee.

Valid uniqueness sources for the proof of concept include:

- caller-provided unique segments
- stack-derived identifiers
- bounded UUID-like partitions from stack IDs
- generated bounded suffixes

This is sufficient for the proof of concept. The system does not need external reservation systems or real-time availability checks to validate the architecture.

## Resource Coverage Strategy

Resource coverage should be intentionally incremental.

The first-pass proof-of-concept set should include:

- SSM Parameters
- IAM Roles
- S3 Buckets
- API Gateway resources

This set is technically useful because it exercises:

- strict length and formatting constraints
- materially different naming systems
- common infrastructure naming scenarios
- at least one resource that is suitable for lightweight, low-cost validation of the abstraction

Coverage beyond that set should be additive and profile-driven.

## Naming Style Support

The system should support common naming styles where they make sense for the target profile, including:

- camelCase
- PascalCase
- kebab-case
- snake_case

Style support should remain subordinate to resource rules. The library should not normalize into an invalid format simply because that style was requested.

## Integration Direction

Troposphere and CloudFormation remain important integration targets, but they should not define the core architecture.

The implementation should therefore:

- support Python infrastructure workflows naturally
- allow adapters to translate deploy-time concepts into the core model
- preserve uncertainty when exact values are unavailable
- keep the core library usable outside any single framework

This keeps the design exploratory and reusable rather than overly specialized.

## Extensibility Requirements

The architecture should support future expansion through:

- new resource profiles
- new component representations
- additional uniqueness strategies
- richer validation policies
- improved bounded-value modeling
- additional integration adapters

Extensibility should come from profile growth and representation additions, not from repeated rewrites of the planning core.

## Implementation Philosophy

The implementation should optimize for:

- deterministic behavior
- explicit diagnostics
- small, understandable abstractions
- visible tradeoffs
- incremental proof-of-concept delivery

It should avoid:

- magical behavior
- overly broad AWS claims
- premature framework complexity
- technical language that implies stronger guarantees than the system can truly provide

## Technical Success Criteria

The technical direction is successful when:

- names are composed as structured plans rather than ad hoc strings
- supported AWS profiles enforce their rules consistently
- exact, bounded, and advisory cases are clearly distinguished
- callers can fail hard or proceed under explicit warning policy
- alternate representations are visible and explainable
- the system can prove its usefulness across a small but varied resource set

At that point, the technical foundation will be strong enough for incremental implementation and issue planning without conflicting signals from the supporting documents.
