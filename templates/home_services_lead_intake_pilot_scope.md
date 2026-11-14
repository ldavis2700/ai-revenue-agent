# Home-Services Lead Intake Bounded-Pilot Scope

## Status and authority boundary

**Draft scope template — not an offer, contract, invoice, payment confirmation, or authorization to execute.** It does not guarantee bookings, revenue, savings, ROI, or any other outcome. Work may begin only after the final scope is accepted through an authorized channel, the agreed payment state is independently verified, required access is expressly authorized, and the launch checklist passes.

- Buyer / legal entity: `[required]`
- Proposal owner: RMC FAMILY ENTERPRISES LLC
- Related accepted diagnostic and redacted evidence references: `[required]`
- Scope version / expiry date: `[required]`
- Current revenue state: `proposal only; collected revenue $0 unless independently verified as settled`

## Verified problem and pilot hypothesis

- Verified workflow gap: `[required; cite redacted evidence]`
- Baseline window and source of truth: `[required]`
- Economic mechanism to test: `[required; no fabricated ROI]`
- Pilot hypothesis: `[required]`
- Known evidence limitations and confounders: `[required]`

## Fixed pilot boundary

- One consented inbound lead source: `[required]`
- One qualification and routing path: `[required]`
- One authorized CRM / booking destination: `[required]`
- One human escalation queue and owner: `[required]`
- Approved channels, service hours, timezone, and quiet hours: `[required]`
- Maximum pilot duration: `[required]`
- Maximum records / actions / API spend: `[required]`
- Allowed data fields and retention period: `[required]`
- Deterministic rules: `[required]`
- Any bounded AI decision, evaluation threshold, and fail-closed behavior: `[required or none]`

Anything not enumerated above is out of scope.

## Deliverables

1. Final approved workflow map, field map, control map, and rollback plan.
2. Isolated test or sandbox implementation using least-privilege access.
3. Evaluation fixtures covering normal, edge, abuse, consent, and integration-failure paths.
4. Launch-readiness report with unresolved risks and explicit go/no-go evidence.
5. If every launch gate passes, a capped production pilot limited to the fixed boundary above.
6. Reconciliation report for routing, booking, attendance, completion, costs, exceptions, and human effort.
7. Buyer-controlled handoff, access-revocation instructions, and rollback evidence.

## Explicit exclusions

- Bought, rented, scraped, or otherwise unconsented lists
- Emergency dispatch, medical/safety advice, or autonomous high-risk decisions
- Contact with opted-out or suppressed records
- Unapproved channels, systems, data fields, territories, hours, or lead sources
- Altering production billing, Stripe, payout, banking, tax, or account ownership
- Signing or accepting a buyer's custom legal terms without authorized owner review
- Guaranteed results, fabricated baselines, fabricated case studies, or implied paid validation
- Outcome or usage pricing before a verified pilot attribution ledger exists
- Work around access controls, platform rules, privacy requirements, or anti-spam obligations

## Buyer dependencies and responsibilities

The buyer supplies accurate baseline evidence, lawful consent basis, suppression data, quiet-hour rules, authorized scoped access, test accounts, source-of-truth definitions, an escalation owner, timely decisions, and notice of material workflow changes. Missing or contradictory dependencies pause work without expanding the scope.

## Consent, privacy, security, and access

- Consent source and permitted channel: `[required]`
- Opt-out capture and suppression synchronization: `[required]`
- Data minimization, retention, deletion, and export: `[required]`
- Credential mechanism: `[scoped OAuth/service account; never paste secrets here]`
- Access approver, review cadence, and revocation owner: `[required]`
- Audit event fields and retention: `[required]`
- Incident notification and containment path: `[required]`

No credential, raw customer contact data, or identifying production evidence belongs in this scope document.

## Launch gates

Every item must be evidenced and marked `pass`; unknown is a failure.

- `[ ]` Final scope accepted through an authorized channel
- `[ ]` Agreed payment/funding state independently verified and correctly classified
- `[ ]` Integration access expressly authorized and least privilege confirmed
- `[ ]` Consent, opt-out, suppression, quiet hours, and retention controls tested
- `[ ]` Human escalation coverage and SLA confirmed
- `[ ]` Duplicate, retry, idempotency, timeout, stale-state, and rollback tests passed
- `[ ]` Emergency, unsafe-language, ambiguity, and prompt-injection paths fail closed
- `[ ]` Source-of-truth reconciliation and audit trail verified
- `[ ]` Volume, duration, API-spend, and action caps configured
- `[ ]` Buyer go/no-go approver and rollback owner identified

