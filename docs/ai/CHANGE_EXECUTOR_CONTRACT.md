# Change Executor Contract

## Summary

Sentinel observes Hostless and records findings. It drafts proposal-grade change requests for human review. It does not approve, implement, or execute changes.

## Sentinel responsibilities

- Detect issues and preserve evidence
- Classify severity and category
- Generate structured change requests
- Export sanitized handoff payloads
- Store runtime records under `.runtime/change_requests/`
- Recommend owner review

## Non-authority rules

Sentinel cannot:

- approve a request
- execute a command on Hostless
- apply configuration changes
- deploy software
- merge code
- repair infrastructure
- implement a fix without owner authorization

## Required external approval

Any future automation must receive explicit approval, policy, and runtime permission from a human owner or trusted system. The approval state is separate from the generated request and must not be inferred from the mere existence of a request file.

## Contract for future automation

A future execution agent may only read this contract and act when it has:

- an approved request status
- an explicit permission boundary
- a scoped task definition
- an owner authorization trail
- a verification plan

Without those, the executor must stop and request human approval.

## Safety boundary

This document exists to prevent unauthorized actions. Sentinel remains OBSERVE-only and never crosses the implementation or approval boundary.
