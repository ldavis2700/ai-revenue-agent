# APEX Instant Lead Recovery — gated pilot (2026-11-15)

**Status:** candidate adjacent to the existing $100 customer-response pack; NOT a launched offer, payment link, deployed integration, funded client, or evidence of revenue. **Do not replace** the live $100/$99 pilot. Only advance this second offer if the existing funded/consented queue is served and experiment limits permit.

## Hypothesis and price
A small U.S. home-services business with existing inbound inquiries may buy a **$249 one-time, one-workflow installation** to reduce manual handling of its own authorized leads. Optional **$79/month** monitoring is separately accepted, never default or automatically enrolled. These are proposed prices, not validated willingness-to-pay. Delivery requires validated customer-owned source and destination accounts, scoped permissions and a tested integration; external provider fees quoted separately. Offer a free anonymized 3-step walkthrough *before* proposing a sale. Never promise bookings, revenue, conversion lift, automatic SMS, or same-day delivery before confirming dependencies.

## Fixed-scope setup
1. One customer-authorized inbound event source: supported web form notification email **or** an existing customer-controlled CRM webhook.
2. One destination: an authorized customer's Google Sheet or existing CRM. Include unique inquiry ID, received timestamp, source, review status; minimize/avoid personal data in demonstration.
3. One owner notification of a new inquiry, through an approved customer-owned channel. No unsolicited customer messages.
4. One owner-approved acknowledgment *draft*, prepared for review, **not auto-sent**. Automated customer delivery requires separate documented consent, channel-specific checks, verified opt-out and explicit scope agreement.
5. Test fixtures with invented records, failure/retry/idempotency tests, a basic handoff guide, and seven days of fixing reproducible defects in the agreed setup.

**Excluded:** voice AI, call recording, mass lead import, scraping, SMS blasts, CRM replacement, automated purchasing, guaranteed appointments, data resale, compliance/legal advice, and unlimited support.

## Buyer qualification checklist
- Verified genuine inbound business inquiry or buyer-initiated discussion; no manufactured buyer records.
- Business identity, authorized representative, use case, current intake channel, estimated weekly lead volume and bottleneck.
- Customer controls source and destination; written access permissions; no passwords sent by email.
- Source and destination can be integrated using approved free/known-cost tools; quota and costs disclosed.
- Actual lead/customer personal data stays in customer-authorized systems and is not included in public code or previews.
- Confirm exact response policy, escalation owner, acceptance test, support contact and refund terms.
- Payment method is property 003 APEX-only Stripe **after** merchant/buyer-specific verification, or an applicable funded marketplace's own rail. Public checkout stays paused. Never borrow HAEVEN links.
- No customer charge, payment link distribution, contract acceptance, or automatic messaging without required provider and owner gates.

## Sales and acceptance sequence
1. Reconcile existing APEX $100 pilot, funded work, consented preview requests and all opt-outs first.
2. When the candidate is eligible for a bounded experiment, offer a private, fictional-data demonstration to a buyer who has opted in; make it clear the demonstration isn't attached to their business.
3. Obtain a scope document with **$249 setup price**, agreed external fees, a realistic deadline based on actual integrations, refund and cancellation policy, one named integration owner, exact deliverables and customer acceptance criteria. Do not promise same-day completion when access is pending.
4. Confirm authorized payment rail and actual provider payment status with buyer-specific ID; preserve reconciliation receipts. Do not activate general public checkout.
5. On a nonproduction sandbox with fictional inputs, verify: one valid lead appears exactly once; duplicates don't multiply; missing fields are safely handled; a failed destination remains queued for manual recovery; notification reaches only authorized owner; no external customer send occurs; secrets aren't logged.
6. After customer sign-off and permissions, provision least privilege, execute and retest in their own environment. Collect approval/acceptance receipt; document rollback and safe disconnect.
7. Offer optional $79/month support separately, with a clear cancellation path. Do not create a subscription without affirmative separate purchase.
8. Record processor charge ID, settlement/refund/dispute states, fees, delivery time, support costs, acceptance and verified owner deposits **separately**; any unknown amount stays unknown.

## Original, truthful sample outreach (use only in permitted, consented channels)
“Thanks for asking about faster responses to new inquiries. I can show a no-cost example of a simple workflow that captures a form inquiry, alerts the owner, and creates a reply draft for approval. If your systems support it, a one-workflow installation is proposed at $249 plus any disclosed third-party charges. No automated customer messages, guaranteed bookings or subscription are included. Would you like the fictional-data preview?”

## Decision checkpoint
A **Day-1** sale is only a hypothesis. Measure paid first-time customer, time from offer to verified payment, actual fulfillment labor, provider fees, support, refunds and contribution. Do not claim revenue from an inquiry, proposal, click, draft invoice, unsigned contract, Stripe link, test payment or unconfirmed settlement.

**Go/no-go:** Do not promote this candidate over existing outstanding commitments. Before an active launch, verify a completed fictional-data integration test, buyer permissions, payment-rail readiness and required policy checks. Otherwise keep as a prepared, bounded upsell/replacement experiment, not a deployed money-making business.
