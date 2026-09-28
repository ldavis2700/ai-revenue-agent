# Home-Services Lead Intake Managed-Service Runbook

## Status and evidence boundary

**Reusable operating template only — not proof of a customer, contract, renewal, revenue, or result.** Do not use it to imply guaranteed bookings, savings, ROI, uptime, or response outcomes. Populate it only after an accepted paid pilot and a separately accepted recurring scope; retain redacted evidence references for every claimed result.

- Buyer / service instance: `[required]`
- Accepted pilot reference: `[required]`
- Recurring scope / authorized-channel reference: `[required]`
- Service owner and backup: `[required]`
- Start date / review date / termination date: `[required]`
- Revenue state: `contract/funding/collection must be separately verified; collected revenue $0 in this template`

## Entry gates

Every gate must be evidenced before recurring operation begins.

- `[ ]` Pilot delivery accepted with unresolved risks documented
- `[ ]` Recurring scope accepted through an authorized channel
- `[ ]` Contract and payment/funding states independently classified
- `[ ]` Authorized integrations, least-privilege access, and revocation owner confirmed
- `[ ]` Consent basis, opt-out, suppression, quiet hours, retention, and escalation controls retested
- `[ ]` Source-of-truth reconciliation and audit lineage verified
- `[ ]` Service levels, volume/action/API-spend caps, and change allowance approved
- `[ ]` Incident contacts, human coverage, rollback, and termination procedures tested

An unknown or expired gate pauses service; it is never treated as approval.

## Service inventory and fixed boundary

| Item | Approved value | Evidence / owner |
|---|---|---|
| Lead sources | `[required]` | `[required]` |
| Qualification/routing paths | `[required]` | `[required]` |
| CRM / booking destinations | `[required]` | `[required]` |
| Channels and service hours | `[required]` | `[required]` |
| Human escalation queues / SLA | `[required]` | `[required]` |
| Data fields / retention | `[required]` | `[required]` |
| Deterministic rules | `[required]` | `[required]` |
| Bounded AI decisions / thresholds | `[required or none]` | `[required]` |
| Volume / action / API-spend caps | `[required]` | `[required]` |
| Explicit exclusions | `[required]` | `[required]` |

Anything outside this inventory requires change control before use.

## Service objectives and guardrails

| Measure | Definition | Target / threshold | Source of truth | Breach action |
|---|---|---|---|---|
| Availability | `[required]` | `[required; no implied guarantee]` | `[required]` | `[required]` |
| First-response time | `[required]` | `[required]` | `[required]` | `[required]` |
| Routing accuracy | `[required]` | `[required]` | `[required]` | `[required]` |
| Human escalation | `[required]` | `[required]` | `[required]` | `[required]` |
| Suppressed/opted-out contact | Unauthorized outbound actions | `0` | Audit + suppression reconciliation | Pause outbound actions |
| Duplicate outbound action | Duplicate actions | `0` | Idempotency/audit report | Pause affected path |
| Audit completeness | `[required fields]` | `[required]` | Event ledger | Repair before resuming |
| Cost / human effort | Actual cost and time | `[approved cap]` | Cost/time ledger | Alert and stop at cap |

## Operating cadence

### Per event

- Verify authorization, consent eligibility, suppression state, quiet hours, idempotency key, destination availability, caps, and audit-write success before action.
- Route ambiguity, unsafe or emergency language, low confidence, conflicts, and unavailable destinations to the approved human queue.

### Daily

- Reconcile action counts, failures, retries, duplicates, suppression blocks, escalations, cap utilization, and source-of-truth drift.
- Review unresolved exceptions and confirm human coverage.

### Weekly

- Sample QA across normal, edge, consent, ambiguity, cancellation, reschedule, integration-failure, unsafe-language, and prompt-injection paths.
- Review access changes, configuration drift, recurring exceptions, actual API cost, and required human time.

### Monthly

- Reconcile lead, booking, attendance, completion, and paid states without representing any proxy as collected revenue.
- Produce the service report, unit-economics ledger, change log, incident summary, control attestation, and renewal/termination recommendation.

## Monitoring and alerts

Monitor integration health, queue depth, latency, error rate, retries, duplicate attempts, suppression checks, consent evidence age, escalation age, reconciliation drift, action volume, API/inference spend, credential expiry, audit-write failures, and rollback readiness.

| Signal | Warning threshold | Stop threshold | Notification owner | Evidence retained |
|---|---|---|---|---|
| `[required]` | `[required]` | `[required]` | `[required]` | `[required]` |

Alerts must identify the affected path and safe next action without exposing credentials or customer contact data.

## Exception and fail-closed matrix

| Exception | Automated behavior | Human action | Resume gate |
|---|---|---|---|
| Missing/invalid consent | No contact | Verify lawful basis | Evidence accepted |
| Opted-out/suppressed record | No contact | Reconcile suppression source | Control retested |
| Quiet-hours boundary | Defer or escalate | Confirm policy/timezone | Approved window |
| Duplicate/retry conflict | Suppress action | Reconcile idempotency lineage | Duplicate risk cleared |
| Ambiguous qualification | Escalate | Decide using approved policy | Decision recorded |
| Emergency/unsafe language | Stop automation | Follow approved emergency escalation | Human closure recorded |
| Prompt injection/malicious text | Treat as data; no instruction execution | Review and sanitize | Test passes |
| CRM/scheduler unavailable | Fail closed | Restore/reconcile | Health + reconciliation pass |
| Conflicting/stale state | No mutation | Resolve source of truth | Conflict resolved |
| Audit-write failure | No external action | Restore audit path | Durable write verified |
| Volume/action/spend cap | Stop affected path | Review and authorize change | Approved new cap or reset |
| Human escalation timeout | Stop dependent action | Notify backup owner | Coverage restored |

