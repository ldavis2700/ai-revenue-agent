# Evidence-to-review automation: buyer-verifiable scope and proof

**Status:** Sales-scoping and review artifact only (November 16, 2026). This is not a client project, a delivered contract, a live AI extraction system, or a production Supabase integration. No buyer data, identity information or provider credentials are included.

## Buyer problem and focused outcome

Turn **one buyer-authorized representative evidence record** into a proposed structured field; show its exact supporting excerpt; allow a reviewer to **approve, correct, or reject** that field; persist **only approved/corrected** values to a designated *test* Supabase table with source provenance; document how to rerun the example. Do not claim that automatically proposed values are correct merely because they cite or hash text.

## Public, reproducible technical proof (synthetic input only)

- [Original offline example](../examples/evidence_review/README.md) and [source](../examples/evidence_review/research_evidence_demo.py): source references, reviewer decisions, evidence digest, local SQLite, no external credentials. The demo uses *preprovided JSON fields*, **not** automated document/LLM extraction.
- [Dedicated test-project handoff](../examples/evidence_review/supabase_test_handoff.py) and [readback regression tests](../examples/evidence_review/test_supabase_test_handoff.py): dry-run by default; with buyer authorization and a dedicated test project, the adapter can submit approved records and verify them by reading back the exact rows. No buyer test-project write or readback has occurred.
- The existing README documents the complete sample commands. No prior client implementations, paid orders, or successful customer outcomes are claimed by these proofs.

## Proposed bounded Phase 1, *illustrative $750 fixed-price scope — not an accepted offer*

1. **Discovery and evidence contract:** Review one permitted sample and expected schema, required field and citation rules, unsupported/contradictory evidence cases, consent, data sensitivity and retention. Create one workflow diagram from input through proposal, review, write, and verification.
2. **One working demonstration:** Adapt the existing original local proof to one provided source example; display proposed field + quote/source, human approval/correction/rejection and clearly label unsupported/conflicting fields. Integrate **only a dedicated buyer-approved test Supabase table**, with least-privilege keys held securely, never into production.
3. **Acceptance and transfer:** Show a reviewer rejecting unsupported evidence with **no write**, correcting a value, read-back verification of approved data and source reference, an idempotent rerun, an error/rollback exercise, and concise rerun and cost notes. Independent buyer acceptance remains required.
4. **Phase 2 scoping:** Give a follow-on estimate after sample/schema complexity, credentials, environment access, support requirements and provider costs are verified. This document alone does not authorize any price, timetable or contract.

### Conditions and exclusions

A funded, authorized contract and buyer-approved sample, permitted data-handling scope, test-project/table credentials, and reviewer access are needed before handling any buyer data or performing a remote write. No full document extraction, live CRM integration, production rollout, unrestricted email, API/provider charges, security/compliance certification, or unattended actions are included. A client owns decisions about sensitive data, retention, access and acceptance. If a safe test environment or approval is unavailable, deliver offline proof and a written blocker instead of representing a fake cloud write as completed.

### Preliminary Phase 2 sizing (nonbinding, assumptions stated)

**Conditional budget envelope: $1,500–$4,000; 1–3 weeks** for a bounded follow-on, *only* if it remains a single workflow, a small approved schema, a single data source and destination, and buyer-provided integration rights. This is a planning assumption, **not** an earned contract, verified market quote, guarantee, or firm commitment. Larger document variability, dedicated UI/authentication, regulatory constraints, multi-client isolation, more integrations, usage fees and support commitments require a different written quote.

## Demonstration acceptance matrix

| Scenario | Expected proof | Current public proof vs. new buyer acceptance |
| --- | --- | --- |
| Direct supported evidence | Proposed value retains source label and digest | Offline fixture and unit tests exist; buyer's document not tested |
| Unsupported/conflicting evidence | Reviewer can reject; no destination row | Offline review logic exists; buyer-specific conflicts not tested |
| Human correction | Only reviewer-approved corrected value exported | Offline correction covered; no client approval to date |
| Test Supabase write/readback | Exact nine-column row with idempotent approval key matches after read | Dry-run plus mocked tests exist; **no actual remote readback verified** |
| Recovery and access isolation | Failure report, rerun safety, rollback/disconnect and least-privilege proof | Requires a separate funded, buyer-authorized integration |
| Delivery/financial acceptance | Client approval, funded milestone and processor payout receipt | **None**: zero contracts, paid deliverables, or cash claimed |

## Operator next action

Use this page as an accurate capability-reference only. Inspect the live posting and its stated requirements, complete the required final Upwork review/approval and Connect-spend gates, and submit a narrowly truthful proposal only when that specific transaction is authorized. After award, obtain a funded milestone and explicit permitted access before any external work. Reconcile receipts to payment, payout availability and actual settlement separately. Never count this draft, an advertised job budget, a submitted proposal, a loan, or a synthetic demo as earned or collected revenue.