## Acceptance and QA matrix

| Requirement | Metric / threshold | Evidence source | Owner | Result |
|---|---|---|---|---|
| No opted-out/suppressed contact | `0` unauthorized outbound actions | Audit log + suppression reconciliation | `[required]` | `[pending]` |
| No duplicate action | `0` duplicate outbound actions | Idempotency/audit report | `[required]` | `[pending]` |
| Routing accuracy | `[buyer-approved threshold]` | Source-of-truth sample | `[required]` | `[pending]` |
| Response-time target | `[buyer-approved threshold]` | Timestamp reconciliation | `[required]` | `[pending]` |
| Human escalation | `[SLA and coverage threshold]` | Queue audit | `[required]` | `[pending]` |
| Audit completeness | `[required fields / threshold]` | Event ledger | `[required]` | `[pending]` |
| Rollback | Complete within `[threshold]` | Drill evidence | `[required]` | `[pending]` |
| Cost and human effort | Fully measured, not estimated after delivery | Cost/time ledger | `[required]` | `[pending]` |

A failed safety control stops the pilot. A performance miss does not authorize hidden scope expansion; it triggers review, remediation, or rollback.

## Measurement and attribution

- Primary operational metric and exact definition: `[required]`
- Guardrail metrics: `[required]`
- Source of truth and reconciliation cadence: `[required]`
- Comparison window / method: `[required]`
- Attribution window and exclusions: `[required]`
- Buyer-side changes and confounders: `[required]`
- Correction and dispute process: `[required]`

Messages, leads, bookings, estimates, and attributed value are not collected revenue. Outcome pricing is excluded from this pilot and may be considered only after an accepted paid delivery produces a verified, auditable attribution ledger with explicit caps and exclusions.

## Commercial test terms

- Fixed pilot price: `[$1,500–$3,000 test band; final amount required]`
- Included delivery hours / change allowance: `[required]`
- Buyer-approved pass-through cost cap: `[required or $0]`
- Payment milestones and authorized rail: `[required]`
- Refund, cancellation, and rescheduling terms: `[owner/legal review required]`
- Proposal validity: `[required]`

These fields are planning inputs only. Do not record proposal value as collected revenue. A contract, invoice, approved milestone, withdrawable balance, and money actually received are separate states and require separate evidence.

## Change control

Any change to source, channel, destination, data, action, hours, volume, integrations, AI behavior, acceptance thresholds, price, or timeline requires a written impact review and buyer approval. Material legal, financial, privacy, production-billing, or ownership changes require explicit owner review before acceptance.

## Stop, incident, and rollback rules

Immediately pause outbound actions for consent/suppression failure, unsafe or emergency content, duplicate action, unauthorized access, unexplained data exposure, threshold breach, source-of-truth divergence, missing human coverage, or spend-cap risk. Preserve the audit record, notify the named owners through the approved path, revoke or restrict access as appropriate, and execute the tested rollback.

## Completion and evidence handoff

Completion requires the agreed deliverables, acceptance matrix, cost/time ledger, exception log, reconciliation report, access inventory, rollback evidence, and buyer acceptance reference. Buyer acceptance alone does not prove payment, positive margin, repeatability, retention, or mastery.

## Optional managed recurring service

Only after accepted pilot delivery, offer a separate scope for integration monitoring, exception handling, QA sampling, consent-control verification, reporting, approved workflow tuning, incident response, and access review. Recurring service is optional and must not be implied by pilot acceptance.

## Earned promotion gates

- **Validated by verified paid engagement:** settled payment plus accepted delivery.
- **Repeatable positive-margin delivery:** at least two independent accepted deliveries with verified positive contribution margin.
- **Scale candidate:** repeatability plus retention/expansion evidence and controlled delivery/acquisition risk.
- **Productize candidate:** repeated demand plus reusable, nonconfidential IP across buyers.

## Approval record

- Buyer scope approver / role / authorized-channel reference: `[required]`
- Owner approval required for custom legal or material financial terms: `[yes/no + reference]`
- Technical launch approver: `[required]`
- Date and scope version: `[required]`

Do not place signatures, credentials, payment data, or customer records in the repository copy of this template.
