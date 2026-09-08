# APEX First-Cash Readiness

## Objective
Move APEX from broad capability to verified collected revenue as quickly as possible without weakening consent, platform, quality, or financial guardrails.

## Current diagnosis
APEX already has an offer, landing funnel, inbound capture, autonomous routing for consented inbound leads, delivery adapter, business-model intelligence, and payment-related code. The principal gap is acquisition throughput: the autonomous cycle intentionally does not create unsolicited prospects or send unsolicited outreach. Therefore capability alone cannot create cash; APEX needs a steady source of qualified, permitted demand.

## First-cash priority stack

### P0 — Convert existing demand
1. Process every affirmative owned inbound lead immediately.
2. Prioritize buyer-requested checkout over follow-up and initial delivery.
3. Deliver requested previews fast and with business-specific facts.
4. Follow up once when permitted.
5. Record conversion, delivery, and payment evidence.

### P1 — Generate permitted demand without paid spend
Run these channels in parallel where terms permit:
- Organic posts in communities that explicitly allow business promotion.
- Referral/partner distribution using the tracked referral URL.
- Owner-controlled social profiles and websites.
- Inbound SEO/content pages aimed at high-intent local-service searches.
- Public opportunity marketplaces where automation/agent participation is permitted and truthful disclosure can be maintained.

Never scrape-and-blast, fabricate identity or proof, evade anti-bot controls, or violate platform terms.

### P2 — Productized fast-cash offers
Rank offers by time-to-cash and autonomous delivery confidence:
1. $100 AI-assisted customer-response setup (existing funnel).
2. Fixed-scope workflow/automation audit with a paid implementation milestone.
3. Data cleanup/transformation and reporting deliverables.
4. Website QA/debugging and conversion fixes.
5. Documentation/SOP generation from customer-provided materials.

Prefer fixed scope, short delivery, clear acceptance criteria, and reusable implementation assets.

## Opportunity scoring
Score every candidate 0–100 using:
- 25: probability of payment/win
- 20: time-to-cash
- 20: execution confidence
- 15: expected net revenue
- 10: repeat/recurring potential
- 10: strategic reuse

Hard reject scams, prohibited work, deceptive identity requirements, unclear payment rails, work outside reliable execution capability, or platform-rule conflicts.

## Daily operating targets
Until first verified cash:
- Process 100% of consented inbound requests.
- Maintain at least 3 active permitted acquisition channels.
- Produce at least 1 reusable proof asset or offer improvement from completed work/evidence.
- Keep owner intervention restricted to genuine identity, CAPTCHA, signature, financial-account, interview, or platform-holder requirements.

After first verified cash, optimize for collected net revenue, repeat rate, time-to-cash, and owner interventions per dollar earned rather than raw lead/message volume.

## Payment outage behavior
Stripe availability must not halt acquisition, qualification, preview production, proposal preparation, execution preparation, or permitted follow-up. Mark checkout/payment as `payment_rail_blocked`, preserve the buyer state, and resume collection as soon as an authorized payment rail is available. Do not claim payment is possible while the rail is unavailable.

## Definition of first-cash success
First-cash is reached only when a legitimate customer payment is verified as collected through an authorized rail and attributable to an APEX opportunity. A proposal, verbal yes, checkout visit, invoice, or test payment is not revenue.

## Immediate implementation queue
1. Keep issue #85 as the job-to-cash architecture source of truth.
2. Add acquisition-channel adapters only for channels whose terms allow the intended behavior.
3. Add opportunity ingestion + dedupe + scoring before autonomous application.
4. Add `payment_rail_blocked` state so temporary Stripe failure cannot stall the rest of the pipeline.
5. Add first-cash dashboard metrics: qualified opportunities, permitted pitches/applications, conversations, accepted work, delivered work, collected revenue, time-to-cash, and owner-only blockers.
6. Require evidence-backed portfolio claims; never fabricate results.
