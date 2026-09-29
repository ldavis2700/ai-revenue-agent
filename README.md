# AI Revenue Agent

AI Revenue Agent is an automation-first revenue pipeline for ingesting business prospects, qualifying them, generating tailored offers, tracking lifecycle state, and feeding approved outreach workflows.

## Current revenue offer

Default offer stack:

- **AI Customer Response System setup — $100 one-time**
- **Optional managed optimization — $99/month**

The recurring managed plan is designed to turn a successful setup into ongoing revenue while keeping the initial purchase simple.

Configure with:

- `OFFER_NAME`
- `OFFER_SETUP_PRICE` (falls back to legacy `OFFER_PRICE`)
- `MANAGED_MONTHLY_PRICE`
- `OFFER_MODE` = `setup_plus_managed`, `setup_only`, or `managed_only`

## Automated revenue loop

1. Ingest leads from `LEADS_JSON` or `LEADS_API_URL`.
2. Normalize and deduplicate prospects.
3. Score each prospect for sales readiness.
4. Generate a personalized outreach draft with the configured offer stack.
5. Persist lead state and events in SQLite.
6. Hourly n8n workflow returns only qualified `contact_ready` leads.
7. Approved downstream senders can deliver the outreach.
8. Reply, interest, meeting, sale, refund, and opt-out events are recorded.
9. Revenue reporting measures conversion rates and revenue per outreach.
10. Successful setup customers can be moved into the managed monthly plan where appropriate.

Paid-work opportunities use a separate evidence-gated ledger. `prepare_proposal`
stores the complete scope, bounded price, balanced milestones, and only explicitly
verified claims in the same transaction that advances an opportunity to
`proposal_ready`. `record_submission` then requires that stored proposal plus a
provider submission ID, HTTPS receipt URL, and timestamp before atomically
advancing it to `submitted`. `record_response` binds a claimed buyer reply to that
submission and the same provider before advancing to `response_received`. Saving
or recording evidence never contacts a buyer. `record_contract` can only record
an externally accepted contract when it matches the proposal, currency, provider,
and either preapproved standard terms or owner-approved terms with HTTPS evidence;
it cannot accept or sign a contract. `start_execution` then requires a stored,
contract-linked plan with explicit deliverables, acceptance criteria, and future
deadlines before work can move into execution. `pass_qa` requires an immutable
artifact SHA-256 plus passing test results backed by HTTPS evidence before work
can be marked `qa_passed`. `record_delivery` then binds the provider delivery
receipt to that exact QA-approved artifact checksum before advancing to
`delivered`. `record_invoice` requires a delivery-linked provider invoice whose
amount and currency remain within the verified contract and whose dates follow
delivery; it records evidence but never creates a charge. Finally,
Opportunity ranking treats an active buyer stage as a strict priority band before
the numeric opportunity score. Any non-prospect `buyer_stage` requires a canonical
HTTP(S) `buyer_stage_evidence_url`; unsupported reply, invitation, interview,
offer, or contract claims fail closed instead of outranking verified prospects.

Opportunity intake can also carry explicit `required_execution_capabilities` and
`available_execution_capabilities` lists. APEX fails closed when any requirement
is unavailable, preventing technically open jobs from reaching proposal work when
the connected execution environment cannot truthfully complete them. Capability
names are normalized, deduplicated, and validated rather than inferred from job
copy.

`record_collected_payment` counts revenue only from a settled provider transaction
linked to that invoice, with exact gross/currency matching and verified fee/net
arithmetic; it never initiates a charge or changes a payout account.
Mission Control includes those settled receipts in verified gross, fee, and net
revenue metrics alongside legacy verified product-sale events, without counting
the same refund twice in its objective score.

