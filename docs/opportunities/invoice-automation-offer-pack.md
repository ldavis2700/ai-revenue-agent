# Invoice Automation Outcome-Service Offer Pack

Status: **qualified candidate only — not saved, applied, offered, contracted, or revenue**

Evidence checked: 2026-10-17 (America/Los_Angeles)

## Marketplace evidence

- Authorized channel: Upwork
- Job ID: `2111575838872460054`
- Posting: “Build an Automated Invoice Processing System in n8n”
- Live state observed: active; zero hires and zero offers; one invitation/interview
- Buyer budget: $70–$100/hour
- Application cost: 15 Connects
- Connected account balance observed: 147 Connects
- Client risk: new client record with no completed hires or feedback
- Competition signal: 50+ proposals in the recommendation snapshot
- Action state: no proposal or spend; explicit approval is required before consuming Connects

This is marketplace evidence, not buyer interest. No message, invitation, offer,
contract, payment, or settled revenue exists.

## Doctrine fit

This maps directly to the reusable
`back_office_document_data_workflows` vertical:

1. paid diagnostic and acceptance-set definition;
2. bounded pilot using representative authorized documents;
3. production implementation;
4. managed monitoring and exception handling;
5. auditable usage and outcome evidence where appropriate;
6. reusable invoice schemas, extraction evaluations, validators, and connectors.

## Draft delivery architecture

- Intake: authorized Gmail inbox plus authenticated upload form.
- Storage: least-privilege document storage with retention rules.
- Extraction: deterministic PDF parsing first; OCR/AI only when necessary.
- Validation: required fields, arithmetic/tax reconciliation, vendor rules, and
  confidence thresholds.
- Deduplication: normalized vendor + invoice number + invoice date + total,
  file-content SHA-256, and a database uniqueness constraint. Retries use the
  same idempotency key.
- Approval: signed, expiring approve/reject/correct links; no public document
  URLs; immutable decision receipt.
- Posting: append only approved records to Google Sheets with reconciliation.
- Exceptions: rejected, duplicate, low-confidence, and provider-failure queues.
- Operations: retry limits, alerts, audit log, rollback procedure, and a manual
  exception owner.

## Proposed staged scope

These are planning estimates, not guarantees or accepted terms.

- Diagnostic: 2–4 hours to map sources, fields, approval authority, retention,
  and an acceptance set.
- Pilot: 12–20 hours for one inbox, one upload route, extraction, validation,
  deduplication, approval, and a test Sheet.
- Implementation: 20–35 additional hours for production hardening,
  observability, documentation, and handoff.
- Managed service: 2–4 hours/month for monitoring, exception review, schema
  drift, and bounded improvements.
- Draft rate: $85/hour, inside the posted range.

Success must be measured with an owner-approved test set: extraction accuracy,
duplicate-prevention accuracy, reconciliation pass rate, approval completion,
exception rate, and required human minutes per accepted invoice.

## Evidence-constrained proposal draft

> INVOICE
>
> I can build this as a staged n8n workflow with deterministic validation and
> idempotency around the AI extraction. My relevant work includes building and
> hardening auditable automation, payment-evidence, retry, validation, and
> exception-handling flows. I will not claim an identical client deployment
> without evidence.
>
> For duplicate prevention, I would combine a normalized business key (vendor,
> invoice number, invoice date, and total) with a SHA-256 file fingerprint and a
> database uniqueness constraint. Every retry reuses the same idempotency key,
> and reconciliation reports expose conflicts instead of silently duplicating
> rows.
>
> I would start with a short diagnostic and representative acceptance set, then
> deliver a testable pilot covering intake, extraction, validation,
> approve/reject/correct links, Google Sheets posting, alerts, and an operator
> guide. A realistic initial pilot is 12–20 hours after access and sample
> documents are available; production hardening follows from measured pilot
> results.
>
> Before starting, I would confirm document sensitivity, retention requirements,
> approval authority, Gmail/Google Workspace access, expected monthly volume,
> and the accepted error/review thresholds.

## Pre-submission gate

Before any proposal is sent:

- obtain explicit approval for the 15-Connect spend and proposed rate;
- verify the posting is still active and has not hired/offered;
- review the attached project brief without exposing its temporary signed URL;
- confirm the profile can truthfully support every claim;
- do not add a boost or attachment unless separately approved.
