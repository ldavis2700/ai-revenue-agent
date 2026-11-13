# APEX business-model curriculum: AI lead generation and sales automation

**Status:** research/training and sandbox prototyping only. Added 2026-11-13. This document is a learning plan, **not** proof of a deployed capability, customer contract, $10,000 sale, or payment.

## Model and buyer promise

Build a productized, client-specific **AI-powered lead-generation and sales-automation web platform** for an authorized business customer. A recently observed opportunity described a $10,000 project, but **$10,000 is a prospect-specific example, not verified market pricing or earned income**.

The product should help the customer discover *permitted* lead sources, organize and deduplicate prospects, evaluate buyer fit with explainable rules, draft useful follow-up material, and provide a dashboard to measure responses and sales outcomes. No automated unsolicited outreach.

## Teach APEX the end-to-end workflow

1. **Research demand.** Use dated buyer requests or approved customer conversations. Record source URL, date, requested deliverables, budget and whether the opportunity is active; do not equate advertised budget with a signed contract.
2. **Qualify the buyer and permission.** Confirm identity/ownership, business use case, permissible data sources, target geography, relevant privacy and marketing rules, project scope, acceptance criteria, timeline and the customer's authority over their CRM and communications.
3. **Propose a scoped MVP.** Quote only after requirements are verified. Illustrative components: an authenticated lead dashboard, source/API import adapters for licensed or customer-owned data, explainable lead scoring, deduplication, human-reviewed message drafts, role-based permissions, and audit logging.
4. **Implement safely in a sandbox.** Use synthetic sample records by default. Keep API keys in secrets; protect personal data with data minimization, encryption and access controls. Respect source terms, robots rules, deletion and suppression requests. No scraping gated sources or bypassing access restrictions.
5. **Approval-gated sales workflow.** Messages stay in `draft`; sending or publishing needs documented authority, applicable consent and an explicit human approval of content and recipient. Support unsubscribe/suppression and rate limits where relevant. Never create fictitious contacts, outcomes or reviews.
6. **Test the MVP.** Unit/integration and browser tests should cover ingestion, duplicate records, invalid URLs, scoring explanations, access boundaries, exports, sender approval gates, opt-outs, failure recovery and billing isolation. Produce reproducible evidence, not statements of success without receipts.
7. **Commercial conversion.** Distinguish lead, proposal, accepted scope, signed agreement, delivered work, buyer acceptance, invoice, provider-confirmed payment settlement, costs, refunds and net revenue. Do not initiate new spend, paid ads, payments or contracts absent the required provider/owner authorization.
8. **Improve with evidence.** Track permitted leads researched, qualified opportunities, sent proposals with approval, signed contracts, accepted deliveries, settled cash, fees, hours and customer outcomes. If no verified conversions, change the offer or channel based on actual observations.

## MVP acceptance rubric

- An authorized business user can import customer-owned/licensed sample records; deduplication is deterministic and repeatable.
- Every lead score exposes contributing factors and source provenance; low-confidence records are flagged rather than invented.
- All outbound actions are disabled by default and remain disabled without verified, per-action authorization; test unauthorized execution is rejected.
- Roles constrain viewing/exporting personally identifiable information; audit records capture sensitive changes.
- Dashboard metrics are computed from actual event data, not synthetic demo counts represented as sales.
- A test buyer can follow a complete mock workflow from intake through approved draft and acceptance, with no live send and no real charge.
- Tests pass against the exact reviewed commit, and a deployed environment is independently validated before a live claim.

## Initial offer packaging

- **Discovery / audit:** free or low-cost consent-based review of an existing sales workflow, with no promises of sales.
- **Milestone 1:** paid discovery and data-source authorization, specification and acceptance tests.
- **Milestone 2:** secure import, qualification, dashboard and review-only sales drafts.
- **Milestone 3:** approved integrations, customer handover, documented support and measured outcomes.

Price these against actual buyer scope and delivery costs, not the single $10k example. APEX should first demonstrate a small, accepted, payable milestone before proposing broad platform commitments.

## Operational integration

Use APEX's **existing** Business Model Intelligence, Mission Control / experiment queue, weekly model-to-cash research and revenue evidence ledger. Do not create a duplicate tracking ledger or a second scheduled workflow. Tag this candidate `ai_leadgen_sales_automation_platform`; compare it with the existing response-service and research-workflow offers by legitimate buyer demand, delivery feasibility, costs, permission availability, and time to first *settled* payment. Keep the existing $750 research-workflow proposal and current funnel unaffected.

**Next execution step:** create an isolated, offline proof-of-concept and tests with synthetic data, then review dated buyer signals and procurement constraints. This document alone does not cause the deployed APEX worker to run new code, send messages or accept money.

## Non-negotiable limits

Keep existing no-new-spend, no-unsolicited-outreach, privacy, account/identity verification, provider authorization, Stripe-checkout pause, owner-only legal/banking decisions, and release controls intact. The $10,000 opportunity is research-only until a separately authorized application/contract step. Never claim fees collected without settlement evidence.