Managed-recurring revenue is recorded through a separate evidence ledger.
`record_settled_recurring_payment` requires the accepted recurring-terms
binding, exact base fee and currency, HTTPS invoice and transaction evidence,
ordered invoice/payment/settlement timestamps, non-overlapping service periods,
and idempotent provider invoice and transaction IDs. Only these settled receipts
appear in `summarize_settled_recurring_revenue`; withdrawable and bank-received
amounts remain separate and zero until independently verified. These functions
never create an invoice, charge a customer, or initiate a payout.
`record_recurring_realized_unit_economics` then calculates contribution
margin and revenue/contribution per required human hour only from one settled
recurring receipt plus separately evidenced delivery, inference/API, CAC, and
human-time costs. Mission Control consolidates one-time and recurring settled
receipts exactly once and exposes recurring totals separately.
Recurring withdrawable balance and money actually received require their own
provider-balance and bank-transfer evidence, exact settled-net/currency
reconciliation, ordered timestamps, and idempotent external IDs. These later
stages are reported independently and never increase collected revenue again.
Settled recurring work can advance reusable-IP maturity only through
`record_recurring_growth_evidence`. The current receipt must have separately
recorded positive realized contribution. Recurring
`repeatable_positive_margin` promotion requires at least two distinct positive-
contribution economics records backed by different settled recurring payments;
one profitable billing period is paid validation, not repeatability. Retention
additionally requires an earlier same-opportunity settled receipt and a subsequent non-overlapping service
period; a contract alone is never retention evidence. Expansion requires an
HTTPS evidence receipt plus explicit, increasing scope and measurable value.
Promotion still proceeds one maturity step at a time.
Mission Control maps those verified recurring receipts back to the relevant
business-model archetype and exposes receipt lineage, realized recurring net and
contribution, retained value, expansion-value delta, and earned mastery. Only
ledger-derived fields receive recurring-growth ranking credit; environment or
manually persisted evidence cannot self-assert retention, expansion, or maturity.
Collected, withdrawable, and received balances remain separate.

## Mission control

`scripts/mission_control.py` gives the agent a measurable operating mission instead of a vague instruction to "make money." It audits the live funnel, rewards only verified net revenue and conversion quality, chooses the current bottleneck, and records every plan in SQLite.

Run it with:

```bash
python3 scripts/mission_control.py
```

Safe defaults are intentionally strict:

- `REVENUE_AGENT_KILL_SWITCH=false`
- `REVENUE_AGENT_EXECUTION_ENABLED=false`
- `REVENUE_AGENT_DAILY_RUN_CAP=0`

With those defaults, the agent may analyze, prioritize, draft, and prepare, but it may not take external actions. A nonzero daily cap and explicit execution enablement are both required before an approved runtime may act. Spending, contracts, automatic charging, customer-system changes, and irreversible production changes remain approval-gated regardless.

## Lead input

Recommended fields:

```json
{
  "first_name": "Jane",
  "company_name": "Jane Plumbing",
  "contact_email": "jane@example.com",
  "industry": "Home Services",
  "pain_point": "missed calls become lost jobs",
  "website": "https://example.com",
  "contact_allowed": true,
  "source": "crm"
}
```

`contact_allowed` defaults to false. Keep it false unless the configured source/channel permits contacting that prospect.

### Zero-budget owned inbound intake

`scripts/capture_inbound_lead.py` turns affirmative website-form requests into normalized, contact-permitted leads. It fails closed unless the submission includes a valid business email, company name, explicit contact consent, and privacy acknowledgement. A honeypot field rejects basic bot submissions, and the consent audit stores an email hash rather than duplicating the address.

```bash
echo '{"email":"owner@example.com","company":"Example Co","contact_consent":true,"privacy_acknowledged":true}' \\
  | python3 scripts/capture_inbound_lead.py \\
  | python3 scripts/revenue_cycle.py
```

An approved deployment should map its form checkbox to `contact_consent`, link the current privacy notice, keep the optional `website_confirm` field hidden from people, and pass a version identifier in `consent_version`. This adapter prepares and audits the lead; it does not send outreach.

## Issue #164 evidence-gated productization

