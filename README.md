# AI Revenue Agent

AI Revenue Agent is an automation-first revenue pipeline for finding or ingesting business prospects, qualifying them, generating a tailored offer, tracking state, and feeding safe outreach workflows.

## Current revenue offer

Default offer: **AI Customer Response System — $100 one-time**.

The offer is configurable with `OFFER_NAME` and `OFFER_PRICE`.

## Revenue loop

1. Ingest leads from a configured JSON/API source.
2. Normalize and deduplicate prospects.
3. Score each prospect for sales readiness.
4. Generate a personalized outreach draft.
5. Persist lead state and events in SQLite.
6. Return qualified drafts to n8n.
7. Only put a lead in `contact_ready` when `contact_allowed=true`.
8. Downstream workflows can send, track replies, record sales, and optimize conversion.

## Lead input

Set either:

- `LEADS_JSON` — a JSON array or `{ "leads": [...] }`
- `LEADS_API_URL` — an HTTP endpoint returning JSON or CSV
- `LEADS_API_TOKEN` — optional bearer token

Recommended lead fields:

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

`contact_allowed` defaults to false. Keep it false unless the configured outreach channel and source permit contacting that prospect.

## Run the revenue engine

```bash
python3 scripts/revenue_cycle.py
```

Useful environment variables:

- `REVENUE_DB_PATH` (default `/files/data/revenue_agent.db`)
- `MIN_LEAD_SCORE` (default `55`)
- `MAX_OUTREACH_PER_RUN` (default `20`)
- `OFFER_PRICE` (default `100`)
- `OFFER_NAME` (default `AI Customer Response System`)

## n8n

The existing `workflow.json` runs hourly and can continue using `scripts/fetch_leads.py`. The next workflow upgrade should pipe fetched leads through `scripts/revenue_cycle.py`, then route `contact_ready` leads to an approved sending channel and log delivery/reply/payment events.

## Safety and deliverability

Do not blindly scrape and mass-message addresses. Use legitimate lead sources, honor opt-outs and channel rules, rate-limit outreach, keep suppression lists, and preserve human review for unusual/high-impact communications. The agent is designed to optimize sustainable revenue rather than spam volume.
