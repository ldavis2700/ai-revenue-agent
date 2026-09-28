# Home-Services Lead Intake Diagnostic

## Evidence boundary

This is a delivery template, not a case study, proof of demand, or claim of a customer result. It makes no guarantee of bookings, revenue, savings, or ROI. Record only buyer-provided or independently verified facts with redacted evidence references; mark every unknown as `[not verified]`.

- Buyer: `[required]`
- Diagnostic period: `[required]`
- Prepared by / reviewed by: `[required]`
- Authorized systems and access scope: `[required]`
- Redacted evidence references: `[required]`
- Evidence limitations: `[required]`

## Buyer context and authorized workflow

- Service lines, territory, hours, and after-hours policy: `[required]`
- Approved lead sources: `[required]`
- Authorized CRM, phone, scheduler, calendar, and reporting systems: `[required]`
- Source of truth for lead, booking, attendance, completion, and payment states: `[required]`
- Current workflow, owners, handoffs, and escalation paths: `[required]`
- Explicitly unauthorized systems or actions: `[required]`

## Baseline metrics

Use one definition and time window for each metric. Do not infer missing values.

| Metric | Definition | Window | Verified value | Redacted evidence reference |
|---|---|---|---:|---|
| Inbound volume by source | `[required]` | `[required]` | `[required]` | `[required]` |
| Missed calls: business hours | `[required]` | `[required]` | `[required]` | `[required]` |
| Missed calls: after hours | `[required]` | `[required]` | `[required]` | `[required]` |
| First-response time | `[required]` | `[required]` | `[required]` | `[required]` |
| Contact rate | `[required]` | `[required]` | `[required]` | `[required]` |
| Qualification rate | `[required]` | `[required]` | `[required]` | `[required]` |
| Booking rate | `[required]` | `[required]` | `[required]` | `[required]` |
| Attendance rate | `[required]` | `[required]` | `[required]` | `[required]` |
| Close/completion rate | `[required]` | `[required]` | `[required]` | `[required]` |
| Average revenue / gross profit | `[required]` | `[required]` | `[required]` | `[required]` |

## Consent, privacy, and operational controls

| Control | Current state and evidence | Required pilot behavior | Owner |
|---|---|---|---|
| Consent source and permitted channel | `[required]` | No action without eligible consent | `[required]` |
| Opt-out capture | `[required]` | Honor immediately | `[required]` |
| Suppression list | `[required]` | Check before every outbound action | `[required]` |
| Quiet hours / timezone | `[required]` | Fail closed outside allowed window | `[required]` |
| Data minimization and retention | `[required]` | Store only approved fields for approved duration | `[required]` |
| Integration authorization | `[required]` | Use only enumerated systems and scopes | `[required]` |
| Human escalation owner and SLA | `[required]` | Queue ambiguity, emergency, and low confidence | `[required]` |

## Leakage and risk register

| Observation | Evidence | Economic mechanism | Severity | Safe action | Owner |
|---|---|---|---|---|---|
| `[required]` | `[required]` | `[required]` | `[required]` | `[required]` | `[required]` |

Label findings that cannot yet be supported as `not verified`. Include a separate finding for anything that is not safe, not measurable, or outside the buyer's authorization.

## Deterministic versus AI decision

Use deterministic rules by default. Introduce AI only where bounded reasoning materially improves classification or routing and the buyer accepts the residual risk.

- Decision requiring reasoning: `[required]`
- Why deterministic logic is insufficient: `[required]`
- Allowed inputs and outputs: `[required]`
- Confidence threshold and fail-closed behavior: `[required]`
- Evaluation set and required pass threshold: `[required]`
- Prompt-injection, unsafe-language, and sensitive-data tests: `[required]`
- Human review and escalation path: `[required]`
- Audit record and rollback mechanism: `[required]`

## Bounded pilot scope

- One approved lead source: `[required]`
- One qualification and routing path: `[required]`
- One authorized booking destination: `[required]`
- One human escalation queue: `[required]`
- Included fields, actions, hours, and volume cap: `[required]`
- Explicit exclusions, including emergency dispatch: `[required]`
- Rollback trigger, procedure, and owner: `[required]`
- Start/end dates and acceptance review: `[required]`

## QA and acceptance matrix

