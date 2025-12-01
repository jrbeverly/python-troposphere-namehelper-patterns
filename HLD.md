# High-Level Design

## Purpose

This document defines the high-level design for a lightweight, constraint-aware AWS naming library for Python infrastructure workflows.

It serves as the canonical architectural view of the system:

- what the system is
- what responsibilities it owns
- how the major pieces fit together
- where the key risks live
- how those risks should be handled
- what implementation workstreams naturally fall out of the design

This is not a detailed implementation spec. It does not lock in exact schemas, classes, or file formats unless doing so is necessary to explain the architecture.

## Design Intent

The system should help developers build AWS-compliant names from structured semantic components while preserving useful meaning and making constraint tradeoffs explicit.

It should be:

- lightweight
- deterministic
- local and side-effect free
- implementation-aware
- explicit rather than magical
- useful in both static and derived naming scenarios

The system should not silently "fix" names in surprising ways. When a name is invalid, risky, or over budget, the system should surface the issue, explain why, and make it easy for the caller to choose a compliant representation.

## System Summary

The proposed product is a Python library centered around a small public helper surface, likely exposed through `NameHelper`.

Internally, the library is composed of:

- a structured naming API
- a component model for literal, derived, and generated segments
- a planning engine that evaluates constraint budgets
- a catalog of AWS/resource-specific constraint profiles
- a normalization and rendering layer
- a validation and diagnostics layer
- optional adapters for Troposphere/CloudFormation and similar workflows

The library should support both:

- exact/static naming, where the final value is known during Python execution
- derived/generated naming, where some values are bounded, approximate, or only known at deployment time

## Goals

- Make structured AWS naming easier than ad hoc string assembly.
- Preserve semantic meaning where possible under resource-specific limits.
- Support explicit constraint reasoning before deployment.
- Make derived and partially known values usable without pretending they are exact.
- Provide practical uniqueness strategies using generated or derived identifiers.
- Allow validation findings to stop generation or be bypassed intentionally.
- Stay small enough to prove the concept without becoming an AWS-wide naming framework.

## Non-Goals

- Exhaustive support for all AWS resource naming rules.
- Perfect prediction of every deploy-time CloudFormation value.
- Hidden automatic compression or heuristic rewriting.
- Global uniqueness guarantees backed by external reservation systems.
- A large declarative framework or control plane.

## System Context

The library sits inside Python-based infrastructure code.

Typical callers include:

- Troposphere template builders
- CloudFormation-oriented helper libraries
- local tooling used to validate infrastructure naming
- CI checks that validate names before deployment

The library consumes:

- semantic naming components
- resource or naming-context selection
- representation preferences
- validation policy

The library produces:

- a rendered name or name expression
- findings describing validity, risk, and tradeoffs
- enough diagnostics for the caller to understand why the result is safe, unsafe, or approximate

## Core Design Principles

### 1. Structured Names, Not Flat Strings

Names should be modeled as ordered compositions of meaningful parts.

### 2. Explicit Constraint Resolution

The system should never rely on hidden compression as its primary behavior. If a shorter representation is needed, the caller should be able to see and choose it.

### 3. Different Knowledge Levels Matter

Static values, bounded derived values, and advisory-only values are not equivalent. The system must represent that distinction directly.

### 4. Validation Is a Product Feature

The library is not only a string formatter. It is also a guardrail layer that should help prevent predictable mistakes before deployment.

### 5. Profiles Own AWS-Specific Rules

Resource-specific knowledge must be isolated from the core composition engine.

### 6. Core Logic Must Stay Adapter-Agnostic

Troposphere and CloudFormation are important integration targets, but they should not define the internal architecture.

### 7. Determinism Builds Trust

The same inputs, profiles, and policy should yield the same result and the same findings.

## Key Concepts

The following concepts define the mental model of the system.

### Name Component

A semantic segment that participates in a final name, such as an environment label, service identifier, stack name, region token, or uniqueness suffix.

### Component Source Type

Each component comes from one of three source types:

- `literal`: exact value known at synthesis time
- `derived`: value may be computed from runtime or contextual information and may only be partially known
- `generated`: value intentionally produced to satisfy uniqueness or boundedness needs

### Representation

A component may expose more than one usable form. For example, a component may have:

- a full representation
- a shortened symbolic representation
- a bounded fragment representation
- a generated uniqueness representation

Representation choice is central to the system. It is how the caller moves from "too long or too risky" to "acceptable under this profile."

### Constraint Profile

A resource-aware rule set that defines the naming envelope for a target surface.

At a minimum, a profile may define:

- length ceilings
- character restrictions
- casing rules
- formatting restrictions
- uniqueness considerations
- whether exact, bounded, or advisory validation is possible for specific component patterns

### Constraint Budget

The total naming space available after accounting for:

- separators
- fixed required segments
- required suffixes
- uniqueness reservations