Reusable IP reaches `repeatable_positive_margin` only after at least two distinct settled positive-contribution economics receipts tied to the same captured asset identity. It reaches `productize_candidate` only after sequential paid validation, positive-margin repeatability, retention, expansion, and an explicit reuse receipt from a second opportunity. The second opportunity must contain the same named asset type and its own independently settled positive-contribution economics record. Duplicate assets, catalog membership, projections, and a single customer's repeated billing cannot establish cross-customer demand.

Outcome-priced offers bind a positive per-unit fee into the immutable accepted terms hash in addition to the overall cap. Outcome events with a caller-selected or changed rate fail closed before accrual or invoicing. Every outcome event must also carry a timestamped HTTPS-backed review bound to the complete contract-accepted outcome terms and the accepted exclusions. Both the outcome event and its eligibility review must include SHA-256 digests that pin their evidence artifacts for later audit. Reviews with missing or malformed artifact digests, or against stale or different terms, fail closed; matched exclusions are rejected, and events marked for human escalation require an approved, timestamped decision with its own pinned evidence artifact before accrual. Invoice allocation revalidates these pins, recomputes the immutable event hash, and rejects legacy, incomplete, or altered outcome rows.

## Run manually

```bash
python3 scripts/fetch_leads.py | python3 scripts/revenue_cycle.py
```

Useful environment variables:

- `REVENUE_DB_PATH` (default `/files/data/revenue_agent.db`)
- `MIN_LEAD_SCORE` (default `55`)
- `MAX_OUTREACH_PER_RUN` (default `20`)
- `OFFER_NAME` (default `AI Customer Response System`)
- `OFFER_SETUP_PRICE` (default `100`, legacy fallback: `OFFER_PRICE`)
- `MANAGED_MONTHLY_PRICE` (default `99`)
- `OFFER_MODE` (default `setup_plus_managed`)
- `LEADS_JSON`
- `LEADS_API_URL`
- `LEADS_API_TOKEN`

## APEX verified-revenue integration

The production APEX Supabase Edge runtime is:

```text
https://wuzmqruxdclstezitsbf.supabase.co/functions/v1/apex-runtime
```

For the live Supabase runtime, configure the Revenue Agent backend with:

```text
APEX_REVENUE_URL=https://wuzmqruxdclstezitsbf.supabase.co/functions/v1/apex-runtime
APEX_AUTH_MODE=supabase_edge
APEX_PROPERTY_ID=003
APEX_API_KEY=<server-side Supabase secret key>
```

`APEX_API_KEY` must remain server-side and must never be committed to Git or exposed to browser/mobile clients. When configured, `record_payment.py` forwards only already-verified processor payments to APEX using the protected `ingest_verified_revenue` action. APEX forwarding is best-effort: a temporary APEX failure does not undo or lose the local payment record.

### Stripe revenue webhook

The Supabase Edge Function in `supabase/functions/stripe-revenue` is the production bridge for verified Stripe revenue. It:

- verifies the raw request body with `STRIPE_REVENUE_WEBHOOK_SECRET` and rejects stale or invalid signatures;
- accepts only paid `checkout.session.completed` and `invoice.paid` events;
- records each Stripe event exactly once in `verified_revenue_events`;
- stores a customer email hash rather than a plaintext payment email and links to a consented inbound lead when hashes match; and
- leaves the revenue table protected by RLS with no public client policy.

Production endpoint: `https://wuzmqruxdclstezitsbf.supabase.co/functions/v1/stripe-revenue`

Activation requires an owner-controlled Stripe webhook endpoint subscribed to `checkout.session.completed` and `invoice.paid`, plus its signing secret stored as the Supabase secret `STRIPE_REVENUE_WEBHOOK_SECRET`. Never commit or paste the signing secret into source, client code, logs, issues, or pull requests. Until the secret is configured, the deployed endpoint intentionally returns `503 service_not_configured` and cannot record events.

Legacy APEX deployments remain supported by leaving `APEX_AUTH_MODE=bearer` and providing `APEX_ADMIN_TOKEN`.

## Referral / partner attribution (prepared, disabled by default)

