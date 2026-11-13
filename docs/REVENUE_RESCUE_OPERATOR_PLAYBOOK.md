# APEX Revenue Rescue — operator playbook (experimental)

**Status:** Proposed add-on to APEX's existing $100 customer-response pilot, not a new live checkout or claim of customers. Source issue: [#261](https://github.com/ldavis2700/ai-revenue-agent/issues/261). Do not replace the existing published offer automatically.

## Buyer and scope

Offer the **$99 Inquiry-to-Booking Quickstart** to appointment-based local service businesses *only when a buyer shows actual need*. Deliver one responsive lead-request form/page; one agreed delivery destination (customer-owned inbox or sheet); a simple owner-operated follow-up tracker; and documented testing. This is a **booking request**, not an appointment-confirmation system or guarantee of new leads. No service fulfillment until permissions, scope and payment terms are agreed.

**Prospective expansion:** $299 for one explicitly scoped integration and consent-controlled routing; optional $49/month for a separately accepted maintenance plan with documented cancellation, response scope and operating costs. Prices are tests, not verified market acceptance. Preserve the existing $100/$99 offer in production while testing differentiation.

## Automated workflow, gated by evidence

1. Discover potential buyers from authorized inbound demand, public business sites where permitted, or supported buyer-intent marketplaces. Prefer real buyer requests over speculative outreach.
2. Dedupe against the existing APEX pipeline. Record public source URL, date, concrete observable friction, service vertical, and which features are *not verified*. Never claim a business is losing sales based only on a website observation.
3. Score buyers using authentic reply/contract signals, evidence of a concrete problem, near-term delivery feasibility, expected gross margin and compliance risk. Existing verified buyer intent takes precedence.
4. Produce a **draft only** with one factual personalized observation, fixed-scope deliverable, transparent pricing, review/consent expectations, and opt-out where appropriate. No bulk unsolicited messaging, identity impersonation or automated messaging without channel permissions.
5. Request minimum necessary client configuration: authorized business contact, permitted logo/assets, business email/CRM destination, privacy notice and lead retention requirement. Do not reuse credentials across clients.
6. Present staging/demo using synthetic data. Before any real-world intake, verify accessibility, responsive behavior, spam/rate limits, server-side validation, secure transport, retention/deletion, correct destination, consent and notifications.
7. Once separately authorized, send a proposal and verified customer-controlled/owner-authorized payment link. Record quote, contract, paid milestone, and collected/settled revenue separately. Never mark a payment received from a sent invoice.
8. Deliver, obtain buyer acceptance, document rollback and transfer, and ask whether they want a separately contracted maintenance plan.

## Example offer text (requires buyer-specific human/channel review)

> I noticed your public site currently asks visitors to contact you to request an appointment. If a short request form would help your team organize those inquiries, I can set up a mobile-friendly inquiry page and route requests to an inbox you control. The introductory pilot is $99 for one page/form, one destination and a tested handoff. This is not a guaranteed lead-generation or automated booking service. Would a preview be useful?

Never assert that the business has broken booking unless actually verified. Do not send this automatically.

## Deployment acceptance checklist

- [ ] Candidate clearly isolated from production offer and existing buyer pipeline.
- [ ] Real form submission uses an authenticated, authorized backend with anti-abuse protection; no simulated success banner for unpersisted requests.
- [ ] No live personally identifying data in demos, logs, code or documentation.
- [ ] Buyer has signed off on business branding, user-facing privacy language and destination.
- [ ] Unit/integration tests cover invalid inputs, injection-safe rendering, duplicate submissions, destination failure, opted-out follow-up, retention and deletion.
- [ ] Buyer is aware of provider/API/hosting costs and any paid plan requires explicit approval.
- [ ] Actual live deployment verified separately; local commits and a green PR do not establish deployment.
- [ ] Revenue dashboard separates *prospect / reply / proposal / accepted / invoiced / settled / withdrawn* with proof.
- [ ] Compare pilot conversion, gross margin, delivery time and churn to existing $100 response pack before expansion.

## Reporting format for hourly APEX review

Report **newly verified** prospect count, genuine buyer replies, proposals (submitted vs draft), paid milestones, gross collected revenue and margin when evidenced, delivered customer work, technical blocker, and next smallest safe action. If none were verified, report zero rather than extrapolate. Maintain HAEVEN precedence and all existing platform/CI/review/payment safety gates.
