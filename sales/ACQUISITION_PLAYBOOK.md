# AI Revenue Agent Acquisition Playbook

## Objective

Drive qualified small-business owners into the existing free tailored preview funnel, convert appropriate prospects into the $100 one-time setup, and offer the optional $99/month managed optimization plan only as a separate customer-initiated decision.

## Operating principles

- Target relevance over volume.
- Do not buy scraped lists or blast unsolicited bulk messages.
- Prefer public business contact channels, inbound communities where promotion is allowed, referrals, and direct one-to-one outreach based on a specific observed business need.
- Respect platform terms, CAN-SPAM requirements where applicable, opt-outs, and all stated contact preferences.
- Never imply a relationship, endorsement, guarantee, or prior consent that does not exist.
- Keep the free preview genuinely free and separate from checkout.

## Ideal customer profile

Prioritize local service businesses where missed inquiries and slow follow-up can directly cost appointments or jobs, especially:

1. Home services: HVAC, plumbing, electrical, roofing, landscaping, cleaning, pest control, mobile detailing, handyman services.
2. Appointment businesses: salons, barbers, spas, tutors, photographers, fitness studios, pet groomers.
3. Professional local services: tax preparation, bookkeeping, small legal offices where outreach is permitted, real estate teams, insurance agencies.

Best signals: active business, visible phone/email/contact form, recent reviews, evidence of lead flow, and a service where fast response matters.

## Core offer

Lead with the preview, not the purchase:

> I noticed your business handles customer inquiries where fast follow-up matters. I build simple AI-assisted response systems for small businesses. I can make a free tailored preview for your business first—no payment or subscription required. If it looks useful, the full setup is $100 one time.

Do not claim the system automatically messages customers. The current offer provides tailored response assets and a practical response system; automated sending requires separate authorization and integration work.

## Campaign links

Use the live landing page with UTM tags so the existing intake endpoint records acquisition source:

- Direct outreach: `https://ai-revenue-agent-seven.vercel.app/?utm_source=direct&utm_medium=one_to_one&utm_campaign=free_preview`
- Referral: `https://ai-revenue-agent-seven.vercel.app/?utm_source=referral&utm_medium=partner&utm_campaign=free_preview`
- Organic social: `https://ai-revenue-agent-seven.vercel.app/?utm_source=social&utm_medium=organic&utm_campaign=free_preview`
- Local community: `https://ai-revenue-agent-seven.vercel.app/?utm_source=community&utm_medium=organic&utm_campaign=free_preview`

Create more tags only when the source is materially different. Keep names short because the inbound function sanitizes and stores the campaign value.

## One-to-one outreach sequence

### First contact

Keep it short and personalized. Mention one real observation about the business when possible.

> Hi [Name] — I came across [Business] and noticed you handle [specific inquiry type/service]. I build simple AI-assisted customer response systems for small businesses. I can make a free tailored preview for [Business] first, with no payment required. If you want to see it, here’s the request page: [tracked link]

### Follow-up

Use at most one reasonable follow-up unless the prospect engages.

> Hi [Name] — following up once in case the free response-system preview would be useful for [Business]. No purchase is required to see it. If it is not relevant, no problem and I won’t keep following up.

If someone declines or asks not to be contacted, stop immediately.

## Inbound / public posting copy

Use only in places where business promotion is permitted.

> Small-business owners: I’m offering a free tailored preview of an AI-assisted customer response system. It includes ready-to-use responses for inquiries, quotes, missed calls, follow-ups, reviews, repeat customers, and FAQs. You see the preview before deciding whether to buy anything. Full setup is $100 one time; optional ongoing optimization is separate. [tracked link]

## Daily acquisition loop

1. Identify 10-20 highly relevant businesses or permitted communities.
2. Qualify for fit before contacting: active business, real inquiry flow, useful response-system use case.
3. Send only personalized or context-appropriate outreach.
4. Use the correct UTM-tagged link.
5. Check `inbound_leads` for new Property `003` leads.
6. Prepare each requested preview promptly using the business facts submitted by the prospect.
7. Present the $100 setup only after delivering or showing the preview.
8. Record purchase and managed-plan conversion separately.
9. Compare conversion by campaign source before increasing volume.

## Metrics

Track these separately:

- qualified prospects contacted
- landing-page visits by source (when analytics is available)
- preview requests
- preview-request rate
- previews delivered
- $100 setup purchases
- preview-to-purchase conversion
- $99/month managed-plan enrollments
- setup-to-managed conversion
- opt-outs / complaints

Do not optimize only for message volume. Optimize for qualified preview requests, paid conversion, low complaint rates, and customer value.

## Decision rules

- If outreach gets clicks but no preview requests, improve landing-page trust or targeting before increasing volume.
- If previews are requested but do not convert, improve preview quality and offer clarity before lowering price.
- If one segment converts materially better, concentrate effort there.
- Do not introduce discounts until enough real prospects have seen the $100 offer to provide evidence that price is the constraint.
- Do not add automated outbound sending without explicit authorization, compliance review, opt-out handling, and platform-specific safeguards.

## Current source of truth

The live funnel is the sales offer page backed by the `revenue-inbound` Supabase Edge Function. A valid preview request requires a business email, company name, affirmative contact consent, and privacy acknowledgement. The backend stores accepted leads for Property `003` in `inbound_leads` and records campaign attribution when supplied.