`scripts/referral_program.py` provides referral-code creation and attribution for clicks, leads, meetings, sales, and attributed revenue. It does **not** send messages, modify pricing, or create/pay commissions.

Write actions stay disabled unless the server environment explicitly contains:

```text
REFERRAL_PROGRAM_ENABLED=true
```

Example preparation flow:

```bash
REFERRAL_PROGRAM_ENABLED=true python3 scripts/referral_program.py create-partner "Partner Name" --code PARTNER1
REFERRAL_PROGRAM_ENABLED=true python3 scripts/referral_program.py record PARTNER1 lead --lead-id LEAD_ID
REFERRAL_PROGRAM_ENABLED=true python3 scripts/referral_program.py record PARTNER1 sale --lead-id LEAD_ID --value 100
python3 scripts/referral_program.py report
```

Referral payouts remain disabled in this implementation. Any commission amount, partner agreement, automatic outreach, or payment action requires a separate business decision and authorization.

## Record lifecycle and revenue events

```bash
python3 scripts/record_event.py LEAD_ID sent
python3 scripts/record_event.py LEAD_ID reply
python3 scripts/record_event.py LEAD_ID interested
python3 scripts/record_event.py LEAD_ID meeting
python3 scripts/record_event.py LEAD_ID sale --value 100
python3 scripts/record_event.py LEAD_ID opt_out
```

Generate the current funnel report:

```bash
python3 scripts/revenue_report.py
```

The report includes lead counts, qualified prospects, sent messages, replies, interested leads, meetings, sales, reply/interest/close rates, gross and net revenue, and revenue per sent message.

## n8n

`workflow.json` runs every hour, pipes the configured lead source through `revenue_cycle.py`, and emits only qualified prospects that pass the explicit contact gate. Connect its output to an approved sending channel, then call `record_event.py` from delivery/reply/payment workflows so the agent can optimize against actual outcomes.

## Safety and deliverability

Do not blindly scrape and mass-message addresses. Use legitimate lead sources, honor opt-outs and channel rules, maintain suppression lists, rate-limit outreach, and preserve human review for unusual or high-impact communications. Optimize sustainable revenue and trust, not spam volume.


## Consented inbound autonomy

`autonomous_cycle.py` is the default hourly operations router. It automatically advances routine work only when the lead came through the owned inbound adapter with affirmative contact consent. It separates work into:

- `autonomous_dispatch` — bounded initial replies, follow-ups, or checkout delivery for verified owned inbound requests;
- `owner_review` — cold/external sources, ambiguous sources, reply interpretation, and actions outside the pre-authorized class; and
- `blocked` — missing delivery data, disabled autonomy, kill-switch activation, or per-run cap exhaustion.

Safe defaults require no owner action:

- `CONSENTED_INBOUND_AUTOMATION_ENABLED=true`
- `CONSENTED_INBOUND_PER_RUN_CAP=5`
- `REVENUE_AGENT_KILL_SWITCH=false`

The router never spends money, signs contracts, changes prices, charges customers, or permits unsolicited outreach. It emits a bounded, consent-verified dispatch queue for an authenticated delivery adapter, which must record successful delivery events idempotently. Until that adapter and an owned inbound endpoint are connected, the agent will continue analyzing and preparing work but cannot contact or close customers autonomously.


### Authenticated delivery adapter

When the owned inbound endpoint and sender are ready, configure the runtime with:

- `DELIVERY_ENABLED=true`
- `DELIVERY_WEBHOOK_URL=https://...`
- `DELIVERY_WEBHOOK_TOKEN=<server-side bearer token>`
- `CONSENTED_INBOUND_DAILY_DELIVERY_CAP=20` (or a lower bounded value)

The endpoint must accept a JSON payload containing `action` and `idempotency_key`, honor the `Idempotency-Key` header, and return a 2xx status only after durable acceptance. The adapter writes one local delivery receipt and lifecycle event only after that response. Duplicate actions, non-HTTPS endpoints, missing authentication, external lead sources, unsupported actions, and daily-cap overflow fail closed. Tokens are never printed or persisted.
