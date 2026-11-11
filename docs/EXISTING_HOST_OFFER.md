# Inquiry-only offer on the existing content host

The public Vercel page was observed serving old Stripe purchase buttons while
current main removes checkout. The connected Vercel team is on Hobby, so a new
commercial sales release there is inappropriate without resolving hosting terms.

The existing paid Railway content service can serve the already-reviewed static
offer and privacy pages without a second service, database or subscription:

`https://apex-content-worker-production.up.railway.app/`

`content_worker.Handler` exposes only an explicit allowlist of five HTML files,
including the `/offer.html` and `.html` privacy aliases. Query strings do not
select files or payment destinations. Canonical and social URLs in the served
HTML are rewritten to this fixed origin, never a caller-supplied Host header.
No arbitrary repository, credential or persistent-state files are served.

The Docker image includes only `sales/*.html` in addition to its existing assets.
Pages preserve the existing CSP and browser privacy headers. Their transfer
shares the existing 100 MB/day media cap; exhaustion returns 429, while health
checks remain available. This intentionally favors bounded costs over unlimited
traffic; review actual traffic before changing the cap. Rendering, queue and
volume configuration are unchanged. No new marketing messages or payments occur.

## Release validation

Run the full Python suite and hosted container build/render checks. Deploy only
the reviewed passing revision to the existing content service, retaining its
volume, resource limits, replica count and current jobs. Reject unrelated staged
environment changes. Verify `/`, `/privacy`, `/home-services`, `/industries`,
`/partners`, `/offer.html` and `/health` on the actual host. Verify no checkout
links or query overrides, and 404 for `/queue.db` and `/content_worker.py`.

A live page is not proof of working form submission. Independently validate the
existing Supabase endpoint from a permitted browser/runtime; do not create fake
buyers or test receipts. A bare invalid request returning a network/proxy 403 is
not evidence of application validation. Merchant identity, non-Stripe collection,
buyer acceptance and genuine settlement remain separate commercial dependencies.

After successful live verification, use the Railway URL in new approved
distribution. Existing Vercel links are not fixed by this deployment; separately
retire or redirect them through authorized controls. Keep checkout paused until
the owner-approved merchant path is independently verified. Roll back only the
service source revision if needed; never reset the `/data` volume or ledger.
