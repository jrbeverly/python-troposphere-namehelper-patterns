# Problem

## Role of This Document

This document defines the problem space the project is solving.

It should be read alongside `HLD.md`, which is the canonical architectural reference. This file focuses on the operational pain, the constraints that make the problem non-trivial, and the behaviors the system must improve.

## Overview

Python-based infrastructure code regularly needs to assemble AWS resource names from meaningful semantic parts.

Those names often need to encode context such as:

- environment
- service or subsystem identity
- functional role
- region or account context
- uniqueness suffixes
- stack-derived identifiers

Today, that work is usually done with ad hoc string assembly. The result is repetitive logic, inconsistent conventions, late validation failures, and names that either lose too much meaning or accidentally violate AWS resource rules.

The system being designed is fundamentally a structured naming composition and validation library. It is not a general guarantee engine, and it should not pretend that every deploy-time value can be known exactly in advance.

## Core Problem

The core problem is not simply "how do we join strings."

The real problem is:

- AWS resources impose different naming rules
- useful names are made of structured semantic parts
- some naming inputs are fully known, while others are only bounded or approximate
- users still need pre-deployment guidance before invalid names reach AWS
- callers need both hard validation modes and overrideable warning modes depending on context

The project must help callers compose names intentionally, understand risk before deployment, and choose bounded or shortened representations explicitly when necessary.

## Why Current Approaches Fail

### Flat String Assembly

Most infrastructure code treats names as plain strings assembled inline.

This causes:

- repetitive join logic
- inconsistent delimiter usage
- hidden formatting assumptions
- duplicated resource-specific edge-case handling

### Late Discovery of Invalid Names

Many naming problems are only discovered at deploy time.

This is especially painful when:

- names exceed service-specific length limits
- invalid characters slip through
- required uniqueness space was not reserved
- deploy-time values combine with static values in ways the author did not anticipate

### Semantic Loss Through Naive Shortening

Developers often shorten names by hand or by naive truncation when they hit length limits.

That leads to:

- operationally weak names
- inconsistent abbreviations
- accidental removal of the most important context
- outputs that are hard to reason about later

The problem is not that names sometimes need to become shorter. The problem is doing that opaquely or inconsistently.

## Resource Constraints Are Not Uniform

AWS naming is not one rule set.

Different resource types vary by:

- maximum length
- character restrictions
- case expectations
- separator rules
- uniqueness expectations
- formatting rules that apply only to certain services

Because of this, a naming helper that does not model resource-specific rules will either be unsafe or too generic to be useful.

## Ambiguity Is Part of the Problem Space

Not every input is equally knowable at planning time.

The system must explicitly handle at least three categories:

- static known values
- bounded deploy-time values
- unbounded or only approximately predictable deploy-time values

This matters because callers still need help even when exact guarantees are not possible.

For example:

- a static name can be validated exactly
- a bounded value can support conservative guardrails
- an advisory or unbounded value may only justify warnings and suggested safer representations

The system should therefore surface ambiguity rather than hiding it.

## Compression and Constraint Resolution Must Be Visible

Early versions of the problem framing implied that the system might "intelligently" compress names for the caller.

That is no longer the intended direction.

The actual problem to solve is:

- users need to know when a name is invalid or risky
- users need to see which components are causing pressure
- users need access to shorter or more bounded representations
- users need to choose those representations deliberately

Constraint handling should therefore be user-visible and explainable, not heuristic magic.

## Validation Is Part of the Product

The project is not only about composing names. It is also about preventing avoidable mistakes before deployment.

That means the system should support:

- deterministic validation when inputs are fully known
- bounded or conservative validation when inputs have usable limits
- warning-oriented behavior when only approximation is available
- hard-failure behavior when a calling context requires strict enforcement
- override or suppression behavior when a caller intentionally accepts risk

This validation role is essential to the problem definition.

## Uniqueness Is Practical, Not Absolute

Many AWS naming surfaces require some degree of uniqueness.

The project does not need to solve universal availability or external reservation. It does need to support practical uniqueness strategies that callers can intentionally use, such as:

- caller-provided unique identifiers
- stack-derived identifiers
- partitioned UUID-like fragments
- other generated bounded suffixes

The problem is therefore not "guarantee uniqueness everywhere." The problem is "support useful uniqueness strategies inside resource-specific naming constraints."

## Proof-of-Concept Scope Matters

This project is intentionally an incremental proof of concept, not a finished AWS naming platform.

The problem framing must therefore support:

- partial resource coverage
- incremental rule modeling
- evolving representations and validation behavior
- early architectural validation across a small but varied AWS profile set

It should not imply that all AWS naming behavior is already solved or will be solved in the first implementation.

## Problem Boundaries

The system should address:

- structured name composition
- resource-aware validation
- visible constraint management
- practical uniqueness strategies
- ambiguity handling for deploy-time values
- integration with Python infrastructure workflows

The system should not be expected to provide:

- exhaustive AWS coverage on day one
- hidden automatic repair of invalid names
- perfect foresight for all deploy-time values
- universal uniqueness guarantees outside the modeled strategy

## Constraints

### Architectural Constraints

- The implementation should remain lightweight.
- The public API should remain ergonomic and easy to adopt.
- The core model should remain usable outside any single integration, including Troposphere.

### Behavioral Constraints

- AWS service-specific rules must be modeled explicitly where supported.
- Constraint resolution must be explainable and user-visible.
- The system must distinguish exact, bounded, and advisory input conditions.
- Validation must support both hard-failure and overrideable-warning workflows.

### Maintainability Constraints

- Naming logic should remain composable.
- Resource-rule coverage should remain incremental and extensible.
- Resource-specific behavior should remain isolated from the core composition and validation engine.

## Desired Outcome

The problem is successfully addressed when callers can:

- build names from meaningful components rather than ad hoc strings
- understand whether those names are valid, bounded, or risky before deployment
- deliberately choose shorter or more bounded representations when needed
- use practical uniqueness strategies without losing control of the naming budget
- adopt the system incrementally across differing AWS resource profiles

At that point, the library will be doing the right job: structured composition, validation, and guidance for AWS naming in real infrastructure workflows.
