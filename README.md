# AI Revenue Agent

AI Revenue Agent is an automation-first revenue pipeline for ingesting business prospects, qualifying them, generating tailored offers, tracking lifecycle state, and feeding approved outreach workflows.

## Current revenue offer

Default offer: **AI Customer Response System — $100 one-time**.

Configure with `OFFER_NAME` and `OFFER_PRICE`.

## Automated revenue loop

1. Ingest leads from `LEADS_JSON` or `LEADS_API_URL`.
2. Normalize and deduplicate prospects.
3. Score each prospect for sales readiness.
4. Generate a personalized outreach draft.
5. Persist lead state and events in SQLite.
6. Hourly n8n workflow returns only qualified `contact_ready` leads.
7. Approved downstream senders can deliver the outreach.
8. Reply, interest, meeting, sale, refund, and opt-out events are recorded.
9. Revenue reporting measures conversion rates and revenue per outreach.

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

## Run manually

```bash
python3 scripts/fetch_leads.py | python3 scripts/revenue_cycle.py
```

Useful environment variables:

- `REVENUE_DB_PATH` (default `/files/data/revenue_agent.db`)
- `MIN_LEAD_SCORE` (default `55`)
- `MAX_OUTREACH_PER_RUN` (default `20`)
- `OFFER_PRICE` (default `100`)
- `OFFER_NAME` (default `AI Customer Response System`)
- `LEADS_JSON`
- `LEADS_API_URL`
- `LEADS_API_TOKEN`

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