### Finding

A diagnostic conclusion produced during planning or validation.

Examples include:

- deterministic violation
- bounded-risk warning
- advisory warning
- suggestion for alternate representation

### Validation Policy

A caller-controlled rule set that determines whether a finding is:

- fatal
- warning-only
- explicitly ignored

This is the mechanism that allows strict template generation in some contexts and more exploratory behavior in others.

## Architectural Overview

At a high level, the library behaves like this:

```text
Caller
  -> Public API
  -> Composition/Planning Core
     -> Component Sources and Representations
     -> Constraint Profile Catalog
     -> Validation Policy
  -> Normalization and Rendering
  -> Validation and Diagnostics
  -> Result
```

When a name is over budget or insufficiently bounded, the system should not silently mutate it and continue. Instead, the flow becomes:

```text
Plan -> Findings -> Caller Chooses Different Representation or Policy -> Re-validate -> Final Result
```

## Major Components

### 1. Public API Layer

#### Responsibility

Provide the small, ergonomic entrypoint used by application code.

#### What it should do

- accept naming inputs in a structured form
- expose common helpers for joins, normalization, validation, and generation
- coordinate planning, validation, and rendering
- return a result that includes both output and diagnostics

#### What it should not do

- own AWS-specific rule logic
- hide important tradeoffs
- force callers into a heavy DSL

#### Design implication

The API should be easy to use for the common path, but still make space for explicit representation choices and validation policy configuration.

### 2. Composition and Planning Core

#### Responsibility

Model the name as a structured plan and reconcile it against the selected constraint profile.

#### What it should do

- maintain ordered component composition
- reserve space for separators and fixed segments
- evaluate the current plan against the resource budget
- identify where the plan is valid, risky, or impossible
- surface alternate representation paths

#### What it should not do

- perform opaque last-minute rewriting
- embed resource-specific AWS details

#### Design implication

The planning core is the system's main decision engine. It should be deterministic and side-effect free.

### 3. Component Model

#### Responsibility

Represent the different kinds of naming inputs and the alternate forms they can take.

#### What it should do

- model literal, derived, and generated components
- attach available representations to a component
- expose known bounds where possible
- expose uncertainty where bounds are approximate or unknown

#### First-class proof-of-concept component families

- stack ID
- stack name
- region
- partitioned stack UUID fragments
- join and delimiter decisions
- resource-derived contextual segments

#### Design implication

This component layer is what makes the system useful beyond basic concatenation. Without it, the project collapses back into string helpers.

### 4. Constraint Profile Catalog

#### Responsibility

Encapsulate resource-specific naming rules.

#### What it should do

- describe the envelope for each supported target
- separate reusable naming logic from AWS surface specifics
- support curated growth of coverage

#### Proof-of-concept resource set

- SSM Parameters
- IAM Roles
- S3 Buckets
- API Gateway resources

#### Why this set matters

- `S3` exercises a strict and widely understood naming envelope.
- `IAM` provides a materially different naming profile.
- `SSM` exercises parameter-oriented naming conventions common in infrastructure code.
- `API Gateway` is a good candidate for a minimally deployable surface with different naming semantics, useful for proving the abstraction across distinct AWS systems.

#### Design implication

Profiles should be explicit and curated. The system should never imply full AWS coverage if only a subset is modeled.

### 5. Normalization and Rendering Layer

#### Responsibility

Convert the planned structure into a final output form appropriate for the selected profile.

#### What it should do

- apply naming style conventions such as kebab, snake, camel, or pascal where appropriate
- normalize separators
- sanitize characters when permitted by profile rules
- render final string or expression output

#### What it should not do

- conceal lossy decisions
- quietly discard semantic intent

#### Design implication

Normalization must be predictable. If a transformation changes meaning or length characteristics in a material way, it should be visible in findings or representation choice.

### 6. Validation and Diagnostics Layer

#### Responsibility

Explain whether the final or proposed name is safe, unsafe, exact, bounded, or advisory.

#### What it should do

- report deterministic violations
- report approximate-risk scenarios
- explain why a result is valid or invalid
- report which representations and policy decisions were used
- support policy-controlled fatal/warn/ignore outcomes

#### Design implication

Diagnostics are a first-class output of the library. They are not only for debugging. They are how callers build trust in the system.

### 7. Adapters

#### Responsibility

Connect the core library to Troposphere/CloudFormation and similar environments without coupling the core to those environments.

#### What it should do

- translate integration-specific inputs into core concepts
- carry through deploy-time uncertainty where applicable
- support failure or warning behavior during template generation

#### What it should not do

- redefine naming rules at the adapter layer
- make the core library dependent on template-generation internals

## Knowledge and Certainty Model

The system must treat not all values as equally knowable.

### Exact

The value is fully known during planning.

Implication:

