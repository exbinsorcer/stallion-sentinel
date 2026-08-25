# Change Requests

## Purpose

Sentinel produces change requests as a safe, review-first handoff. A change request is a structured record of a validated operational problem, the evidence trail, and the proposed remediation path. It is not an authorization to act.

## Safety model

- Sentinel may find issues and record them.
- Sentinel may draft and export a change request.
- Sentinel does not approve the work.
- Sentinel does not execute any remediation.
- Sentinel does not apply, deploy, merge, repair, or implement production changes.
- Any future executor must receive explicit owner authorization outside the Sentinel runtime.

## Supported lifecycle

1. DRAFT
   - The issue has been identified and evidence is attached.
2. READY_FOR_REVIEW
   - The issue has enough evidence and the request is ready for human review.
3. APPROVED_FOR_IMPLEMENTATION
   - Only an external owner or approver can create this state.
4. IMPLEMENTATION_IN_PROGRESS
   - Only after explicit approval.
5. VERIFIED / CLOSED
   - Verification happens after implementation and only under an approved workflow.

Sentinel itself is limited to DRAFT and READY_FOR_REVIEW creation states. It cannot automatically self-transition to implementation authorization.

## Request fields

Each request contains:

- request ID
- timestamps
- category
- severity
- priority
- status
- affected system, component, app
- evidence
- related findings and run IDs
- verified root cause or UNKNOWN
- unresolved questions
- requested outcome
- constraints
- verification plan
- required permission
- approval status
- implementation status
- verification status

## Permission model

The system intentionally models approval levels instead of granting authority:

- OBSERVE
- PATCH_PROPOSAL
- TEST_BRANCH
- PREPARE_RELEASE
- PRODUCTION_CHANGE

Sentinel remains OBSERVE-only. It may generate a change request, but it cannot elevate its own authority or satisfy the approval requirement.

## Runtime storage

Change requests are stored under `.runtime/change_requests/` and are excluded from Git. They are runtime artifacts only.

## Export rules

Exports are sanitized and do not include:

- passwords
- SSH private keys
- tokens
- Mongo credentials
- environment dumps
- raw secrets

The exported payload may include approval_status: NOT_APPROVED as proof that the request is a proposal, not permission.

## Future enforcement

A future execution layer may operate only after explicit owner authorization. Sentinel does not create that bridge in this milestone.
