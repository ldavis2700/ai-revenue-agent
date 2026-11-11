# APEX customer-response offer — inquiry only while checkout is paused

The current public offer is served from the **existing, previously authorized**
Railway content worker:

`https://apex-content-worker-production.up.railway.app/`

Its HTML comes from `sales/offer.html` and the other reviewed `sales/*.html`
assets. The offer describes a proposed $100 setup and separately optional
$99/month support; these are **not** an active checkout or a promise that APEX
can accept money. The consent-based preview request does not create a purchase,
subscription, customer contract, or permission to message anyone else.

**Stripe is paused.** Do not add Stripe checkout links, query-parameter
`setup`/`managed` redirects, external payment buttons, or subscription signup
until the owner approves an actual merchant rail, its eligibility and payout
are verified, and separately tested release gates pass. Old instructions for
inserting checkout URLs into the URL query string were retired. Never treat a
payment link, invoice draft, or web page as evidence of collection.

## Existing intake integration and safety

The offer uses the deployed HTTPS Supabase `revenue-inbound` function with its
allowlisted origin, signed-off privacy notice, affirmative contact consent,
16 KiB actual-body size cap, deduplication, and preservation of withdrawn
consent. No automated messages, outside outreach, or paid activities are
activated by the HTML. Before promoting an alternate domain, validate CORS
with its exact origin and independently verify actual deployed function state.
Do not create fake buyer records or disturb existing opt-outs to test.

## Legacy public links and release verification

The prior Vercel commercial page was observed exposing old Stripe purchase
buttons while the checked-in source was already paused. Its production project
routing was therefore retired in favor of a **temporary HTTP 307 redirect** to
the verified Railway site, with path and query preserved. The Vercel alias
`https://ai-revenue-agent-seven.vercel.app/` must **not** directly serve old
HTML; an accidental rollback of routing could restore the unsafe checkout.

To independently verify this drift from a networked operator environment, run
`python scripts/verify_live_offer.py`. The script only GETs the allowlisted
public legacy and Railway URLs; it never follows redirects, submits the form,
invokes checkout, collects personal data, or changes providers. It fails closed
if redirects are missing/misdirected, if the live offer again displays a
checkout or query override, or if the public network is inaccessible. It does
not confirm merchant readiness, buyer demand, revenue, or the Python worker's
runtime. Exercise with offline regression cases via
`python -m unittest discover -s tests -p 'test_verify_live_offer.py' -v`.

For a complete release, also follow `docs/EXISTING_HOST_OFFER.md`: confirm
Railway `/health`, static public routes, forbidden file 404s, security headers,
and the Supabase live negative-intake tests. Preserve the old Vercel routing
version for rollback, but do **not** restore old Stripe checkout functionality
while payments remain paused. No new hosting or scheduling is required.