- deterministic validation is possible
- exact budget accounting is possible

### Bounded

The exact value is not known, but a meaningful upper bound or shape is known.

Implication:

- strong guardrails are possible
- exact rendering may still be deferred
- validation can be conservative and useful

### Advisory

The value is only loosely predictable or represented by approximation.

Implication:

- the system should not claim hard guarantees
- warnings and suggestions are the primary tools
- callers may proceed only through policy or explicit override

This model is essential to the project's credibility. It allows the library to remain useful under ambiguity without overstating certainty.

## Constraint Resolution Model

Constraint resolution is a visible planning loop, not hidden behavior.

### Desired behavior

1. The caller proposes a structured name.
2. The system evaluates that name against the selected profile and current component representations.
3. If the plan is valid, the system returns the result.
4. If the plan is invalid or risky, the system surfaces findings and alternate representation paths.
5. The caller either:
   - accepts a compliant alternate representation
   - changes the component mix
   - changes validation policy
   - ignores selected warnings intentionally
6. The system re-validates and returns the final outcome.

### Important boundary

The system may recommend alternate shorter or more bounded representations, but it should not silently adopt them as its primary mode of operation.

## Uniqueness Strategy

The system should support practical uniqueness, not pretend it can solve global uniqueness universally.

### Strategy types

- caller-provided exact identifiers
- generated uniqueness segments
- derived uniqueness segments such as stack ID fragments
- bounded partitions of UUID-like stack identifiers

### Design stance

- uniqueness should be explicit
- uniqueness affects the budget and must be planned for
- uniqueness tradeoffs should be visible in diagnostics
- the proof of concept does not need external reservation or availability checks

This is enough to validate the naming concept without expanding the project into a coordination service.

## Validation Model

Validation should operate at two levels:

### 1. Structural Validation

Checks whether the composition can fit the selected profile under the current representations and certainty model.

Examples:

- over-length names
- incompatible separators
- impossible fixed-segment combinations

### 2. Confidence Validation

Checks whether the system has enough certainty to claim the result is safe.

Examples:

- bounded values that still fit under worst-case assumptions
- advisory values that prevent hard guarantees
- generated uniqueness that is collision-resistant but not externally reserved

### Validation policy behavior

The policy model should support:

- hard failure for deterministic violations
- warnings for uncertain-but-usable paths
- explicit ignore or bypass controls for accepted risk

This is necessary because the same naming library may be used in:

- strict CI validation
- local experimentation
- template generation pipelines
- exploratory infrastructure prototypes

## High-Level Flows

### Flow 1: Exact Static Naming

1. Caller provides exact literal components.
2. Profile is selected.
3. Plan is composed and normalized.
4. Budget is evaluated exactly.
5. Validation passes or fails deterministically.
6. Final output and diagnostics are returned.

### Flow 2: Derived Naming With Bounds

1. Caller provides a mix of literal and bounded derived components.
2. The planner uses worst-case or declared bounds.
3. If the composition fits within bounds, the system can report bounded confidence.
4. If it does not fit, the system surfaces alternate representations or warnings.
5. Caller chooses whether to revise the plan or proceed under policy.

### Flow 3: Over-Budget Resolution

1. Caller submits a name that exceeds the target profile.
2. System identifies the specific components driving the excess.
3. System presents viable shorter or more bounded representations.
4. Caller chooses the revised form.
5. System re-validates and finalizes the result.

### Flow 4: Practical Uniqueness

1. Caller needs uniqueness beyond a semantic base name.
2. System offers or accepts explicit uniqueness components.
3. Budget is reserved for that uniqueness strategy.
4. Final output reflects the selected uniqueness tradeoff.

### Flow 5: Template Generation Gate

1. Template-generation code requests a final name.
2. Findings are produced under the active validation policy.
3. Fatal findings stop generation.
4. Warning-level findings permit continuation unless policy or caller behavior escalates them.
5. Explicitly ignored findings allow generation to continue while preserving traceable diagnostics.

## Repository and Module Shape

The repository should separate public API, core logic, profiles, and adapters cleanly.

```text
src/
  namehelper/
    api/
    core/
    components/
    profiles/
    adapters/
    diagnostics/
tests/
  unit/
  integration/
  contract/
docs/
examples/
```

### Boundary intent

- `api`: caller-facing helpers and orchestration
- `core`: composition, planning, and budget evaluation
- `components`: literal/derived/generated component behavior and alternate representations
- `profiles`: AWS/resource-specific naming rules
- `adapters`: Troposphere/CloudFormation and related integrations
- `diagnostics`: findings, policy interpretation, and explainability
- `tests`: behavioral validation at multiple levels

The exact filesystem layout may change, but these boundaries should remain.

## Implementation Workstreams

This section does not prescribe a final roadmap, but it does define the natural implementation slices an AI or human planner should use when creating issues.