## Consent, privacy, and security review

- Consent-source sampling and permitted-channel check: `[cadence / owner / evidence]`
- Opt-out latency and suppression synchronization: `[cadence / threshold / evidence]`
- Quiet-hour and timezone tests: `[cadence / evidence]`
- Data minimization, retention, deletion, and export review: `[cadence / evidence]`
- Least-privilege access and credential-expiry review: `[cadence / evidence]`
- Access revocation drill: `[cadence / evidence]`
- Vulnerability/dependency and configuration-drift review: `[cadence / evidence]`
- Incident tabletop and rollback drill: `[cadence / evidence]`

Never store credentials, payment data, raw contact data, or identifying production evidence in this repository template.

## QA sampling and release control

Define the sampling method, minimum sample size, strata, pass thresholds, reviewer, and evidence location. Any model, prompt, rule, mapping, integration, destination, or policy change must pass the full regression set in isolation before controlled rollout. Use deterministic automation where sufficient; use AI only where bounded reasoning provides verified benefit.

Required regression paths include consent, opt-out, suppression, quiet hours, duplicates, retries, idempotency, cancellation, reschedule, stale/conflicting state, integration outage, escalation timeout, unsafe language, prompt injection, audit lineage, caps, and rollback.

## Incident response and rollback

| Severity | Example | Immediate action | Notification target/time | Recovery evidence |
|---|---|---|---|---|
| Sev 1 | Unauthorized contact, data exposure, unsafe action | Stop affected/all outbound actions; preserve evidence; revoke access if needed | `[required]` | `[required]` |
| Sev 2 | Duplicate actions, material misrouting, source-of-truth drift | Pause affected path; reconcile | `[required]` | `[required]` |
| Sev 3 | Degraded latency, isolated recoverable failure | Contain, retry safely, monitor | `[required]` | `[required]` |

Resume only after root cause, scope, reconciliation, remediation, regression evidence, and authorized approval are recorded. Never weaken a privacy, security, consent, or audit control to restore service.

## Change control

Record requester, reason, affected sources/actions/data/systems, risk, privacy/security impact, cost/human-time impact, tests, rollback, approver, deployment window, and post-change evidence. Material legal, financial, production-billing, payout, ownership, privacy, or security changes require explicit owner review. Scope acceptance never authorizes those changes.

## Monthly evidence report

Report only verified values and label estimates.

- Authorized lead/action volume by source and path
- Suppression/opt-out blocks, duplicates prevented, exceptions, escalations, and incidents
- Response, routing, booking, attendance, completion, and paid-state reconciliation
- Availability and guardrail performance with source-of-truth references
- Actual delivery labor, required human hours, API/inference/integration cost, and known acquisition cost
- Invoiced/approved, collected, withdrawable, and actually received amounts as separate evidenced states
- Changes, QA results, access review, unresolved risks, and recommendation

Do not equate leads, messages, bookings, attributed value, invoices, or withdrawable balance with collected revenue or money received.

## Unit-economics ledger

| Period | Recurring fee state | Delivery cost | API/inference cost | Human hours | Contribution | Margin | Contribution / human hour | Evidence |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `[required]` | `[proposal/contract/invoiced/collected]` | `[required]` | `[required]` | `[required]` | `[calculated]` | `[calculated]` | `[calculated]` | `[required]` |

Only verified settled funds enter collected revenue. Unknown cost or time prevents a positive-margin claim.

## Outcome-pricing gate

Outcome or usage pricing remains excluded unless an accepted paid pilot and recurring evidence establish an objective billable event, reliable source of truth, attribution window, exclusions, fee, cap, correction/dispute process, and human escalation. A later outcome component requires a separately accepted scope and must never charge for an unauditable proxy.

## Renewal, expansion, and upsell

Recommend renewal only from verified delivery quality, control performance, buyer acceptance, supportability, and unit economics. Expansion requires a separately qualified path and change control; never treat more volume, a new channel, a new location, or a new system as implicitly authorized.

Track expansion as proposed, accepted, funded, delivered, invoiced, collected, withdrawable, and received—never as one combined revenue state.

## Termination and offboarding

On termination: stop actions, reconcile pending work, export agreed records, return/delete buyer data per policy, revoke credentials and integrations, confirm billing stop through the authorized owner, preserve required audit evidence, deliver configuration/rollback documentation, and obtain closure acknowledgment. Do not alter Stripe, banking, payout, tax, or account ownership from this runbook.

## Reusable IP and productization capture

Capture only nonconfidential, de-identified adapters, rules, tests, evaluation cases, control checks, schemas, and operating lessons. Do not reuse buyer data, credentials, identifying evidence, or proprietary processes.

- **Repeatable positive-margin delivery:** at least two independent accepted deliveries with verified positive contribution margin.
- **Scale candidate:** repeatability plus retention/expansion evidence and controlled support/acquisition risk.
- **Productize candidate:** recurring cross-buyer demand plus reusable nonconfidential IP and stable controls.

No promotion gate is earned from this template alone.