| Scenario | Expected safe behavior | Evidence produced | Pass/fail |
|---|---|---|---|
| Duplicate lead/action | Suppress duplicate outbound action | `[required]` | `[required]` |
| Missing contact or consent | Do not contact; escalate if appropriate | `[required]` | `[required]` |
| Opted-out or suppressed record | No outbound action | `[required]` | `[required]` |
| Quiet hours / timezone boundary | Defer or escalate per approved policy | `[required]` | `[required]` |
| Ambiguous qualification | Human escalation | `[required]` | `[required]` |
| Emergency or unsafe language | No automation; immediate approved escalation | `[required]` | `[required]` |
| Unavailable integration | Fail closed; alert owner | `[required]` | `[required]` |
| Invalid or stale booking slot | Do not confirm; refresh or escalate | `[required]` | `[required]` |
| Retry / idempotency | One durable action and auditable retry | `[required]` | `[required]` |
| Escalation timeout | Alert backup owner; retain audit trail | `[required]` | `[required]` |
| Cancellation / reschedule | Update source of truth without duplicate action | `[required]` | `[required]` |
| Conflicting CRM state | Fail closed and reconcile manually | `[required]` | `[required]` |
| Prompt injection / malicious text | Treat as data, not instruction; escalate | `[required]` | `[required]` |
| Audit trail / rollback | Reconstruct action and complete rollback | `[required]` | `[required]` |

## Measurement and attribution

- Source of truth and reconciliation cadence: `[required]`
- Response-time target: `[required]`
- Maximum misroute / unsafe-action threshold: `[required]`
- Booked, attended, completed, and paid-state reconciliation: `[required]`
- Attribution window and exclusions: `[required]`
- Buyer-side changes that invalidate comparison: `[required]`
- Dispute and correction process: `[required]`

Outcome pricing is prohibited until a paid pilot produces a verified, auditable ledger with an objective billable event, explicit attribution, exclusions, cap, dispute process, and human escalation. Messages, leads, or bookings are not collected client revenue.

## Unit economics

- Diagnostic fee: `[estimate only]`
- Implementation / pilot fee: `[estimate only]`
- Managed monthly fee: `[estimate only]`
- Delivery labor and required human hours: `[estimate only]`
- API / inference / integration cost: `[estimate only]`
- Known acquisition cost: `[estimate only]`
- Estimated contribution dollars and margin: `[estimate only]`
- Estimated contribution per required human hour: `[estimate only]`
- Collected revenue: $0 unless independently verified as settled

All projected economics remain estimate-only and must be kept separate from proposals, contracts, invoiced amounts, withdrawable balances, and money actually received.

## Implementation and managed recurring option

If the buyer approves a pilot, define integration monitoring, exception handling, QA sampling, consent-control verification, reporting cadence, change allowance, incident response, access revocation, and termination/rollback. Recurring service is optional and requires a separately accepted scope.

## Reusable IP capture

Capture only nonconfidential, de-identified patterns: qualification rules, adapters, test fixtures, control checks, evaluation cases, reporting schemas, and delivery lessons. Do not reuse buyer data, credentials, proprietary processes, or identifying evidence.

## Findings not safe or not measurable

- Not safe to automate: `[required or none with rationale]`
- Not measurable with current evidence: `[required or none with rationale]`
- Required buyer remediation before a pilot: `[required or none]`

## Buyer acceptance

Buyer acceptance confirms only that the baseline is accurate to the buyer's knowledge, access is authorized, controls and escalation paths are correct, metrics are measurable, and exclusions are acknowledged. It is not proof of a contract, payment, collected revenue, or outcome.

- Buyer approver / role: `[required]`
- Accepted baseline and evidence limitations: `[yes/no + notes]`
- Authorized access and systems: `[yes/no + notes]`
- Consent, suppression, quiet-hour, and escalation controls: `[yes/no + notes]`
- Pilot metrics, exclusions, and rollback: `[yes/no + notes]`
- Date / evidence reference: `[required]`

## Promotion gates

- **Learned:** documented workflow, controls, risks, and testable hypothesis.
- **Validated by verified paid engagement:** settled payment plus accepted diagnostic or pilot delivery; never inferred from a proposal or buyer acceptance alone.
- **Repeatable positive-margin delivery:** at least two independent accepted deliveries with verified positive contribution margin.
- **Scale candidate:** repeatability plus retained demand, controlled delivery risk, and supportable acquisition economics.
- **Productize candidate:** verified expansion/retention evidence and reusable nonconfidential IP across buyers.