### Workstream 1: Core Domain and Result Model

Focus:

- structured naming concepts
- component ordering
- result and finding concepts
- certainty model
- validation policy model

Why it matters:

This establishes the language the rest of the system will use.

### Workstream 2: Component and Representation System

Focus:

- literal, derived, and generated components
- alternate representations
- bounded and advisory metadata
- stack ID, stack name, region, and UUID-fragment support

Why it matters:

This is the main differentiator between the proposed system and generic string utilities.

### Workstream 3: Profile Framework and Initial AWS Profiles

Focus:

- profile abstraction
- SSM, IAM, S3, and API Gateway proof-of-concept profiles
- reusable rule composition where sensible

Why it matters:

This proves the abstraction across genuinely different naming systems.

### Workstream 4: Planning and Constraint Resolution

Focus:

- budget accounting
- over-budget detection
- alternate representation suggestion
- deterministic planning behavior

Why it matters:

This is the engine that turns structured inputs into actionable naming outcomes.

### Workstream 5: Validation, Diagnostics, and Policy

Focus:

- fatal vs warning vs ignored findings
- explainability
- template-generation gating behavior
- policy-driven continuation rules

Why it matters:

This is what makes the library safe and usable in real workflows.

### Workstream 6: Adapters and Examples

Focus:

- Troposphere/CloudFormation integration
- example usage patterns
- derived-value handling in realistic calling contexts

Why it matters:

This proves the core library fits the workflow it is intended to serve.

### Workstream 7: Verification and Behavioral Coverage

Focus:

- profile behavior tests
- certainty model tests
- constraint resolution behavior
- policy interaction tests
- regression protection for deterministic output

Why it matters:

The product succeeds or fails on trust. Behavioral coverage is part of the architecture.

## Architectural Risks and Mitigations

### Risk 1: Deploy-Time Uncertainty Makes Guarantees Murky

Concern:

CloudFormation- or environment-derived values may not be exactly known during planning.

Mitigation:

- use the exact/bounded/advisory model
- surface uncertainty directly in findings
- allow strict or permissive policy behavior

### Risk 2: Hidden Compression Erodes Trust

Concern:

Silent shortening or heuristic rewriting will make outputs hard to reason about.

Mitigation:

- require visible representation changes
- return diagnostics explaining the chosen path
- keep deterministic behavior across repeated runs

### Risk 3: AWS Rule Coverage Expands Too Quickly

Concern:

Profile coverage can outgrow the proof of concept and distort the architecture.

Mitigation:

- keep the initial profile set curated
- treat unsupported profiles explicitly
- validate the architecture on variety, not exhaustiveness

### Risk 4: API Surface Becomes Too Heavy

Concern:

Supporting many edge cases can create a complicated public interface.

Mitigation:

- keep advanced behavior in components, profiles, and policy
- keep the public entrypoints narrow
- favor structured outputs over many ad hoc helper variants

### Risk 5: Uniqueness Is Misunderstood as Guaranteed Availability

Concern:

Users may over-interpret generated identifiers as universal guarantees.

Mitigation:

- distinguish syntactic validity from practical uniqueness
- explain selected uniqueness strategies in diagnostics
- avoid implying external reservation or existence checks

### Risk 6: Adapter Concerns Leak Into the Core

Concern:

Troposphere or CloudFormation concerns may accidentally define the core model.

Mitigation:

- keep adapter logic separate
- define core abstractions independently of template-generation internals
- treat adapters as translation layers

## Implementation Guidance

These are architectural expectations that should shape implementation, regardless of language-level details.

- Core planning and validation logic should be pure and deterministic.
- The system should return diagnostics by default rather than forcing callers to re-run special debug paths.
- Unsupported or partially supported cases should be called out explicitly, not handled implicitly.
- Any behavior that changes the visible structure of a name should be explainable.
- Initial implementation should optimize for clarity of model and findings over cleverness.
- Resource support should grow through profile addition, not core rewrites.

## What This Design Should Enable

After reading this document, an implementation planner should be able to identify:

- the system boundaries
- the central abstractions
- the major module seams
- the proof-of-concept profile set
- the key flows that must work
- the failure and warning behaviors that must exist
- the major risks that require explicit handling

That should be enough to propose a concrete set of implementation issues without needing to rediscover the architecture from the original problem statement.

## Final Assessment

The proposed system is architecturally coherent and implementable as a lightweight Python library.

Its success depends on treating naming as a structured planning problem, not a string utility problem. The most important design commitments are:

- explicit modeling of literal, derived, and generated components
- direct handling of exact, bounded, and advisory certainty levels
- visible constraint resolution rather than hidden compression
- curated AWS profile support
- policy-driven validation outcomes
- adapter-friendly but adapter-independent core logic

If those commitments hold, the design is strong enough to support disciplined issue planning and incremental implementation.
