# Fictional home-service handoff audit — offline capability proof

**Status:** Original, synthetic, source-only demonstration. No real customer, measured savings, accepted delivery, Upwork submission, AI provider integration or payment. No production deployment.

**Buyer problem to validate:** A U.S. home-service company can have separate inquiry, estimate, scheduling and invoice systems; a paid discovery audit can test whether handoffs are recorded, where staff review is necessary, and whether existing software is sufficient. Do not assert gaps or costs until the customer supplies **authorized aggregate observations**.

## Independent reproduction

In the repository root:

```bash
python -m unittest tests.test_home_service_handoff_audit -v
python scripts/home_service_handoff_audit.py --input docs/upwork/fictional_home_service_counts.json
```

The fictional input includes no contact, employee, deal, lead, address, payment or provider data. The tool accepts only four named handoff types and bounded integer totals. It **rejects** unexpected keys that could leak identifying content. Output sorts observed late/missing handoff shares (with `null` for an unknown denominator), flags workflows for human investigation and reports observed minutes. It does **not** calculate financial savings or assign causes.

## Honest paid audit acceptance proposal (uncontracted)

1. Confirm written engagement, business systems involved, data access and authorization; use existing access roles, no passwords or unnecessary customer PII.
2. Map the current inquiry → estimate → scheduled job → invoice → follow-up handoffs and the authoritative system for each state.
3. Collect a bounded seven-day **aggregate** baseline per flow, exception definition and manual review minutes; record source/export date and data limitations.
4. With the owner or operations lead, verify a small sample of missing/late flags and identify false positives. Distinguish process/design flaws from missing observations.
5. Deliver the workflow map, permissions/consent risk matrix, ranked improvement options, no-new-software alternatives, implementation prerequisites, actual known subscription/processor/labor costs and QA/rollback plan. Any ROI model is separately conditional and needs client-provided baseline rates and costs.
6. Request approval for a separately funded implementation phase. Never activate auto-messaging, telephone calls, financial writes, client-account integrations or outreach as part of this offline proof.

**Commercial gate:** Current Upwork opportunities are merely job advertisements. A client may require prior audited results; APEX must never fabricate customer examples, quantified savings or provider connections. Proposal Connects and submission require action-specific permission and any account-holder verification. This proof does not meet all contractor prerequisites by itself.
