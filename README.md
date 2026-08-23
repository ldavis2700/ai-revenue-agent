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
